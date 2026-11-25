"""The file lists (0.9.0, DASH-546; owner, 23 November 2026: "I need a better way to list and sort files for each of the
options and each channel").

One list for each kind of file the owner adds (Ident, Promo clip, Adverts, PSA), that can be searched, sorted, filtered
and paged, with several files ticked and added to or removed from a channel together. Everything here is a pure
function on rows, so the page, the plug-in and the tests share one set of rules, and the page only ever asks for one
page of rows: nothing is loaded all at once, however many files there are.

A row is {"key", "role", "id", "title", "dur", "size", "added", "audio", "held", "used_by"}:
  key      "role:id", what a tick box and a change name
  held     where the file is kept: "station" (every channel that uses the station's can play it) and the ids of channels
           that have it in their own list
  used_by  the ids of the channels that play it, from what each has chosen (own, the station's, both or none)
"""
KINDS = {"idents": "Ident", "clips": "Promo clip", "extras": "Adverts", "psa": "PSA"}
SORTS = {"name": "Name", "length": "Length", "added": "Date added", "size": "Size"}
SCOPES = {"all": "All channels", "this": "This channel", "unused": "Not used by any channel"}
LENGTHS = {"any": "Any length", "short": "Too short (under 5 seconds)", "long": "Too long (over 2 minutes)"}
SOUNDS = {"any": "With or without sound", "with": "With sound", "without": "Without sound"}
SHORT, LONG = 5.0, 120.0
PAGE = 50  # rows in one page, at most


def uses(ch, role):
    """The way a channel uses the station's and its own files of a kind: none, own, shared or both."""
    got = ch.get(role) if role in ("idents", "clips") else (ch.get(role) or "both")
    return got or "none"


def rows(state, sizes=None):
    """Every file of every kind, one row for each, from the station's lists and each channel's own. sizes: {file name:
    (bytes, seconds since 1970 it was added)} for what is on disk; a file not there has no size and no date."""
    sizes = sizes or {}
    found = {}
    channels = [c for c in state.get("channels") or []]
    for role in KINDS:
        for holder, where in [(state.get("shared") or {}, "station")] + [((c.get("own") or {}), c["id"]) for c in channels]:
            for c in holder.get(role) or []:
                key = f"{role}:{c['id']}"
                r = found.get(key)
                if not r:
                    base = str(c.get("src") or "")[5:] if str(c.get("src") or "").startswith("file:") else ""
                    size, added = sizes.get(base, (None, None))
                    r = found[key] = {"key": key, "role": role, "kind": KINDS[role], "id": c["id"], "title": str(c.get("title") or c["id"]),
                                      "dur": float(c.get("dur") or 0), "size": size, "added": added, "audio": bool(c.get("has_audio")),
                                      "held": [], "used_by": []}
                r["held"].append(where)
    for r in found.values():
        for ch in channels:
            way = uses(ch, r["role"])
            if (way in ("shared", "both") and "station" in r["held"]) or (way in ("own", "both") and ch["id"] in r["held"]):
                r["used_by"].append(ch["id"])
    return list(found.values())


def matches(r, q="", kind="", channel="", scope="all", length="any", sound="any"):
    """Whether a row passes the search and the filters. scope this needs a channel."""
    if kind and r["role"] != kind:
        return False
    if q and q.strip().lower() not in r["title"].lower():
        return False
    if scope == "this" and channel and channel not in r["held"] and channel not in r["used_by"]:
        return False
    if scope == "unused" and r["used_by"]:
        return False
    if length == "short" and not 0 < r["dur"] < SHORT:
        return False
    if length == "long" and r["dur"] <= LONG:
        return False
    if sound == "with" and not r["audio"]:
        return False
    if sound == "without" and r["audio"]:
        return False
    return True


def query(all_rows, q="", kind="", channel="", scope="all", length="any", sound="any", sort="name", descending=False, page=1, size=PAGE):
    """One page of the list: {"rows", "total", "page", "pages", "first", "last"}. Rows with no size or date sort last
    whichever way the list runs, and ties go by name, so the order never jumps about between two requests."""
    got = [r for r in all_rows if matches(r, q, kind, channel, scope, length, sound)]
    if sort not in SORTS:
        sort = "name"
    name = lambda r: r["title"].lower()  # noqa: E731
    field = {"name": name, "length": lambda r: r["dur"], "added": lambda r: r["added"], "size": lambda r: r["size"]}[sort]
    have = sorted((r for r in got if sort in ("name", "length") or field(r) is not None), key=lambda r: (field(r), name(r)), reverse=bool(descending))
    rest = sorted((r for r in got if not (sort in ("name", "length") or field(r) is not None)), key=name)
    got = have + rest
    size = max(1, min(PAGE, int(size or PAGE)))
    pages = max(1, -(-len(got) // size))
    page = max(1, min(pages, int(page or 1)))
    a = (page - 1) * size
    return {"rows": got[a:a + size], "total": len(got), "page": page, "pages": pages, "first": a + 1 if got else 0, "last": min(len(got), a + size)}


class ListError(ValueError):
    pass


def change(state, keys, channel, action):
    """Several files added to, or removed from, a channel's own list in one change (a state is changed in place).
    channel "station" is the station's list. Adding copies the file's record, never the file; removing takes the record
    out of that list only, and never deletes a file. Returns the number changed. Pure apart from the state it is given."""
    if action not in ("add", "remove"):
        raise ListError("That change is not known")
    if channel == "station":
        holder = state.setdefault("shared", {})
    else:
        ch = next((c for c in state.get("channels") or [] if c["id"] == channel), None)
        if not ch:
            raise ListError("That channel has gone")
        holder = ch.setdefault("own", {"idents": [], "clips": [], "sources": []})
    keys = [str(k) for k in keys or []]
    if not keys:
        raise ListError("Tick at least one file first")
    if len(keys) > 500:
        raise ListError("Tick 500 files or fewer at a time")
    done = 0
    for key in keys:
        role, _, fid = key.partition(":")
        if role not in KINDS:
            raise ListError("That kind of file is not known")
        mine = holder.setdefault(role, [])
        if action == "remove":
            keep = [c for c in mine if c["id"] != fid]
            done += len(mine) - len(keep)
            holder[role] = keep
        elif not any(c["id"] == fid for c in mine):
            src = next((c for ch in [state.get("shared") or {}] + [(x.get("own") or {}) for x in state.get("channels") or []]
                        for c in ch.get(role) or [] if c["id"] == fid), None)
            if src:
                mine.append(dict(src))
                done += 1
    return done
