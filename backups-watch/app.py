"""Backups watch: the last run, size and failures of a Backrest or Kopia backup, and an alert when one is overdue.

Starboard runs its job once an hour and the container rests between runs (start: when_needed). The job asks the backup
tool once, keeps the answer in /data/state.json, and raises or clears Starboard alerts (plug-in API 1.17). The cards
only read that file, so a card never wakes the backup tool. The tool's password is a secret setting: it is read from the
settings each time and never written to /data, a card or an error message.

How each tool is read (from its own documentation; neither was tried against the real program, see the help):
- Backrest: POST <address>/v1.Backrest/GetSummaryDashboard, a Connect RPC with a JSON body of {}; one summary per plan.
- Kopia: GET <address>/api/v1/control/sources, the server control API, with HTTP Basic sign-in; one entry per source.
"""
import base64
import http.client
import json
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

import sbplugin as sb
from sbplugin import band, keep, remember, serve, setting

TOOLS = {"backrest": "Backrest", "kopia": "Kopia"}
KEEP_RUNS = 30  # runs kept for each backup, for the size card
HOUR = 3600
STATE = {"alerts_api": None}


# Words ---------------------------------------------------------------------------------------------------------

def size_words(n):
    n = float(n or 0)
    for unit in ("bytes", "KB", "MB", "GB", "TB"):
        if n < 1000 or unit == "TB":
            return f"{n:.0f} {unit}" if unit in ("bytes", "KB") else f"{n:.1f} {unit}"
        n /= 1000


def ago(seconds):
    if seconds < 90:
        return "a moment ago"
    if seconds < 3600 * 1.5:
        return f"{round(seconds / 60)} minutes ago"
    if seconds < 3600 * 36:
        return f"{round(seconds / 3600)} hours ago"
    return f"{round(seconds / 86400)} days ago"


def clean(text):
    """An error with the password, the user name and the address's own sign-in taken out."""
    text = str(text)
    for key in ("password", "user"):
        v = str(setting(key, "") or "")
        if v:
            text = text.replace(v, "***")
    return text[:200]


def _why(e):
    code = getattr(e, "code", None)
    if code in (401, 403):
        return "it refused the user name or password"
    if code == 404:
        return "the address does not answer like this tool (is it the right address and tool?)"
    if code:
        return f"it answered with error {code}"
    if isinstance(e, ssl.SSLError) or "CERTIFICATE" in str(e).upper():
        return "its certificate is not trusted (Accept a self-signed certificate lets this plug-in use it)"
    if isinstance(e, (OSError, http.client.HTTPException)):
        return "it could not be reached"
    return clean(e)


# Reading the tools ---------------------------------------------------------------------------------------------

def _context():
    if setting("self_signed", False) is True:
        c = ssl.create_default_context()
        c.check_hostname, c.verify_mode = False, ssl.CERT_NONE
        return c
    return None


def _headers():
    user, password = str(setting("user", "") or ""), str(setting("password", "") or "")
    h = {"User-Agent": sb.AGENT, "Accept": "application/json"}
    if user or password:
        h["Authorization"] = "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()
    return h


def _call(url, body=None):
    h = _headers()
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        h.update({"Content-Type": "application/json", "Connect-Protocol-Version": "1"})
    req = urllib.request.Request(url, data=data, headers=h, method="POST" if body is not None else "GET")
    with urllib.request.urlopen(req, timeout=15, context=_context()) as r:  # the address the owner gave  # nosec B310
        return json.loads(r.read(sb.MAX) or b"null")


def _int(v):
    try:
        return int(v)  # protobuf JSON writes 64 bit numbers as text
    except (TypeError, ValueError):
        return 0


def _epoch(text):
    """A time such as 2026-11-22T03:00:12.5Z or with +00:00, in seconds since 1970; 0 when it is not one."""
    t = str(text or "")
    if not t or t.startswith("0001"):
        return 0
    try:
        import datetime as dt
        t = t.replace("Z", "+00:00")
        if "." in t:  # more than six decimals is more than Python reads
            head, _, rest = t.partition(".")
            frac = "".join(ch for ch in rest if ch.isdigit())[:6]
            tail = rest[len([ch for ch in rest if ch.isdigit()]):]
            t = f"{head}.{frac}{tail}"
        d = dt.datetime.fromisoformat(t)
        if d.tzinfo is None:
            d = d.replace(tzinfo=dt.timezone.utc)
        return int(d.timestamp())
    except ValueError:
        return 0


OK_WORDS = ("SUCCESS", "WARNING")


def read_backrest(answer):
    """Backrest's GetSummaryDashboard: one summary for each plan. The newest run and the newest good run come from its
    recent_backups chart, which lists each run's time, status and bytes added in step (arrays of the same length)."""
    out = []
    for p in (answer or {}).get("planSummaries") or (answer or {}).get("plan_summaries") or []:
        chart = p.get("recentBackups") or p.get("recent_backups") or {}
        times = [_int(x) for x in chart.get("timestampMs") or chart.get("timestamp_ms") or []]
        states = chart.get("status") or []
        added = [_int(x) for x in chart.get("bytesAdded") or chart.get("bytes_added") or []]
        runs = []
        for i, t in enumerate(times):
            st = str(states[i]) if i < len(states) else ""
            runs.append({"at": t // 1000, "ok": any(w in st.upper() for w in OK_WORDS), "added": added[i] if i < len(added) else 0})
        runs.sort(key=lambda r: r["at"])
        last = runs[-1] if runs else None
        good = [r for r in runs if r["ok"]]
        out.append({"name": str(p.get("id") or "Plan"), "last": last["at"] if last else 0, "last_ok": good[-1]["at"] if good else 0,
                    "last_failed": bool(last and not last["ok"]),
                    "failures": _int(p.get("backupsFailed30days") or p.get("backups_failed_30days")),
                    "size": _int(p.get("protectedBytes") or p.get("protected_bytes")),
                    "next": _int(p.get("nextBackupTimeMs") or p.get("next_backup_time_ms")) // 1000, "runs": runs[-KEEP_RUNS:]})
    return out


def read_kopia(answer):
    """Kopia's control API: each source's last snapshot, with its times, size and the number of files it could not read."""
    out = []
    for s in (answer or {}).get("sources") or []:
        src = s.get("source") or {}
        snap = s.get("lastSnapshot") or {}
        name = f"{src.get('userName', '')}@{src.get('host', '')}:{src.get('path', '')}".strip("@:") or "Source"
        stats = snap.get("stats") or {}
        summ = (snap.get("rootEntry") or {}).get("summ") or {}
        failed = _int(stats.get("errorCount")) or _int(summ.get("numFailed"))
        incomplete = bool(snap.get("incomplete"))
        end = _epoch(snap.get("endTime"))
        size = _int(stats.get("totalSize")) or _int(summ.get("size"))
        ok = bool(end) and not failed and not incomplete
        out.append({"name": name[:80], "last": end, "last_ok": end if ok else 0, "last_failed": bool(end) and not ok,
                    "failures": failed + (1 if incomplete else 0), "size": size, "next": _epoch(s.get("nextSnapshotTime")),
                    "runs": [{"at": end, "ok": ok, "added": size}] if end else []})
    return out


def read_tool():
    tool, base = setting("tool", "backrest"), str(setting("address", "") or "").rstrip("/")
    if not base:
        raise ValueError("Enter the tool's address first")
    if tool == "kopia":
        return read_kopia(_call(f"{base}/api/v1/control/sources"))
    return read_backrest(_call(f"{base}/v1.Backrest/GetSummaryDashboard", {}))


# What is kept ---------------------------------------------------------------------------------------------------

def merge(old, new, now):
    """The new reading with each backup's run history carried forward (a run is told apart by its time)."""
    before = {b["name"]: b for b in old or []}
    for b in new:
        runs = {r["at"]: r for r in (before.get(b["name"]) or {}).get("runs", [])}
        runs.update({r["at"]: r for r in b["runs"]})
        b["runs"] = sorted(runs.values(), key=lambda r: r["at"])[-KEEP_RUNS:]
        if not b["last_ok"]:  # the tool only showed a failure: the newest good run it showed us before still counts
            b["last_ok"] = (before.get(b["name"]) or {}).get("last_ok", 0)
    return new


def overdue_hours():
    try:
        return max(1, min(int(setting("overdue_hours", 36)), 24 * 60))
    except (TypeError, ValueError):
        return 36


def problems(backups, now):
    """key -> (title, message) for every backup that is overdue or whose last run failed."""
    limit = overdue_hours() * HOUR
    out = {}
    for b in backups:
        if b["last_failed"]:
            out[f"failed:{b['name']}"] = (f"Backup failed: {b['name']}", f"The last run of {b['name']} had a problem. It has failed {b['failures']} times in the last 30 days.")
        if not b["last_ok"] or now - b["last_ok"] > limit:
            when = f"The last good run was {ago(now - b['last_ok'])}." if b["last_ok"] else "There has been no good run yet."
            out[f"overdue:{b['name']}"] = (f"Backup overdue: {b['name']}", f"{when} It is overdue after {overdue_hours()} hours.")
    return out


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


def alert(backups, now):
    """Raises each problem once and clears it when it is over; what was raised is kept, so a restart sends nothing twice."""
    raised = dict(remember("raised", {}) or {})
    want = problems(backups, now) if setting("alerts", True) is True else {}
    for key, (title, message) in want.items():
        if key not in raised and send_alert(key, "raised", title, message):
            raised[key] = now
    for key in [k for k in raised if k not in want]:
        if send_alert(key, "cleared", "Backup is fine again", ""):
            del raised[key]
    if raised != (remember("raised", {}) or {}):
        keep("raised", raised)


def check():
    """The job: ask the tool, keep what it said, and alert."""
    now = time.time()
    try:
        got = read_tool()
    except Exception as e:  # noqa: BLE001 - said on the card, never a stop
        keep("state", {**(remember("state", {}) or {}), "error": f"{TOOLS.get(setting('tool', 'backrest'), 'The tool')}: {_why(e)}", "checked": now})
        return {"said": f"Could not check the backups: {_why(e)}"}
    state = remember("state", {}) or {}
    backups = merge(state.get("backups"), got, now)
    keep("state", {"backups": backups, "checked": now, "tool": setting("tool", "backrest")})
    alert(backups, now)
    bad = len(problems(backups, now))
    return {"said": f"Checked {len(backups)} backup{'s' if len(backups) != 1 else ''}: " + (f"{bad} need attention" if bad else "all well")}


# Cards ------------------------------------------------------------------------------------------------------------

def _state():
    return remember("state", {}) or {}


def _needs():
    s = _state()
    if not setting("address"):
        return band({"state": "warning", "text": "Choose the tool and enter its address in Settings, Plug-ins, Backups watch."}, "needs_setup", label="Needs setting up")
    if s.get("error") and not s.get("backups"):
        return band({"state": "problem", "text": s["error"]}, "problem", s.get("checked"), "Cannot check")
    if not s.get("backups"):
        return band({"state": "ok", "text": "Waiting for the first check, which runs within the hour."}, "scheduled")
    return None


def card():
    n = _needs()
    if n:
        return n
    s = _state()
    now = time.time()
    bad = problems(s["backups"], now)
    total = len(s["backups"])
    last = max((b["last"] for b in s["backups"]), default=0)
    if bad:
        names = sorted({k.split(":", 1)[1] for k in bad})
        return band({"state": "problem", "text": f"{len(names)} of {total} need attention: {', '.join(names)}"[:160]}, "problem", s["checked"], "Needs attention")
    text = f"All {total} backed up. Last run {ago(now - last)}." if total != 1 else f"Backed up. Last run {ago(now - last)}."
    if s.get("error"):
        return band({"state": "warning", "text": f"{text} The last check failed: {s['error']}"[:160]}, "warning", s["checked"], "Last check failed")
    return band({"state": "ok", "text": text}, "ok", s["checked"])


def runs_list():
    n = _needs()
    if n:
        return band({"items": []}, n["status"], label=n.get("status_label"))
    s, now = _state(), time.time()
    bad = problems(s["backups"], now)
    items = []
    for b in sorted(s["backups"], key=lambda b: b["name"]):
        flags = [w for k, w in (("overdue:", "overdue"), ("failed:", "last run failed")) if f"{k}{b['name']}" in bad]
        last = f"last run {ago(now - b['last'])}" if b["last"] else "no run yet"
        items.append({"title": b["name"], "detail": f"{', '.join(flags).capitalize() + '. ' if flags else ''}{last.capitalize() if not flags else last}, "
                                                    f"{size_words(b['size'])}, {b['failures']} failed in 30 days"[:200]})
    return band({"items": items[:12]}, "warning" if bad else "ok", s["checked"], "Needs attention" if bad else None)


def sizes():
    n = _needs()
    if n:
        return band({"series": []}, n["status"], label=n.get("status_label"))
    s = _state()
    series = []
    for b in sorted(s["backups"], key=lambda b: b["name"])[:8]:
        pts = [r["added"] if r["ok"] else None for r in b["runs"]]
        series.append({"title": b["name"], "points": pts, "unit": "bytes",
                       "detail": f"{len(b['runs'])} runs kept. Latest {size_words(pts[-1])} added." if pts and pts[-1] is not None else f"{len(b['runs'])} runs kept"})
    return band({"series": series, "note": "Data added by each run the plug-in has kept. A gap is a failed run."}, "ok", s["checked"])


ROUTES = {"/card": card, "/runs": runs_list, "/sizes": sizes, ("POST", "/jobs/check"): check, ("POST", "/check"): check}

if __name__ == "__main__":
    serve(ROUTES, port=int(os.environ.get("PORT", 8080)))
