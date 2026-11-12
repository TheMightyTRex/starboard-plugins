"""Library health: Films and series in Jellyfin with no poster, no description or no year, so you can fix them."""
from sbplugin import every, jellyfin, keep, last_error, plural, remember, serve


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


def count():
    r = remember("result") or {}
    return {"value": len(r.get("bad", [])), "label": "to fix", "note": f"of {r.get('total', 0):,} titles" if r else (last_error() or "Not checked yet")}


def card():
    bad = (remember("result") or {}).get("bad", [])
    return {"items": bad[:10] or [{"title": "Nothing to fix", "detail": "Every title has a poster, a description and a year"}]}


every(6 * 3600, check)
serve({"/count": count, "/card": card, ("POST", "/check"): check})
