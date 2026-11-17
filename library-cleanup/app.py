"""Library clean-up: moves films and series that have been watched, or that nobody watches, to the holding folder, so
a small server's disks do not fill up (DASH-406; the comparison report's recommendation 6). It never deletes.

The rules, each activated or deactivated, for the libraries you choose:
- Watched by everyone: a film every person counted has watched, last watched more than N days ago (90).
- Not watched for a long time: a film or series nobody has watched for N months (12), and added more than N months
  ago, so nothing new is caught.
- Series that ended, all watched: a series Jellyfin says has ended, every episode watched by everyone counted, last
  watched more than the same N days ago.

Always kept: favourites of anyone, anything someone is part way through, films in a collection, and anything with the
keep tag (keep), each a setting.

Where things go: the holding folder inside the media folder, /media/.holding/library-cleanup/, keeping the folders it
was in, so /media/movies/A Film (2001) becomes /media/.holding/library-cleanup/movies/A Film (2001). A move is a rename
inside one mount (plug-in API 1.15, media:holding), so it is instant and needs no free space; if it would have to copy
it is refused. Nothing is ever removed: this file has no call that deletes a file or a folder.

Reelix stops following what moves, so it is not downloaded again, and Jellyfin is told the folder has gone. Put back
moves it to the same place, Reelix follows it again exactly as it did (the same episodes), and Jellyfin is told.

When it runs: once a day in quiet hours, only when Move items each day is activated (deactivated when added). Preview
lists what would move and the space it frees, worked out in the background when asked; nothing moves from Preview.

Lightweight: the container rests when not used (start: when_needed), Python's standard library only, and Jellyfin is
read a page of 200 at a time with only the fields the rules need.
"""
import datetime as dt
import errno
import hashlib
import json
import os
import threading
import time
import urllib.parse

import sbplugin
from sbplugin import band, keep, plural, remember, serve, setting

PID = "library-cleanup"
MEDIA = os.environ.get("CLEANUP_MEDIA", "/media")
HOLD_NAME = ".holding"
PAGE = 200
MOVE_LIMIT = 200  # items one run moves at most; the next run carries on
RUN_LIMIT = 50 * 60  # inside the job's 60 minutes
PREVIEW_STALE = 6 * 3600  # Preview is worked out again when opened after this, or when a setting changed
KEEP_RUNS = 20
VIDEO = {".mkv", ".mp4", ".m4v", ".avi", ".mov", ".wmv", ".ts", ".m2ts", ".webm", ".mpg", ".mpeg", ".iso"}
RULES = {"watched": "Watched by everyone", "unwatched": "Not watched for a long time", "ended": "Ended, all watched"}
now = time.time  # replaced in tests

_lock = threading.Lock()
_job = {"thread": None, "kind": "", "progress": None}


def hold_root():
    return os.path.join(MEDIA, HOLD_NAME, PID)


# Settings ------------------------------------------------------------------------------------------------------

def _num(key, default, lo, hi):
    try:
        return int(max(lo, min(float(setting(key, default)), hi)))
    except (TypeError, ValueError):
        return default


def _on(key, default):
    v = setting(key, default)
    return v if isinstance(v, bool) else default


def rules():
    """The settings the rules use, as one dict (also what Preview is worked out from)."""
    tag = sbplugin.settings().get("keep_tag", "keep")  # empty means no keep tag, so not setting(), which gives the default
    people = setting("ignore_people", []) or []
    if isinstance(people, str):
        people = [p for p in people.split(",")]
    return {"watched": _on("watched", True), "watched_days": _num("watched_days", 90, 7, 3650),
            "unwatched": _on("unwatched", True), "unwatched_months": _num("unwatched_months", 12, 1, 120),
            "ended": _on("ended", True), "keep_favourites": _on("keep_favourites", True),
            "keep_in_progress": _on("keep_in_progress", True), "keep_collections": _on("keep_collections", True),
            "keep_tag": str(tag or "").strip().lower(),
            "ignore_people": sorted({str(p).strip().lower() for p in people if str(p).strip()}),
            "libraries_off": sorted(_libraries_off())}


def active():
    return _on("active", False)


def _libraries_off():
    return set((remember("libraries", None) or {}).get("off") or [])


def rules_key(r):
    return hashlib.sha256(json.dumps(r, sort_keys=True).encode()).hexdigest()[:16]


# Jellyfin and Reelix -------------------------------------------------------------------------------------------

def _run_json(name):
    try:
        with open(os.path.join(sbplugin.RUN, name), encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        return {}


def jf(path, data=None, method=None):
    j = _run_json("jellyfin.json")
    if not j.get("url") or not j.get("api_key"):
        raise LookupError("Starboard has no Jellyfin key to give yet: add Jellyfin in Settings, Apps")
    return sbplugin.fetch(j["url"].rstrip("/") + path, sbplugin.jellyfin_headers(j["api_key"]), data=data, method=method, timeout=60)


def rx(path, data=None, method=None):
    """Reelix's API, or None when Starboard has no Reelix key to give (Reelix is optional)."""
    r = _run_json("reelix.json")
    if not r.get("url") or not r.get("api_key"):
        return None
    return sbplugin.fetch(r["url"].rstrip("/") + path, {"X-Api-Key": r["api_key"]}, data=data, method=method, timeout=60)


def reelix_known():
    r = _run_json("reelix.json")
    return bool(r.get("url") and r.get("api_key"))


def _q(**params):
    return urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})


def libraries():
    """Jellyfin's film and series libraries: [{id, name, kind (films or series), locations}]."""
    out = []
    for f in jf("/Library/VirtualFolders") or []:
        kind = {"movies": "films", "tvshows": "series"}.get(str(f.get("CollectionType") or "").lower())
        if kind and f.get("ItemId"):
            out.append({"id": str(f["ItemId"]), "name": str(f.get("Name") or ""), "kind": kind,
                        "locations": [str(x) for x in f.get("Locations") or [] if x]})
    return out


def people(ignore=()):
    """The people who count: Jellyfin's users that are not disabled, less those named in People to leave out."""
    out = []
    for u in jf("/Users") or []:
        if (u.get("Policy") or {}).get("IsDisabled") or str(u.get("Name") or "").strip().lower() in ignore:
            continue
        out.append({"id": str(u["Id"]), "name": str(u.get("Name") or "")})
    return out


def _pages(path, **params):
    start = 0
    while True:
        got = jf(f"{path}?{_q(**params, StartIndex=start, Limit=PAGE)}") or {}
        items = got.get("Items") or []
        yield from items
        start += len(items)
        if len(items) < PAGE or start >= int(got.get("TotalRecordCount") or 0):
            return


def _when(value):
    """Seconds since 1970 from Jellyfin's time, such as 2026-11-01T20:15:03.1234567Z (UTC), or None."""
    try:
        return dt.datetime.strptime(str(value)[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc).timestamp()
    except ValueError:
        return None


# Paths: Jellyfin's and Reelix's own folders, as this container sees them ---------------------------------------

def local_for(path, media=None):
    """This container's path for a folder another app names, by the longest tail that is under the media folder:
    /data/media/movies (Jellyfin's) is /media/movies here. None when no tail is there."""
    media = media or MEDIA
    parts = [p for p in str(path).split("/") if p]
    for i in range(len(parts)):
        here = os.path.join(media, *parts[i:])
        if os.path.isdir(here):
            return here
    return None


def mappings(libs):
    """[(Jellyfin's folder, this container's folder, library)] for every library location found here, longest first."""
    out = []
    for lib in libs:
        for loc in lib["locations"]:
            here = local_for(loc)
            if here and os.path.realpath(here) != os.path.realpath(MEDIA):
                out.append((loc.rstrip("/"), here, lib))
    return sorted(out, key=lambda m: -len(m[0]))


def to_local(path, maps):
    """(this container's path, its library root here) for a path Jellyfin gives, or (None, None)."""
    for theirs, ours, _ in maps:
        if path == theirs or path.startswith(theirs + "/"):
            return ours + path[len(theirs):], ours
    return None, None


def _inside(path, root):
    rp, rr = os.path.realpath(path), os.path.realpath(root)
    return rp != rr and rp.startswith(rr + os.sep)


def unit(item, local, root, film_paths):
    """What moves for one item, as a list of paths here: a series' folder; a film's own folder when it holds no other
    film; else the film's file and the files beside it that share its name (subtitles, details). [] when it cannot
    be worked out safely, such as a path at the library's top."""
    if not local or not root or not _inside(local, root) or os.path.islink(local):
        return []
    if item["kind"] == "series" or os.path.isdir(local):
        return [local] if os.path.isdir(local) else []
    folder = os.path.dirname(local)
    if not os.path.isfile(local):
        return []
    if _inside(folder, root) and not os.path.islink(folder):
        others = [p for p in film_paths.get(folder, ()) if p != local]
        if not others and not _hold_inside(folder):
            return [folder]
    stem = os.path.splitext(os.path.basename(local))[0]
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return []
    return [os.path.join(folder, n) for n in names
            if n == os.path.basename(local) or (n.startswith(stem + ".") and os.path.splitext(n)[1].lower() not in VIDEO)]


def _hold_inside(folder):
    """True when the holding folder is inside this folder: never moved into itself."""
    hold = os.path.realpath(os.path.join(MEDIA, HOLD_NAME))
    return hold == os.path.realpath(folder) or hold.startswith(os.path.realpath(folder) + os.sep)


def size_of(paths):
    total = 0
    for p in paths:
        if os.path.islink(p):
            continue
        if os.path.isfile(p):
            try:
                total += os.path.getsize(p)
            except OSError:
                pass
            continue
        for folder, dirs, names in os.walk(p):
            dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(folder, d))]
            for n in names:
                try:
                    total += os.lstat(os.path.join(folder, n)).st_size
                except OSError:
                    pass
    return total


# Reading Jellyfin ----------------------------------------------------------------------------------------------

FIELDS = "Path,DateCreated,Tags,ProviderIds"


def gather(r, progress=None):
    """Every film and series in the chosen libraries with what each person counted did with it: {id: item}."""
    libs = [lib for lib in libraries() if lib["id"] not in set(r["libraries_off"])]
    who = people(set(r["ignore_people"]))
    items = {}
    steps, step = max(1, len(libs) * max(1, len(who))), 0
    for lib in libs:
        kind = "Movie" if lib["kind"] == "films" else "Series"
        for person in who:
            for it in _pages("/Items", userId=person["id"], ParentId=lib["id"], Recursive="true", IncludeItemTypes=kind,
                             Fields=FIELDS, EnableImages="false", EnableTotalRecordCount="true"):
                if not it.get("Id"):
                    continue
                got = items.get(it["Id"])
                if got is None:
                    got = items[it["Id"]] = {
                        "id": it["Id"], "title": str(it.get("Name") or ""), "year": it.get("ProductionYear"),
                        "kind": "films" if kind == "Movie" else "series", "library": lib["name"], "library_id": lib["id"],
                        "path": str(it.get("Path") or ""), "added": _when(it.get("DateCreated")),
                        "tags": [str(t).lower() for t in it.get("Tags") or []], "status": str(it.get("Status") or ""),
                        "ids": {k.lower(): str(v) for k, v in (it.get("ProviderIds") or {}).items() if v}, "people": {}}
                u = it.get("UserData") or {}
                got["people"][person["id"]] = {
                    "played": bool(u.get("Played")), "favourite": bool(u.get("IsFavorite")),
                    "position": int(u.get("PlaybackPositionTicks") or 0), "last": _when(u.get("LastPlayedDate")),
                    "percent": float(u.get("PlayedPercentage") or 0)}
            step += 1
            if progress:
                progress(int(70 * step / steps))
    return items, who, libs


def resuming(who):
    """Ids of films and series someone is part way through, from each person's Continue watching."""
    out = set()
    for person in who:
        try:  # Jellyfin 10.9 and later; /Users/{id}/Items/Resume before
            rows = list(_pages("/UserItems/Resume", userId=person["id"], IncludeItemTypes="Movie,Episode", EnableImages="false"))
        except Exception:  # noqa: BLE001 - an older Jellyfin
            rows = list(_pages(f"/Users/{person['id']}/Items/Resume", IncludeItemTypes="Movie,Episode", EnableImages="false"))
        for it in rows:
            out.add(it.get("Id"))
            if it.get("SeriesId"):
                out.add(it["SeriesId"])
    out.discard(None)
    return out


def in_collections():
    """Ids of everything in a collection (Jellyfin's box sets)."""
    out = set()
    for box in _pages("/Items", Recursive="true", IncludeItemTypes="BoxSet", EnableImages="false"):
        for it in _pages("/Items", ParentId=box["Id"], EnableImages="false"):
            out.add(it.get("Id"))
    out.discard(None)
    return out


def series_last_watched(sid, who):
    """When anyone counted last watched an episode of a series, or None."""
    last = None
    for person in who:
        got = jf("/Items?" + _q(userId=person["id"], ParentId=sid, Recursive="true", IncludeItemTypes="Episode", Filters="IsPlayed",
                                SortBy="DatePlayed", SortOrder="Descending", Limit=1, EnableImages="false")) or {}
        for it in got.get("Items") or []:
            t = _when((it.get("UserData") or {}).get("LastPlayedDate"))
            if t and (last is None or t > last):
                last = t
    return last


# The rules -----------------------------------------------------------------------------------------------------

def kept_why(item, r, resume, boxed):
    """Why an item is always kept, in words, or None."""
    ps = item["people"].values()
    if r["keep_favourites"] and any(p["favourite"] for p in ps):
        return "A favourite"
    if r["keep_in_progress"] and (item["id"] in resume or any(
            (p["position"] > 0 and not p["played"]) or (item["kind"] == "series" and not p["played"] and 0 < p["percent"] < 100) for p in ps)):
        return "Someone is part way through"
    if r["keep_collections"] and item["id"] in boxed:
        return "In a collection"
    if r["keep_tag"] and r["keep_tag"] in item["tags"]:
        return f"Tagged {r['keep_tag']}"
    return None


def rule_for(item, r, who, at, last_episode=None):
    """The first rule an item meets, as (rule, words), or None. `last_episode`: a function giving a series' last watch."""
    ps = [item["people"].get(p["id"]) for p in who]
    if not who or any(p is None for p in ps):
        return None  # someone counted cannot see it: not watched by everyone, and not safe to judge
    day = 86400
    added = item["added"] or at
    if item["kind"] == "films":
        lasts = [p["last"] for p in ps if p["last"]]
        last = max(lasts) if lasts else None
        if r["watched"] and all(p["played"] for p in ps) and (last or added) < at - r["watched_days"] * day:
            ago = int((at - (last or added)) // day)
            return "watched", f"Watched by everyone, last {ago:,} days ago"
        months = r["unwatched_months"]
        if r["unwatched"] and added < at - months * 30.4375 * day and (last is None or last < at - months * 30.4375 * day):
            return "unwatched", f"Not watched for {months} months" if last else f"Never watched, added {months}+ months ago"
        return None
    every = all(p["played"] for p in ps)
    if r["ended"] and every and item["status"].lower() == "ended":
        last = last_episode(item["id"]) if last_episode else None
        if (last or added) < at - r["watched_days"] * day:
            return "ended", "Ended, and every episode watched by everyone"
    months = r["unwatched_months"]
    if r["unwatched"] and added < at - months * 30.4375 * day and not any(p["played"] or p["percent"] > 0 for p in ps):
        return "unwatched", f"Not watched for {months} months"
    if r["unwatched"] and added < at - months * 30.4375 * day and last_episode:
        last = last_episode(item["id"])
        if last and last < at - months * 30.4375 * day:
            return "unwatched", f"Not watched for {months} months"
    return None


def plan(r=None, progress=None):
    """What would move now: {"items": [...], "kept": n, "size": bytes, "at", "rules_key", "problems": [...]}."""
    r = r or rules()
    at = now()
    items, who, libs = gather(r, progress)
    maps = mappings(libs)
    resume = resuming(who) if r["keep_in_progress"] else set()
    boxed = in_collections() if r["keep_collections"] else set()
    if progress:
        progress(80)
    film_paths = {}
    for it in items.values():
        if it["kind"] == "films":
            local, _ = to_local(it["path"], maps)
            if local:
                film_paths.setdefault(os.path.dirname(local), []).append(local)
    cache = {}

    def last_episode(sid):
        if sid not in cache:
            cache[sid] = series_last_watched(sid, who)
        return cache[sid]
    out, kept, problems = [], 0, []
    for it in sorted(items.values(), key=lambda x: (x["library"], x["title"].lower())):
        why = rule_for(it, r, who, at, last_episode)
        if not why:
            continue
        if kept_why(it, r, resume, boxed):
            kept += 1
            continue
        local, root = to_local(it["path"], maps)
        paths = unit(it, local, root, film_paths)
        if not paths:
            if len(problems) < 20:
                problems.append(f"{it['title']}: its folder was not found in the media folder")
            continue
        out.append({"id": it["id"], "title": it["title"], "year": it["year"], "kind": it["kind"], "library": it["library"],
                    "rule": why[0], "why": why[1], "paths": [os.path.relpath(p, MEDIA) for p in paths], "size": size_of(paths),
                    "jellyfin_path": it["path"], "ids": it["ids"]})
    if progress:
        progress(100)
    return {"items": out, "kept": kept, "size": sum(i["size"] for i in out), "at": at, "rules_key": rules_key(r),
            "people": len(who), "libraries": len(libs), "problems": problems}


# Moving and putting back ---------------------------------------------------------------------------------------

def _held():
    return remember("held", None) or []


def _save_held(rows):
    keep("held", rows)


def move_paths(rels):
    """Renames each path (relative to the media folder) into the holding folder at the same place. Never copies: a
    move that would need a copy is refused. Returns [{"from", "to"}]; on a refusal part way, what moved is put back."""
    done = []
    try:
        for rel in rels:
            src = os.path.join(MEDIA, rel)
            dst = os.path.join(hold_root(), rel)
            if not os.path.lexists(src):
                raise FileNotFoundError(f"{rel} is not there any more")
            if os.path.lexists(dst):
                raise FileExistsError(f"Something called {rel} is in the holding folder already")
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            try:
                os.rename(src, dst)
            except OSError as e:
                if e.errno == errno.EXDEV:
                    raise OSError("The holding folder is on another disk here, so nothing was moved") from None
                raise
            done.append({"from": rel, "to": os.path.relpath(dst, MEDIA)})
    except OSError:
        for d in reversed(done):  # all or nothing for one item
            try:
                os.rename(os.path.join(MEDIA, d["to"]), os.path.join(MEDIA, d["from"]))
            except OSError:
                pass
        raise
    return done


def _reelix_index():
    """{("films"|"series", "tmdb"|"tvdb", id): (Reelix id, monitored)} for matching what moves."""
    out = {}
    for kind, path in (("films", "/movies"), ("series", "/series")):
        page = 1
        while True:
            got = rx(f"{path}?{_q(page=page, page_size=500)}") or {}
            rows = got.get("items") if isinstance(got, dict) else got
            for m in rows or []:
                for key in ("tmdb_id", "tvdb_id", "imdb_id"):
                    if m.get(key):
                        out[(kind, key[:4], str(m[key]))] = (int(m["id"]), bool(m.get("monitored", True)))
            if not isinstance(got, dict) or len(rows or []) < 500 or page * 500 >= int(got.get("total") or 0):
                break
            page += 1
    return out


def reelix_stop(item, index):
    """Reelix stops following it. Returns what to undo on Put back, or None when Reelix does not have it."""
    found = None
    for key in ("tmdb", "tvdb", "imdb"):
        if item["ids"].get(key) and (item["kind"], key, item["ids"][key]) in index:
            found = index[(item["kind"], key, item["ids"][key])]
            break
    if not found:
        return None
    rid, was = found
    if item["kind"] == "films":
        rx(f"/movies/{rid}", {"monitored": False}, "PUT")
        rx(f"/movies/{rid}/rescan", {}, "POST")
        return {"kind": "films", "id": rid, "was": was, "episodes": []}
    episodes = rx(f"/series/{rid}/episodes") or []
    episodes = episodes.get("items") if isinstance(episodes, dict) else episodes
    followed = [int(e["id"]) for e in episodes or [] if isinstance(e, dict) and e.get("id") and e.get("monitored")]
    rx(f"/series/{rid}", {"monitored": False}, "PUT")
    if followed:
        rx("/episodes/monitor", {"episode_ids": followed, "monitored": False}, "PUT")
    rx(f"/series/{rid}/rescan", {}, "POST")
    return {"kind": "series", "id": rid, "was": was, "episodes": followed}


def reelix_follow_again(undo):
    if not undo:
        return
    base = "/movies" if undo["kind"] == "films" else "/series"
    if undo.get("was"):
        rx(f"{base}/{undo['id']}", {"monitored": True}, "PUT")
    if undo.get("episodes"):
        rx("/episodes/monitor", {"episode_ids": undo["episodes"], "monitored": True}, "PUT")
    rx(f"{base}/{undo['id']}/rescan", {}, "POST")


def jellyfin_told(path, kind):
    """Tells Jellyfin a folder has gone (Deleted) or is back (Created), so it updates without a full scan."""
    if path:
        jf("/Library/Media/Updated", {"Updates": [{"Path": path, "UpdateType": kind}]}, "POST")


def move(item, index=None):
    """Moves one planned item to the holding folder and tells Reelix and Jellyfin. Returns its record."""
    done = move_paths(item["paths"])
    rec = {"id": hashlib.sha256(f"{item['id']}{now()}".encode()).hexdigest()[:12], "title": item["title"], "year": item.get("year"),
           "kind": item["kind"], "library": item["library"], "why": item["why"], "size": item["size"], "moved": now(),
           "entries": done, "jellyfin_id": item["id"], "jellyfin_path": item["jellyfin_path"], "ids": item["ids"],
           "reelix": None, "notes": []}
    rows = _held()
    rows.append(rec)
    _save_held(rows)  # kept before Reelix and Jellyfin are told, so Put back always knows where it is
    try:
        rec["reelix"] = reelix_stop(item, index) if index is not None else None
        if index is not None and rec["reelix"] is None:
            rec["notes"].append("Reelix does not have it")
    except Exception as e:  # noqa: BLE001 - the move stands; said on the row
        rec["notes"].append(f"Reelix was not told: {e}"[:160])
    try:
        jellyfin_told(item["jellyfin_path"], "Deleted")
    except Exception as e:  # noqa: BLE001
        rec["notes"].append(f"Jellyfin was not told: {e}"[:160])
    rows = [r if r["id"] != rec["id"] else rec for r in _held()]
    _save_held(rows)
    return rec


def put_back(hid):
    """Moves one held item back where it was, Reelix follows it again as it did, and Jellyfin is told. Returns words."""
    rows = _held()
    rec = next((r for r in rows if r["id"] == hid), None)
    if not rec:
        raise LookupError("That is not in the holding folder any more. Reload the page")
    for e in rec["entries"]:
        if not os.path.lexists(os.path.join(MEDIA, e["to"])):
            raise FileNotFoundError(f"{e['to']} is not in the holding folder any more, so nothing was put back")
        if os.path.lexists(os.path.join(MEDIA, e["from"])):
            raise FileExistsError(f"Something is at {e['from']} now, so it stays in the holding folder")
    back = []
    try:
        for e in rec["entries"]:
            dst = os.path.join(MEDIA, e["from"])
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            os.rename(os.path.join(MEDIA, e["to"]), dst)
            back.append(e)
    except OSError:
        for e in reversed(back):
            try:
                os.rename(os.path.join(MEDIA, e["from"]), os.path.join(MEDIA, e["to"]))
            except OSError:
                pass
        raise
    _save_held([r for r in rows if r["id"] != hid])
    said = [f"Put back {name(rec)} in {os.path.dirname(rec['entries'][0]['from']) or 'the media folder'}"]
    try:
        reelix_follow_again(rec.get("reelix"))
        if rec.get("reelix"):
            said.append("Reelix follows it again")
    except Exception as e:  # noqa: BLE001
        said.append(f"Reelix was not told: {e}"[:120])
    try:
        jellyfin_told(rec.get("jellyfin_path"), "Created")
    except Exception as e:  # noqa: BLE001
        said.append(f"Jellyfin was not told: {e}"[:120])
    log = remember("put_back", None) or []
    keep("put_back", (log + [{"title": name(rec), "at": now()}])[-KEEP_RUNS:])
    return ". ".join(said)


def name(rec):
    return f"{rec['title']} ({rec['year']})" if rec.get("year") else rec["title"]


# Runs ----------------------------------------------------------------------------------------------------------

def _state():
    return {"runs": [], **(remember("state", None) or {})}


def work_out_preview():
    """Works out Preview and keeps it."""
    r = rules()

    def progress(n):
        _job["progress"] = {"kind": "preview", "percent": n, "at": now()}
    p = plan(r, progress)
    keep("preview", p)
    return p


def run_moves(limit=RUN_LIMIT):
    """One run: works out what to move now, then moves up to MOVE_LIMIT items. Returns its record."""
    started = now()
    rec = {"start": started, "end": None, "moved": 0, "size": 0, "failed": 0, "kept": 0, "stopped": "", "failures": []}
    p = plan(rules(), lambda n: _job.update(progress={"kind": "move", "percent": n // 2, "at": now()}))
    keep("preview", p)
    rec["kept"] = p["kept"]
    index = None
    if p["items"] and reelix_known():
        try:
            index = _reelix_index()
        except Exception as e:  # noqa: BLE001 - moved all the same; each row says Reelix was not told
            rec["failures"].append({"title": "Reelix", "why": f"Not reached, so it was not told: {e}"[:160]})
    for n, item in enumerate(p["items"]):
        if n >= MOVE_LIMIT or now() - started > limit:
            rec["stopped"] = "Stopped at its limit; the next run carries on"
            break
        if sbplugin.holding():
            rec["stopped"] = "Stopped for an update"
            break
        try:
            move(item, index)
            rec["moved"] += 1
            rec["size"] += item["size"]
        except Exception as e:  # noqa: BLE001 - an item that cannot move stays where it is
            rec["failed"] += 1
            if len(rec["failures"]) < 20:
                rec["failures"].append({"title": item["title"], "why": f"{e}"[:160]})
        _job["progress"] = {"kind": "move", "percent": 50 + int(50 * (n + 1) / max(1, len(p["items"]))), "at": now(), "moved": rec["moved"]}
    rec["end"] = now()
    s = _state()
    s["runs"] = (s["runs"] + [rec])[-KEEP_RUNS:]
    keep("state", s)
    if rec["moved"]:
        left = [i for i in p["items"] if not any(h["jellyfin_id"] == i["id"] for h in _held())]
        keep("preview", {**p, "items": left, "size": sum(i["size"] for i in left)})
    return rec


def start(kind, fn):
    with _lock:
        if (_job["thread"] and _job["thread"].is_alive()) or sbplugin.holding():
            return False
        out = {}

        def go():
            try:
                with sbplugin.working("moving items" if kind == "move" else "working out the preview"):
                    out["rec"] = fn()
                keep("_error", None)
            except Exception as e:  # noqa: BLE001 - kept for the card and page, never fatal
                keep("_error", {"at": now(), "text": f"{type(e).__name__}: {e}"[:200]})
            finally:
                _job["progress"] = None
        t = threading.Thread(target=go, daemon=True)
        _job.update(thread=t, kind=kind, result=out)
        t.start()
        return True


def running():
    t = _job["thread"]
    return bool(t and t.is_alive())


def _wait(limit):
    t = _job["thread"]
    if t:
        t.join(limit)
    return (_job.get("result") or {}).get("rec")


def size_words(n):
    n = float(n or 0)
    for unit_name, by in (("TB", 1e12), ("GB", 1e9), ("MB", 1e6), ("KB", 1e3)):
        if abs(n) >= by:
            return f"{n / by:.1f} {unit_name}"
    return f"{int(n):,} bytes"


def summary(rec):
    if not rec:
        return "Nothing moved"
    words = f"Moved {plural(rec['moved'], 'item')} to the holding folder, freeing {size_words(rec['size'])}"
    if rec["failed"]:
        words += f"; {rec['failed']:,} could not move"
    return words + (f". {rec['stopped']}" if rec["stopped"] else "")


# What Starboard calls ------------------------------------------------------------------------------------------

def job_move():
    """Once a day in quiet hours: moves what the rules find, only when Move items each day is activated."""
    if not active():
        return {"said": "Move items each day is deactivated, so nothing moved. Preview lists what would"}
    if not start("move", run_moves):
        return {"said": "Already working" if running() else "Not started: the plug-in is about to be updated"}
    return {"said": summary(_wait(RUN_LIMIT + 300))}


def preview_again():
    if running():
        return {"said": "Already working. Preview says how far it has gone"}
    if not start("preview", work_out_preview):
        return {"said": "Not started: the plug-in is about to be updated"}
    return {"said": "Working out Preview again. Open 'Preview' when it is ready"}


def _preview_fresh(p):
    return bool(p) and p.get("rules_key") == rules_key(rules()) and now() - float(p.get("at") or 0) < PREVIEW_STALE


def _notices(kind):
    out, prog = [], _job["progress"]
    if prog and prog.get("kind") == kind:
        out.append({"id": "working", "tone": "info", "progress": prog["percent"],
                    "title": "Working out Preview" if kind == "preview" else "Moving items to the holding folder",
                    "text": "Reading your libraries from Jellyfin. This page updates by itself."})
    err = remember("_error")
    if isinstance(err, dict) and err.get("text"):
        out.append({"id": "error", "tone": "danger", "title": "The last run did not finish", "text": err["text"][:300], "dismiss": True})
    return out


def preview_screen():
    """Preview: what would move now and the space it frees, in a table to read. Worked out in the background when it
    is older than six hours or a setting changed; nothing moves from here."""
    p = remember("preview", None)
    if not _preview_fresh(p) and not running():
        start("preview", work_out_preview)
    notices = _notices("preview")
    if not p:
        intro = "Preview is being worked out from Jellyfin. Nothing moves until you activate 'Move items each day'."
        return {"type": "list", "title": "Preview", "layout": "folds", "readonly": True, "intro": intro, "columns": COLUMNS,
                "notices": notices or [{"id": "working", "tone": "info", "progress": 0, "title": "Working out Preview", "text": "Reading your libraries from Jellyfin."}],
                "items": []}
    when = dt.datetime.fromtimestamp(p["at"])
    n = len(p["items"])
    intro = (f"{plural(n, 'item')} would move to the holding folder, freeing {size_words(p['size'])}. "
             f"{plural(p['kept'], 'item')} the rules found {'is' if p['kept'] == 1 else 'are'} always kept. "
             f"Worked out {when:%a %-d %b at %H:%M} for {plural(p['people'], 'person', 'people')} in {plural(p['libraries'], 'library', 'libraries')}. ")
    intro += "It moves these once a day in quiet hours." if active() else "Nothing moves until you activate 'Move items each day'."
    if not _preview_fresh(p) and running():
        notices = notices or [{"id": "working", "tone": "info", "progress": 0, "title": "Working out Preview again", "text": "A setting changed."}]
    for i, prob in enumerate(p.get("problems") or []):
        if i == 0:
            notices.append({"id": "problems", "tone": "warning", "title": f"{plural(len(p['problems']), 'item')} could not be found here",
                            "text": "; ".join(p["problems"][:5])[:400]})
    items = [{"id": i["id"], "title": name(i), "group": i["library"], "actions": [],
              "cells": {"title": name(i), "library": i["library"], "why": i["why"], "size": size_words(i["size"]),
                        "where": i["paths"][0] if len(i["paths"]) == 1 else f"{os.path.dirname(i['paths'][0])} ({len(i['paths'])} files)"}}
             for i in p["items"]]
    return {"type": "list", "title": "Preview", "layout": "folds", "readonly": True, "intro": intro[:400], "columns": COLUMNS,
            "filters": [{"key": "why", "label": "Why"}], "notices": notices[:5], "items": items}


COLUMNS = [{"key": "title", "label": "Title"}, {"key": "library", "label": "Library"}, {"key": "why", "label": "Why it would move"},
           {"key": "size", "label": "Space"}, {"key": "where", "label": "Folder"}]


def preview_post(body=None):
    if (body or {}).get("action") == "dismiss":
        keep("_error", None)
    return preview_screen()


def held_screen(said=None):
    """The holding folder: what this plug-in moved, newest first, each with Put back."""
    rows = sorted(_held(), key=lambda r: -r["moved"])
    total = sum(r["size"] for r in rows)
    items = []
    for r in rows:
        there = all(os.path.lexists(os.path.join(MEDIA, e["to"])) for e in r["entries"])
        when = dt.datetime.fromtimestamp(r["moved"])
        detail = f"{r['library']}. Moved {when:%A %-d %B}, {size_words(r['size'])}. {r['why']}"
        if r.get("notes"):
            detail += ". " + "; ".join(r["notes"])
        items.append({"id": r["id"], "title": name(r), "detail": detail[:200], "group": r["library"],
                      "state": "off" if there else "problem", "state_label": "In holding" if there else "Not found",
                      "actions": ["restore"] if there else []})
    intro = (f"{plural(len(rows), 'item')} in media/.holding/{PID}, {size_words(total)}. Put back returns each to where it was"
             + (", and Reelix follows it again." if reelix_known() else ".") + " Nothing here is deleted; to free the space permanently, delete them yourself.")
    out = {"type": "list", "title": "Holding folder", "intro": intro[:400], "items": items, "notices": _notices("move")}
    if said:
        out["said"] = said
    return out


def held_post(body=None):
    body = body or {}
    if body.get("action") == "dismiss":
        keep("_error", None)
        return held_screen()
    if body.get("action") != "restore":
        return held_screen("Not something this list does")
    if running() and _job["kind"] == "move":
        return held_screen("Items are being moved now. Put it back when that finishes")
    try:
        with sbplugin.working("putting back"):
            said = put_back(str(body.get("id") or ""))
    except (OSError, LookupError) as e:
        said = str(e)
    return held_screen(said[:200])


def libraries_screen(said=None):
    """The libraries it looks at: each film and series library in Jellyfin, activated or deactivated."""
    off = _libraries_off()
    try:
        libs = libraries()
    except Exception as e:  # noqa: BLE001 - said on the screen
        return {"type": "list", "title": "Libraries", "intro": f"Jellyfin did not answer: {e}"[:400], "items": []}
    items = [{"id": lib["id"], "title": lib["name"], "detail": ("Films" if lib["kind"] == "films" else "Series") + ": " + ", ".join(lib["locations"])[:150],
              "group": "Films" if lib["kind"] == "films" else "Series", "on": lib["id"] not in off,
              "state": "ok" if lib["id"] not in off else "off", "state_label": "Checked" if lib["id"] not in off else "Left alone",
              "actions": ["toggle"]} for lib in libs]
    out = {"type": "list", "title": "Libraries", "intro": "The rules check only the libraries activated here. A library you add to Jellyfin is checked until you deactivate it.",
           "items": items}
    if said:
        out["said"] = said
    return out


def libraries_post(body=None):
    body = body or {}
    if body.get("action") != "toggle":
        return libraries_screen("Not something this list does")
    off = _libraries_off()
    lid = str(body.get("id") or "")
    if lid in off:
        off.discard(lid)
        said = "The rules check this library again"
    else:
        off.add(lid)
        said = "The rules leave this library alone"
    keep("libraries", {"off": sorted(off)})
    return libraries_screen(said)


def card():
    """The holding folder's size, with the band's status: working now, deactivated, or the next run."""
    rows, prog = _held(), _job["progress"]
    total = sum(r["size"] for r in rows)
    err = remember("_error")
    if prog:
        what = "Moving items" if prog["kind"] == "move" else "Working out Preview"
        return band({"value": total, "label": "in the holding folder", "note": f"{what}: {prog['percent']}%"}, "working", prog["at"], what, refresh=30)
    if isinstance(err, dict) and err.get("text"):
        return band({"value": total, "label": "in the holding folder", "note": f"The last run did not finish: {err['text']}"[:80]}, "problem",
                    err.get("at"), "Last run failed", refresh=600)
    p = remember("preview", None) or {}
    would = f"Preview: {plural(len(p.get('items') or []), 'item')}, {size_words(p.get('size'))}" if p else "Open 'Preview' to find what would move"
    if not active():
        return band({"value": total, "label": "in the holding folder", "note": f"Deactivated. {would}"[:80]}, "inactive", sbplugin.changed("preview"),
                    "Deactivated", refresh=600)
    s = _state()
    note = f"{plural(len(rows), 'item')} held. Next check in quiet hours"
    return band({"value": total, "label": "in the holding folder", "note": note}, "scheduled",
                (s["runs"][-1]["end"] if s["runs"] else None), "Next in quiet hours", refresh=600)


def before_update(body=None):
    """POST /update/before: no new run starts, and one that is running stops after the item it is on (every move is
    whole, so nothing is left half moved; the next run carries on)."""
    sbplugin._work["hold"] = now() + sbplugin.HOLD_SECONDS
    t = _job["thread"]
    if t:
        t.join(45)
    if running():
        sbplugin._work["hold"] = 0.0
        return {"ok": False, "said": "Still working. Try again in a minute"}
    return {"ok": True, "said": "Ready to update: nothing is being moved"}


def after_update(body=None):
    sbplugin._work["hold"] = 0.0
    return {"ok": True, "said": "Ready. " + ("It checks again in quiet hours" if active() else "Move items each day is deactivated")}


def health():
    """200 only while it can do its work: the media folder is there to read and change, and its own folder too."""
    if not os.path.isdir(MEDIA) or not os.access(MEDIA, os.R_OK | os.W_OK | os.X_OK):
        raise RuntimeError("The media folder cannot be read and changed")
    if not os.access(sbplugin.DATA, os.W_OK):
        raise RuntimeError("Its own folder cannot be written")
    return {"ok": True}


ROUTES = {("GET", "/health"): health, "/card": card, "/preview": preview_screen, ("POST", "/preview"): preview_post,
          "/held": held_screen, ("POST", "/held"): held_post, "/libraries": libraries_screen, ("POST", "/libraries"): libraries_post,
          ("POST", "/preview-again"): preview_again, ("POST", "/jobs/move"): job_move,
          ("POST", "/update/before"): before_update, ("POST", "/update/after"): after_update}

if __name__ == "__main__":
    serve(ROUTES)
