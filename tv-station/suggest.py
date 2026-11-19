"""Suggest a schedule: a week for a channel, proposed from watch history. It only proposes: the grid page shows it
unsaved, to change, save or discard.

What it does, in the way broadcast schedulers work (stripping series on weekdays, films at the weekend):
- Reads plays: Playback Reporting's table when Jellyfin has it (what the Watch statistics plug-in reads), and each
  person's played list in Jellyfin always, with the date and time of each last play.
- Counts plays of each series and film, newer plays counting more, and notes the hours they are watched at.
- Strips the most watched series on weekdays, Monday to Friday, at the half hour people most often watch them in the
  evening (from 18:00), one after another, starting from the next episode not watched.
- Puts the most watched films on Saturday and Sunday at 20:00, and at 15:00 when there are more.
- On a channel with a line-up, only its own series and films are used; on one without, anything watched.

What it is made from is chosen first (0.2.0, owner, 19 November 2026: "ignore the settings and give a choice"):
- Watch history: as described first, the channel's own series and films that have been watched.
- General watch history: everything anyone has watched, whatever the channel shows.
- All TV, All films, TV and Films: from the whole library, the most watched first and then the rest; All TV strips
  series every day, All films puts a film on every evening, TV and Films does both, as described first.

    python3 suggest.py --url http://jellyfin:8096 --key <API key> [--days 90] [--from history|everyone|tv|films|both]

prints a week from this Jellyfin's history, so it can be tried with no plug-in.
"""
import argparse
import json
import math
import time
import urllib.parse
import urllib.request

import grid

EVENING = (18 * 60, 23 * 60)  # series are stripped in the evening, between these times
FILM_TIMES = ((5, 20 * 60), (6, 20 * 60), (5, 15 * 60), (6, 15 * 60))  # (day, minute): Saturday and Sunday
MOST_SERIES = 4
SOURCES = {"history": "Watch history", "everyone": "General watch history", "tv": "All TV", "films": "All films", "both": "TV and Films"}
FILM_EVENINGS = tuple((d, 20 * 60) for d in range(7)) + ((5, 15 * 60), (6, 15 * 60))  # All films: every evening
HALF_LIFE = 30 * 86400  # a play a month old counts half


def _q(**p):
    return urllib.parse.urlencode({k: v for k, v in p.items() if v not in (None, "")})


def _utc(text):
    import calendar
    try:
        return float(calendar.timegm(time.strptime(str(text)[:19], "%Y-%m-%dT%H:%M:%S")))
    except ValueError:
        return 0.0


def _local(text):
    try:
        return time.mktime(time.strptime(str(text)[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S"))
    except ValueError:
        return 0.0


# Reading history ---------------------------------------------------------------------------------------------------
def from_jellyfin(jf, days=90):
    """Each person's plays from Jellyfin's own played lists: [{"at", "kind", "id", "name"}]."""
    since = time.time() - days * 86400
    plays = []
    for u in jf("/Users") or []:
        got = jf(f"/Users/{u['Id']}/Items?" + _q(Filters="IsPlayed", IncludeItemTypes="Episode,Movie", Recursive="true",
                                                SortBy="DatePlayed", SortOrder="Descending", Limit=1000, Fields="UserData,SeriesId")) or {}
        for i in got.get("Items") or []:
            t = _utc((i.get("UserData") or {}).get("LastPlayedDate"))
            if t < since:
                continue
            if i.get("Type") == "Episode" and i.get("SeriesId"):
                plays.append({"at": t, "kind": "series", "id": i["SeriesId"], "name": i.get("SeriesName") or ""})
            elif i.get("Type") == "Movie":
                plays.append({"at": t, "kind": "film", "id": i["Id"], "name": i.get("Name") or ""})
    return plays


def from_reporting(jf_post, jf, days=90):
    """Every play from Playback Reporting's table, when Jellyfin has it, with its episode's series."""
    sql = ("SELECT DateCreated, ItemId, ItemType, ItemName FROM PlaybackActivity "
           f"WHERE DateCreated >= datetime('now', 'localtime', '-{int(days)} days') ORDER BY DateCreated DESC LIMIT 5000")
    got = jf_post("/user_usage_stats/submit_custom_query", {"CustomQueryString": sql, "ReplaceUserId": True}) or {}
    rows = [r for r in got.get("results") or [] if len(r) >= 4]
    series_of = {}
    ids = sorted({str(r[1]) for r in rows if str(r[2]) == "Episode"})
    for k in range(0, len(ids), 100):
        found = jf("/Items?" + _q(Ids=",".join(ids[k:k + 100]), Fields="SeriesId")) or {}
        for i in found.get("Items") or []:
            series_of[i["Id"].replace("-", "")] = (i.get("SeriesId"), i.get("SeriesName") or "")
    plays = []
    for r in rows:
        t = _local(r[0])
        if str(r[2]) == "Episode":
            sid, name = series_of.get(str(r[1]).replace("-", ""), (None, ""))
            if sid:
                plays.append({"at": t, "kind": "series", "id": sid, "name": name})
        elif str(r[2]) == "Movie":
            plays.append({"at": t, "kind": "film", "id": str(r[1]), "name": str(r[3] or "")})
    return plays


def history(jf, jf_post=None, days=90):
    """Plays from Playback Reporting when it answers, and from Jellyfin's played lists. Never fails: no history is
    an empty list."""
    plays = []
    if jf_post:
        try:
            plays += from_reporting(jf_post, jf, days)
        except Exception:  # noqa: BLE001 - Playback Reporting is not installed
            pass
    try:
        plays += from_jellyfin(jf, days)
    except Exception:  # noqa: BLE001 - Jellyfin did not answer
        pass
    return plays


# Proposing ----------------------------------------------------------------------------------------------------------
def scores(plays, now):
    """Per (kind, id): {"score", "name", "hours": {half hour of the day: weight}}."""
    out = {}
    for p in plays:
        w = math.pow(0.5, max(0.0, now - float(p["at"])) / HALF_LIFE)
        s = out.setdefault((p["kind"], str(p["id"])), {"score": 0.0, "name": p.get("name") or "", "hours": {}})
        s["score"] += w
        lt = time.localtime(p["at"])
        half = lt.tm_hour * 60 + (30 if lt.tm_min >= 30 else 0)
        s["hours"][half] = s["hours"].get(half, 0.0) + w
    return out


def best_time(hours):
    """The evening half hour it is most watched at, else 20:00."""
    evening = {h: w for h, w in hours.items() if EVENING[0] <= h <= EVENING[1]}
    return max(sorted(evening), key=lambda h: evening[h]) if evening else 20 * 60


def propose(channel_groups, plays, now, series_info, film_info, most_series=MOST_SERIES, source="history", pool=None):
    """A week for one channel, as a grid document, and the reasons in words.

    channel_groups: the series and film ids of the channel's line-up, or None for anything watched
    series_info(id) -> {"id", "name", "episodes": [...], "unwatched": index} or None
    film_info(id)   -> a programme (library.entry) or None
    source:         one of SOURCES: what the week is made from
    pool:           for All TV, All films and TV and Films, the library's [(kind, id, name)], kind series or film
    """
    sc = scores(plays, now)
    ranked = sorted(sc.items(), key=lambda kv: -kv[1]["score"])
    if channel_groups is not None and source == "history":
        ranked = [kv for kv in ranked if kv[0][1] in channel_groups]
    if source in ("tv", "films", "both"):
        # The whole library: what has been watched first, then the rest in the order the library gave.
        have = {k for k, _ in ranked}
        ranked += [((kind, str(iid)), {"score": 0.0, "name": name, "hours": {}}) for kind, iid, name in pool or [] if (kind, str(iid)) not in have]
        keep = {"tv": ("series",), "films": ("film",), "both": ("series", "film")}[source]
        ranked = [kv for kv in ranked if kv[0][0] in keep]
    doc, notes = grid.empty(), []
    taken_series = 0
    for (kind, iid), s in ranked:
        if kind != "series" or taken_series >= most_series:
            continue
        info = series_info(iid)
        if not info or not info.get("episodes"):
            continue
        t = best_time(s["hours"])
        for _ in range(12):  # the next free half hour, if that time is taken
            try:
                d2, sid, _ = grid.add(doc, 0, t, "series", {"id": info["id"], "name": info["name"]}, now, info["episodes"],
                                      start_mode={"mode": "unwatched", "unwatched_index": info.get("unwatched", 0)})
                d2, _ = grid.stripe(d2, sid, [0, 1, 2, 3, 4], 1, source == "tv", now)
                doc = d2
                break
            except grid.GridError:
                t += 30
                if t > EVENING[1]:
                    t = EVENING[0]
        else:
            continue
        taken_series += 1
        when = "every day" if source == "tv" else "weekdays"
        notes.append(f"{info['name']}: {when} at {grid.hm(t)}, " + (f"watched {round(s['score'], 1)} times lately, most often then"
                                                                    if s["score"] else "from your library"))
    films = [(iid, s) for (kind, iid), s in ranked if kind == "film"]
    for (day, minute), (iid, s) in zip(FILM_EVENINGS if source == "films" else FILM_TIMES, films):
        f = film_info(iid)
        if not f:
            continue
        try:
            doc, _, _ = grid.add(doc, day, minute, "film", f, now)
            notes.append(f"{f.get('title') or s['name']}: {grid.DAYS[day]} at {grid.hm(minute)}, " +
                         ("a film people watch" if s["score"] else "a film from your library"))
        except grid.GridError:
            continue
    if not doc["slots"]:
        notes.append({"history": "No watch history for this channel's series and films yet, so nothing to suggest. Try General watch history",
                      "everyone": "No watch history yet, so nothing to suggest. Try All TV, All films or TV and Films"}.get(
                          source, "Jellyfin's library has nothing of that kind to suggest"))
    doc["suggested"] = int(now)
    doc["note"] = notes[:12]
    return doc, notes


def library_pool(jf, source, most=60):
    """Series and films from the whole library, in a random order, for All TV, All films and TV and Films:
    [(kind, id, name)]. At most `most` of each, so it stays one small answer from Jellyfin."""
    out = []
    for kind, t in (("series", "Series"), ("film", "Movie")):
        if (kind == "series" and source == "films") or (kind == "film" and source == "tv"):
            continue
        got = jf("/Items?" + _q(IncludeItemTypes=t, Recursive="true", SortBy="Random", Limit=most)) or {}
        out += [(kind, i["Id"], i.get("Name") or "") for i in got.get("Items") or []]
    return out


# The script ----------------------------------------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description="Suggest a week of programmes from Jellyfin's watch history.")
    ap.add_argument("--url", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--from", dest="source", choices=list(SOURCES), default="everyone",
                    help="what to make it from: history and everyone use watch history; tv, films and both the whole library")
    a = ap.parse_args(argv)
    head = {"Authorization": f'MediaBrowser Token="{a.key}"', "Accept": "application/json"}

    def jf(path, body=None):
        req = urllib.request.Request(a.url.rstrip("/") + path, headers={**head, "Content-Type": "application/json"},
                                     data=json.dumps(body).encode() if body is not None else None, method="POST" if body is not None else "GET")
        with urllib.request.urlopen(req, timeout=30) as r:  # the address given on the command line  # nosec B310
            return json.loads(r.read() or b"null")

    import library
    plays = history(jf, lambda p, b: jf(p, b), a.days)
    now = time.time()

    def series_info(sid):
        eps = library.lineup(jf, [{"kind": "series", "id": sid}])
        return {"id": sid, "name": eps[0]["title"] if eps else "Series", "episodes": eps, "unwatched": 0} if eps else None

    def film_info(fid):
        got = library.lineup(jf, [{"kind": "film", "id": fid}])
        return got[0] if got else None

    doc, notes = propose(None, plays, now, series_info, film_info, source=a.source,
                         pool=library_pool(jf, a.source) if a.source in ("tv", "films", "both") else None)
    for s in grid.view(doc, grid.week_start(now))["slots"]:
        print(f"{grid.DAYS[s['day']]:9} {grid.hm(s['start'])}  {s['title']}  {s['detail']}")
    for n in notes:
        print("-", n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
