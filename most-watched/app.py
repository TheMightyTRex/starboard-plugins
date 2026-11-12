"""Most watched: The films and series most people watched in Jellyfin in the last week."""
import time
from collections import defaultdict
from sbplugin import every, jellyfin, keep, last_error, plural, remember, serve, setting


def count():
    since = time.time() - 86400 * int(setting("days", 7))
    titles = defaultdict(lambda: {"people": set(), "plays": 0})
    for u in jellyfin("/Users") or []:
        got = jellyfin(f"/Users/{u['Id']}/Items?Recursive=true&IncludeItemTypes=Movie,Episode&Filters=IsPlayed"
                       "&SortBy=DatePlayed&SortOrder=Descending&Limit=200&Fields=UserData") or {}
        for it in got.get("Items") or []:
            played = (it.get("UserData") or {}).get("LastPlayedDate") or ""
            if not played or time.mktime(time.strptime(played[:19], "%Y-%m-%dT%H:%M:%S")) < since:
                continue
            name = it.get("SeriesName") or it.get("Name")
            titles[name]["people"].add(u["Id"])
            titles[name]["plays"] += 1
    top = sorted(titles.items(), key=lambda kv: (-len(kv[1]["people"]), -kv[1]["plays"]))[:10]
    keep("top", [{"title": t, "people": len(v["people"]), "plays": v["plays"]} for t, v in top])


def card():
    top = remember("top", [])
    if not top:
        return {"items": [{"title": "Nothing watched yet", "detail": last_error() or f"in the last {setting('days', 7)} days"}]}
    return {"items": [{"title": t["title"], "detail": f"{t['people']} {'person' if t['people'] == 1 else 'people'}, {plural(t['plays'], 'play')}"} for t in top]}


every(3600, count)
serve({"/card": card})
