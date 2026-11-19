"""The small helper every example plug-in uses: Python's standard library only.

- settings(): the plug-in's settings, kept by Starboard at /run/starboard/settings.json (read only).
- starboard(path): Starboard's API v1 with the plug-in's own key (only the scopes the owner approved). Through the
  socket STARBOARD_API_SOCKET when Starboard gives one (Starboard 0.22 and later, DASH-482): a plug-in on its own
  network has no other way to reach Starboard, which runs on the server's own network. Over HTTP otherwise.
- jellyfin(path): Jellyfin's API with the key Starboard keeps (only for plug-ins allowed jellyfin:key).
- fetch(url): any address, JSON or bytes, with a time limit and a size limit.
- remember(name) and keep(name, value): a small JSON file in /data, the plug-in's own folder.
- every(seconds, job): a background job; serve(routes): the HTTP answers Starboard asks for (cards, buttons, health),
  waking about once a minute when nothing asks.
  A POST answer that takes one argument is given the JSON body Starboard sent, such as an event (64 KB at most).
  A ("FILE", path) answer is given a file Starboard streams to it (the name, the item, its length and the stream),
  which it reads a piece at a time (Audio description tracks, DASH-410).
- band(answer, status): adds the card band's status, status_label and updated to a card answer (plug-in API 1.14);
  changed(name) is when /data/<name>.json last changed, for updated.
- Updates (plug-in API 1.14): serve() answers POST /update/before by holding new background runs and waiting for any
  that is running to finish, and POST /update/after by letting them run again, so an update never cuts one short.
"""
import contextlib
import http.client
import json
import os
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DATA = os.environ.get("PLUGIN_DATA", "/data")
RUN = os.environ.get("PLUGIN_RUN", "/run/starboard")
API = os.environ.get("STARBOARD_API", "http://starboard:8095/api/v1/")
API_SOCKET = os.environ.get("STARBOARD_API_SOCKET", "")  # /run/starboard/api.sock, kept by Starboard (DASH-482)
AGENT = "Starboard plug-in"
MAX = 4 * 1024 * 1024
POLL_SECONDS = 60  # how often the idle HTTP server looks for a shutdown that never comes


def _json_file(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def settings():
    return _json_file(os.path.join(RUN, "settings.json"), {}) or {}


def setting(key, default=None):
    v = settings().get(key)
    return default if v in (None, "") else v


def _key():
    try:
        with open(os.path.join(RUN, "key"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def fetch(url, headers=None, data=None, method=None, timeout=15, raw=False, limit=MAX):
    body = json.dumps(data).encode() if isinstance(data, (dict, list)) else data
    h = {"User-Agent": AGENT, "Accept": "application/json", **(headers or {})}
    if isinstance(data, (dict, list)):
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=h, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:  # addresses the owner gave, or Starboard's own  # nosec B310
        out = r.read(limit)
    return out if raw else json.loads(out or b"null")


class _SocketConnection(http.client.HTTPConnection):
    """HTTP to Starboard through its socket in /run/starboard, instead of a network address."""

    def __init__(self, path, timeout):
        super().__init__("localhost", timeout=timeout)
        self.socket_path = path

    def connect(self):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(self.timeout)
        try:
            s.connect(self.socket_path)
        except OSError:
            s.close()
            raise
        self.sock = s


def starboard(path, timeout=15):
    url = urllib.parse.urljoin(API, path.lstrip("/"))
    headers = {"Authorization": f"Bearer {_key()}"}
    if not (API_SOCKET and os.path.exists(API_SOCKET)):
        return fetch(url, headers, timeout=timeout)
    u = urllib.parse.urlsplit(url)
    c = _SocketConnection(API_SOCKET, timeout)
    try:
        c.request("GET", u.path + (f"?{u.query}" if u.query else ""), headers={"User-Agent": AGENT, "Accept": "application/json", **headers})
        r = c.getresponse()
        out = r.read(MAX)
        if r.status >= 400:  # as urlopen does, so a plug-in's error handling stays the same
            raise urllib.error.HTTPError(url, r.status, r.reason, r.headers, None)
    finally:
        c.close()
    return json.loads(out or b"null")


def jellyfin(path):
    jf = _json_file(os.path.join(RUN, "jellyfin.json"), {}) or {}
    if not jf.get("url") or not jf.get("api_key"):
        raise LookupError("Starboard has no Jellyfin key to give yet: add Jellyfin in Settings, Apps")
    return fetch(jf["url"].rstrip("/") + path, jellyfin_headers(jf["api_key"]))


def jellyfin_headers(key):
    """The key as Jellyfin wants it. Jellyfin 12 with legacy authorisation off refuses it in X-Emby-Token alone (401),
    so it goes in Authorization too; X-Emby-Token stays for older Jellyfin and Emby (DASH-458)."""
    return {"Authorization": f'MediaBrowser Token="{key}"', "X-Emby-Token": key}


def remember(name, default=None):
    return _json_file(os.path.join(DATA, f"{name}.json"), default)


def keep(name, value):
    path = os.path.join(DATA, f"{name}.json")
    os.makedirs(DATA, exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(value, f)
    os.replace(path + ".tmp", path)


def every(seconds, job, first=5):
    """Runs job() now (after `first` seconds) and then every `seconds`, in the background. Errors are kept for the
    status card, never fatal. A run that works clears the kept error, writing the file only when there was one."""
    def loop():
        time.sleep(first)
        while True:
            while holding():  # an update is about to start: no new run until it is done (API 1.14)
                time.sleep(5)
            try:
                with working(getattr(job, "__name__", "a background job")):
                    job()
                clear_error()
            except Exception as e:  # noqa: BLE001 - a plug-in keeps running and says what went wrong
                keep("_error", {"at": time.time(), "text": f"{type(e).__name__}: {e}"[:200]})
            time.sleep(seconds)
    threading.Thread(target=loop, daemon=True).start()


def clear_error():
    """After a run that worked: empties /data/_error.json, writing it only when it holds an error, so a plug-in at rest
    never writes to the disk just to say nothing went wrong."""
    if remember("_error") is not None:
        keep("_error", None)


def last_error():
    e = remember("_error")
    return e.get("text") if isinstance(e, dict) else ""


# The card band (plug-in API 1.14, DASH-428) -------------------------------------------------------------------
STATUSES = {"ok", "done", "ready", "protected", "working", "converting", "scanning", "updating", "running", "waiting", "idle",
            "scheduled", "paused", "inactive", "warning", "needs_setup", "problem", "failed", "stopped"}


def changed(name):
    """When /data/<name>.json last changed, in whole seconds since 1970, or None when it is not there yet."""
    try:
        return int(os.stat(os.path.join(DATA, f"{name}.json")).st_mtime)
    except OSError:
        return None


def band(answer, status, updated=None, label=None, refresh=None):
    """The card answer with the band's fields: status (one of STATUSES), status_label (24 characters at most) and
    updated (seconds since 1970, never in the future). An older Starboard ignores them."""
    if status not in STATUSES:
        raise ValueError(f"Unknown card status {status}")
    out = {**answer, "status": status}
    if label:
        out["status_label"] = str(label)[:24]
    if updated:
        out["updated"] = min(int(updated), int(time.time()))
    if refresh:
        out["refresh_seconds"] = max(10, min(int(refresh), 3600))
    return out


# Updates (plug-in API 1.14, DASH-424) -------------------------------------------------------------------------
_work = {"running": [], "hold": 0.0}
_work_lock = threading.Lock()
HOLD_SECONDS = 600  # the longest an update may hold new runs, in case its after step never comes
WAIT_SECONDS = 50  # how long the before step waits for a run to finish: inside Starboard's 60 seconds


@contextlib.contextmanager
def working(what):
    """Marks a background run or a button as running, so the update's before step can wait for it."""
    with _work_lock:
        _work["running"].append(what)
    try:
        yield
    finally:
        with _work_lock:
            _work["running"].remove(what)


def holding():
    return time.time() < _work["hold"]


def before_update(body=None):
    """POST /update/before: no new background run starts, and one that is running is given time to finish."""
    _work["hold"] = time.time() + HOLD_SECONDS
    waited = time.monotonic()
    while _work["running"] and time.monotonic() - waited < WAIT_SECONDS:
        time.sleep(0.5)
    if _work["running"]:
        _work["hold"] = 0.0
        return {"ok": False, "said": f"Still busy with {_work['running'][0].replace('_', ' ')}. Try again in a few minutes"}
    return {"ok": True, "said": "Ready to update: nothing is running" if time.monotonic() - waited < 1 else "Ready to update: the last run finished"}


def after_update(body=None):
    """POST /update/after: background runs may start again, after an update or a Roll back."""
    _work["hold"] = 0.0
    return {"ok": True, "said": f"Running again after the {'roll back' if (body or {}).get('outcome') == 'rolled_back' else 'update'}"}


def plural(n, one, many=None):
    return f"{n:,} {one if n == 1 else (many or one + 's')}"


def serve(routes, port=8080):
    """routes: {"/card": fn() -> dict, ("POST", "/run"): fn() -> dict}. /health, /update/before and /update/after are
    added unless given. A POST other than those is counted as running work, and a job (/jobs/...) is not started
    while an update holds new runs."""
    table = {("GET", "/health"): lambda: {"ok": True}, ("POST", "/update/before"): before_update,
             ("POST", "/update/after"): after_update}
    for k, fn in routes.items():
        table[k if isinstance(k, tuple) else ("GET", k)] = fn

    class Handler(BaseHTTPRequestHandler):
        def _answer(self, method):
            url = urllib.parse.urlparse(self.path)
            upload = table.get(("FILE", url.path)) if method == "POST" else None
            if upload:  # a chosen file, streamed as it is: never read whole into memory
                q = urllib.parse.parse_qs(url.query)
                try:
                    with working("a file being added"):
                        return self._send(200, upload((q.get("name") or [""])[0], (q.get("id") or [""])[0],
                                                      int(self.headers.get("Content-Length") or 0), self.rfile))
                except Exception as e:  # noqa: BLE001 - Starboard shows the message
                    return self._send(400 if isinstance(e, ValueError) else 502, {"error": f"{e}"[:200]})
            fn = table.get((method, url.path))
            if not fn:
                return self._send(404, {"error": "Not found"})
            try:
                if method == "POST" and url.path.startswith("/update/"):
                    return self._send(200, fn(self._body()) if getattr(fn, "__code__", None) and fn.__code__.co_argcount else fn())
                if method == "POST" and url.path.startswith("/jobs/") and holding():
                    return self._send(200, {"said": "Not started: the plug-in is about to be updated"})
                with (working(url.path.rsplit("/", 1)[-1] or "a job") if method == "POST" else contextlib.nullcontext()):
                    if method == "POST" and getattr(fn, "__code__", None) and fn.__code__.co_argcount:
                        return self._send(200, fn(self._body()))
                    return self._send(200, fn())
            except Exception as e:  # noqa: BLE001 - Starboard shows the message
                return self._send(502, {"error": f"{e}"[:200]})

        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            try:
                got = json.loads(self.rfile.read(min(n, 65536)) or b"{}") if n else {}
            except ValueError:
                got = {}
            return got if isinstance(got, dict) else {}

        def _send(self, status, body):
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):  # noqa: N802
            self._answer("GET")

        def do_POST(self):  # noqa: N802
            self._answer("POST")

        def log_message(self, *a):
            pass

    port = int(os.environ.get("PORT", port))
    print(f"Listening on {port}", flush=True)
    # A look for a shutdown once a minute, not twice a second: nothing stops the server but the container ending, so an
    # idle plug-in wakes about once a minute instead of 120 times.
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever(poll_interval=POLL_SECONDS)  # inside its own container  # nosec B104
