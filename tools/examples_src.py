"""The example plug-ins (owner, 12 November 2026: "build all the plug-in examples", from the list of plug-ins that can
be built now). Each is: what it does, its manifest, and app.py. tools/make_examples.py writes each folder."""

COMMON = {"manifest_version": 1, "author": "TheMightyTRexUK", "licence": "MIT",
          "support_url": "https://github.com/TheMightyTRex/starboard-plugins/issues", "starboard_api": ">=1.14 <2.0"}
# 1.1.0 (plug-in API 1.14, 15 November 2026): a logo, the card band's status and updated, and the update tools.
# 1.1.1 (16 November 2026, DASH-453): lighter at rest and faster to start; Library health a page at a time.
# 1.1.2 (17 November 2026, DASH-458): sbplugin sends Jellyfin's key in Authorization too, for Jellyfin 12.
# 1.1.3 (17 November 2026, design system audit): clearer words, chips with no numbers, and the logo's alt text is the
# plug-in's name. Not published until the owner's OK: the changed apps name the image's next tag until then.
# 1.1.4 (19 November 2026, DASH-482): sbplugin reaches Starboard's API through the socket in its run folder when
# Starboard gives one (STARBOARD_API_SOCKET, Starboard 0.23.0), so plug-ins on their own internal network can call it.
# The shared image pinned on 19 November 2026 (sha256:7e1f325875b0, built from 985c491) already has it.
VERSION = "1.1.4"
VERSION_113 = "1.1.3"
VERSION_112 = "1.1.2"
VERSION_111 = "1.1.1"
VERSION_110 = "1.1.0"


def image(pid):
    return f"ghcr.io/themightytrex/starboard-plugin-{pid}:{VERSION}"


# Plug-in API 1.14 (15 November 2026) ---------------------------------------------------------------------------
# Update steps for the examples that work in the background: sbplugin's /update/before holds new runs and waits for one
# that is running to finish, and /update/after lets them run again. The others finish what they do in a second.
_STEPS = {"before": {"path": "/update/before", "time_limit_seconds": 60}, "after": {"path": "/update/after", "time_limit_seconds": 10}}
UPDATE_STEPS = {pid: _STEPS for pid in ("line-speed", "most-watched", "library-health", "notifications", "watch-stats", "backups-watch", "ups-power")}
RELEASED = "2026-11-15"
RELEASED_111 = "2026-11-16"
RELEASED_112 = "2026-11-17"
RELEASED_113 = "2026-11-17"
RELEASED_114 = "2026-11-19"
SOCKET_114 = ["**Reaches Starboard on any network:** with Starboard 0.23.0 or later it calls Starboard through a socket in "
              "its own folder. So it works on its own closed network too. An older Starboard works as before."]
FIRST = "2026-11-12"
# A text-only patch (26 November 2026, DASH-593): each example whose words changed has its own next patch version and
# one "changes" entry, whatever the shared version is. The image and its pinned digest are not touched.
TEXT_PATCH = {"vpn-check", "line-speed", "watching-now", "most-watched", "library-health", "dns-blocking", "home-assistant",
              "download-summary", "disk-forecast", "notifications", "backups-watch", "watch-stats"}
TEXT_PATCH_DATE = "2026-11-26"
TEXT_PATCH_CHANGE = "Plainer wording in the text and help pages. How it works has not changed."


def changes_for(pid, m):
    """What is new in each version (plug-in API 1.10, shown before an update from API 1.14): 1.1.0 first, then the
    plug-in's own list, or its first version."""
    earlier = [c for c in m.get("changes") or [] if c.get("version") not in (VERSION, VERSION_113, VERSION_112, VERSION_111, VERSION_110)] or [
        {"version": "1.0.0", "date": FIRST, "added": [m["description"]]}]
    added = ["**A logo** in Settings, Plug-ins, in the Catalogue and on its dashboard cards.",
             "**Its cards say how things are:** a status and when they last changed, in the grey band at the top of each card."]
    if pid in UPDATE_STEPS:
        added.append("**Updates safely:** before an update it finishes what it is doing and starts nothing new.")
    if any(c.get("refresh_seconds") for c in m.get("cards") or []):
        added.append("**Kept up to date:** its card is asked every 30 seconds while the dashboard is open.")
    light = ["**Lighter at rest:** it wakes about once a minute while nothing asks it anything, not twice a second. It writes nothing to its folder when a run goes well.", "**Starts faster:** its image comes with Python's modules already compiled, so a start takes about a quarter of the processor time."]
    fixed = (["**Large libraries:** it asks Jellyfin a page of 500 titles at a time, so a large library no longer makes the check "
              "fail."] if pid == "library-health" else [])
    v111 = {"version": VERSION_111, "date": RELEASED_111, "changed": light, **({"fixed": fixed} if fixed else {})}
    v112 = {"version": VERSION_112, "date": RELEASED_112, **({"fixed": JELLYFIN_12} if pid in CALLS_JELLYFIN else {"changed": SHARED_ONLY})}
    v114 = {"version": VERSION, "date": RELEASED_114, "changed": SOCKET_114}
    newest = {"version": VERSION_113, "date": RELEASED_113, "changed": WORDS_113.get(pid, []) + [
        f"**Logo description:** a screen reader says \"{m['name']} logo\", the plug-in's name, "
        "instead of a description of the symbol."]}
    if m.get("_own_changes"):  # a plug-in made after the shared helper's versions has only its own history (Backups watch 0.1.0)
        return m["changes"]
    before = m.get("_before") or []
    own = [m["_newest"]] + (before if isinstance(before, list) else [before]) if m.get("_newest") else []  # a version of its own after the shared one (Notifications 1.3.0)
    return own + [v114, newest, v112, v111, {"version": VERSION_110, "date": RELEASED, "added": added,
             "changed": ["Needs Starboard with plug-in API 1.14 or later. A Starboard with an older plug-in API keeps version 1.0.0."]}] + earlier


# 1.1.2 (DASH-458): Jellyfin 12 with legacy authorisation off refuses the key in X-Emby-Token alone.
CALLS_JELLYFIN = {"watching-now", "most-watched", "library-health", "watch-stats"}
JELLYFIN_12 = ["**Jellyfin 12:** it sends Jellyfin's key the way Jellyfin 12 asks for it, so Jellyfin no longer refuses its "
               "requests where legacy authorisation is off. Older Jellyfin still works."]
SHARED_ONLY = ["**Shared helper:** the helper every example shares sends Jellyfin's key the way Jellyfin 12 asks for it. "
               "This plug-in does not ask Jellyfin anything, so it works as before."]

# 1.1.3 (design system audit, 17 November 2026): what changed in each example's words.
WORDS_113 = {
    "vpn-check": ["**Clearer words:** the hint and the card's example use addresses kept for examples. The hint says the card "
                  "says Problem, not what colour it turns."],
    "line-speed": ["**Clearer words:** **Test now** asks \"Download a test file now? It uses some of any data allowance.\" Before the "
                   "first test, the band says **Scheduled** and the card says when the next test is."],
    "watching-now": ["**Clearer words:** the band says **Watching**, and the card lists each person."],
    "library-health": ["**Clearer words:** the band says **To fix**, and the number card says how many."],
    "home-assistant": ["**Clearer words:** **Warn when any is** says the card gives a warning, not what colour it turns."],
    "outside-services": ["**Clearer words:** the band says **Not answering**, and the card names each one. Its description spells "
                         "out NAS."],
    "download-summary": ["**Clearer words:** its description says it counts the download queue in Starboard."],
    "disk-forecast": ["**Clearer words:** the band says **Filling fast**, and the card says when each disk fills."],
    "notifications": ["**Clearer words:** each channel's switch says what to enter before you activate it, the band says **Not "
                      "sent**, and a message about an event it does not know says \"Starboard has an alert. Open Starboard for the "
                      "details.\""],
    "watch-stats": ["**Clearer words:** **Read the figures again now** is now **Check now**, as on the other plug-ins."],
}

EXAMPLES = {}

# 1. VPN check ------------------------------------------------------------------------------------------------------
EXAMPLES["vpn-check"] = ({
    "name": "VPN check", "description": "Shows the address and country your downloads use through the VPN, and warns if it is your home address.",
    "permissions": ["network:vpn"],
    "containers": [{"name": "main", "image": image("vpn-check"), "port": 7791, "network": "vpn", "volumes": ["data"],
                    "env": {"PORT": "7791"}}],
    "resources": {"main": {"memory": 48, "cpus": 0.1}}, "health": "/health",
    "settings": [{"key": "home_address", "label": "Your home's public address", "type": "text",
                  "hint": "Optional, such as 203.0.113.7. If the VPN ever shows this address, the card says Problem."},
                 {"key": "minutes", "label": "Check every", "type": "number", "unit": "minutes", "default": 15, "min": 5, "max": 240}],
    "actions": [{"id": "check", "label": "Check now", "path": "/check"}],
    "cards": [{"id": "status", "title": "VPN", "type": "status", "path": "/card", "example": {"state": "ok", "text": "198.51.100.23 in the Netherlands", "status": "protected", "updated": 1794694110}}],
}, '''import os
import time
from sbplugin import band, every, fetch, keep, last_error, remember, serve, setting


def check():
    started = time.monotonic()
    ip = fetch("https://ipinfo.io/json", timeout=10)
    keep("last", {"ip": ip.get("ip", ""), "country": ip.get("country", ""), "city": ip.get("city", ""),
                  "ms": round((time.monotonic() - started) * 1000), "at": time.time()})
    return {"said": f"Through the VPN: {ip.get('ip')} in {ip.get('city') or ip.get('country')}"}


def card():
    last = remember("last") or {}
    if not last:
        err = last_error()
        return band({"state": "warning", "text": err or "Not checked yet"}, "problem" if err else "waiting", label=None if err else "Checking soon")
    home = str(setting("home_address", "")).strip()
    if home and last["ip"] == home:
        return band({"state": "problem", "text": f"The VPN shows your home address, {home}. Downloads are not hidden."},
                    "problem", last["at"], "Home address showing")
    if time.time() - last["at"] > 3 * 60 * float(setting("minutes", 15)):
        return band({"state": "warning", "text": f"No answer through the VPN since {time.strftime('%H:%M', time.localtime(last['at']))}. {last_error()}"},
                    "warning", last["at"], "No answer")
    return band({"state": "ok", "text": f"{last['ip']} in {', '.join(x for x in (last['city'], last['country']) if x)}, {last['ms']} ms"},
                "protected", last["at"])


every(60 * float(setting("minutes", 15)), check)
serve({"/card": card, ("POST", "/check"): check}, port=int(os.environ.get("PORT", 7791)))
''')

# 2. Line speed -----------------------------------------------------------------------------------------------------
EXAMPLES["line-speed"] = ({
    "name": "Line speed", "description": "Tests your internet download speed once a night, outside download hours, and keeps a week of results.",
    "permissions": ["network:lan"],
    "containers": [{"name": "main", "image": image("line-speed"), "port": 8080, "network": "lan", "volumes": ["data"]}],
    "resources": {"main": {"memory": 64, "cpus": 0.25}}, "health": "/health",
    "settings": [{"key": "hour", "label": "Test at", "type": "number", "unit": "o'clock", "default": 4, "min": 0, "max": 23,
                  "hint": "Choose an hour when nothing is downloading."},
                 {"key": "megabytes", "label": "Test size", "type": "number", "unit": "MB", "default": 25, "min": 5, "max": 200,
                  "hint": "Larger is more accurate on fast lines, and uses more of any data allowance."}],
    "actions": [{"id": "test", "label": "Test now", "path": "/test", "confirm": "Download a test file now? It uses some of any data allowance."}],
    "cards": [{"id": "speed", "title": "Line speed", "type": "stat", "path": "/card", "format": "number", "example": {"value": 72, "label": "Mbps", "note": "04:00 today", "status": "ok", "updated": 1794694110}},
              {"id": "week", "title": "Line speed this week", "type": "list", "path": "/week", "example": {"items": [{"title": "72 Mbps", "detail": "Wednesday 04:00"}], "status": "ok", "updated": 1794694110}}],
}, '''import time
from sbplugin import band, every, fetch, keep, last_error, remember, serve, setting


def test():
    size = int(setting("megabytes", 25)) * 1_000_000
    started = time.monotonic()
    got = len(fetch(f"https://speed.cloudflare.com/__down?bytes={size}", timeout=120, raw=True, limit=size + 1))
    mbps = round(got * 8 / (time.monotonic() - started) / 1_000_000, 1)
    runs = (remember("runs", []) + [{"at": time.time(), "mbps": mbps}])[-14:]
    keep("runs", runs)
    return {"said": f"{mbps} Mbps"}


def nightly():
    runs = remember("runs", [])
    today = time.strftime("%Y-%m-%d")
    if time.localtime().tm_hour == int(setting("hour", 4)) and not any(time.strftime("%Y-%m-%d", time.localtime(r["at"])) == today for r in runs):
        test()


def next_test():
    return f"Next test at {int(setting('hour', 4)):02d}:00"


def card():
    runs = remember("runs", [])
    if not runs:
        err = last_error()
        return band({"value": 0, "label": "Mbps", "note": err or f"Not tested yet. {next_test()}"}, "problem" if err else "scheduled")
    r = runs[-1]
    return band({"value": r["mbps"], "label": "Mbps", "note": time.strftime("%a %H:%M", time.localtime(r["at"]))}, "ok", r["at"])


def week():
    runs = remember("runs", [])
    items = [{"title": f"{r['mbps']} Mbps", "detail": time.strftime("%A %d %b, %H:%M", time.localtime(r["at"]))} for r in reversed(runs[-7:])]
    if not items:
        return band({"items": [{"title": "Not tested yet", "detail": next_test()}]}, "scheduled")
    return band({"items": items}, "ok", runs[-1]["at"])


every(600, nightly)
serve({"/card": card, "/week": week, ("POST", "/test"): test})
''')

# 3. Watching now ---------------------------------------------------------------------------------------------------
EXAMPLES["watching-now"] = ({
    "name": "Watching now", "description": "Who is watching what in Jellyfin right now, with how far through they are.",
    "permissions": ["jellyfin:key", "network:lan"],
    "containers": [{"name": "main", "image": image("watching-now"), "port": 8080, "network": "lan"}],
    "resources": {"main": {"memory": 48, "cpus": 0.1}}, "health": "/health",
    "cards": [{"id": "now", "title": "Watching now", "type": "list", "path": "/card", "refresh_seconds": 30,
               "example": {"items": [{"title": "Dune: Part Two", "detail": "Sam, living room TV, 40%"}], "status": "running", "status_label": "Watching", "updated": 1794694110}}],
}, '''import time
from sbplugin import band, jellyfin, serve


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
    if not rows:
        return band({"items": [{"title": "Nobody is watching", "detail": "Jellyfin is quiet"}]}, "idle", time.time(), "Nobody watching")
    return band({"items": rows}, "running", time.time(), "Watching")


serve({"/card": card})
''')

# 4. Most watched ---------------------------------------------------------------------------------------------------
EXAMPLES["most-watched"] = ({
    "name": "Most watched", "description": "The films and series most people watched in Jellyfin in the last week.",
    "permissions": ["jellyfin:key", "network:lan"],
    "containers": [{"name": "main", "image": image("most-watched"), "port": 8080, "network": "lan", "volumes": ["data"]}],
    "resources": {"main": {"memory": 64, "cpus": 0.1}}, "health": "/health",
    "settings": [{"key": "days", "label": "Over the last", "type": "number", "unit": "days", "default": 7, "min": 1, "max": 90}],
    "cards": [{"id": "top", "title": "Most watched", "type": "list", "path": "/card", "example": {"items": [{"title": "Slow Horses", "detail": "3 people, 11 plays"}], "status": "ok", "updated": 1794694110}}],
}, '''import time
from collections import defaultdict
from sbplugin import band, changed, every, jellyfin, keep, last_error, plural, remember, serve, setting


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
        err = last_error()
        return band({"items": [{"title": "Nothing watched yet", "detail": err or f"in the last {setting('days', 7)} days"}]},
                    "problem" if err else "idle", changed("top"))
    return band({"items": [{"title": t["title"], "detail": f"{t['people']} {'person' if t['people'] == 1 else 'people'}, {plural(t['plays'], 'play')}"} for t in top]},
                "ok", changed("top"))


every(3600, count)
serve({"/card": card})
''')

# 5. Library health -------------------------------------------------------------------------------------------------
EXAMPLES["library-health"] = ({
    "name": "Library health", "description": "Films and series in Jellyfin with no poster, no description or no year, so you can fix them.",
    "permissions": ["jellyfin:key", "network:lan"],
    "containers": [{"name": "main", "image": image("library-health"), "port": 8080, "network": "lan", "volumes": ["data"]}],
    "resources": {"main": {"memory": 96, "cpus": 0.25}}, "health": "/health",
    "actions": [{"id": "check", "label": "Check now", "path": "/check"}],
    "cards": [{"id": "count", "title": "Library health", "type": "stat", "path": "/count", "format": "number", "example": {"value": 4, "label": "to fix", "note": "of 1,240 titles", "status": "warning", "status_label": "4 titles to fix", "updated": 1794694110}},
              {"id": "list", "title": "To fix in Jellyfin", "type": "list", "path": "/card", "example": {"items": [{"title": "Brazil (1985)", "detail": "No poster"}], "status": "warning", "status_label": "4 titles to fix", "updated": 1794694110}}],
}, '''from sbplugin import band, changed, every, jellyfin, keep, last_error, plural, remember, serve


PAGE = 500  # titles in each answer from Jellyfin: a large library never arrives, or is held, all at once


def titles():
    """Every film and series, a page at a time."""
    start = 0
    while True:
        got = jellyfin("/Items?Recursive=true&IncludeItemTypes=Movie,Series&Fields=Overview,ProductionYear&EnableImageTypes=Primary"
                       f"&EnableUserData=false&StartIndex={start}&Limit={PAGE}") or {}
        items = got.get("Items") or []
        yield from items
        start += len(items)
        if len(items) < PAGE or start >= int(got.get("TotalRecordCount") or start + 1):
            return


def check():
    total, bad = 0, []
    for it in titles():
        total += 1
        why = [w for w, missing in (("no poster", "Primary" not in (it.get("ImageTags") or {})),
                                    ("no description", not it.get("Overview")), ("no year", not it.get("ProductionYear"))) if missing]
        if why:
            bad.append({"title": f"{it.get('Name')}" + (f" ({it['ProductionYear']})" if it.get("ProductionYear") else ""),
                        "detail": ", ".join(why).capitalize()})
    keep("result", {"bad": bad, "total": total})
    return {"said": f"{plural(len(bad), 'title')} to fix of {total:,}"}


def state():
    r = remember("result") or {}
    if not r:
        return ("problem", None) if last_error() else ("waiting", "Checking soon")
    n = len(r.get("bad", []))
    return ("warning", "To fix") if n else ("ok", "Nothing to fix")


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
''')

# 6. Pi-hole or AdGuard Home ----------------------------------------------------------------------------------------
EXAMPLES["dns-blocking"] = ({
    "name": "Ad blocking", "description": "How many adverts and trackers Pi-hole or AdGuard Home blocked today.",
    "permissions": ["network:lan"],
    "containers": [{"name": "main", "image": image("dns-blocking"), "port": 8080, "network": "lan"}],
    "resources": {"main": {"memory": 48, "cpus": 0.1}}, "health": "/health",
    "settings": [{"key": "kind", "label": "Which one", "type": "choice", "choices": ["Pi-hole", "AdGuard Home"], "default": "Pi-hole"},
                 {"key": "address", "label": "Its address", "type": "address", "hint": "Such as http://192.0.2.2 for Pi-hole, or http://192.0.2.2:3000 for AdGuard Home."},
                 {"key": "username", "label": "User name", "type": "text", "hint": "AdGuard Home only."},
                 {"key": "password", "label": "Password", "type": "secret", "hint": "Pi-hole's web password, or AdGuard Home's. Kept by Starboard."}],
    "cards": [{"id": "blocked", "title": "Blocked today", "type": "stat", "path": "/card", "format": "number", "example": {"value": 4210, "label": "blocked", "note": "12% of 35,000 lookups", "status": "protected", "updated": 1794694110}}],
}, '''import base64
import time
from sbplugin import band, fetch, serve, setting


def card():
    base = str(setting("address", "")).rstrip("/")
    if not base:
        return band({"value": 0, "label": "blocked", "note": "Add the address in the plug-in's settings"}, "needs_setup")
    if setting("kind", "Pi-hole") == "AdGuard Home":
        auth = base64.b64encode(f"{setting('username', '')}:{setting('password', '')}".encode()).decode()
        s = fetch(f"{base}/control/stats", {"Authorization": f"Basic {auth}"})
        blocked, total = int(s.get("num_blocked_filtering") or 0), int(s.get("num_dns_queries") or 0)
    else:  # Pi-hole 6: a session for this one question, then signed out
        sid = (fetch(f"{base}/api/auth", data={"password": setting("password", "")}).get("session") or {}).get("sid")
        try:
            q = (fetch(f"{base}/api/stats/summary", {"X-FTL-SID": sid or ""}).get("queries") or {})
        finally:
            if sid:
                fetch(f"{base}/api/auth", {"X-FTL-SID": sid}, method="DELETE", raw=True)
        blocked, total = int(q.get("blocked") or 0), int(q.get("total") or 0)
    share = f"{round(100 * blocked / total)}% of {total:,} lookups" if total else "no lookups yet"
    return band({"value": blocked, "label": "blocked", "note": share}, "protected", time.time())


serve({"/card": card})
''')

# 7. Home Assistant -------------------------------------------------------------------------------------------------
EXAMPLES["home-assistant"] = ({
    "name": "Home Assistant", "description": "Your house in one sentence on the dashboard: the things you choose from Home Assistant.",
    "permissions": ["network:lan"],
    "containers": [{"name": "main", "image": image("home-assistant"), "port": 8080, "network": "lan"}],
    "resources": {"main": {"memory": 48, "cpus": 0.1}}, "health": "/health",
    "settings": [{"key": "address", "label": "Home Assistant's address", "type": "address", "hint": "Such as http://192.0.2.30:8123"},
                 {"key": "token", "label": "Long-lived access token", "type": "secret",
                  "hint": "In Home Assistant: your profile, Security, Long-lived access tokens, Create token. Kept by Starboard."},
                 {"key": "entities", "label": "What to show", "type": "list",
                  "hint": "One entity id each, such as binary_sensor.front_door or sensor.lounge_temperature."},
                 {"key": "alert_on", "label": "Warn when any is", "type": "text", "default": "on, open, unlocked",
                  "hint": "States that give the card a warning, separated by commas."}],
    "cards": [{"id": "house", "title": "Home", "type": "status", "path": "/card", "example": {"state": "ok", "text": "Front door: closed. Lounge: 20.5 °C", "status": "ok", "updated": 1794694110}}],
}, '''import time
from sbplugin import band, fetch, serve, setting


def card():
    base, token = str(setting("address", "")).rstrip("/"), setting("token", "")
    ids = setting("entities", []) or []
    if not base or not token or not ids:
        return band({"state": "warning", "text": "Add the address, a token and what to show in the plug-in's settings"}, "needs_setup")
    alert = {s.strip().lower() for s in str(setting("alert_on", "on, open, unlocked")).split(",") if s.strip()}
    parts, warn = [], False
    for eid in ids[:8]:
        s = fetch(f"{base}/api/states/{eid}", {"Authorization": f"Bearer {token}"})
        name = (s.get("attributes") or {}).get("friendly_name") or eid
        unit = (s.get("attributes") or {}).get("unit_of_measurement") or ""
        state = s.get("state", "")
        warn |= state.lower() in alert
        parts.append(f"{name}: {state}{' ' + unit if unit else ''}")
    return band({"state": "warning" if warn else "ok", "text": ". ".join(parts)}, "warning" if warn else "ok", time.time())


serve({"/card": card})
''')

# 8. Outside services: hand-made since 2.0.0 (Uptime and status, 20 November 2026), in its own folder with its own image.
# 9. Download summary -----------------------------------------------------------------------------------------------
EXAMPLES["download-summary"] = ({
    "name": "Download summary", "description": "How much has downloaded today and this week, from the download queue in Starboard.",
    "permissions": ["downloads:read"],
    "containers": [{"name": "main", "image": image("download-summary"), "port": 8080, "volumes": ["data"]}],
    "resources": {"main": {"memory": 48, "cpus": 0.1}}, "health": "/health",
    "cards": [{"id": "today", "title": "Downloaded today", "type": "stat", "path": "/card", "format": "bytes", "example": {"value": 12884901888, "label": "today", "note": "41 GB this week", "status": "ok", "updated": 1794694110}}],
}, '''import time
from sbplugin import band, changed, every, keep, last_error, remember, serve, starboard


def sample():
    seen = remember("seen", {})
    days = remember("days", {})
    today = time.strftime("%Y-%m-%d")
    now = {}
    for it in (starboard("downloads") or {}).get("items") or []:
        key = f"{it.get('client', '')}:{it.get('id', it.get('name', ''))}"
        size = float(it.get("size") or 0)
        done = size * float(it.get("progress") or 0) / (100 if float(it.get("progress") or 0) > 1 else 1)
        now[key] = done
        days[today] = days.get(today, 0) + max(0.0, done - seen.get(key, done))
    keep("seen", now)
    keep("days", dict(sorted(days.items())[-14:]))


def card():
    days = remember("days", {})
    week = sum(v for k, v in days.items() if k >= time.strftime("%Y-%m-%d", time.localtime(time.time() - 6 * 86400)))
    err = last_error()
    return band({"value": int(days.get(time.strftime("%Y-%m-%d"), 0)), "label": "today", "note": err or f"{week / 1e9:.1f} GB this week"},
                "problem" if err else "ok", changed("days"))


every(60, sample)
serve({"/card": card})
''')

# 10. Disk forecast -------------------------------------------------------------------------------------------------
EXAMPLES["disk-forecast"] = ({
    "name": "Disk forecast", "description": "When each disk fills at the rate it has been filling over the last month.",
    "permissions": ["system:read"],
    "containers": [{"name": "main", "image": image("disk-forecast"), "port": 8080, "volumes": ["data"]}],
    "resources": {"main": {"memory": 48, "cpus": 0.1}}, "health": "/health",
    "cards": [{"id": "forecast", "title": "Disk forecast", "type": "status", "path": "/card", "example": {"state": "ok", "text": "Pool full in about 140 days", "status": "ok", "updated": 1794694110}}],
}, '''import time
from sbplugin import band, changed, every, keep, last_error, remember, serve, starboard


def sample():
    hist = remember("history", {})
    day = time.strftime("%Y-%m-%d")
    for d in (starboard("system") or {}).get("disks") or []:
        name = d.get("label") or d.get("mount") or d.get("name")
        if name and d.get("total"):
            hist.setdefault(name, {})[day] = [float(d.get("used") or 0), float(d["total"])]
    keep("history", {k: dict(sorted(v.items())[-35:]) for k, v in hist.items()})


def card():
    hist = remember("history", {})
    if not hist:
        err = last_error()
        return band({"state": "warning", "text": err or "Measuring: a forecast after two days"}, "problem" if err else "waiting",
                    label=None if err else "Measuring")
    worst, parts = None, []
    for name, days in hist.items():
        rows = sorted(days.items())
        (d0, (u0, _)), (d1, (u1, total)) = rows[0], rows[-1]
        span = (time.mktime(time.strptime(d1, "%Y-%m-%d")) - time.mktime(time.strptime(d0, "%Y-%m-%d"))) / 86400
        rate = (u1 - u0) / span if span >= 1 else 0
        if rate <= 0:
            parts.append(f"{name}: {round(100 * u1 / total)}% full, not growing")
            continue
        left = (total - u1) / rate
        worst = left if worst is None else min(worst, left)
        parts.append(f"{name}: full in about {round(left):,} days")
    state = "problem" if worst is not None and worst < 14 else "warning" if worst is not None and worst < 60 else "ok"
    label = "Filling fast" if worst is not None and worst < 60 else None  # the days are in the text
    return band({"state": state, "text": ". ".join(parts)}, state, changed("history"), label)


every(3600, sample)
serve({"/card": card})
''')

# The recommended plug-ins (owner, 13 November 2026: "Start working on all the recommended plugins", from
# STACK-COMPARISON-2026-11-13.md). Each keeps its own version, its changes and its app.py in its own folder ("file"),
# and runs from the shared image. A plug-in new to the image goes in NEW_IN_IMAGE and names its next tag
# (IMAGE_VERSION) until GitHub builds it and its digest is pinned in tools/examples-digest.txt; 1.1.0 was built and
# pinned on 14 November 2026 with Notifications and Watch statistics.
# 1.2.0 (15 November 2026, plug-in API 1.14): every example's card answers the band's status and updated, and sbplugin
# answers the update steps, so every plug-in in the image names this tag until it is built and pinned again.
# 1.2.1 (16 November 2026, DASH-453): every example in the image names this tag until it is built and pinned.
# 1.2.2 (17 November 2026, DASH-458): sbplugin's Jellyfin key fix, so every example names this tag until it is built
# and pinned again.
# 1.2.3 (17 November 2026, design system audit): the examples whose app.py changed name this tag until it is built and
# pinned; the others run unchanged code, so they keep the pinned 1.2.2 image. Audio description names it in its own
# manifest.
IMAGE_VERSION = "1.2.10"  # 1.2.10 (27 November 2026, DASH-578): Immich has a job queues page. 1.2.9 (27 November 2026, DASH-572): UPS and power holds Starboard's heavy jobs on battery. 1.2.8 (27 November 2026, DASH-589): Single sign-on is in the Dockerfile and names this tag until it is built and pinned. 1.2.7 (26 November 2026, DASH-517, DASH-518): UPS and power and Immich are in the Dockerfile; their manifests name this tag until it is built and pinned
# 1.2.3 built and pinned on 17 November 2026 (sha256:c4e1d651a52c...): every example runs from the pinned image again.
# Built again under the same tag for Audio description 1.3.0 (pull request 9) and pinned on 17 November 2026
# (sha256:26c490dec620...).
# 1.2.4 (22 November 2026, DASH-514): Notifications 1.3.0's app.py is not in the pinned image, so its manifest names this
# tag, and the catalogue lists it as coming soon, until GitHub builds it and its digest is pinned in tools/examples-digest.txt.
NEW_IN_IMAGE = {"single-sign-on", "ups-power", "immich"}  # ups-power: 0.2.0 holds Starboard's heavy jobs on battery (DASH-572)
# 1.2.7 was built from 152366e (UPS and power 0.1.0 and Immich 0.1.0 app.py included) and pinned on 26 November 2026
# (sha256:d31add45f768...), checked by listing /app in the pinned image, so both run from it and are published.
# 1.2.6 was built from 0a0be8a (Notifications 1.4.0 and Backups watch 0.1.0's app.py included) and pinned on 25 November 2026
# (sha256:0f5dc5966760...), so both run from the pinned image like the others and are published.
# 1.2.5 (25 November 2026, DASH-522): Notifications 1.4.0's app.py is not in the pinned image, so its manifest names this tag
# until GitHub builds it and its digest is pinned in tools/examples-digest.txt.
# 1.2.6 (25 November 2026): the Dockerfile had no COPY for Backups watch, so the 1.2.5 image (sha256:866e3a790459...) has no
# /app/backups-watch/app.py and Backups watch would not start. 1.2.6 adds it; Notifications 1.4.0 (in 1.2.5) and Backups watch
# name this tag until it is built and pinned.
# 1.2.4 was built from 0b10e00 (Notifications 1.3.0 and Backups watch 0.1.0 included) and pinned on 22 November 2026
# (sha256:c99b4b167a4e...), so Notifications and Backups watch run from the pinned image like the others and are published.


def _switch(key, label, hint, group, default=True):
    return {"key": key, "label": label, "type": "switch", "default": default, "hint": hint, "group": group}


# 11. Notifications (DASH-401) -------------------------------------------------------------------------------------
EXAMPLES["notifications"] = ({
    "name": "Notifications", "version": "1.4.0",
    "description": "Sends Starboard's events to email, Telegram, Discord, Signal, Pushover, ntfy or a webhook, in plain words, and a weekly New this week.",
    "starboard_api": ">=1.16 <2.0",
    # 1.2.0 (owner, 19 November 2026, Starboard issue #187): a message whenever a disk is erased, added to the pool or
    # taken out of it, from Starboard's disk.changed event (plug-in API 1.16).
    "_newest": {"version": "1.4.0", "date": "2026-11-25", "added": [
        "**Quiet hours:** choose the hours when it should not wake you. Alerts that are not urgent wait, and one summary goes when the hours end. "
        "An app that stops answering, a full disk and a disk change still go at once. Deactivated until you activate it."]},
    "_before": [{"version": "1.3.0", "date": "2026-11-22", "added": [
        "**New this week, by email:** a weekly email of what was added to Jellyfin: films, episodes, albums and books. It has titles and years only, and no pictures. You choose the day and the hour, and it can go by email alone or by every "
        "way you activated."],
        "changed": [
        "**Deactivated at first:** New this week is now deactivated until you activate it under What to send. "
        "Send New this week on is replaced by **When to send New this week**, one setting for the day and the hour."]},
        {"version": "1.2.0", "date": "2026-11-19", "added": [
        "**Disk changes:** a message whenever a disk is erased, added to the pool or taken out of it, however it was asked "
        "for, so an erase you did not start reaches you at once. Needs Starboard with plug-in API 1.16 or later; an older "
        "Starboard keeps 1.1.3."]}],
    "permissions": ["apps:read", "downloads:read", "media:read", "system:read", "network:lan"],
    "containers": [{"name": "main", "image": "", "port": 8080, "network": "lan", "volumes": ["data"], "start": "when_needed",
                    "idle_stop_minutes": 5}],
    "resources": {"main": {"memory": 48, "cpus": 0.1}}, "health": "/health",
    "settings": [
        _switch("send_requests", "Something someone asked for is ready", "Reelix's or Seerr's requests that become ready to watch.", "What to send"),
        _switch("tell_requester", "Tell the person who asked too", "By the email address or Telegram chat given for them under People.", "What to send"),
        _switch("send_failed", "A download failed", "A download that stops with a problem.", "What to send"),
        _switch("send_apps", "An app stops answering, and when it is back", "After two checks in a row with no answer.", "What to send"),
        _switch("send_disk", "A disk is nearly full", "At the limit set for alerts in Settings, Alerts, or 90%.", "What to send"),
        _switch("send_disk_changes", "A disk is erased, added or taken out", "Every change Starboard's disk pool helper makes, however it was asked for.", "What to send"),
        _switch("send_updates", "An update is ready", "For Starboard, your apps and your plug-ins.", "What to send"),
        _switch("send_weekly", "New this week", "A weekly email of what was added to Jellyfin: films, episodes, albums and books, with titles and years only. Deactivated until you activate it.", "What to send", False),
        {"key": "weekly_when", "label": "When to send New this week", "type": "schedule", "default": {"every": "week", "day": "monday", "time": "09:00"},
         "group": "What to send", "hint": "The day and the hour. It lists what arrived in the last 7 days."},
        {"key": "weekly_by", "label": "Send New this week by", "type": "choice", "default": "email", "group": "What to send",
         "hint": "Email uses the settings in Email. The other choice uses every way you activated.",
         "choices": [{"value": "email", "label": "Email only"}, {"value": "all", "label": "Every way I activated"}]},
        {"key": "starboard_address", "label": "Starboard's address, for links", "type": "address", "group": "What to send",
         "hint": "Optional, such as http://192.0.2.10:8095. Messages end with Open Starboard and this address."},
        _switch("quiet_on", "Hold alerts that are not urgent in quiet hours", "A request ready, a failed download, an app back or an update ready wait. One summary goes when the quiet hours end. Deactivated until you activate it.", "Quiet hours", False),
        {"key": "quiet_from", "label": "Quiet hours start at", "type": "schedule", "default": {"every": "day", "time": "22:00"},
         "group": "Quiet hours", "hint": "Choose every day. Only the hour counts."},
        {"key": "quiet_until", "label": "Quiet hours end at", "type": "schedule", "default": {"every": "day", "time": "07:00"},
         "group": "Quiet hours", "hint": "Choose every day. The summary is sent at this hour."},
        _switch("quiet_urgent", "Still send urgent ones", "An app that stops answering, a disk nearly full, and a disk erased, added or taken out go at once. Deactivate it to hold them too.", "Quiet hours"),
        _switch("email_active", "Send by email", "Activate once the email details are entered and the test arrives.", "Email", False),
        {"key": "smtp_host", "label": "Email server", "type": "text", "group": "Email", "hint": "Such as smtp.example.com"},
        {"key": "smtp_port", "label": "Port", "type": "number", "default": 587, "min": 1, "max": 65535, "group": "Email"},
        {"key": "smtp_security", "label": "Security", "type": "choice", "default": "starttls", "group": "Email",
         "hint": "How the connection to your email server is protected. Your email service says which to use.",
         "choices": [{"value": "starttls", "label": "STARTTLS (usually port 587)"}, {"value": "ssl", "label": "SSL (usually port 465)"},
                     {"value": "none", "label": "None (only on your own network)"}]},
        {"key": "smtp_user", "label": "User name", "type": "text", "group": "Email"},
        {"key": "smtp_password", "label": "Password", "type": "secret", "group": "Email", "hint": "An app password where your email service offers one."},
        {"key": "email_from", "label": "Send from", "type": "text", "group": "Email", "hint": "Such as starboard@example.com"},
        {"key": "email_to", "label": "Send email to", "type": "list", "group": "Email", "hint": "One address a line."},
        _switch("telegram_active", "Send by Telegram", "Activate once the bot token and chat are entered and the test arrives.", "Telegram", False),
        {"key": "telegram_token", "label": "Bot token", "type": "secret", "group": "Telegram", "hint": "From @BotFather in Telegram."},
        {"key": "telegram_chat", "label": "Telegram chat", "type": "list", "group": "Telegram",
         "hint": "One chat id a line. Send your bot a message first, so it may write to you."},
        _switch("discord_active", "Send by Discord", "Activate once the webhook is filled in and the test arrives.", "Discord", False),
        {"key": "discord_webhook", "label": "Discord webhook address", "type": "secret", "group": "Discord",
         "hint": "In Discord: the channel's Edit channel, Integrations, Webhooks, Copy webhook URL."},
        _switch("signal_active", "Send by Signal", "Only if you run signal-cli-rest-api, which sends for a number you registered with it.", "Signal", False),
        {"key": "signal_api", "label": "signal-cli-rest-api address", "type": "address", "group": "Signal", "hint": "Such as http://192.0.2.10:8080"},
        {"key": "signal_number", "label": "Send from number", "type": "text", "group": "Signal", "hint": "The number registered with it, such as +447700900123."},
        {"key": "signal_to", "label": "Send Signal messages to", "type": "list", "group": "Signal", "hint": "One number or group id a line."},
        _switch("pushover_active", "Send by Pushover", "Activate once both keys are entered and the test arrives.", "Pushover", False),
        {"key": "pushover_user", "label": "User key", "type": "secret", "group": "Pushover"},
        {"key": "pushover_token", "label": "Application token", "type": "secret", "group": "Pushover", "hint": "Make an application for Starboard on pushover.net."},
        _switch("ntfy_active", "Send by ntfy", "Activate once the topic is filled in and the test arrives.", "ntfy", False),
        {"key": "ntfy_url", "label": "ntfy server", "type": "address", "default": "https://ntfy.sh", "group": "ntfy"},
        {"key": "ntfy_topic", "label": "Topic", "type": "text", "group": "ntfy", "hint": "On ntfy.sh anyone who knows the topic can read it, so make it hard to guess."},
        {"key": "ntfy_token", "label": "Access token", "type": "secret", "group": "ntfy", "hint": "Optional, for a server or topic that needs one."},
        _switch("webhook_active", "Send to webhooks", "Activate once an address is filled in and the test arrives.", "Webhooks", False),
        {"key": "webhooks", "label": "Webhook addresses", "type": "secret", "group": "Webhooks",
         "hint": "One or more, separated by spaces. Each gets title, body and type as JSON, as the Apprise API's notify address takes them."},
        {"key": "people", "label": "People", "type": "list", "group": "People",
         "hint": "One person a line: the name they use in Reelix or Seerr, a comma, then their email address, or \"telegram\" and their chat id."},
    ],
    "actions": [{"id": "test-email", "label": "Send a test email", "path": "/test/email"},
                {"id": "test-telegram", "label": "Send a test to Telegram", "path": "/test/telegram"},
                {"id": "test-discord", "label": "Send a test to Discord", "path": "/test/discord"},
                {"id": "test-signal", "label": "Send a test by Signal", "path": "/test/signal"},
                {"id": "test-pushover", "label": "Send a test by Pushover", "path": "/test/pushover"},
                {"id": "test-ntfy", "label": "Send a test by ntfy", "path": "/test/ntfy"},
                {"id": "test-webhook", "label": "Send a test to the webhooks", "path": "/test/webhook"},
                {"id": "weekly-now", "label": "Send New this week now", "path": "/weekly-now"},
                {"id": "held-now", "label": "Send what quiet hours held now", "path": "/held-now"}],
    "cards": [{"id": "status", "title": "Notifications", "type": "status", "path": "/card", "refresh_minutes": 60,
               "example": {"state": "ok", "text": "Mon 09:00, New this week: sent by Email, Telegram", "status": "ok", "updated": 1794694110}},
              {"id": "recent", "title": "Notifications sent", "type": "list", "path": "/recent", "refresh_minutes": 60,
               "example": {"items": [{"title": "Ready to watch: Dune (2021)", "detail": "Mon 12 Nov 20:15, sent by Email, Telegram"}], "status": "ok", "updated": 1794694110}}],
    "events": ["request.available", "download.failed", "app.down", "app.up", "disk.nearly_full", "disk.changed", "update.available", "item.added"],
    "jobs": [{"id": "weekly", "label": "Send New this week", "path": "/jobs/weekly", "schedule": "weekly_when", "time_limit_minutes": 2},
             {"id": "quiet-end", "label": "Send what quiet hours held", "path": "/jobs/quiet-end", "schedule": "quiet_until", "time_limit_minutes": 2}],
    "changes": [{"version": "1.0.0", "date": "2026-11-13", "added": [
        "**Seven ways to send:** email, Telegram, Discord, Signal (through signal-cli-rest-api), Pushover, ntfy and Apprise-style webhooks, each with a Test button.",
        "**What it sends:** a request ready to watch (to the person who asked too), a failed download, an app down and back, a disk nearly full, an update ready, and New this week.",
        "Plain words with no meaning in symbols, and links with words before them.",
        "Rests between messages: Starboard's events and its daily job wake it, so it uses no memory while idle."]}],
    "_readme": """## How it stays light

It has no timer of its own. Starboard sends it each event and runs its daily job, and it rests (stops) 5 minutes after
the last one. A message takes about a second and 14 MB of memory while it runs.

## Secrets

Passwords, tokens, keys and the webhook addresses are secret settings. Starboard never shows them again, and the
plug-in never writes them to its log, its card or its folder. A failed message says only which channel failed and why,
in words such as "it refused the sign-in or token".

## Per person

Under **People**, give one line for each person who asks for things. Write the name they use in Reelix or Seerr, a comma,
then their email address, or `telegram` and their chat id. When their request is ready, they hear too.

## Signal

Signal has no official way for a server to send messages. If you already run
[signal-cli-rest-api](https://github.com/bbernhard/signal-cli-rest-api) with a number registered, give its address
and that number. Otherwise leave Signal deactivated.
""",
}, "file")

# 13. Backups watch (DASH-513) --------------------------------------------------------------------------------------
EXAMPLES["backups-watch"] = ({
    "name": "Backups watch", "version": "0.1.0",
    "description": "The last run, size and failures of your Backrest or Kopia backups on a card, and an alert when one is overdue.",
    "starboard_api": ">=1.17 <2.0", "_own_changes": True,
    "permissions": ["network:lan", "alerts:send"],
    "containers": [{"name": "main", "image": "", "port": 8080, "network": "lan", "volumes": ["data"], "start": "when_needed",
                    "idle_stop_minutes": 5}],
    "resources": {"main": {"memory": 48, "cpus": 0.1}}, "health": "/health",
    "settings": [
        {"key": "tool", "label": "Backup tool", "type": "choice", "default": "backrest", "group": "The backup tool",
         "hint": "Backrest or Kopia. Duplicati is not offered yet: its server API could not be checked from its documentation.",
         "choices": [{"value": "backrest", "label": "Backrest"}, {"value": "kopia", "label": "Kopia"}]},
        {"key": "address", "label": "Its address", "type": "address", "group": "The backup tool", "required": True,
         "hint": "Such as http://192.0.2.10:9898 for Backrest, or https://192.0.2.10:51515 for the Kopia server."},
        {"key": "user", "label": "User name", "type": "text", "group": "The backup tool",
         "hint": "Leave empty if the tool needs no sign-in. For Kopia, the server's user name."},
        {"key": "password", "label": "Password", "type": "secret", "group": "The backup tool",
         "hint": "The tool's password. Starboard never shows it again."},
        _switch("self_signed", "Accept a self-signed certificate", "For a Kopia server that makes its own certificate. Only on your own network.", "The backup tool", False),
        {"key": "overdue_hours", "label": "Overdue after", "type": "number", "unit": "hours", "default": 36, "min": 1, "max": 1440,
         "group": "Alerts", "hint": "How many hours without a good run count as overdue. 36 suits a nightly backup."},
        _switch("alerts", "Send alerts through Starboard", "Sends one alert when a backup is overdue or failed, and one when it is fine again, to where Starboard sends its own alerts.", "Alerts"),
    ],
    "actions": [{"id": "check", "label": "Check now", "path": "/check"}],
    "cards": [{"id": "status", "title": "Backups", "type": "status", "path": "/card", "refresh_minutes": 60,
               "example": {"state": "ok", "text": "All 3 backed up. Last run 6 hours ago.", "status": "ok", "updated": 1794694110}},
              {"id": "runs", "title": "Backup runs", "type": "list", "path": "/runs", "refresh_minutes": 60,
               "example": {"items": [{"title": "documents", "detail": "Last run 6 hours ago, 41.2 GB, 0 failed in 30 days"}], "status": "ok", "updated": 1794694110}},
              {"id": "sizes", "title": "Backup sizes", "type": "sparkline", "path": "/sizes", "refresh_minutes": 60,
               "example": {"series": [{"title": "documents", "points": [120, 90, 4, 60, None, 88], "unit": "bytes", "detail": "6 runs kept. Latest 88 bytes added."}],
                           "note": "Data added by each run the plug-in has kept. A gap is a failed run.", "status": "ok", "updated": 1794694110}}],
    "jobs": [{"id": "check", "label": "Check the backups", "path": "/jobs/check", "every_hours": 1, "time_limit_minutes": 2}],
    "changes": [{"version": "0.1.0", "date": "2026-11-22", "added": [
        "**One card for your backups:** the last run, the size and the failures of each Backrest plan or Kopia source.",
        "**Alerts:** once when a backup is overdue or its last run failed, and once when it is fine again, through Starboard.",
        "**You choose** the tool, its address and password, and how many hours count as overdue.",
        "**Light:** it wakes once an hour, asks the tool once and rests; its cards read what it kept."]}],
    "_readme": """## What it reads

- **Backrest:** its summary dashboard (`/v1.Backrest/GetSummaryDashboard`), one summary for each plan.
- **Kopia:** the server control API (`/api/v1/control/sources`), the last snapshot of each source.

Both are read only. Neither was tried against the real program when this version was written: read the help's
Problems page before relying on it.
""",
}, "file")

# 14. UPS and power (DASH-517) -------------------------------------------------------------------------------------
EXAMPLES["ups-power"] = ({
    "name": "UPS and power", "version": "0.2.0",
    "description": "Load, battery and time left of your UPS on a card, and an alert when the mains power is lost, read from NUT or PeaNUT.",
    "starboard_api": ">=1.24 <2.0", "_own_changes": True,
    "permissions": ["network:lan", "alerts:send", "power:hold"],
    "containers": [{"name": "main", "image": "", "port": 8080, "network": "lan", "volumes": ["data"]}],
    "resources": {"main": {"memory": 32, "cpus": 0.1}}, "health": "/health",
    "settings": [
        {"key": "tool", "label": "Read the UPS through", "type": "choice", "default": "nut", "group": "The UPS",
         "hint": "NUT is the Network UPS Tools server (upsd). PeaNUT is the web page that sits in front of NUT.",
         "choices": [{"value": "nut", "label": "NUT"}, {"value": "peanut", "label": "PeaNUT"}]},
        {"key": "host", "label": "NUT server", "type": "text", "group": "The UPS",
         "hint": "For NUT: its address, such as 192.0.2.10, or 192.0.2.10:3493 for another port. NUT must allow this computer to read (LISTEN and ACCESS in its upsd.conf)."},
        {"key": "peanut_address", "label": "PeaNUT's address", "type": "address", "group": "The UPS",
         "hint": "For PeaNUT: such as http://192.0.2.10:8080."},
        {"key": "ups", "label": "UPS name", "type": "text", "group": "The UPS",
         "hint": "Leave empty to use the first UPS the server lists. Otherwise the name in ups.conf, such as ups."},
        {"key": "user", "label": "User name", "type": "text", "group": "The UPS",
         "hint": "For PeaNUT only, when it asks for a sign-in. Leave empty otherwise."},
        {"key": "password", "label": "Password", "type": "secret", "group": "The UPS",
         "hint": "PeaNUT's password. Starboard never shows it again."},
        _switch("alerts", "Send alerts through Starboard", "Sends one alert when the mains power is lost, the battery is low, it needs replacing or the UPS cannot be reached. Sends one more when each is over, to where Starboard sends its own alerts.", "Alerts"),
        _switch("hold", "Hold Starboard's heavy jobs on battery", "While the UPS is on battery, Starboard holds its background jobs, scheduled backups and downloads, and starts them again when the mains power is back. A job you start yourself still runs.", "Heavy jobs"),
        {"key": "low_percent", "label": "Low battery at", "type": "number", "unit": "%", "default": 30, "min": 0, "max": 99, "group": "Alerts",
         "hint": "On battery, a charge at or under this counts as low. 0 leaves it to the UPS's own low battery flag."},
        {"key": "low_minutes", "label": "Low battery under", "type": "number", "unit": "minutes", "default": 5, "min": 0, "max": 600, "group": "Alerts",
         "hint": "On battery, a time left at or under this counts as low. 0 leaves it to the UPS's own flag."},
    ],
    "actions": [{"id": "check", "label": "Check now", "path": "/check"}],
    "cards": [{"id": "status", "title": "Power", "type": "status", "path": "/card", "refresh_minutes": 1,
               "example": {"state": "ok", "text": "On mains power: battery 100%, about 42 minutes left, load 23%.", "status": "ok", "status_label": "On mains power", "updated": 1794694110}},
              {"id": "details", "title": "UPS details", "type": "list", "path": "/details", "refresh_minutes": 5,
               "example": {"items": [{"title": "ups (APC Back-UPS ES 700)", "detail": "On mains power, charging"}, {"title": "Battery", "detail": "100%"},
                                     {"title": "Time left on battery", "detail": "42 minutes"}, {"title": "Load", "detail": "23%"}], "status": "ok", "updated": 1794694110}},
              {"id": "history", "title": "Load and battery", "type": "sparkline", "path": "/history", "refresh_minutes": 5,
               "example": {"series": [{"title": "Load", "points": [21, 23, 22, 40, 23], "unit": "%", "detail": "Latest 23%"},
                                      {"title": "Battery", "points": [100, 100, 100, 100, 100], "unit": "%", "detail": "Latest 100%"}],
                           "note": "One point every 5 minutes for the last 8 hours.", "status": "ok", "updated": 1794694110}}],
    "changes": [{"version": "0.2.0", "date": "2026-11-27", "added": [
        "**Heavy jobs held on battery:** while the UPS is on battery, Starboard holds its background jobs, scheduled backups and downloads, and starts them again when the mains power is back. A job you start yourself still runs. You can deactivate this in Settings.",
        "**The card says so:** the Power card says when Starboard's heavy jobs are held."],
        "changed": ["It needs Starboard 0.40.0 or later (plug-in API 1.24). It asks for one more permission: to hold Starboard's heavy jobs."]},
        {"version": "0.1.1", "date": "2026-11-26", "changed": ["Plainer wording in the text and help pages. How it works has not changed."]},
        {"version": "0.1.0", "date": "2026-11-25", "added": [
        "**One card for your UPS:** it says whether you are on mains power or battery, and shows the battery charge, the time left and the load. A list has the voltage and power used.",
        "**Alerts:** through Starboard, once when the mains power is lost, the battery is low, it needs replacing or the UPS cannot be reached. You get one more when each is over.",
        "**NUT or PeaNUT:** it reads NUT's own protocol, or PeaNUT's web address; you choose, and the UPS if there is more than one.",
        "**Light:** one small question a minute, about 32 MB of memory at most, and a short history kept for the sparkline."]}],
    "_readme": """## What it reads

- **NUT:** the Network UPS Tools server (`upsd`, port 3493), with its text protocol: `LIST UPS`, then `LIST VAR <ups>`. It
  needs no sign-in to read, but `upsd.conf` must listen on an address this computer can reach, and `upsd.users` or
  access rules must allow it.
- **PeaNUT:** `GET /api/v1/devices/<ups>` (or `/api/v1/devices` for the first), with a sign-in when PeaNUT is set to ask for one.

Both are read only. Neither was tried against a real UPS when this version was written: read the help's Problems page
before relying on it.

## Heavy jobs on battery

While the UPS is on battery, this plug-in asks Starboard once a minute to hold its heavy work for 5 minutes: its background
jobs, scheduled backups, other plug-ins' scheduled jobs and downloads. When the mains power is back it lets them go at
once, and what was held starts again. If this plug-in stops, Starboard ends the hold by itself within 5 minutes. A job you
start yourself still runs. It uses the permission `power:hold` (plug-in API 1.24, Starboard 0.40.0). The setting **Hold
Starboard's heavy jobs on battery** is where you deactivate it.
""",
}, "file")

# 15. Immich (DASH-518) ---------------------------------------------------------------------------------------------
EXAMPLES["immich"] = ({
    "name": "Immich", "version": "0.2.0",
    "description": "Photo and video counts, storage used and the job queues of your Immich server on cards, and a page to pause, resume and clear them.",
    "starboard_api": ">=1.17 <2.0", "_own_changes": True,
    "permissions": ["network:lan"],
    "containers": [{"name": "main", "image": "", "port": 8080, "network": "lan", "volumes": ["data"], "start": "when_needed",
                    "idle_stop_minutes": 5}],
    "resources": {"main": {"memory": 32, "cpus": 0.1}}, "health": "/health",
    "settings": [
        {"key": "address", "label": "Immich's address", "type": "address", "group": "Immich", "required": True,
         "hint": "Such as http://192.0.2.10:2283, without /api on the end."},
        {"key": "api_key", "label": "API key", "type": "secret", "group": "Immich", "required": True,
         "hint": "Made in Immich under Account settings, API keys. Give it the permissions server.statistics, server.storage and queue.read (job.read for an older Immich), and queue.update (job.create) to pause, resume or clear queues from Starboard. Starboard never shows it again."},
        {"key": "queues", "label": "Job queues", "type": "custom", "choices": "/screen/queues", "group": "Immich",
         "hint": "Pause or resume each queue, and clear its failed jobs, without opening Immich. Changing a queue needs the permission queue.update on the API key."},
    ],
    "cards": [{"id": "library", "title": "Immich library", "type": "stat", "path": "/library", "format": "number", "refresh_minutes": 5,
               "example": {"value": 48210, "label": "photos and videos", "note": "44,870 photos, 3,340 videos, 412.6 GB", "status": "ok", "updated": 1794694110}},
              {"id": "storage", "title": "Immich storage", "type": "list", "path": "/storage", "refresh_minutes": 5,
               "example": {"items": [{"title": "Photos", "detail": "44,870, 301.2 GB"}, {"title": "Videos", "detail": "3,340, 111.4 GB"},
                                     {"title": "The disk Immich is on", "detail": "1.2 TB used of 4.0 TB (30%), 2.8 TB free"}], "status": "ok", "updated": 1794694110}},
              {"id": "jobs", "title": "Immich jobs", "type": "status", "path": "/jobs", "refresh_minutes": 1,
               "example": {"state": "ok", "text": "Working: Thumbnails, Smart search. 340 waiting.", "status": "working", "status_label": "Working", "updated": 1794694110}}],
    "changes": [{"version": "0.2.0", "date": "2026-11-27", "added": [
        "**A page for the job queues:** in Settings, Plug-ins, Immich, each queue has a switch to pause or resume it and a choice to clear its failed jobs, so you do not need Immich's own pages, which are hard to use with a keyboard or a screen reader.",
        "**Only when open:** Starboard asks Immich for the queues only while the page is open."],
        "changed": ["To pause, resume or clear a queue, give the API key the permission queue.update (job.create on an older Immich). The cards work as before without it."]},
        {"version": "0.1.1", "date": "2026-11-26", "changed": ["Plainer wording in the text and help pages. How it works has not changed."]},
        {"version": "0.1.0", "date": "2026-11-25", "added": [
        "**Three cards for Immich:** the photos and videos, where the space goes, how full the disk is, and what the job queues are doing.",
        "**Failed jobs** are said on the jobs card, so a stuck queue does not hide.",
        "**Light:** it runs only when a card asks, keeps each answer for a minute, and rests five minutes after; nothing at rest.",
        "**You choose** the address and an API key with only the permissions it needs."]}],
    "_readme": """## What it reads

Immich's own API, with your API key in the `x-api-key` header, read only:

- `GET /api/server/statistics`: the photo and video counts and the space they use, in total and for each person.
- `GET /api/server/storage`: how full the disk Immich keeps its library on is.
- `GET /api/queues` (or `GET /api/jobs` on an Immich from before it): each job queue's active, waiting and failed jobs.

The cards never change anything in Immich. The job queues page changes a queue only when you use its switch or its choice,
with `PUT /api/queues/<name>` (`isPaused`) and `DELETE /api/queues/<name>/jobs` (`failed`), or `PUT /api/jobs/<name>` on an
older Immich. It was not tried against a real server when this version was written: read the
help's Problems page before relying on it.
""",
}, "file")

# 16. Single sign-on (DASH-589, stage 1): the skeleton of the sign-in provider -----------------------------------------------
EXAMPLES["single-sign-on"] = ({
    "name": "Single sign-on", "version": "0.1.0",
    "description": "One sign-in for your apps and the people who use them. This first version holds the on and off switch and the Tailscale name the provider will live at.",
    "starboard_api": ">=1.21 <2.0", "_own_changes": True, "switch": "enabled",
    "permissions": [],
    "containers": [{"name": "main", "image": "", "port": 8080, "volumes": ["data"], "start": "when_needed",
                    "idle_stop_minutes": 5}],
    "resources": {"main": {"memory": 32, "cpus": 0.1}}, "health": "/health",
    "settings": [
        {"key": "enabled", "label": "Use single sign-on", "type": "switch", "default": False, "group": "Single sign-on",
         "hint": "Leave it off on a server only you use. Off means nothing runs for it. To stop the plug-in completely, deactivate it in Settings, Plug-ins, Manage."},
        {"key": "tailscale_name", "label": "This server's Tailscale name", "type": "text", "group": "Single sign-on",
         "hint": "Such as starboard.tail1234.ts.net, found in Tailscale's admin page under Machines. Set it once. Passkeys are tied to this address for ever: if it changes, every passkey stops working and has to be made again. Tailscale needs MagicDNS and HTTPS certificates activated."},
    ],
    "actions": [{"id": "check", "label": "Check the name", "path": "/check"},
                {"id": "use-new-address", "label": "Use the new address", "path": "/use-new-address",
                 "confirm": "The provider keeps the first Tailscale name it was given, because passkeys are tied to it. Use the name now in the settings instead? Passkeys made at the old name will not work at the new one."}],
    "cards": [{"id": "status", "title": "Single sign-on", "type": "status", "path": "/card", "refresh_minutes": 5,
               "example": {"state": "ok", "text": "The provider will live at https://starboard.tail1234.ts.net. Passkeys will be tied to this address. The provider is not in this version yet.",
                           "status": "waiting", "status_label": "Waiting for provider", "updated": 1794694110}}],
    "changes": [{"version": "0.1.0", "date": "2026-11-27", "added": [
        "**An on and off switch:** off means nothing runs for single sign-on. If other plug-ins need it, Starboard names them and asks before it deactivates them too (plug-in API 1.21).",
        "**The provider's address:** the Tailscale name of your server, checked, and kept the first time it is valid, because passkeys are tied to it for ever.",
        "**A warning if the name changes:** the card says passkeys made at the old name will not work, and Use the new address asks before it changes.",
        "**No provider yet:** this version only holds the settings. It makes no network call and starts only when a card asks."]}],
    "_readme": """## What this version does

It holds the settings that the sign-in provider will use, and nothing else. There is no provider in it yet, so nothing signs in
through it, and it makes no network call.

- **Use single sign-on** is off until you activate it. Leave it off on a server only you use.
- **This server's Tailscale name** is the address the provider will live at, such as `starboard.tail1234.ts.net`. Set it once.
  **Passkeys are tied to this address for ever.** A passkey made at one address does not work at another, so changing the
  name later means making every passkey again.
- The first valid name is kept in the plug-in's own folder. If the setting later differs, the card says so and keeps the first
  name until you choose **Use the new address**.

Starboard stays the one page you use and the one list of people (Settings, People). The provider will work behind it.
""",
}, "file")

# 12. Watch statistics (DASH-402) ----------------------------------------------------------------------------------
EXAMPLES["watch-stats"] = ({
    "name": "Watch statistics", "version": VERSION,
    "description": "What was watched, by whom and when, and the top titles, from Jellyfin's Playback Reporting, with no second database.",
    "starboard_api": ">=1.14 <2.0",
    "permissions": ["jellyfin:key", "network:lan"],
    "needs": ["jellyfin"],
    "containers": [{"name": "main", "image": "", "port": 8080, "network": "lan", "volumes": ["data"], "start": "when_needed",
                    "idle_stop_minutes": 5}],
    "resources": {"main": {"memory": 64, "cpus": 0.25}}, "health": "/health",
    "settings": [
        {"key": "plays", "label": "Recent plays", "type": "custom", "choices": "/screen/plays"},
        {"key": "titles", "label": "Top titles", "type": "custom", "choices": "/screen/titles"},
        {"key": "people", "label": "People", "type": "custom", "choices": "/screen/people"},
        {"key": "days", "label": "Over the last", "type": "number", "unit": "days", "default": 30, "min": 1, "max": 365},
        {"key": "leave_out", "label": "Leave out these people", "type": "list",
         "hint": "One Jellyfin user name a line, such as an account for testing."},
    ],
    "actions": [{"id": "refresh", "label": "Check now", "path": "/refresh"}],
    "cards": [{"id": "week", "title": "Plays this week", "type": "stat", "path": "/card/week", "format": "number", "refresh_minutes": 30,
               "example": {"value": 23, "label": "plays this week", "note": "14.5 hours by 3 people", "status": "ok", "updated": 1794694110}},
              {"id": "top", "title": "Top titles", "type": "list", "path": "/card/top", "refresh_minutes": 30,
               "example": {"items": [{"title": "Slow Horses", "detail": "2 people, 3 plays"}], "status": "ok", "updated": 1794694110}},
              {"id": "people", "title": "Who watched most", "type": "list", "path": "/card/people", "refresh_minutes": 30,
               "example": {"items": [{"title": "Sam", "detail": "4.1 hours, 5 plays, most Slow Horses"}], "status": "ok", "updated": 1794694110}},
              {"id": "source", "title": "Watch statistics source", "type": "status", "path": "/card/source", "refresh_minutes": 60,
               "example": {"state": "ok", "text": "Reading Jellyfin's Playback Reporting", "status": "ok", "updated": 1794694110}}],
    "changes": [{"version": "1.0.0", "date": "2026-11-13", "added": [
        "**Three tables:** recent plays by day, top titles and people, each to read only, with search and sorting.",
        "**Four cards:** plays this week, top titles, who watched most, and where the figures come from.",
        "Reads Jellyfin's Playback Reporting with one query, so a Full install can go without Jellystat and its PostgreSQL.",
        "Without Playback Reporting it says so and how to add it, and shows each person's last plays from Jellyfin itself.",
        "Rests when not in use, and keeps each answer for 15 minutes."]}],
    "_readme": """## Playback Reporting

The figures come from [Playback Reporting](https://github.com/jellyfin/jellyfin-plugin-playbackreporting), a plug-in
for Jellyfin in its official catalogue. Add it in Starboard's **Settings**, **Jellyfin**, or in Jellyfin's
**Dashboard**, **Plugins**, **Catalogue**, then restart Jellyfin. It counts from then on, and keeps its own history
inside Jellyfin's data, so nothing else needs a database.

Without it, this plug-in says so on its tables and its **Watch statistics source** card. It then shows what Jellyfin knows
itself: each person's last play of each title, with no device or time watched.

## In place of Jellystat

Jellystat needs two containers and PostgreSQL (about 60 MB measured on a small server, 150 to 250 MB on a busy one).
This plug-in rests when nobody is using it, and uses about 14 MB for a few seconds when a card or table asks.
""",
}, "file")
