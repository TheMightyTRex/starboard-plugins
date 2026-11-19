"""Sports streams: live and upcoming sports matches from a Stremio sports addon."""
import urllib.error
from sbplugin import band, changed, every, fetch, keep, plural, remember, serve, setting

CATALOGS = {
    "sports_live": "Live now",
    "sports_today": "Today",
    "sports_football": "Football",
    "sports_basketball": "Basketball",
    "sports_american_football": "American football",
    "sports_hockey": "Hockey",
    "sports_baseball": "Baseball",
    "sports_motor_sports": "Motor sports",
    "sports_fight": "Fight",
    "sports_tennis": "Tennis",
    "sports_rugby": "Rugby",
    "sports_golf": "Golf",
    "sports_cricket": "Cricket",
    "sports_other": "Other",
}


def addon_url():
    return (setting("addon_url", "https://sports.highfly.dev") or "https://sports.highfly.dev").rstrip("/")


def poll():
    url = f"{addon_url()}/catalog/sport/sports_live.json"
    try:
        data = fetch(url, timeout=15)
    except Exception:  # noqa: BLE001
        keep("matches", [])
        return
    rows = []
    for m in (data.get("metas") or [])[:50]:
        name = m.get("name", "")
        genres = m.get("genres") or []
        sport = genres[0] if genres else ""
        desc = (m.get("description") or "").split("\n")[0]
        rows.append({"name": name, "sport": sport, "description": desc})
    keep("matches", rows)


def status():
    rows = remember("matches")
    if rows is None:
        return band({"state": "warning", "text": "Not checked yet"}, "waiting")
    if not rows:
        return band({"state": "ok", "text": "No live matches"}, "idle", changed("matches"))
    return band({"state": "ok", "text": plural(len(rows), "match", "matches") + " live"},
                "running", changed("matches"), "Live")


def card():
    rows = remember("matches")
    if rows is None:
        return band({"items": []}, "waiting")
    items = [{"title": r["name"], "detail": r["sport"] or r["description"]} for r in rows][:20]
    if not rows:
        return band({"items": items}, "idle", changed("matches"))
    return band({"items": items}, "running", changed("matches"), "Live")


every(60 * float(setting("minutes", 5)), poll, first=2)
serve({"/status": status, "/card": card})
