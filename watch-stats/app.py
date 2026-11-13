"""Watch statistics: What was watched, by whom and when, from Jellyfin's Playback Reporting, with no second database.

It reads Playback Reporting's own table through Jellyfin's API with one query, keeps the answer for 15 minutes in
/data, and draws cards and three read-only tables (plug-in API 1.11). Without Playback Reporting it says so, how to
add it, and shows what Jellyfin itself knows: each person's last play of each title (DASH-402)."""
import calendar
import datetime as dt
import json
import os
import time
import urllib.parse
from collections import Counter, defaultdict

from sbplugin import RUN, fetch, jellyfin, keep, plural, remember, serve, setting

FRESH = 15 * 60
LIMIT = 5000  # rows read at most, about 750 KB from Jellyfin
SHOWN = 300   # plays in the Recent plays table
HOW_TO_ADD = ("Add it in Starboard's Settings, Jellyfin, or in Jellyfin's Dashboard, Plugins, Catalogue (it is in the "
              "official catalogue), then restart Jellyfin. It starts counting from then.")
KINDS = {"Movie": "Films", "Episode": "Series", "Audio": "Music", "AudioBook": "Audiobooks", "MusicVideo": "Music"}


def days():
    return int(setting("days", 30))


def left_out():
    v = setting("leave_out", []) or []
    return {str(x).strip().lower() for x in (v if isinstance(v, list) else [v]) if str(x).strip()}


def has_reporting():
    for p in jellyfin("/Plugins") or []:
        if "playback reporting" in str(p.get("Name", "")).lower():
            return str(p.get("Status", "Active")) in ("Active", "Restart", "")
    return False


def _when(text):
    try:
        return time.mktime(time.strptime(str(text)[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S"))
    except ValueError:
        return 0.0


def _utc(text):
    """Jellyfin's own dates are in UTC, such as 2026-11-13T20:15:01.0000000Z."""
    try:
        return float(calendar.timegm(time.strptime(str(text)[:19], "%Y-%m-%dT%H:%M:%S")))
    except ValueError:
        return 0.0


def from_reporting(n):
    """One query to Playback Reporting's table, newest first. Its answer spells columns as 'colums'."""
    sql = ("SELECT DateCreated, UserId, ItemName, ItemType, DeviceName, ClientName, PlayDuration FROM PlaybackActivity "
           f"WHERE DateCreated >= datetime('now', 'localtime', '-{int(n)} days') ORDER BY DateCreated DESC LIMIT {LIMIT}")
    got = jellyfin_post("/user_usage_stats/submit_custom_query", {"CustomQueryString": sql, "ReplaceUserId": True}) or {}
    rows = []
    for r in got.get("results") or []:
        if len(r) < 7:
            continue
        rows.append({"at": _when(r[0]), "who": str(r[1] or "Someone"), "name": str(r[2] or ""), "type": str(r[3] or ""),
                     "device": str(r[4] or r[5] or ""), "seconds": int(float(r[6] or 0))})
    return rows


def jellyfin_post(path, body):
    """Jellyfin with a JSON body (sbplugin's jellyfin() only reads)."""
    with open(os.path.join(RUN, "jellyfin.json"), encoding="utf-8") as f:
        jf = json.load(f)
    if not jf.get("url") or not jf.get("api_key"):
        raise LookupError("Starboard has no Jellyfin key to give yet: add Jellyfin in Settings, Apps")
    return fetch(jf["url"].rstrip("/") + path, {"X-Emby-Token": jf["api_key"]}, data=body, method="POST")


def from_jellyfin(n):
    """Without Playback Reporting: each person's last play of each title, from Jellyfin's own played list."""
    since = time.time() - 86400 * n
    rows = []
    for u in jellyfin("/Users") or []:
        got = jellyfin(f"/Users/{urllib.parse.quote(u['Id'])}/Items?Recursive=true&IncludeItemTypes=Movie,Episode,Audio,AudioBook"
                       "&Filters=IsPlayed&SortBy=DatePlayed&SortOrder=Descending&Limit=200&Fields=UserData") or {}
        for it in got.get("Items") or []:
            at = _utc((it.get("UserData") or {}).get("LastPlayedDate") or "")
            if at < since:
                continue
            name = f"{it['SeriesName']} - {it.get('Name', '')}" if it.get("SeriesName") else it.get("Name", "")
            rows.append({"at": at, "who": u.get("Name") or "Someone", "name": name, "type": it.get("Type", ""),
                         "device": "", "seconds": 0})
    rows.sort(key=lambda r: -r["at"])
    return rows


def plays(force=False):
    """{source, rows, at}: from /data while fresh, else read again."""
    hit = remember("plays") or {}
    if not force and hit.get("at", 0) > time.time() - FRESH and hit.get("days") == days():
        rows = hit["rows"]
    else:
        source = "reporting" if has_reporting() else "jellyfin"
        rows = from_reporting(days()) if source == "reporting" else from_jellyfin(days())
        hit = {"at": time.time(), "days": days(), "source": source, "rows": rows}
        keep("plays", hit)
    out = left_out()
    return {**hit, "rows": [r for r in rows if r["who"].lower() not in out]}


def title_of(r):
    """A series' episodes count as the series: Playback Reporting names them 'Series - s01e02 - Episode'."""
    if r["type"] == "Episode" and " - " in r["name"]:
        return r["name"].split(" - ", 1)[0]
    return r["name"]


def hours(seconds):
    return f"{seconds / 3600:.1f}"


def _day(at):
    d = dt.date.fromtimestamp(at)
    today = dt.date.today()
    return "Today" if d == today else "Yesterday" if d == today - dt.timedelta(days=1) else f"{d:%A} {d.day} {d:%B}"


def tops(rows):
    t = defaultdict(lambda: {"plays": 0, "people": set(), "seconds": 0, "last": 0, "type": ""})
    for r in rows:
        x = t[title_of(r)]
        x["plays"] += 1
        x["people"].add(r["who"])
        x["seconds"] += r["seconds"]
        x["last"] = max(x["last"], r["at"])
        x["type"] = x["type"] or r["type"]
    return sorted(t.items(), key=lambda kv: (-len(kv[1]["people"]), -kv[1]["plays"], kv[0].lower()))


def by_person(rows):
    p = defaultdict(lambda: {"plays": 0, "seconds": 0, "last": 0, "titles": Counter()})
    for r in rows:
        x = p[r["who"]]
        x["plays"] += 1
        x["seconds"] += r["seconds"]
        x["last"] = max(x["last"], r["at"])
        x["titles"][title_of(r)] += 1
    return sorted(p.items(), key=lambda kv: (-kv[1]["seconds"], -kv[1]["plays"], kv[0].lower()))


# Words when Playback Reporting is missing ---------------------------------------------------------------------

def missing_text():
    return ("Playback Reporting is not installed in Jellyfin, so these figures are only each person's last play of each "
            "title, with no device or time watched. " + HOW_TO_ADD)


def _notices(data):
    if data.get("source") == "reporting":
        return []
    return [{"id": "no-reporting", "tone": "warning", "title": "Playback Reporting is not installed in Jellyfin", "text": missing_text()}]


def _screen(title, intro, columns, items, data):
    return {"type": "list", "title": title, "layout": "folds", "readonly": True, "intro": intro,
            "columns": [{"key": k, "label": w, **({"type": "number"} if t else {})} for k, w, t in columns],
            "notices": _notices(data), "items": items}


def _period():
    return f"over the last {plural(days(), 'day')}"


# What Starboard calls ------------------------------------------------------------------------------------------

def screen_plays():
    data = plays()
    items = [{"id": f"p{i}", "title": r["name"], "group": _day(r["at"]), "actions": [],
              "cells": {"time": time.strftime("%H:%M", time.localtime(r["at"])), "person": r["who"], "title": r["name"],
                        "device": r["device"], "minutes": str(round(r["seconds"] / 60))}}
             for i, r in enumerate(data["rows"][:SHOWN])]
    cols = [("time", "Time", 0), ("person", "Person", 0), ("title", "Title", 0), ("device", "Device", 0), ("minutes", "Minutes", 1)]
    return _screen("Plays", f"The newest {min(len(data['rows']), SHOWN):,} plays, {_period()}, by day.", cols, items, data)


def screen_titles():
    data = plays()
    items = [{"id": f"t{i}", "title": name, "group": KINDS.get(x["type"], "Other"), "actions": [],
              "cells": {"title": name, "plays": str(x["plays"]), "people": str(len(x["people"])), "hours": hours(x["seconds"]),
                        "last": f"{_day(x['last'])}"}}
             for i, (name, x) in enumerate(tops(data["rows"]))]
    cols = [("title", "Title", 0), ("plays", "Plays", 1), ("people", "People", 1), ("hours", "Hours", 1), ("last", "Last watched", 0)]
    return _screen("Titles", f"Every title watched {_period()}, most people first. A series counts all its episodes.", cols, items, data)


def screen_people():
    data = plays()
    items = [{"id": f"u{i}", "title": who, "group": "Everyone", "actions": [],
              "cells": {"person": who, "plays": str(x["plays"]), "hours": hours(x["seconds"]),
                        "most": x["titles"].most_common(1)[0][0] if x["titles"] else "", "last": _day(x["last"])}}
             for i, (who, x) in enumerate(by_person(data["rows"]))]
    cols = [("person", "Person", 0), ("plays", "Plays", 1), ("hours", "Hours", 1), ("most", "Watched most", 0), ("last", "Last watched", 0)]
    return _screen("People", f"Who watched what {_period()}.", cols, items, data)


def card_week():
    data = plays()
    week = [r for r in data["rows"] if r["at"] >= time.time() - 7 * 86400]
    people = len({r["who"] for r in week})
    note = (f"{hours(sum(r['seconds'] for r in week))} hours by {plural(people, 'person', 'people')}" if data.get("source") == "reporting"
            else "Playback Reporting is not installed in Jellyfin")
    return {"value": len(week), "label": "plays this week", "note": note}


def card_top():
    data = plays()
    top = tops(data["rows"])[:10]
    if not top:
        return {"items": [{"title": "Nothing watched yet", "detail": _period()}]}
    return {"items": [{"title": name, "detail": f"{plural(len(x['people']), 'person', 'people')}, {plural(x['plays'], 'play')}"}
                      for name, x in top]}


def card_people():
    data = plays()
    rows = by_person(data["rows"])[:10]
    if not rows:
        return {"items": [{"title": "Nobody has watched anything yet", "detail": _period()}]}
    return {"items": [{"title": who, "detail": (f"{hours(x['seconds'])} hours, " if data.get("source") == "reporting" else "")
                       + plural(x["plays"], "play") + (f", most {x['titles'].most_common(1)[0][0]}" if x["titles"] else "")}
                      for who, x in rows]}


def card_source():
    try:
        ok = has_reporting()
    except Exception as e:  # noqa: BLE001
        return {"state": "problem", "text": f"Jellyfin did not answer: {e}"[:160]}
    if ok:
        return {"state": "ok", "text": "Reading Jellyfin's Playback Reporting"}
    return {"state": "warning", "text": "Playback Reporting is not installed in Jellyfin. Add it in Settings, Jellyfin, or Jellyfin's catalogue."}


def refresh():
    data = plays(force=True)
    return {"said": f"Read {plural(len(data['rows']), 'play')} {_period()}"
            + ("" if data["source"] == "reporting" else ". Playback Reporting is not installed in Jellyfin, so these are last plays only")}


def act(body):
    raise ValueError("These figures are read only")


ROUTES = {"/card/week": card_week, "/card/top": card_top, "/card/people": card_people, "/card/source": card_source,
          "/screen/plays": screen_plays, "/screen/titles": screen_titles, "/screen/people": screen_people,
          ("POST", "/screen/plays"): act, ("POST", "/screen/titles"): act, ("POST", "/screen/people"): act,
          ("POST", "/refresh"): refresh}

if __name__ == "__main__":
    serve(ROUTES, port=int(os.environ.get("PORT", 8080)))
