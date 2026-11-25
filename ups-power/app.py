"""UPS and power: load, battery and runtime of a UPS on a card, and an alert when the mains power is lost.

It reads the UPS through NUT (the Network UPS Tools server, upsd, on port 3493) or through PeaNUT, the web page that
sits in front of NUT. It asks once a minute, keeps the last answer and a short history in /data, and raises or clears
Starboard alerts (plug-in API 1.17). The cards read what it kept, so a card never asks the UPS. A password is a secret
setting: read from the settings each time and never written to /data, a card or an error message.

How each is read (from their own documentation; neither was tried against a real UPS, see the help):
- NUT: the text protocol on TCP port 3493. LIST UPS, then LIST VAR <ups>; each variable is VAR <ups> <name> "<value>".
  No sign-in is needed to read.
- PeaNUT: GET <address>/api/v1/devices/<ups> (or /api/v1/devices for the first one), with HTTP Basic sign-in when it is on.
  Its answer is NUT's variables, flat (battery.charge) or nested (battery: {charge}); both are read.

Pausing heavy jobs while on battery is not here: a plug-in cannot pause Starboard's jobs (see the help).
"""
import base64
import http.client
import json
import os
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request

import sbplugin as sb
from sbplugin import band, keep, remember, serve, setting

STATE = {"alerts_api": None, "failures": 0}
HOUR = 3600
SAMPLE_EVERY = 300  # a point on the history every 5 minutes
HISTORY = 96  # 8 hours of points
ASK_EVERY = 60
MAX_LINES = 600
MAX_BYTES = 128 * 1024
NUT_PORT = 3493
# ups.status words (NUT's docs/new-drivers.txt): OL online, OB on battery, LB low battery, RB replace battery, CHRG, DISCHRG, OVER, BYPASS
STATUS_WORDS = {"OL": "on mains power", "OB": "on battery", "LB": "low battery", "RB": "replace the battery", "CHRG": "charging",
                "DISCHRG": "discharging", "OVER": "overloaded", "BYPASS": "in bypass", "TRIM": "trimming a high voltage", "BOOST": "boosting a low voltage",
                "OFF": "off", "CAL": "calibrating", "FSD": "shutting down"}


# Words ---------------------------------------------------------------------------------------------------------

def clean(text):
    """An error with the password and the user name taken out."""
    text = str(text)
    for key in ("password", "user"):
        v = str(setting(key, "") or "")
        if v:
            text = text.replace(v, "***")
    return text[:200]


def minutes_words(seconds):
    m = round(float(seconds) / 60)
    if m < 1:
        return "under a minute"
    if m < 90:
        return f"{m} minute{'s' if m != 1 else ''}"
    h, r = divmod(m, 60)
    return f"{h} h {r} min" if r else f"{h} hours"


def number(v):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def _why(e):
    code = getattr(e, "code", None)
    if code in (401, 403):
        return "it refused the user name or password"
    if code == 404:
        return "the address does not answer like PeaNUT (is it the right address?)"
    if code:
        return f"it answered with error {code}"
    if isinstance(e, socket.timeout) or "timed out" in str(e):
        return "it did not answer in time"
    if isinstance(e, ConnectionRefusedError):
        return "nothing is listening at that address and port"
    if isinstance(e, (OSError, http.client.HTTPException)):
        return "it could not be reached"
    return clean(e)


# NUT -----------------------------------------------------------------------------------------------------------

def parse_value(text):
    """A NUT quoted string: "..." with \\" and \\\\ escapes."""
    t = text.strip()
    if len(t) >= 2 and t[0] == '"' and t[-1] == '"':
        t = t[1:-1]
    return re.sub(r"\\(.)", r"\1", t)


def parse_nut(lines, ups=None):
    """Variables (and the UPS names) from the lines of a LIST UPS and a LIST VAR answer."""
    names, out = [], {}
    for line in lines:
        if line.startswith("UPS "):
            rest = line[4:].split(" ", 1)
            names.append(rest[0])
        elif line.startswith("VAR "):
            parts = line[4:].split(" ", 2)
            if len(parts) == 3:
                out[parts[1][:80]] = parse_value(parts[2])[:200]
    return names, out


def _exchange(f, command, deadline):
    f.write(command.encode() + b"\n")
    f.flush()
    lines, total = [], 0
    while len(lines) < MAX_LINES:
        if time.monotonic() > deadline:
            raise socket.timeout("too slow")
        raw = f.readline(2048)
        if not raw:
            raise OSError("the connection closed")
        total += len(raw)
        if total > MAX_BYTES:
            raise ValueError("it sent too much")
        line = raw.decode("utf-8", "replace").rstrip("\r\n")
        if line.startswith("ERR "):
            raise ValueError("NUT said: " + line[4:60])
        if line.startswith("END LIST") or not command.startswith("LIST"):
            return lines
        lines.append(line)
    raise ValueError("it sent too many lines")


def host_port(text):
    t = str(text or "").strip()
    if t.startswith("["):  # [::1]:3493
        host, _, rest = t[1:].partition("]")
        return host, int(rest[1:]) if rest[1:].isdigit() else NUT_PORT
    if t.count(":") == 1:
        host, port = t.split(":")
        if port.isdigit():
            return host, int(port)
    return t, NUT_PORT


def read_nut(host, port, ups="", timeout=6):
    deadline = time.monotonic() + 2 * timeout
    with socket.create_connection((host, port), timeout=timeout) as s:
        s.settimeout(timeout)
        f = s.makefile("rwb")
        try:
            names, _ = parse_nut(_exchange(f, "LIST UPS", deadline))
            if not names:
                raise ValueError("NUT has no UPS listed")
            chosen = ups or names[0]
            if chosen not in names:
                raise ValueError(f"NUT has no UPS called {chosen[:30]} (it has {', '.join(names)[:80]})")
            _, got = parse_nut(_exchange(f, f"LIST VAR {chosen}", deadline))
            try:
                f.write(b"LOGOUT\n")
                f.flush()
            except OSError:
                pass
            return chosen, got
        finally:
            f.close()


# PeaNUT --------------------------------------------------------------------------------------------------------

def flatten(value, prefix="", out=None):
    """NUT variables from a flat or a nested JSON object: {"battery.charge": 100} or {"battery": {"charge": 100}}."""
    out = {} if out is None else out
    if isinstance(value, dict):
        for k, v in value.items():
            if len(out) > 400:
                break
            flatten(v, f"{prefix}.{k}" if prefix else str(k), out)
    elif isinstance(value, (str, int, float, bool)) and prefix:
        out[prefix[:80]] = str(value)[:200]
    return out


def read_peanut(base, ups="", user="", password=""):
    h = {}
    if user or password:
        h["Authorization"] = "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()
    base = base.rstrip("/")
    name = ups
    if ups:
        got = sb.fetch(f"{base}/api/v1/devices/{urllib.parse.quote(ups, safe='')}", h, timeout=10, limit=256 * 1024)
    else:
        got = sb.fetch(f"{base}/api/v1/devices?meta=true", h, timeout=10, limit=256 * 1024)
        if isinstance(got, list):
            got = got[0] if got else {}
        elif isinstance(got, dict) and got and all(isinstance(v, dict) for v in got.values()):
            # {"rack": {...its variables...}}, a device by name; but {"battery": {...}, "ups": {...}} is one UPS's variables, nested
            for k, v in got.items():
                inner = flatten(v)
                if "ups.status" in inner or "battery.charge" in inner:
                    name, got = k, v
                    break
    v = flatten(got)
    name = name or v.get("peanut.device_id") or v.get("device.model") or "UPS"
    return name[:60], v


def read_ups():
    tool = setting("tool", "nut")
    if tool == "peanut":
        base = str(setting("peanut_address", "") or "")
        if not base:
            raise ValueError("Enter PeaNUT's address first")
        return read_peanut(base, str(setting("ups", "") or ""), str(setting("user", "") or ""), str(setting("password", "") or ""))
    host = str(setting("host", "") or "")
    if not host:
        raise ValueError("Enter the NUT server's address first")
    h, p = host_port(host)
    return read_nut(h, p, str(setting("ups", "") or ""))


# What the variables mean ---------------------------------------------------------------------------------------

def summarise(name, v):
    """The figures a card needs, from NUT's variables."""
    flags = [w for w in str(v.get("ups.status", "")).upper().split() if w]
    charge, runtime, load = number(v.get("battery.charge")), number(v.get("battery.runtime")), number(v.get("ups.load"))
    on_battery = "OB" in flags
    return {"name": name, "model": " ".join(x for x in (v.get("device.mfr") or v.get("ups.mfr"), v.get("device.model") or v.get("ups.model")) if x)[:80],
            "flags": flags, "on_battery": on_battery, "low": "LB" in flags, "replace": "RB" in flags,
            "charge": charge, "runtime": runtime, "load": load, "input": number(v.get("input.voltage")),
            "output": number(v.get("output.voltage")), "watts": number(v.get("ups.realpower")),
            "known": bool(flags) or charge is not None}


def low_percent():
    try:
        return max(0, min(int(setting("low_percent", 30)), 99))
    except (TypeError, ValueError):
        return 30


def low_minutes():
    try:
        return max(0, min(int(setting("low_minutes", 5)), 600))
    except (TypeError, ValueError):
        return 5


def problems(u):
    """key -> (title, message, level) for what needs a person's attention now."""
    out = {}
    if not u or not u.get("known"):
        return out
    name = u["name"]
    if u["on_battery"]:
        left = f" About {minutes_words(u['runtime'])} left." if u.get("runtime") is not None else ""
        pct = f" The battery is at {u['charge']:.0f}%." if u.get("charge") is not None else ""
        out["mains"] = (f"Mains power lost: {name} is on battery", f"The UPS has switched to its battery.{pct}{left}", "problem")
    low = u["low"] or (u["on_battery"] and ((u["charge"] is not None and u["charge"] <= low_percent())
                                             or (u["runtime"] is not None and u["runtime"] <= low_minutes() * 60)))
    if low:
        out["low"] = (f"Low battery: {name}", "The battery is nearly flat. Save your work: the server may shut down soon.", "problem")
    if u["replace"]:
        out["replace"] = (f"Replace the battery: {name}", "The UPS says its battery needs replacing.", "warning")
    return out


# Alerts ----------------------------------------------------------------------------------------------------------

def _post_starboard(path, body):
    url = urllib.parse.urljoin(sb.API, path)
    data = json.dumps(body).encode()
    headers = {"Authorization": f"Bearer {sb._key()}", "Content-Type": "application/json", "User-Agent": sb.AGENT, "Accept": "application/json"}
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
    """True when Starboard took it. A Starboard without plug-in API 1.17, or without alerts:send, answers 404."""
    api = STATE.get("alerts_api")
    if api and api.get("missing") and time.time() - api["at"] < HOUR:
        return False
    try:
        status = _post_starboard("plugin/alerts", {"key": key, "state": state, "title": title[:120], "message": message[:500], "level": level})
    except (OSError, http.client.HTTPException):
        return False
    STATE["alerts_api"] = {"missing": status in (403, 404, 405), "at": time.time()}
    return 200 <= status < 300


def alert(want, now):
    """Raises each problem once and clears it when it is over; what was raised is kept, so a restart sends nothing twice."""
    raised = dict(remember("raised", {}) or {})
    if setting("alerts", True) is not True:
        want = {}
    for key, (title, message, level) in want.items():
        if key not in raised and send_alert(key, "raised", title, message, level):
            raised[key] = now
    for key in [k for k in raised if k not in want]:
        title = {"mains": "Mains power is back", "low": "The battery is no longer low", "replace": "The battery was replaced", "unreachable": "The UPS answers again"}.get(key, "Fine again")
        if send_alert(key, "cleared", title, ""):
            del raised[key]
    if raised != (remember("raised", {}) or {}):
        keep("raised", raised)


# The job and what is kept --------------------------------------------------------------------------------------

def check(now=None):
    """Ask the UPS, keep what it said, and alert."""
    now = now if now is not None else time.time()
    state = remember("state", {}) or {}
    try:
        name, v = read_ups()
        STATE["failures"] = 0
    except Exception as e:  # noqa: BLE001 - said on the card, never a stop
        STATE["failures"] += 1
        words = f"{'PeaNUT' if setting('tool', 'nut') == 'peanut' else 'NUT'}: {_why(e)}"
        keep("state", {**state, "error": words, "checked": now})
        if STATE["failures"] >= 3:  # three minutes of silence is worth saying; one missed answer is not
            alert({"unreachable": ("The UPS cannot be reached", f"Starboard cannot read the UPS: {words}.", "warning")}, now)
        return {"said": f"Could not read the UPS: {words}"}
    u = summarise(name, v)
    hist = list(state.get("history") or [])
    if not hist or now - hist[-1]["at"] >= SAMPLE_EVERY - 5 or (hist and hist[-1].get("ob") != u["on_battery"]):
        hist.append({"at": int(now), "load": u["load"], "charge": u["charge"], "runtime": u["runtime"], "ob": u["on_battery"]})
    hist = hist[-HISTORY:]
    events = list(state.get("events") or [])
    if state.get("ups") and bool(state["ups"].get("on_battery")) != u["on_battery"]:
        events.append({"at": int(now), "what": "Switched to battery" if u["on_battery"] else "Mains power came back"})
    keep("state", {"ups": u, "history": hist, "events": events[-10:], "checked": now})
    alert(problems(u), now)
    return {"said": f"{u['name']}: {'on battery' if u['on_battery'] else 'on mains power'}" + (f", battery {u['charge']:.0f}%" if u["charge"] is not None else "")}


def _state():
    return remember("state", {}) or {}


def _configured():
    return bool(setting("peanut_address") if setting("tool", "nut") == "peanut" else setting("host"))


def _needs():
    s = _state()
    if not _configured():
        return band({"state": "warning", "text": "Choose how to read the UPS and enter its address in Settings, Plug-ins, UPS and power."}, "needs_setup", label="Needs setting up")
    if s.get("error") and not s.get("ups"):
        return band({"state": "problem", "text": s["error"]}, "problem", s.get("checked"), "Cannot read it")
    if not s.get("ups"):
        return band({"state": "ok", "text": "Waiting for the first reading, which comes within a minute."}, "scheduled")
    return None


def _fresh(s):
    """The last reading is old when the plug-in could not ask for a while (it is asked once a minute)."""
    return time.time() - s.get("checked", 0) < 10 * ASK_EVERY


def card():
    n = _needs()
    if n:
        return n
    s = _state()
    u = s["ups"]
    if not _fresh(s) or s.get("error"):
        return band({"state": "warning", "text": f"The last reading failed: {s.get('error', 'it is old')}"[:160]}, "warning", s["checked"], "Last reading failed")
    bits = []
    if u["charge"] is not None:
        bits.append(f"battery {u['charge']:.0f}%")
    if u["runtime"] is not None:
        bits.append(f"about {minutes_words(u['runtime'])} left")
    if u["load"] is not None:
        bits.append(f"load {u['load']:.0f}%")
    tail = ", ".join(bits)
    bad = problems(u)
    if "low" in bad:
        return band({"state": "problem", "text": f"Low battery on {u['name']}: {tail}."[:160]}, "problem", s["checked"], "Low battery")
    if u["on_battery"]:
        return band({"state": "problem", "text": f"On battery power: {tail}."[:160]}, "problem", s["checked"], "On battery")
    if u["replace"]:
        return band({"state": "warning", "text": f"On mains power, but the battery needs replacing: {tail}."[:160]}, "warning", s["checked"], "Replace the battery")
    if not u["known"]:
        return band({"state": "warning", "text": "The UPS answered, but with no status or battery figure."}, "warning", s["checked"], "Nothing to show")
    return band({"state": "ok", "text": f"On mains power: {tail}."[:160]}, "ok", s["checked"], "On mains power")


def details():
    n = _needs()
    if n:
        return band({"items": []}, n["status"], label=n.get("status_label"))
    s = _state()
    u = s["ups"]
    items = [{"title": u["name"] + (f" ({u['model']})" if u["model"] else ""), "detail": ", ".join(STATUS_WORDS.get(f, f).capitalize() if i == 0 else STATUS_WORDS.get(f, f) for i, f in enumerate(u["flags"])) or "No status"}]
    for title, key, unit, fmt in (("Battery", "charge", "%", "{:.0f}"), ("Time left on battery", "runtime", "", None), ("Load", "load", "%", "{:.0f}"),
                                  ("Power in", "input", " V", "{:.0f}"), ("Power out", "output", " V", "{:.0f}"), ("Power used", "watts", " W", "{:.0f}")):
        if u.get(key) is None:
            continue
        items.append({"title": title, "detail": minutes_words(u[key]) if key == "runtime" else fmt.format(u[key]) + unit})
    for e in reversed(s.get("events") or []):
        items.append({"title": e["what"], "detail": time.strftime("%a %d %b %H:%M", time.localtime(e["at"]))})
        break
    return band({"items": items[:12]}, "problem" if u["on_battery"] else "ok", s["checked"], "On battery" if u["on_battery"] else None)


def _nothing(why):
    """A sparkline card must have a series (Starboard checks): one with no points to draw, saying why."""
    return {"series": [{"title": "No readings yet", "points": [None], "unit": "", "detail": why[:120]}]}


def history():
    n = _needs()
    if n:
        return band(_nothing(n.get("text") or "Nothing to show yet."), n["status"], label=n.get("status_label"))
    s = _state()
    h = s.get("history") or []
    series = []
    for title, key, unit, scale in (("Load", "load", "%", 1), ("Battery", "charge", "%", 1), ("Time left", "runtime", " min", 1 / 60)):
        pts = [None if p.get(key) is None else round(p[key] * scale, 1) for p in h]
        if any(p is not None for p in pts):
            series.append({"title": title, "points": pts[-96:], "unit": unit.strip(),
                           "detail": f"Latest {pts[-1]:g}{unit}" if pts and pts[-1] is not None else "No reading"})
    if not series:
        return band(_nothing("The UPS reports no load or battery figure."), "warning", s["checked"], "Nothing to show")
    lost = sum(1 for p in h if p.get("ob"))
    note = f"One point every 5 minutes for the last {len(h) * 5 // 60 or 1} hours." + (f" {lost} on battery." if lost else "")
    return band({"series": series, "note": note}, "ok", s["checked"])


def refresh():
    out = check()
    return out


def start():
    sb.every(ASK_EVERY, check, first=3)


ROUTES = {"/card": card, "/details": details, "/history": history, ("POST", "/check"): refresh}

if __name__ == "__main__":
    start()
    serve(ROUTES, port=int(os.environ.get("PORT", 8080)))
