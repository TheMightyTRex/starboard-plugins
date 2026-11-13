"""The small helper every example plug-in uses: Python's standard library only.

- settings(): the plug-in's settings, kept by Starboard at /run/starboard/settings.json (read only).
- starboard(path): Starboard's API v1 with the plug-in's own key (only the scopes the owner approved).
- jellyfin(path): Jellyfin's API with the key Starboard keeps (only for plug-ins allowed jellyfin:key).
- fetch(url): any address, JSON or bytes, with a time limit and a size limit.
- remember(name) and keep(name, value): a small JSON file in /data, the plug-in's own folder.
- every(seconds, job): a background job; serve(routes): the HTTP answers Starboard asks for (cards, buttons, health).
  A POST answer that takes one argument is given the JSON body Starboard sent, such as an event (64 KB at most).
  A ("FILE", path) answer is given a file Starboard streams to it (the name, the item, its length and the stream),
  which it reads a piece at a time (Audio description tracks, DASH-410).
"""
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DATA = os.environ.get("PLUGIN_DATA", "/data")
RUN = os.environ.get("PLUGIN_RUN", "/run/starboard")
API = os.environ.get("STARBOARD_API", "http://starboard:8095/api/v1/")
AGENT = "Starboard plug-in"
MAX = 4 * 1024 * 1024


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


def starboard(path):
    return fetch(urllib.parse.urljoin(API, path.lstrip("/")), {"Authorization": f"Bearer {_key()}"})


def jellyfin(path):
    jf = _json_file(os.path.join(RUN, "jellyfin.json"), {}) or {}
    if not jf.get("url") or not jf.get("api_key"):
        raise LookupError("Starboard has no Jellyfin key to give yet: add Jellyfin in Settings, Apps")
    return fetch(jf["url"].rstrip("/") + path, {"X-Emby-Token": jf["api_key"]})


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
    status card, never fatal."""
    def loop():
        time.sleep(first)
        while True:
            try:
                job()
                keep("_error", None)
            except Exception as e:  # noqa: BLE001 - a plug-in keeps running and says what went wrong
                keep("_error", {"at": time.time(), "text": f"{type(e).__name__}: {e}"[:200]})
            time.sleep(seconds)
    threading.Thread(target=loop, daemon=True).start()


def last_error():
    e = remember("_error")
    return e.get("text") if isinstance(e, dict) else ""


def plural(n, one, many=None):
    return f"{n:,} {one if n == 1 else (many or one + 's')}"


def serve(routes, port=8080):
    """routes: {"/card": fn() -> dict, ("POST", "/run"): fn() -> dict}. /health is added."""
    table = {("GET", "/health"): lambda: {"ok": True}}
    for k, fn in routes.items():
        table[k if isinstance(k, tuple) else ("GET", k)] = fn

    class Handler(BaseHTTPRequestHandler):
        def _answer(self, method):
            url = urllib.parse.urlparse(self.path)
            upload = table.get(("FILE", url.path)) if method == "POST" else None
            if upload:  # a chosen file, streamed as it is: never read whole into memory
                q = urllib.parse.parse_qs(url.query)
                try:
                    return self._send(200, upload((q.get("name") or [""])[0], (q.get("id") or [""])[0],
                                                  int(self.headers.get("Content-Length") or 0), self.rfile))
                except Exception as e:  # noqa: BLE001 - Starboard shows the message
                    return self._send(400 if isinstance(e, ValueError) else 502, {"error": f"{e}"[:200]})
            fn = table.get((method, url.path))
            if not fn:
                return self._send(404, {"error": "Not found"})
            try:
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
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()  # inside its own container  # nosec B104
