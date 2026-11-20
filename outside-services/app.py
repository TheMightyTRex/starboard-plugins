"""Uptime and status (2.0.0, which takes over Outside services): checks things on your home network and the internet,
keeps 90 days of response times, warns before certificates run out, pauses its alerts in maintenance windows, and
writes a read-only status page for your home network.

- Checks: http, keyword, tcp, ping, dns and push (heartbeat), in checks.py, each written as one line in Settings,
  Plug-ins, Uptime and status, Checks. The addresses of Outside services' "Addresses to check" are web address checks,
  as before, so an update keeps them with no step.
- History: history.py, 43 KB a check for 90 days, written once an hour.
- Alerts: through Starboard (plug-in API 1.17, POST /api/v1/plugin/alerts with the permission alerts:send), once when
  a check goes down and once when it is up again; never while its group is in a maintenance window (windows.py).
- Status page: page.py, plain HTML in the container's memory after each round, on the port Starboard publishes on the
  home network, with the heartbeat addresses (/push/<secret>).
- Cards: a summary, the checks, the groups, response times (a sparkline card, API 1.17) and certificates.

One thread checks; it sleeps until the next check is due, at most a minute. Up to four checks run at once.
"""
import hmac
import http.client
import json
import os
import signal
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import checks as ck  # noqa: E402
import page  # noqa: E402
import sbplugin as sb  # noqa: E402
import windows as win  # noqa: E402
from history import History  # noqa: E402
from sbplugin import band, keep, remember, setting  # noqa: E402

NAME = "Uptime and status"
HERE = os.path.dirname(os.path.abspath(__file__))
PAGE_DIR = os.environ.get("STATUS_DIR", "/tmp/status")  # nosec B108 - the container's own /tmp, in memory
MAX_CHECKS = 100
WORKERS = 4
CERT_EVERY = 6 * 3600
OTHER = "Other checks"
QUICK_GROUP = "Outside services"  # the addresses from Outside services 1.x keep a group of their own
STATIC = {"/ds.css": ("ds.css", "text/css; charset=utf-8"), "/status.css": ("status.css", "text/css; charset=utf-8"),
          "/theme.js": ("theme.js", "text/javascript; charset=utf-8"),
          "/fonts/atkinson-hyperlegible-next.woff2": ("font.woff2", "font/woff2")}
WORDS = {"up": "Up", "down": "Down", "retry": "Trying again", "waiting": "Not checked yet", "off": "Paused"}
CUSTOM_STATE = {"up": "ok", "down": "problem", "retry": "warning", "waiting": "unknown", "off": "off"}

_lock = threading.RLock()
_wake = threading.Event()
HISTORY = History(os.path.join(sb.DATA, "history"))
LIVE = {}  # check id -> {"up": True, False or None, "ms", "said", "at", "fails", "since"}
CERTS = {}  # check id -> the certificate's fields, or {"error": words, "checked": t}
NEXT = {}  # check id -> when it is next due
PUSH_SAMPLED = {}  # check id -> when a heartbeat's state was last kept in the history
STATE = {"raised": {}, "pushes": {}, "alerts_api": None}  # kept in /data/state.json when it changes


# What is kept -----------------------------------------------------------------------------------------------------------

def load():
    s = remember("state", {}) or {}
    STATE["raised"] = s.get("raised") or {}
    STATE["pushes"] = s.get("pushes") or {}
    for cid, live in (s.get("live") or {}).items():
        LIVE[cid] = live


def save_state():
    with _lock:
        keep("state", {"raised": STATE["raised"], "pushes": STATE["pushes"],
                       "live": {k: {n: v.get(n) for n in ("up", "fails", "since", "said")} for k, v in LIVE.items()}})


def stored():
    return remember("checks", []) or []


def store(rows):
    keep("checks", rows)


def groups_kept():
    return remember("groups", {}) or {}


def keep_groups(g):
    keep("groups", g)


def every_default():
    try:
        return max(1, min(int(float(setting("minutes", 5))), 60)) * 60
    except (TypeError, ValueError):
        return 300


def quick():
    """The addresses in "Addresses to check" (Outside services 1.x), as web address checks: "Router http://..."."""
    out = []
    for i, row in enumerate((setting("addresses", []) or [])[:20]):
        parts = str(row).split()
        if not parts:
            continue
        url = parts[-1]
        out.append({"id": f"addr{i}", "name": (" ".join(parts[:-1]) or url)[:60], "kind": "http", "target": url,
                    "group": QUICK_GROUP, "tags": [], "every": every_default(), "on": True, "quick": True})
    return out


def all_checks():
    return stored() + quick()


def find(cid):
    return next((c for c in all_checks() if c["id"] == cid), None)


def group_of(c):
    return c.get("group") or OTHER


def down_after():
    try:
        return max(1, min(int(setting("down_after", 2)), 10))
    except (TypeError, ValueError):
        return 2


def cert_days():
    try:
        return max(1, min(int(setting("cert_days", 14)), 90))
    except (TypeError, ValueError):
        return 14


# The state of a check --------------------------------------------------------------------------------------------------

def state_of(c, now=None):
    if not c.get("on", True):
        return "off"
    if c["kind"] == "push":
        r = ck.check_push(c, STATE["pushes"].get(c["id"]), now)
        return "waiting" if r["up"] is None else "up" if r["up"] else "down"
    live = LIVE.get(c["id"])
    if not live or live.get("up") is None:
        return "waiting"
    if live["up"]:
        return "up"
    return "down" if live.get("fails", 0) >= down_after() else "retry"


def said_of(c, now=None):
    if c["kind"] == "push":
        return ck.check_push(c, STATE["pushes"].get(c["id"]), now)["said"]
    return (LIVE.get(c["id"]) or {}).get("said") or "Not checked yet"


def in_maintenance(group, now=None):
    return win.active((groups_kept().get(group) or {}).get("windows"), now)


def days_left(cert, now=None):
    now = time.time() if now is None else now
    return int((cert["not_after"] - now) // 86400)


def cert_words(cid, now=None):
    cert = CERTS.get(cid)
    if not cert:
        return ""
    if cert.get("error"):
        return f"Not read: {cert['error']}"
    left = days_left(cert, now)
    names = ", ".join(cert.get("names") or [cert.get("subject") or "no name"])[:80]
    when = "Ran out" if left < 0 else f"{left} day{'s' if left != 1 else ''} left"
    trust = "" if cert.get("trusted") else f". Not trusted: {cert.get('why') or 'not trusted'}"
    return f"{when}, for {names}{trust}"


def record(c, result, now=None):
    now = time.time() if now is None else now
    with _lock:
        prev = LIVE.get(c["id"]) or {}
        up = bool(result.get("up"))
        fails = 0 if up else int(prev.get("fails") or 0) + 1
        changed = prev.get("up") != up or (not up and fails == down_after())
        LIVE[c["id"]] = {"up": up, "ms": result.get("ms"), "said": result.get("said", ""), "at": now, "fails": fails,
                         "since": now if prev.get("up") != up else prev.get("since", now)}
    HISTORY.add(c["id"], up, result.get("ms") if up else None, now)
    if changed:
        save_state()


def run_one(c, now=None):
    record(c, ck.run(c), now)
    target = ck.cert_target(c)
    if target and (time.time() - (CERTS.get(c["id"]) or {}).get("checked", 0) > CERT_EVERY):
        try:
            CERTS[c["id"]] = ck.fetch_cert(*target)
        except Exception as e:  # noqa: BLE001 - said on the check, never a stop
            CERTS[c["id"]] = {"error": ck._words(e), "checked": time.time()}


# Alerts through Starboard (plug-in API 1.17) ---------------------------------------------------------------------------

def _post_starboard(path, body):
    """POST to Starboard's API with the plug-in's own key, through its socket when there is one. Returns the status."""
    url = urllib.parse.urljoin(sb.API, path)
    data = json.dumps(body).encode()
    headers = {"Authorization": f"Bearer {sb._key()}", "Content-Type": "application/json", "User-Agent": sb.AGENT,
               "Accept": "application/json"}
    if sb.API_SOCKET and os.path.exists(sb.API_SOCKET):
        c = sb._SocketConnection(sb.API_SOCKET, 10)
        try:
            c.request("POST", urllib.parse.urlsplit(url).path, body=data, headers=headers)
            r = c.getresponse()
            r.read(65536)
            return r.status
        finally:
            c.close()
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:  # Starboard's own address  # nosec B310
            r.read(65536)
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def send_alert(key, state, title, message, level="problem"):
    """True when Starboard took it. Starboard without plug-in API 1.17, or without alerts:send, answers 404: then no
    more are tried for an hour, and the summary card says so."""
    api = STATE.get("alerts_api")
    if api and api.get("missing") and time.time() - api["at"] < 3600:
        return False
    try:
        status = _post_starboard("plugin/alerts", {"key": key, "state": state, "title": title[:120], "message": message[:500],
                                                    "level": level})
    except (OSError, http.client.HTTPException):
        return False
    if status in (403, 404, 405):
        STATE["alerts_api"] = {"missing": True, "at": time.time()}
        return False
    STATE["alerts_api"] = {"missing": False, "at": time.time()}
    return 200 <= status < 300


def causes(now=None):
    """Every alert there is a reason for now, paused or not: key -> (title, message, level, paused)."""
    out = {}
    alerts_on = bool(setting("alerts", True))
    kept = groups_kept()
    for c in all_checks():
        if not c.get("on", True):
            continue
        g = group_of(c)
        gk = kept.get(g) or {}
        paused = not alerts_on or gk.get("alerts") is False or bool(win.active(gk.get("windows"), now))
        if state_of(c, now) == "down":
            out[f"check-{c['id']}"] = (f"{c['name']} is down", f"{ck.KIND_WORDS[c['kind']]}: {said_of(c, now)}. Group: {g}.",
                                       "problem", paused)
        cert = CERTS.get(c["id"])
        if cert and not cert.get("error") and days_left(cert, now) <= cert_days():
            left = days_left(cert, now)
            title = f"{c['name']}'s certificate has run out" if left < 0 else f"{c['name']}'s certificate runs out in {left} days"
            out[f"cert-{c['id']}"] = (title, f"It is for {', '.join(cert.get('names') or [cert.get('subject', '')])[:200]}.",
                                      "warning", paused)
    return out


def reconcile(now=None):
    """Raises what has a reason and is not paused; clears what no longer has a reason. A check that is still down when
    its maintenance window ends is raised then. A clear is never sent just because alerts were paused."""
    want = causes(now)
    names = {f"{p}-{c['id']}": c["name"] for c in all_checks() for p in ("check", "cert")}
    changed = False
    for key, (title, message, level, paused) in want.items():
        if key not in STATE["raised"] and not paused and send_alert(key, "raised", title, message, level):
            STATE["raised"][key] = title
            changed = True
    for key in [k for k in STATE["raised"] if k not in want]:
        name = names.get(key)
        if not name:
            title = f"{STATE['raised'][key]}: the check was removed"
        elif key.startswith("check-"):
            title = f"{name} is up again"
        else:
            title = f"{name}'s certificate was renewed"
        if not setting("alerts", True) or send_alert(key, "cleared", title, "", "info"):
            STATE["raised"].pop(key, None)
            changed = True
    if changed:
        save_state()


# The rounds ---------------------------------------------------------------------------------------------------------------

def due(now):
    return [c for c in all_checks() if c.get("on", True) and c["kind"] != "push" and NEXT.get(c["id"], 0) <= now]


def round_once(now=None):
    now = time.time() if now is None else now
    todo = due(now)
    for c in todo:
        NEXT[c["id"]] = now + c.get("every", 300)
    if todo:
        with ThreadPoolExecutor(max_workers=min(WORKERS, len(todo))) as pool:
            list(pool.map(run_one, todo))
    for c in all_checks():  # heartbeats: kept in the history at most once a minute
        if c["kind"] == "push" and c.get("on", True) and now - PUSH_SAMPLED.get(c["id"], 0) >= 60:
            s = state_of(c, now)
            if s in ("up", "down"):
                HISTORY.add(c["id"], s == "up", None, now)
            PUSH_SAMPLED[c["id"]] = now
    reconcile(now)
    write_page(now)


def loop():
    time.sleep(2)
    while True:
        while sb.holding():
            time.sleep(5)
        try:
            with sb.working("checks"):
                round_once()
            sb.clear_error()
        except Exception as e:  # noqa: BLE001 - kept for the summary card, never a stop
            keep("_error", {"at": time.time(), "text": f"{type(e).__name__}: {e}"[:200]})
        nxt = min([NEXT.get(c["id"], 0) for c in all_checks() if c.get("on", True) and c["kind"] != "push"] or [time.time() + 60])
        _wake.wait(max(1, min(60, nxt - time.time())))
        _wake.clear()


# The groups -----------------------------------------------------------------------------------------------------------

def group_rows(now=None):
    """[{"name", "checks", "states", "up", "total", "maintenance": window or None, "alerts": bool}] in name order, with
    the Outside services group and Other checks last."""
    by = {}
    for c in all_checks():
        by.setdefault(group_of(c), []).append(c)
    kept = groups_kept()
    order = sorted(by, key=lambda n: (n in (OTHER, QUICK_GROUP), n.lower()))
    out = []
    for name in order:
        cs = by[name]
        states = [state_of(c, now) for c in cs]
        out.append({"name": name, "checks": cs, "states": states, "up": states.count("up"),
                    "total": len([s for s in states if s != "off"]),
                    "maintenance": win.active((kept.get(name) or {}).get("windows"), now),
                    "alerts": (kept.get(name) or {}).get("alerts") is not False})
    return out


def group_state(g):
    if g["maintenance"]:
        return "maintenance"
    if "down" in g["states"]:
        return "down"
    if g["total"] and g["up"] == g["total"]:
        return "up"
    return "waiting" if g["total"] else "off"


# The status page -----------------------------------------------------------------------------------------------------------

def page_rows(now=None):
    out = []
    for g in group_rows(now):
        w = g["maintenance"]
        rows = []
        for c, s in zip(g["checks"], g["states"], strict=True):
            if s == "off":
                continue
            live = LIVE.get(c["id"]) or {}
            rows.append({"name": c["name"], "kind": ck.KIND_WORDS[c["kind"]], "state": s,
                         "ms": live.get("ms") if s == "up" and c["kind"] != "push" else None,
                         "day": HISTORY.uptime(c["id"], 24, now), "month": HISTORY.uptime(c["id"], 30 * 24, now),
                         "quarter": HISTORY.uptime(c["id"], 90 * 24, now), "cert": cert_words(c["id"], now)})
        if rows:
            out.append({"name": g["name"], "state": group_state(g), "up": g["up"], "total": len(rows),
                        "maintenance": win.words(w) if w else "", "checks": rows})
    return out


def write_page(now=None):
    if not setting("status_page", True):
        return
    text = page.build(str(setting("status_title", "") or "Home services")[:80], page_rows(now), now)
    os.makedirs(PAGE_DIR, exist_ok=True)
    path = os.path.join(PAGE_DIR, "index.html")
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(path + ".tmp", path)


# Cards ----------------------------------------------------------------------------------------------------------------------

def _since(t, now=None):
    return ck._span_words((time.time() if now is None else now) - t) if t else ""


def summary():
    now = time.time()
    cs = [c for c in all_checks() if c.get("on", True)]
    if not cs:
        return band({"state": "warning", "text": "Add checks in Settings, Plug-ins, Uptime and status, Checks"}, "needs_setup")
    states = {c["id"]: state_of(c, now) for c in cs}
    if all(s == "waiting" for s in states.values()):
        return band({"state": "ok", "text": "Checking for the first time"}, "waiting")
    down = [c["name"] for c in cs if states[c["id"]] == "down"]
    up = sum(1 for s in states.values() if s == "up")
    if down:
        parts = [f"Down: {', '.join(down[:5])}{' and more' if len(down) > 5 else ''}"]
    elif up == len(cs):
        parts = [f"All {sb.plural(len(cs), 'check')} {'is' if len(cs) == 1 else 'are'} up"]
    else:
        parts = [f"{up} of {sb.plural(len(cs), 'check')} {'is' if up == 1 else 'are'} up, the others are not checked yet or trying again"]
    maint = [g["name"] for g in group_rows(now) if g["maintenance"]]
    if maint:
        parts.append(f"Maintenance: {', '.join(maint)}")
    api = STATE.get("alerts_api") or {}
    if setting("alerts", True) and api.get("missing"):
        parts.append("This Starboard does not take alerts from plug-ins yet: update Starboard")
    err = sb.last_error()
    if err:
        parts.append(f"Last round: {err}")
    status = "problem" if down else "warning" if err else "ok"
    return band({"state": status if status != "ok" else "ok", "text": ". ".join(parts)}, status,
                max([v.get("at") or 0 for v in LIVE.values()] or [0]) or None, "Down" if down else None)


def check_detail(c, s, now=None):
    live = LIVE.get(c["id"]) or {}
    if s == "up" and live.get("ms") is not None and c["kind"] != "push":
        words = "Up, under 1 ms" if live["ms"] < 1 else f"Up, {live['ms']:,.0f} ms"
    elif s == "up":
        words = f"Up: {said_of(c, now)}"
    elif s == "down" and c["kind"] != "push" and live.get("since"):
        words = f"Down for {_since(live['since'], now)}: {said_of(c, now)}"
    elif s == "down":
        words = f"Down: {said_of(c, now)}"
    elif s == "retry":
        words = f"Trying again: {said_of(c, now)}"
    else:
        words = WORDS[s]
    week = HISTORY.uptime(c["id"], 7 * 24, now)
    return words + (f", {page.percent(week)} this week" if week is not None and s in ("up", "retry") else "")


def checks_card():
    now = time.time()
    cs = [c for c in all_checks() if c.get("on", True)]
    if not cs:
        return band({"items": []}, "needs_setup")
    order = {"down": 0, "retry": 1, "waiting": 2, "up": 3}
    states = {c["id"]: state_of(c, now) for c in cs}
    cs.sort(key=lambda c: (order.get(states[c["id"]], 4), c["name"].lower()))
    items = []
    for c in cs[:10]:
        item = {"title": c["name"], "detail": check_detail(c, states[c["id"]], now)[:120]}
        if c["kind"] in ("http", "keyword"):
            item["link"] = c["target"]
        items.append(item)
    down = "down" in states.values()
    return band({"items": items}, "problem" if down else "ok", None, "Down" if down else None)


def groups_card():
    now = time.time()
    rows = [g for g in group_rows(now) if g["total"]]
    if not rows:
        return band({"items": []}, "needs_setup")
    items = []
    for g in rows[:10]:
        st = group_state(g)
        bits = [f"{g['up']} of {g['total']} up"]
        week = [HISTORY.uptime(c["id"], 7 * 24, now) for c in g["checks"] if c.get("on", True)]
        week = [w for w in week if w is not None]
        if week:
            bits.append(f"{page.percent(sum(week) / len(week))} this week")
        if g["maintenance"]:
            bits.append(f"maintenance {win.words(g['maintenance'])}, alerts paused")
        elif not g["alerts"]:
            bits.append("alerts paused")
        items.append({"title": f"{g['name']}: {page.TONES[st][1]}", "detail": ", ".join(bits)[:120]})
    down = any(group_state(g) == "down" for g in rows)
    return band({"items": items}, "problem" if down else "ok", None, "Down" if down else None)


def trend_card():
    """Response times (a sparkline card, plug-in API 1.17): each check's average an hour for the last 24 hours, the
    ones down first, then the slowest, up to 8."""
    now = time.time()
    cs = [c for c in all_checks() if c.get("on", True) and c["kind"] != "push"]
    if not cs:
        return band({"series": [], "note": "Add checks in the plug-in's settings"}, "needs_setup")
    points = {c["id"]: HISTORY.hourly_ms(c["id"], 24, now) for c in cs}

    def order(c):
        pts = [p for p in points[c["id"]] if p is not None]
        return (state_of(c, now) != "down", -(sum(pts) / len(pts) if pts else 0))
    series = []
    for c in sorted(cs, key=order)[:8]:
        day = HISTORY.uptime(c["id"], 24, now)
        series.append({"title": c["name"], "points": points[c["id"]], "unit": "ms",
                       "detail": f"Up {page.percent(day)} of the last 24 hours" if day is not None else "No checks yet"})
    down = any(state_of(c, now) == "down" for c in cs)
    return band({"series": series, "note": "Average each hour, the last 24 hours. A gap is an hour with no answer."},
                "problem" if down else "ok", None, "Down" if down else None)


def certs_card():
    now = time.time()
    rows = [(c, CERTS[c["id"]]) for c in all_checks() if c["id"] in CERTS and not CERTS[c["id"]].get("error")]
    if not rows:
        return band({"items": []}, "idle")
    rows.sort(key=lambda r: r[1]["not_after"])
    items = [{"title": c["name"], "detail": cert_words(c["id"], now)[:120]} for c, _ in rows[:10]]
    soon = any(days_left(cert, now) <= cert_days() for _, cert in rows)
    return band({"items": items}, "warning" if soon else "ok", None, "Runs out soon" if soon else None)


def run_now():
    NEXT.clear()
    for cert in CERTS.values():
        cert["checked"] = 0
    _wake.set()
    return {"said": "Checking everything now"}


# Settings, Plug-ins: the Checks and Groups pages (custom settings, drawn by Starboard) ------------------------------------

INTRO = ("Each check is one line: a name, a colon, then what to check. Router: ping 192.168.1.1 in Home. Website: http "
         "https://example.org. Shop: keyword https://example.org/shop \"In stock\". NAS: tcp 192.168.1.5:445. Home name: dns "
         "example.org A. Backup: push grace 25h gives an address for the backup to call. Add #tags, or every 1m to check "
         "more often.")


def push_address(c):
    home = os.environ.get("STARBOARD_HOME_ADDRESS", "").rstrip("/")
    return f"{home}/push/{c['token']}" if home else f"/push/{c['token']} at this plug-in's address on your home network"


def checks_page(said=None):
    now = time.time()
    items = []
    for c in all_checks():
        s = state_of(c, now)
        bits = [ck.KIND_WORDS[c["kind"]], check_detail(c, s, now)]
        cert = cert_words(c["id"], now)
        if cert:
            bits.append(f"Certificate: {cert}")
        if c.get("tags"):
            bits.append("Tags: " + ", ".join(c["tags"]))
        if c.get("quick"):
            bits.append("From Addresses to check, in this plug-in's Settings")
        item = {"id": c["id"], "title": c["name"], "detail": ". ".join(bits)[:200], "state": CUSTOM_STATE[s],
                "state_label": WORDS[s], "group": group_of(c), "on": c.get("on", True),
                "address": push_address(c) if c["kind"] == "push" else c["target"],
                "actions": ["test"] if c.get("quick") else ["test", "toggle", "attach", "remove"]}
        if not c.get("quick"):
            item["attach"] = {"label": "Change", "field": "The check, as one line", "value": ck.line(c),
                              "hint": "Change the line and save. Its history stays."}
        items.append(item)
    out = {"type": "list", "title": "Checks", "intro": INTRO,
           "add": {"label": "Add a check", "placeholder": "Router: ping 192.168.1.1 in Home",
                   "hint": "A name, a colon, then http, keyword, tcp, ping, dns or push and what to check"},
           "items": items}
    if said:
        out["said"] = said
    return out


class Refused(ValueError):
    pass


def _test(c):
    if c["kind"] == "push":
        return f"{c['name']}: {said_of(c)}"
    run_one(c)
    reconcile()
    write_page()
    s = state_of(c)
    return f"{c['name']}: {'Down once, trying again' if s == 'retry' else WORDS[s]}. {said_of(c)}"


def checks_action(body):
    action, cid, value = body.get("action"), str(body.get("id") or ""), str(body.get("value") or "")
    with _lock:
        rows = stored()
        c = next((r for r in rows if r["id"] == cid), None)
        if action == "add":
            if len(rows) >= MAX_CHECKS:
                raise Refused(f"Up to {MAX_CHECKS} checks")
            new = ck.parse(value, every_default())
            new["id"] = uuid.uuid4().hex[:10]
            rows.append(new)
            store(rows)
            _wake.set()
            extra = f" Give it this address to call: {push_address(new)}" if new["kind"] == "push" else " It is checked now."
            return checks_page(f"Added {new['name']}.{extra}")
        if action == "test_all":
            return checks_page(run_now()["said"])
        if action == "test":
            target = c or find(cid)
            if not target:
                raise Refused("That check is not there any more")
            return checks_page(_test(target))
        if not c:
            raise Refused("Change it in Addresses to check, in this plug-in's Settings" if cid.startswith("addr") else
                          "That check is not there any more")
        if action == "toggle":
            c["on"] = not c.get("on", True)
            store(rows)
            _wake.set()
            return checks_page(f"{c['name']} is {'checked again' if c['on'] else 'paused: it is not checked and sends no alerts'}.")
        if action == "remove":
            rows.remove(c)
            store(rows)
            HISTORY.forget(c["id"])
            LIVE.pop(c["id"], None)
            CERTS.pop(c["id"], None)
            NEXT.pop(c["id"], None)
            STATE["pushes"].pop(c["id"], None)
            reconcile()
            save_state()
            return checks_page(f"Removed {c['name']} and its history.")
        if action == "attach":
            new = ck.parse(value, every_default())
            new["id"], new["on"] = c["id"], c.get("on", True)
            if new["kind"] == "push" and c["kind"] == "push":
                new["token"] = c["token"]  # its address stays the same
            if (new["kind"], new.get("target")) != (c["kind"], c.get("target")):
                LIVE.pop(c["id"], None)
                CERTS.pop(c["id"], None)
            rows[rows.index(c)] = new
            store(rows)
            NEXT.pop(c["id"], None)
            _wake.set()
            return checks_page(f"Changed {new['name']}.")
    raise Refused("Starboard asked for something this list does not do")


def groups_page(said=None):
    now = time.time()
    kept_all = groups_kept()
    items = []
    for g in group_rows(now):
        w = g["maintenance"]
        kept = (kept_all.get(g["name"]) or {}).get("windows") or []
        bits = [f"{g['up']} of {g['total']} up" if g["total"] else "Every check in it is paused"]
        bits.append("Alerts on" if g["alerts"] else "Alerts paused")
        if kept:
            bits.append("Maintenance: " + "; ".join(win.words(x) for x in kept) + (" (on now)" if w else ""))
        st = group_state(g)
        items.append({"id": g["name"], "title": g["name"], "detail": ". ".join(bits)[:200],
                      "state": "off" if st == "maintenance" else CUSTOM_STATE.get(st, "unknown"),
                      "state_label": page.TONES[st][1], "on": g["alerts"], "actions": ["toggle", "attach", "detach"],
                      "attach": {"label": "Maintenance", "field": "Maintenance windows", "value": win.line(kept),
                                 "hint": "Such as Sunday 02:00 to 04:00; now for 2 hours. Split several with ;"}})
    out = {"type": "list", "title": "Groups and maintenance",
           "intro": ("A group is made when a check names it with in, such as Router: ping 192.168.1.1 in Home. Deactivate a "
                     "group to pause its alerts. Maintenance windows pause them at set times: its checks still run, and "
                     "the status page says Maintenance."),
           "items": items}
    if said:
        out["said"] = said
    return out


def groups_action(body):
    action, name, value = body.get("action"), str(body.get("id") or "")[:40], str(body.get("value") or "")
    if name not in [g["name"] for g in group_rows()]:
        raise Refused("That group has no checks any more")
    with _lock:
        kept = groups_kept()
        g = kept.setdefault(name, {})
        if action == "toggle":
            g["alerts"] = g.get("alerts") is False
            keep_groups(kept)
            reconcile()
            return groups_page(f"Alerts for {name} are {'on' if g['alerts'] else 'paused. Its checks still run'}.")
        if action in ("attach", "detach"):
            g["windows"] = win.live(win.parse(value)) if action == "attach" else []
            keep_groups(kept)
            reconcile()
            write_page()
            if not g["windows"]:
                return groups_page(f"{name} has no maintenance windows.")
            return groups_page(f"{name}: maintenance {'; '.join(win.words(w) for w in g['windows'])}.")
    raise Refused("Starboard asked for something this list does not do")


# Heartbeats ------------------------------------------------------------------------------------------------------------

def push(token, query):
    for c in stored():
        if c["kind"] == "push" and hmac.compare_digest(str(c.get("token", "")).encode(), token.encode()):
            down = (query.get("status") or [""])[0].lower() in ("down", "fail", "failed", "error")
            msg = (query.get("msg") or [""])[0][:120]
            with _lock:
                STATE["pushes"][c["id"]] = {"at": time.time(), "down": down, "said": msg}
            HISTORY.add(c["id"], not down, None)
            PUSH_SAMPLED[c["id"]] = time.time()
            save_state()
            _wake.set()
            return True
    return False


# The web server: Starboard's calls, the status page and heartbeats on one port ----------------------------------------------

def _key_ok(header):
    key = sb._key()
    return bool(key) and hmac.compare_digest(key.encode(), str(header or "").encode())


ROUTES = {("GET", "/health"): lambda: {"ok": True}, ("GET", "/status"): summary, ("GET", "/card"): checks_card,
          ("GET", "/groups"): groups_card, ("GET", "/trend"): trend_card, ("GET", "/certs"): certs_card,
          ("POST", "/run"): run_now}
PAGE_HEADERS = {"Cache-Control": "no-cache", "X-Frame-Options": "DENY",
                "Content-Security-Policy": "default-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"}


def before_update(body=None):
    HISTORY.save()
    save_state()
    return sb.before_update(body)


class Handler(BaseHTTPRequestHandler):
    server_version = "Starboard-plug-in"
    sys_version = ""

    def _send(self, status, body, kind="application/json", extra=None):
        if isinstance(body, bytes):
            data = body
        else:
            data = json.dumps(body).encode() if kind == "application/json" else body.encode()
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            got = json.loads(self.rfile.read(min(n, 65536)) or b"{}") if n else {}
        except ValueError:
            got = {}
        return got if isinstance(got, dict) else {}

    def _page(self, path):
        if path in STATIC:
            name, kind = STATIC[path]
            with open(os.path.join(HERE, name), "rb") as f:
                return self._send(200, f.read(), kind, {"Cache-Control": "max-age=86400"})
        if not setting("status_page", True):
            return self._send(404, "<!doctype html><html lang=\"en-GB\"><title>Status page</title><h1>Status page</h1>"
                              "<p>The status page is deactivated in Starboard.</p></html>", "text/html; charset=utf-8", PAGE_HEADERS)
        path = os.path.join(PAGE_DIR, "index.html")
        if not os.path.isfile(path):
            write_page()
        with open(path, "rb") as f:
            return self._send(200, f.read(), "text/html; charset=utf-8", PAGE_HEADERS)

    def _answer(self, method):
        url = urllib.parse.urlparse(self.path)
        path = url.path
        try:
            if path.startswith("/push/"):
                if push(path[6:], urllib.parse.parse_qs(url.query)):
                    return self._send(200, {"ok": True})
                return self._send(404, {"error": "No heartbeat has this address"})
            if path.startswith("/manage/"):
                if not _key_ok(self.headers.get("X-Api-Key")):
                    return self._send(401, {"error": "Only Starboard may use this"})
                fns = {"/manage/checks": (checks_page, checks_action), "/manage/groups": (groups_page, groups_action)}.get(path)
                if not fns:
                    return self._send(404, {"error": "Not found"})
                return self._send(200, fns[0]() if method == "GET" else fns[1](self._body()))
            if method in ("GET", "HEAD") and (path in ("/", "/index.html") or path in STATIC):
                return self._page(path)
            if method == "POST" and path == "/update/before":
                return self._send(200, before_update(self._body()))
            if method == "POST" and path == "/update/after":
                return self._send(200, sb.after_update(self._body()))
            fn = ROUTES.get(("GET" if method == "HEAD" else method, path))
            if not fn:
                return self._send(404, {"error": "Not found"})
            return self._send(200, fn())
        except (ck.LineError, win.WindowError, Refused) as e:
            return self._send(400, {"error": str(e)[:200]})
        except Exception as e:  # noqa: BLE001 - Starboard shows the message
            return self._send(502, {"error": f"{e}"[:200]})

    def do_GET(self):  # noqa: N802
        self._answer("GET")

    def do_HEAD(self):  # noqa: N802
        self._answer("HEAD")

    def do_POST(self):  # noqa: N802
        self._answer("POST")

    def log_message(self, *a):
        pass


def _stop(*_):
    """On SIGTERM (docker stop): the history and state are written by another thread, so a lock the interrupted code
    holds cannot block it, then the process ends at once without waiting for a round's threads."""
    def finish():
        try:
            HISTORY.save()
            save_state()
        finally:
            os._exit(0)
    threading.Thread(target=finish, daemon=True).start()


def main(port=8080):
    load()
    signal.signal(signal.SIGTERM, _stop)
    threading.Thread(target=loop, daemon=True).start()
    port = int(os.environ.get("PORT", port))
    print(f"Listening on {port}", flush=True)
    # Wakes once a minute to look for a shutdown, not twice a second (lighter at rest).
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever(poll_interval=60)  # inside its own container  # nosec B104


if __name__ == "__main__":
    main()
