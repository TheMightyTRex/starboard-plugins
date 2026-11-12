"""Watching now: Who is watching what in Jellyfin right now, with how far through they are."""
from sbplugin import jellyfin, serve


def card():
    rows = []
    for s in jellyfin("/Sessions?ActiveWithinSeconds=120") or []:
        item = s.get("NowPlayingItem")
        if not item:
            continue
        title = item.get("Name", "")
        if item.get("SeriesName"):
            title = f"{item['SeriesName']}: S{item.get('ParentIndexNumber', 0):02d}E{item.get('IndexNumber', 0):02d} {title}"
        ticks, at = item.get("RunTimeTicks") or 0, (s.get("PlayState") or {}).get("PositionTicks") or 0
        bits = [s.get("UserName"), s.get("DeviceName"), f"{round(100 * at / ticks)}%" if ticks else "",
                "paused" if (s.get("PlayState") or {}).get("IsPaused") else ""]
        rows.append({"title": title, "detail": ", ".join(b for b in bits if b)})
    return {"items": rows or [{"title": "Nobody is watching", "detail": "Jellyfin is quiet"}]}


serve({"/card": card})
