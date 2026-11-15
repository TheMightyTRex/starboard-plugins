"""Library health: Films and series in Jellyfin with no poster, no description or no year, so you can fix them."""
from sbplugin import band, changed, every, jellyfin, keep, last_error, plural, remember, serve


def check():
    got = jellyfin("/Items?Recursive=true&IncludeItemTypes=Movie,Series&Fields=Overview,ProductionYear&EnableImageTypes=Primary") or {}
    items = got.get("Items") or []
    bad = []
    for it in items:
        why = [w for w, missing in (("no poster", "Primary" not in (it.get("ImageTags") or {})),
                                    ("no description", not it.get("Overview")), ("no year", not it.get("ProductionYear"))) if missing]
        if why:
            bad.append({"title": f"{it.get('Name')}" + (f" ({it['ProductionYear']})" if it.get("ProductionYear") else ""),
                        "detail": ", ".join(why).capitalize()})
    keep("result", {"bad": bad, "total": len(items)})
    return {"said": f"{plural(len(bad), 'title')} to fix of {len(items):,}"}


def state():
    r = remember("result") or {}
    if not r:
        return ("problem", None) if last_error() else ("waiting", "Checking soon")
    n = len(r.get("bad", []))
    return ("warning", plural(n, "title") + " to fix") if n else ("ok", "Nothing to fix")


def count():
    r = remember("result") or {}
    status, label = state()
    return band({"value": len(r.get("bad", [])), "label": "to fix", "note": f"of {r.get('total', 0):,} titles" if r else (last_error() or "Not checked yet")},
                status, changed("result"), label)


def card():
    bad = (remember("result") or {}).get("bad", [])
    status, label = state()
    return band({"items": bad[:10] or [{"title": "Nothing to fix", "detail": "Every title has a poster, a description and a year"}]},
                status, changed("result"), label)


every(6 * 3600, check)
serve({"/count": count, "/card": card, ("POST", "/check"): check})
