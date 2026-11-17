"""checkrr plug-in helper: the small part Starboard talks to, beside checkrr.

- Tells Starboard how checkrr's last check went: a card with how many files failed it, and a page listing them with
  the reason checkrr gave. checkrr only reports here: it is given no Radarr, Sonarr or Lidarr and reads the films and
  series folders read only, so it cannot delete, move or replace a file.
- The Check now button asks checkrr to start a check straight away rather than on Sunday night.

Python's standard library only. Starboard writes this file into the helper's own folder (files in the manifest) and
runs it in the official Python image, so no image of ours is built. tools/make_app_helpers.py copies it into the
manifest; the file name carries the version, so an update writes the new one beside the old.
"""
import datetime as dt
import json
import os
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

APP = os.environ.get("CHECKRR_URL", "http://plugin-checkrr-app:8585").rstrip("/")
RUN = os.environ.get("STARBOARD_RUN", "/run/starboard")
PORT = int(os.environ.get("PORT", "8080"))
EVERY = int(os.environ.get("EVERY_SECONDS", "300"))
STATE = {"state": "waiting", "label": "Starting", "said": "Starting", "at": 0, "bad": [], "stats": {}, "next": ""}
_lock = threading.Lock()


def call(path, data=None, timeout=10):
    req = urllib.request.Request(APP + path, data=data, method="POST" if data is not None else "GET",
                                 headers={"Accept": "application/json", "User-Agent": "Starboard"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read(4_000_000)
    return json.loads(raw) if raw else None


def plural(n, one, many):
    return f"{n:,} {one if n == 1 else many}"


def when(seconds):
    if not seconds:
        return ""
    try:
        return dt.datetime.fromtimestamp(int(seconds)).strftime("%d %B %Y at %H:%M").lstrip("0")
    except (TypeError, ValueError, OverflowError, OSError):
        return ""


def ask():
    """One round: checkrr's figures from its last check and the files that failed it."""
    try:
        stats = call("/api/stats/current") or {}
        bad = call("/api/files/bad") or []
        nxt = call("/api/schedule") or ""
    except Exception as e:  # noqa: BLE001 - checkrr still starting
        return _keep("waiting", "Starting", f"checkrr is not answering yet: {getattr(e, 'reason', e)}"[:200])
    rows = []
    for b in bad if isinstance(bad, list) else []:
        d = b.get("Data") or {}
        rows.append({"path": str(b.get("Path") or ""), "reason": str(d.get("reason") or "not given"), "date": d.get("date") or 0})
    rows.sort(key=lambda r: (-int(r["date"] or 0), r["path"]))
    STATE.update(bad=rows, stats=stats, next=str(nxt))
    checked = int(stats.get("filesChecked") or 0)
    if stats.get("running"):
        return _keep("scanning", "Checking", f"Checking your films and series now: {plural(checked, 'file', 'files')} so far.")
    if not checked and not rows:
        return _keep("idle", "Not checked yet", "Not checked yet. The first check is on Sunday at 03:30, or select Check now.")
    if rows:
        return _keep("warning", plural(len(rows), "bad file", "bad files"),
                     f"{plural(len(rows), 'file', 'files')} failed the check. Nothing was changed: replace them yourself.")
    return _keep("ok", None, f"Every file passed: {plural(checked, 'file', 'files')} checked.")


def _keep(state, label, said):
    with _lock:
        if (STATE["state"], STATE["said"]) != (state, said):
            STATE["at"] = int(time.time())
        STATE.update(state=state, label=label, said=said)
    return STATE


def card():
    checked = int((STATE["stats"] or {}).get("filesChecked") or 0)
    note = STATE["said"] if STATE["state"] in ("waiting", "idle", "scanning") else f"Of {plural(checked, 'file', 'files')} in the last check"
    out = {"value": len(STATE["bad"]), "label": "files failed the check", "note": note[:80], "status": STATE["state"],
           "updated": STATE["at"] or None, "status_label": STATE["label"]}
    return {k: v for k, v in out.items() if v is not None}


def bad_files():
    items = []
    for i, r in enumerate(STATE["bad"][:4000]):
        folder, _, name = r["path"].rpartition("/")
        items.append({"id": f"bad-{i}", "title": name[:120] or r["path"][:120], "detail": (f"{r['reason']}. Found {when(r['date'])}" if when(r["date"]) else r["reason"])[:200],
                      "address": r["path"], "state": "warning", "state_label": "Failed the check", "actions": [],
                      "group": "Films" if folder.startswith("/media/movies") else "Series"})
    intro = ("Files checkrr could not read as a film or episode in its last check, with its reason. Nothing was deleted, "
             "moved or replaced: replace a file yourself, such as by searching for it again in Reelix.")
    if not items:
        intro = "No file failed the last check. " + STATE["said"]
    return {"type": "list", "title": "Files that failed the check", "intro": intro, "items": items}


def loop():
    time.sleep(int(os.environ.get("FIRST_SECONDS", "10")))
    while True:
        try:
            ask()
        except Exception as e:  # noqa: BLE001 - keep going; the card says what went wrong
            _keep("warning", "Problem", f"Something went wrong: {e}"[:200])
        time.sleep(EVERY if STATE["state"] != "scanning" else 30)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet: Starboard asks often
        pass

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/health":
            return self._send(200, {"ok": True, "state": STATE["state"]})
        if path == "/card":
            return self._send(200, card())
        if path == "/bad-files":
            return self._send(200, bad_files())
        return self._send(404, {"error": "Not found"})

    def do_POST(self):
        path = self.path.split("?")[0]
        n = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(min(n, 65536))
        if path == "/check-now":
            try:
                if (call("/api/stats/current") or {}).get("running"):
                    return self._send(200, {"said": "checkrr is checking already. The card shows how far it is."})
                call("/api/run", data=b"")
            except Exception as e:  # noqa: BLE001
                return self._send(502, {"error": f"checkrr is not answering: {getattr(e, 'reason', e)}"[:200]})
            _keep("scanning", "Checking", "Checking your films and series now.")
            return self._send(200, {"said": "checkrr is checking your films and series now. It changes nothing."})
        if path == "/bad-files":
            return self._send(400, {"error": "Nothing here changes: replace a file yourself"})
        return self._send(404, {"error": "Not found"})


def main():
    threading.Thread(target=loop, daemon=True).start()
    ThreadingHTTPServer(("", PORT), Handler).serve_forever(poll_interval=60)  # wakes once a minute, not twice a second


if __name__ == "__main__":
    main()
