"""The example plug-ins (owner, 12 November 2026: "build all the plug-in examples", from the list of plug-ins that can
be built now). Each is: what it does, its manifest, and app.py. tools/make_examples.py writes each folder."""

COMMON = {"manifest_version": 1, "author": "TheMightyTRexUK", "licence": "MIT",
          "support_url": "https://github.com/TheMightyTRex/starboard-plugins/issues", "starboard_api": ">=1.1 <2.0"}
VERSION = "1.0.0"


def image(pid):
    return f"ghcr.io/themightytrex/starboard-plugin-{pid}:{VERSION}"


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
    "cards": [{"id": "status", "title": "VPN", "type": "status", "path": "/card", "example": {"state": "ok", "text": "185.65.134.12 in the Netherlands"}}],
}, '''import os
import time
from sbplugin import every, fetch, keep, last_error, remember, serve, setting


def check():
    started = time.monotonic()
    ip = fetch("https://ipinfo.io/json", timeout=10)
    keep("last", {"ip": ip.get("ip", ""), "country": ip.get("country", ""), "city": ip.get("city", ""),
                  "ms": round((time.monotonic() - started) * 1000), "at": time.time()})
    return {"said": f"Through the VPN: {ip.get('ip')} in {ip.get('city') or ip.get('country')}"}


def card():
    last = remember("last") or {}
    if not last:
        return {"state": "warning", "text": last_error() or "Not checked yet"}
    home = str(setting("home_address", "")).strip()
    if home and last["ip"] == home:
        return {"state": "problem", "text": f"The VPN shows your home address, {home}. Downloads are not hidden."}
    if time.time() - last["at"] > 3 * 60 * float(setting("minutes", 15)):
        return {"state": "warning", "text": f"No answer through the VPN since {time.strftime('%H:%M', time.localtime(last['at']))}. {last_error()}"}
    return {"state": "ok", "text": f"{last['ip']} in {', '.join(x for x in (last['city'], last['country']) if x)}, {last['ms']} ms"}


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
    "cards": [{"id": "speed", "title": "Line speed", "type": "stat", "path": "/card", "format": "number", "example": {"value": 72, "label": "Mbps", "note": "04:00 today"}},
              {"id": "week", "title": "Line speed this week", "type": "list", "path": "/week", "example": {"items": [{"title": "72 Mbps", "detail": "Wednesday 04:00"}]}}],
}, '''import time
from sbplugin import every, fetch, keep, last_error, remember, serve, setting


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


def card():
    runs = remember("runs", [])
    if not runs:
        return {"value": 0, "label": "Mbps", "note": last_error() or "Not tested yet"}
    r = runs[-1]
    return {"value": r["mbps"], "label": "Mbps", "note": time.strftime("%a %H:%M", time.localtime(r["at"]))}


def week():
    return {"items": [{"title": f"{r['mbps']} Mbps", "detail": time.strftime("%A %d %b, %H:%M", time.localtime(r["at"]))}
                      for r in reversed(remember("runs", [])[-7:])]}


every(600, nightly)
serve({"/card": card, "/week": week, ("POST", "/test"): test})
''')

# 3. Watching now ---------------------------------------------------------------------------------------------------
EXAMPLES["watching-now"] = ({
    "name": "Watching now", "description": "Who is watching what in Jellyfin right now, with how far through they are.",
    "permissions": ["jellyfin:key", "network:lan"],
    "containers": [{"name": "main", "image": image("watching-now"), "port": 8080, "network": "lan"}],
    "resources": {"main": {"memory": 48, "cpus": 0.1}}, "health": "/health",
    "cards": [{"id": "now", "title": "Watching now", "type": "list", "path": "/card", "example": {"items": [{"title": "Dune: Part Two", "detail": "Sam, living room TV, 40%"}]}}],
}, '''from sbplugin import jellyfin, serve


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
''')

# 4. Most watched ---------------------------------------------------------------------------------------------------
EXAMPLES["most-watched"] = ({
    "name": "Most watched", "description": "The films and series most people watched in Jellyfin in the last week.",
    "permissions": ["jellyfin:key", "network:lan"],
    "containers": [{"name": "main", "image": image("most-watched"), "port": 8080, "network": "lan", "volumes": ["data"]}],
    "resources": {"main": {"memory": 64, "cpus": 0.1}}, "health": "/health",
    "settings": [{"key": "days", "label": "Over the last", "type": "number", "unit": "days", "default": 7, "min": 1, "max": 90}],
    "cards": [{"id": "top", "title": "Most watched", "type": "list", "path": "/card", "example": {"items": [{"title": "Slow Horses", "detail": "3 people, 11 plays"}]}}],
}, '''import time
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
''')

# 5. Library health -------------------------------------------------------------------------------------------------
EXAMPLES["library-health"] = ({
    "name": "Library health", "description": "Films and series in Jellyfin with no poster, no description or no year, so you can fix them.",
    "permissions": ["jellyfin:key", "network:lan"],
    "containers": [{"name": "main", "image": image("library-health"), "port": 8080, "network": "lan", "volumes": ["data"]}],
    "resources": {"main": {"memory": 96, "cpus": 0.25}}, "health": "/health",
    "actions": [{"id": "check", "label": "Check now", "path": "/check"}],
    "cards": [{"id": "count", "title": "Library health", "type": "stat", "path": "/count", "format": "number", "example": {"value": 4, "label": "to fix", "note": "of 1,240 titles"}},
              {"id": "list", "title": "To fix in Jellyfin", "type": "list", "path": "/card", "example": {"items": [{"title": "Brazil (1985)", "detail": "No poster"}]}}],
}, '''from sbplugin import every, jellyfin, keep, last_error, plural, remember, serve


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
''')

# 6. Pi-hole or AdGuard Home ----------------------------------------------------------------------------------------
EXAMPLES["dns-blocking"] = ({
    "name": "Ad blocking", "description": "How many adverts and trackers Pi-hole or AdGuard Home blocked today.",
    "permissions": ["network:lan"],
    "containers": [{"name": "main", "image": image("dns-blocking"), "port": 8080, "network": "lan"}],
    "resources": {"main": {"memory": 48, "cpus": 0.1}}, "health": "/health",
    "settings": [{"key": "kind", "label": "Which one", "type": "choice", "choices": ["Pi-hole", "AdGuard Home"], "default": "Pi-hole"},
                 {"key": "address", "label": "Its address", "type": "address", "hint": "Such as http://192.168.1.2 for Pi-hole, or http://192.168.1.2:3000 for AdGuard Home."},
                 {"key": "username", "label": "User name", "type": "text", "hint": "AdGuard Home only."},
                 {"key": "password", "label": "Password", "type": "secret", "hint": "Pi-hole's web password, or AdGuard Home's. Kept by Starboard."}],
    "cards": [{"id": "blocked", "title": "Blocked today", "type": "stat", "path": "/card", "format": "number", "example": {"value": 4210, "label": "blocked", "note": "12% of 35,000 lookups"}}],
}, '''import base64
from sbplugin import fetch, serve, setting


def card():
    base = str(setting("address", "")).rstrip("/")
    if not base:
        raise ValueError("Add the address in the plug-in's settings")
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
    return {"value": blocked, "label": "blocked", "note": share}


serve({"/card": card})
''')

# 7. Home Assistant -------------------------------------------------------------------------------------------------
EXAMPLES["home-assistant"] = ({
    "name": "Home Assistant", "description": "Your house in one sentence on the dashboard: the things you choose from Home Assistant.",
    "permissions": ["network:lan"],
    "containers": [{"name": "main", "image": image("home-assistant"), "port": 8080, "network": "lan"}],
    "resources": {"main": {"memory": 48, "cpus": 0.1}}, "health": "/health",
    "settings": [{"key": "address", "label": "Home Assistant's address", "type": "address", "hint": "Such as http://192.168.1.30:8123"},
                 {"key": "token", "label": "Long-lived access token", "type": "secret",
                  "hint": "In Home Assistant: your profile, Security, Long-lived access tokens, Create token. Kept by Starboard."},
                 {"key": "entities", "label": "What to show", "type": "list",
                  "hint": "One entity id each, such as binary_sensor.front_door or sensor.lounge_temperature."},
                 {"key": "alert_on", "label": "Warn when any is", "type": "text", "default": "on, open, unlocked",
                  "hint": "States that turn the card amber, separated by commas."}],
    "cards": [{"id": "house", "title": "Home", "type": "status", "path": "/card", "example": {"state": "ok", "text": "Front door: closed. Lounge: 20.5 °C"}}],
}, '''from sbplugin import fetch, serve, setting


def card():
    base, token = str(setting("address", "")).rstrip("/"), setting("token", "")
    ids = setting("entities", []) or []
    if not base or not token or not ids:
        return {"state": "warning", "text": "Add the address, a token and what to show in the plug-in's settings"}
    alert = {s.strip().lower() for s in str(setting("alert_on", "on, open, unlocked")).split(",") if s.strip()}
    parts, warn = [], False
    for eid in ids[:8]:
        s = fetch(f"{base}/api/states/{eid}", {"Authorization": f"Bearer {token}"})
        name = (s.get("attributes") or {}).get("friendly_name") or eid
        unit = (s.get("attributes") or {}).get("unit_of_measurement") or ""
        state = s.get("state", "")
        warn |= state.lower() in alert
        parts.append(f"{name}: {state}{' ' + unit if unit else ''}")
    return {"state": "warning" if warn else "ok", "text": ". ".join(parts)}


serve({"/card": card})
''')

# 8. Outside services -----------------------------------------------------------------------------------------------
EXAMPLES["outside-services"] = ({
    "name": "Outside services", "description": "Up or down for things that are not on this server: your router, a NAS, a website.",
    "permissions": ["network:lan"],
    "containers": [{"name": "main", "image": image("outside-services"), "port": 8080, "network": "lan", "volumes": ["data"]}],
    "resources": {"main": {"memory": 48, "cpus": 0.1}}, "health": "/health",
    "settings": [{"key": "addresses", "label": "Addresses to check", "type": "list",
                  "hint": "One each, such as http://192.168.1.1 or https://example.org. Give a name first if you like: Router http://192.168.1.1"},
                 {"key": "minutes", "label": "Check every", "type": "number", "unit": "minutes", "default": 5, "min": 1, "max": 60}],
    "cards": [{"id": "summary", "title": "Outside services", "type": "status", "path": "/status", "example": {"state": "ok", "text": "All 4 answer"}},
              {"id": "list", "title": "Outside services", "type": "list", "path": "/card", "example": {"items": [{"title": "Router", "detail": "Up, 4 ms"}]}}],
}, '''import time
import urllib.error
from sbplugin import every, fetch, keep, remember, serve, setting


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
        return {"state": "warning", "text": "Add addresses in the plug-in's settings" if not targets() else "Not checked yet"}
    down = [r["name"] for r in rows if not r["up"]]
    return {"state": "problem" if down else "ok", "text": f"Not answering: {', '.join(down)}" if down else f"All {len(rows)} answer"}


def card():
    return {"items": [{"title": r["name"], "detail": f"Up, {r['ms']} ms" if r["up"] else "Not answering", "link": r["url"]}
                      for r in remember("rows", [])][:10]}


every(60 * float(setting("minutes", 5)), check, first=2)
serve({"/status": status, "/card": card})
''')

# 9. Download summary -----------------------------------------------------------------------------------------------
EXAMPLES["download-summary"] = ({
    "name": "Download summary", "description": "How much has downloaded today and this week, from what Starboard sees in the queue.",
    "permissions": ["downloads:read"],
    "containers": [{"name": "main", "image": image("download-summary"), "port": 8080, "volumes": ["data"]}],
    "resources": {"main": {"memory": 48, "cpus": 0.1}}, "health": "/health",
    "cards": [{"id": "today", "title": "Downloaded today", "type": "stat", "path": "/card", "format": "bytes", "example": {"value": 12884901888, "label": "today", "note": "41 GB this week"}}],
}, '''import time
from sbplugin import every, keep, remember, serve, starboard


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
    return {"value": int(days.get(time.strftime("%Y-%m-%d"), 0)), "label": "today", "note": f"{week / 1e9:.1f} GB this week"}


every(60, sample)
serve({"/card": card})
''')

# 10. Disk forecast -------------------------------------------------------------------------------------------------
EXAMPLES["disk-forecast"] = ({
    "name": "Disk forecast", "description": "When each disk fills at the rate it has been filling over the last month.",
    "permissions": ["system:read"],
    "containers": [{"name": "main", "image": image("disk-forecast"), "port": 8080, "volumes": ["data"]}],
    "resources": {"main": {"memory": 48, "cpus": 0.1}}, "health": "/health",
    "cards": [{"id": "forecast", "title": "Disk forecast", "type": "status", "path": "/card", "example": {"state": "ok", "text": "Pool full in about 140 days"}}],
}, '''import time
from sbplugin import every, keep, last_error, remember, serve, starboard


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
        return {"state": "warning", "text": last_error() or "Measuring: a forecast after two days"}
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
    return {"state": state, "text": ". ".join(parts)}


every(3600, sample)
serve({"/card": card})
''')

# 11. Seasonal styles: styles only, no containers -------------------------------------------------------------------
EXAMPLES["seasonal-styles"] = ({
    "name": "Seasonal styles", "description": "Two more styles for Display: Winter, in deep green and berry red, and Large and clear, for easy reading.",
    "permissions": ["appearance:styles"], "containers": [],
    "styles": [
        {"id": "winter", "name": "Winter", "description": "Deep pine green and berry red, warm and calm for the darker months.",
         "radius": 10, "font": "hyperlegible", "shadow": "soft",
         "light": {"bg": "#f3f6f2", "header": "#fbfcfa", "surface": "#f7f9f6", "surface_raised": "#ffffff", "surface_sunken": "#e3eae1",
                   "text": "#132018", "text_muted": "#3f5145", "border": "#6b7d70", "divider": "#cbd6cd", "accent": "#a3172f",
                   "accent_text": "#ffffff", "accent_soft": "#f8e1e5", "focus": "#1d5a36"},
         "dark": {"bg": "#0b1510", "header": "#0f1d16", "surface": "#11211a", "surface_raised": "#172b22", "surface_sunken": "#07100b",
                  "text": "#eaf2ec", "text_muted": "#a9bcae", "border": "#6f8a78", "divider": "#24392d", "accent": "#ff8a9c",
                  "accent_text": "#0b1510", "accent_soft": "#3b1820", "focus": "#8fd6a8"}},
        {"id": "large-clear", "name": "Large and clear", "description": "Strong contrast, wide focus rings and a heavier font, for easy reading.",
         "radius": 4, "font": "hyperlegible", "shadow": "none", "heading_weight": 800, "focus_width": 4,
         "light": {"bg": "#ffffff", "header": "#ffffff", "surface": "#ffffff", "surface_raised": "#ffffff", "surface_sunken": "#eeeeee",
                   "text": "#000000", "text_muted": "#2b2b2b", "border": "#4a4a4a", "divider": "#8a8a8a", "accent": "#0040b0",
                   "accent_text": "#ffffff", "accent_soft": "#dfe8fb", "focus": "#000000"},
         "dark": {"bg": "#000000", "header": "#000000", "surface": "#000000", "surface_raised": "#111111", "surface_sunken": "#000000",
                  "text": "#ffffff", "text_muted": "#dddddd", "border": "#b5b5b5", "divider": "#6b6b6b", "accent": "#ffd23f",
                  "accent_text": "#000000", "accent_soft": "#3a3000", "focus": "#ffffff"}}],
}, None)
