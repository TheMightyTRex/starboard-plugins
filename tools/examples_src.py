"""The example plug-ins (owner, 12 November 2026: "build all the plug-in examples", from the list of plug-ins that can
be built now). Each is: what it does, its manifest, and app.py. tools/make_examples.py writes each folder."""

COMMON = {"manifest_version": 1, "author": "TheMightyTRexUK", "licence": "MIT",
          "support_url": "https://github.com/TheMightyTRex/starboard-plugins/issues", "starboard_api": ">=1.14 <2.0"}
# 1.1.0 (plug-in API 1.14, 15 November 2026): a logo, the card band's status and updated, and the update tools.
# 1.1.1 (16 November 2026, DASH-453): lighter at rest and faster to start; Library health a page at a time.
# 1.1.2 (17 November 2026, DASH-458): sbplugin sends Jellyfin's key in Authorization too, for Jellyfin 12.
VERSION = "1.1.2"
VERSION_111 = "1.1.1"
VERSION_110 = "1.1.0"


def image(pid):
    return f"ghcr.io/themightytrex/starboard-plugin-{pid}:{VERSION}"


# Plug-in API 1.14 (15 November 2026) ---------------------------------------------------------------------------
# Update steps for the examples that work in the background: sbplugin's /update/before holds new runs and waits for one
# that is running to finish, and /update/after lets them run again. The others finish what they do in a second.
_STEPS = {"before": {"path": "/update/before", "time_limit_seconds": 60}, "after": {"path": "/update/after", "time_limit_seconds": 10}}
UPDATE_STEPS = {pid: _STEPS for pid in ("line-speed", "most-watched", "library-health", "notifications", "watch-stats")}
RELEASED = "2026-11-15"
RELEASED_111 = "2026-11-16"
RELEASED_112 = "2026-11-17"
FIRST = "2026-11-12"


def changes_for(pid, m):
    """What is new in each version (plug-in API 1.10, shown before an update from API 1.14): 1.1.0 first, then the
    plug-in's own list, or its first version."""
    earlier = [c for c in m.get("changes") or [] if c.get("version") not in (VERSION, VERSION_111, VERSION_110)] or [
        {"version": "1.0.0", "date": FIRST, "added": [m["description"]]}]
    added = ["**A logo** in Settings, Plug-ins, in the Catalogue and on its dashboard cards.",
             "**Its cards say how things are:** a status and when they last changed, in the grey band at the top of each card."]
    if pid in UPDATE_STEPS:
        added.append("**Updates safely:** before an update it finishes what it is doing and starts nothing new.")
    if any(c.get("refresh_seconds") for c in m.get("cards") or []):
        added.append("**Kept up to date:** its card is asked every 30 seconds while the dashboard is open.")
    light = ["**Lighter at rest:** it wakes about once a minute while nothing asks it anything, not twice a second, and writes nothing to its folder when a run goes well.", "**Starts faster:** its image comes with Python's modules already compiled, so a start takes about a quarter of the processor time."]
    fixed = (["**Large libraries:** it asks Jellyfin a page of 500 titles at a time, so a large library no longer makes the check "
              "fail."] if pid == "library-health" else [])
    v111 = {"version": VERSION_111, "date": RELEASED_111, "changed": light, **({"fixed": fixed} if fixed else {})}
    newest = {"version": VERSION, "date": RELEASED_112, **({"fixed": JELLYFIN_12} if pid in CALLS_JELLYFIN else {"changed": SHARED_ONLY})}
    return [newest, v111, {"version": VERSION_110, "date": RELEASED, "added": added,
             "changed": ["Needs Starboard with plug-in API 1.14 or later. A Starboard with an older plug-in API keeps version 1.0.0."]}] + earlier


# 1.1.2 (DASH-458): Jellyfin 12 with legacy authorisation off refuses the key in X-Emby-Token alone.
CALLS_JELLYFIN = {"watching-now", "most-watched", "library-health", "watch-stats"}
JELLYFIN_12 = ["**Jellyfin 12:** it sends Jellyfin's key the way Jellyfin 12 asks for it, so Jellyfin no longer refuses its "
               "requests where legacy authorisation is off. Older Jellyfin still works."]
SHARED_ONLY = ["**Shared helper:** the helper every example shares sends Jellyfin's key the way Jellyfin 12 asks for it. "
               "This plug-in does not ask Jellyfin anything, so it works as before."]

EXAMPLES = {}

# 1. VPN check ------------------------------------------------------------------------------------------------------
EXAMPLES["vpn-check"] = ({
    "name": "VPN check", "description": "Shows the address and country your downloads use through the VPN, and warns if it is your home address.",
    "permissions": ["network:vpn"],
    "containers": [{"name": "main", "image": image("vpn-check"), "port": 7791, "network": "vpn", "volumes": ["data"],
                    "env": {"PORT": "7791"}}],
    "resources": {"main": {"memory": 48, "cpus": 0.1}}, "health": "/health",
    "settings": [{"key": "home_address", "label": "Your home's public address", "type": "text",
                  "hint": "Optional, such as 81.2.69.160. If the VPN ever shows this address, the card turns red."},
                 {"key": "minutes", "label": "Check every", "type": "number", "unit": "minutes", "default": 15, "min": 5, "max": 240}],
    "actions": [{"id": "check", "label": "Check now", "path": "/check"}],
    "cards": [{"id": "status", "title": "VPN", "type": "status", "path": "/card", "example": {"state": "ok", "text": "185.65.134.12 in the Netherlands", "status": "protected", "updated": 1794694110}}],
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
    "actions": [{"id": "test", "label": "Test now", "path": "/test", "confirm": "Downloads a test file now. Continue?"}],
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
        return band({"value": 0, "label": "Mbps", "note": err or "Not tested yet"}, "problem" if err else "scheduled",
                    label=None if err else next_test())
    r = runs[-1]
    return band({"value": r["mbps"], "label": "Mbps", "note": time.strftime("%a %H:%M", time.localtime(r["at"]))}, "ok", r["at"])


def week():
    runs = remember("runs", [])
    items = [{"title": f"{r['mbps']} Mbps", "detail": time.strftime("%A %d %b, %H:%M", time.localtime(r["at"]))} for r in reversed(runs[-7:])]
    if not items:
        return band({"items": [{"title": "Not tested yet", "detail": next_test()}]}, "scheduled", label=next_test())
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
               "example": {"items": [{"title": "Dune: Part Two", "detail": "Sam, living room TV, 40%"}], "status": "running", "status_label": "1 watching", "updated": 1794694110}}],
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
    return band({"items": rows}, "running", time.time(), f"{len(rows)} watching")


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
                  "hint": "States that turn the card amber, separated by commas."}],
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

# 8. Outside services -----------------------------------------------------------------------------------------------
EXAMPLES["outside-services"] = ({
    "name": "Outside services", "description": "Up or down for things that are not on this server: your router, a NAS, a website.",
    "permissions": ["network:lan"],
    "containers": [{"name": "main", "image": image("outside-services"), "port": 8080, "network": "lan", "volumes": ["data"]}],
    "resources": {"main": {"memory": 48, "cpus": 0.1}}, "health": "/health",
    "settings": [{"key": "addresses", "label": "Addresses to check", "type": "list",
                  "hint": "One each, such as http://192.0.2.1 or https://example.org. Give a name first if you like: Router http://192.0.2.1"},
                 {"key": "minutes", "label": "Check every", "type": "number", "unit": "minutes", "default": 5, "min": 1, "max": 60}],
    "cards": [{"id": "summary", "title": "Outside services", "type": "status", "path": "/status", "example": {"state": "ok", "text": "All 4 answer", "status": "ok", "updated": 1794694110}},
              {"id": "list", "title": "Outside services", "type": "list", "path": "/card", "example": {"items": [{"title": "Router", "detail": "Up, 4 ms"}], "status": "ok", "updated": 1794694110}}],
}, '''import time
import urllib.error
from sbplugin import band, changed, every, fetch, keep, remember, serve, setting


def targets():
    out = []
    for line in setting("addresses", []) or []:
        parts = str(line).split()
        if parts:
            out.append((" ".join(parts[:-1]) or parts[-1], parts[-1]))
    return out[:20]


def check():
    rows = []
    for name, url in targets():
        started = time.monotonic()
        try:
            fetch(url, timeout=8, raw=True, limit=1024)
            up = True
        except urllib.error.HTTPError as e:
            up = e.code < 500  # it answered: a sign-in page or 404 still means it is up
        except Exception:  # noqa: BLE001
            up = False
        rows.append({"name": name, "url": url, "up": up, "ms": round((time.monotonic() - started) * 1000)})
    keep("rows", rows)


def status():
    rows = remember("rows", [])
    if not rows:
        return band({"state": "warning", "text": "Add addresses in the plug-in's settings" if not targets() else "Not checked yet"},
                    "needs_setup" if not targets() else "waiting")
    down = [r["name"] for r in rows if not r["up"]]
    return band({"state": "problem" if down else "ok", "text": f"Not answering: {', '.join(down)}" if down else f"All {len(rows)} answer"},
                "problem" if down else "ok", changed("rows"), f"{len(down)} not answering" if down else None)


def card():
    rows = remember("rows", [])
    down = sum(1 for r in rows if not r["up"])
    out = {"items": [{"title": r["name"], "detail": f"Up, {r['ms']} ms" if r["up"] else "Not answering", "link": r["url"]} for r in rows][:10]}
    if not rows:
        return band(out, "needs_setup" if not targets() else "waiting")
    return band(out, "problem" if down else "ok", changed("rows"), f"{down} not answering" if down else None)


every(60 * float(setting("minutes", 5)), check, first=2)
serve({"/status": status, "/card": card})
''')

# 9. Download summary -----------------------------------------------------------------------------------------------
EXAMPLES["download-summary"] = ({
    "name": "Download summary", "description": "How much has downloaded today and this week, from what Starboard sees in the queue.",
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
    label = f"Full in {round(worst):,} days" if worst is not None and worst < 60 else None
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
IMAGE_VERSION = "1.2.2"
# Built and pinned on 17 November 2026 (sha256:ccd38ab9d0a8...): every example runs from the pinned image again.
NEW_IN_IMAGE = set()


def _switch(key, label, hint, group, default=True):
    return {"key": key, "label": label, "type": "switch", "default": default, "hint": hint, "group": group}


# 11. Notifications (DASH-401) -------------------------------------------------------------------------------------
EXAMPLES["notifications"] = ({
    "name": "Notifications", "version": VERSION,
    "description": "Sends Starboard's events to email, Telegram, Discord, Signal, Pushover, ntfy or a webhook, in plain words, and a weekly New this week.",
    "starboard_api": ">=1.14 <2.0",
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
        _switch("send_updates", "An update is ready", "For Starboard, your apps and your plug-ins.", "What to send"),
        _switch("send_weekly", "New this week", "Films, series and more that arrived in the last 7 days, once a week at 09:00.", "What to send"),
        {"key": "weekly_day", "label": "Send New this week on", "type": "choice", "default": "monday", "group": "What to send",
         "hint": "The day New this week is sent, at 09:00.",
         "choices": [{"value": d.lower(), "label": d} for d in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")]},
        {"key": "starboard_address", "label": "Starboard's address, for links", "type": "address", "group": "What to send",
         "hint": "Optional, such as http://192.0.2.10:8095. Messages end with Open Starboard and this address."},
        _switch("email_active", "Send by email", "Activate once the details below are filled in and the test arrives.", "Email", False),
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
        _switch("telegram_active", "Send by Telegram", "Activate once the details below are filled in and the test arrives.", "Telegram", False),
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
        _switch("pushover_active", "Send by Pushover", "Activate once the keys below are filled in and the test arrives.", "Pushover", False),
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
         "hint": "One person a line: the name they use in Reelix or Seerr, a comma, then their email address or telegram and their chat id."},
    ],
    "actions": [{"id": "test-email", "label": "Send a test email", "path": "/test/email"},
                {"id": "test-telegram", "label": "Send a test to Telegram", "path": "/test/telegram"},
                {"id": "test-discord", "label": "Send a test to Discord", "path": "/test/discord"},
                {"id": "test-signal", "label": "Send a test by Signal", "path": "/test/signal"},
                {"id": "test-pushover", "label": "Send a test by Pushover", "path": "/test/pushover"},
                {"id": "test-ntfy", "label": "Send a test by ntfy", "path": "/test/ntfy"},
                {"id": "test-webhook", "label": "Send a test to the webhooks", "path": "/test/webhook"},
                {"id": "weekly-now", "label": "Send New this week now", "path": "/weekly-now"}],
    "cards": [{"id": "status", "title": "Notifications", "type": "status", "path": "/card", "refresh_minutes": 60,
               "example": {"state": "ok", "text": "Mon 09:00, New this week: sent by Email, Telegram", "status": "ok", "updated": 1794694110}},
              {"id": "recent", "title": "Notifications sent", "type": "list", "path": "/recent", "refresh_minutes": 60,
               "example": {"items": [{"title": "Ready to watch: Dune (2021)", "detail": "Mon 12 Nov 20:15, sent by Email, Telegram"}], "status": "ok", "updated": 1794694110}}],
    "events": ["request.available", "download.failed", "app.down", "app.up", "disk.nearly_full", "update.available", "item.added"],
    "jobs": [{"id": "weekly", "label": "Send New this week on the chosen day", "path": "/jobs/weekly", "daily": "09:00", "time_limit_minutes": 2}],
    "changes": [{"version": "1.0.0", "date": "2026-11-13", "added": [
        "**Seven ways to send:** email, Telegram, Discord, Signal (through signal-cli-rest-api), Pushover, ntfy and Apprise-style webhooks, each with a Test button.",
        "**What it sends:** a request ready to watch (to the person who asked too), a failed download, an app down and back, a disk nearly full, an update ready, and New this week.",
        "Plain words with no meaning in symbols, and links with words before them.",
        "Rests between messages: Starboard's events and its daily job wake it, so it uses no memory while idle."]}],
    "_readme": """## How it stays light

It has no timer of its own. Starboard sends it each event and runs its daily job, and it rests (stops) 5 minutes after
the last one. A message takes about a second and 14 MB of memory while it runs.

## Secrets

Passwords, tokens, keys and the webhook addresses are secret settings: Starboard never shows them again, and the
plug-in never writes them to its log, its card or its folder. A failed message says only which channel failed and why,
in words such as "it refused the sign-in or token".

## Per person

Under **People**, give one line for each person who asks for things: the name they use in Reelix or Seerr, a comma,
then their email address, or `telegram` and their chat id. When their request is ready, they hear too.

## Signal

Signal has no official way for a server to send messages. If you already run
[signal-cli-rest-api](https://github.com/bbernhard/signal-cli-rest-api) with a number registered, give its address
and that number. Otherwise leave Signal deactivated.
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
    "actions": [{"id": "refresh", "label": "Read the figures again now", "path": "/refresh"}],
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

Without it, this plug-in says so on its tables and its **Watch statistics source** card, and shows what Jellyfin knows
itself: each person's last play of each title, with no device or time watched.

## In place of Jellystat

Jellystat needs two containers and PostgreSQL (about 60 MB measured on a small server, 150 to 250 MB on a busy one).
This plug-in rests when no one is looking, and uses about 14 MB for a few seconds when a card or table asks.
""",
}, "file")
