"""Themearr plug-in helper: the small part Starboard talks to, beside Themearr.

- Gives Themearr Reelix's address and key (from Starboard, permission reelix:key) as its Radarr, so it reads the
  films Reelix has with nobody entering them. Reelix answers Radarr's API at <Reelix>/radarr.
- Tells Themearr where the films are (/media/movies, the films folder it is given) and how Reelix's paths map to it.
- Passes on the RapidAPI key and user name from the plug-in's settings in Starboard, which Themearr needs to fetch
  theme tunes, and whether it fetches them by itself.
- Tells Starboard how Themearr is: a card with how many films have a theme, and a page with Themearr's access token.

Python's standard library only. Starboard writes this file into the helper's own folder (files in the manifest) and
runs it in the official Python image, so no image of ours is built. tools/make_app_helpers.py copies it into the
manifest; the file name carries the version, so an update writes the new one beside the old.
"""
import hashlib
import json
import os
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

APP = os.environ.get("THEMEARR_URL", "http://plugin-themearr-app:8080").rstrip("/")
TOKEN = os.environ.get("THEMEARR_AUTH_TOKEN", "")
RUN = os.environ.get("STARBOARD_RUN", "/run/starboard")
HERE = os.environ.get("HELPER_DATA") or os.path.dirname(os.path.abspath(__file__))
FILMS = os.environ.get("FILMS_FOLDER", "/media/movies")  # where Themearr finds the films
REELIX_FILMS = os.environ.get("REELIX_FILMS_FOLDER", "/data/media/movies")  # where Reelix keeps them (Install apps)
PORT = int(os.environ.get("PORT", "8080"))
EVERY = int(os.environ.get("EVERY_SECONDS", "120"))
STATE = {"state": "waiting", "label": "Starting", "said": "Starting", "at": 0, "figures": {}}
_lock = threading.Lock()


def _read(name, default=None):
    try:
        with open(os.path.join(RUN, name), encoding="utf-8") as f:
            return json.load(f) if name.endswith(".json") else f.read().strip()
    except (OSError, ValueError):
        return default


def _given():
    """What this helper last gave Themearr, as fingerprints, so it sends each thing once and not every round."""
    try:
        with open(os.path.join(HERE, "given.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _give(**kw):
    g = {**_given(), **kw}
    tmp = os.path.join(HERE, ".given.json.new")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(g, f)
    os.replace(tmp, os.path.join(HERE, "given.json"))


def _print(*parts):
    return hashlib.sha256("\n".join(str(p) for p in parts).encode()).hexdigest()[:16]


def call(path, data=None, method=None, timeout=15):
    """Themearr's API with its access token; the answer as JSON, or raises."""
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(APP + path, data=body, method=method or ("POST" if body is not None else "GET"),
                                 headers={"Authorization": f"Bearer {TOKEN}", "Accept": "application/json",
                                          "Content-Type": "application/json", "User-Agent": "Starboard"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read(2_000_000)
    return json.loads(raw) if raw else {}


def _why(e):
    if isinstance(e, urllib.error.HTTPError):
        try:
            return json.loads(e.read(4000)).get("detail") or f"HTTP {e.code}"
        except ValueError:
            return f"HTTP {e.code}"
    return str(getattr(e, "reason", e))


def _settings():
    return _read("settings.json", {}) or {}


def connect():
    """One round: Reelix as Themearr's Radarr, the films folder, the RapidAPI key, then the figures for the card."""
    try:
        radarr = call("/api/settings/radarr")
    except Exception as e:  # noqa: BLE001 - Themearr still starting
        return _keep("waiting", "Starting", f"Themearr is not answering yet: {_why(e)}"[:200])
    rx = _read("reelix.json", {}) or {}
    if not rx.get("url") or not rx.get("api_key"):
        if radarr.get("source") != "radarr" or not radarr.get("configured"):
            return _keep("warning", "No Reelix", "Starboard has no Reelix key to give yet: add Reelix in Settings, Apps.")
    else:
        url = rx["url"].rstrip("/") + "/radarr"
        mark = _print(url, rx["api_key"])
        if not radarr.get("configured") or radarr.get("url") != url or _given().get("reelix") != mark:
            try:
                call("/api/settings/radarr", {"source": "radarr", "url": url, "apiKey": rx["api_key"]})
                _give(reelix=mark)
            except Exception as e:  # noqa: BLE001
                return _keep("warning", "Not connected", f"Themearr did not take Reelix's address and key: {_why(e)}"[:200])
    try:
        _folders()
        status = call("/api/setup/status")
        if not status.get("setupComplete"):
            call("/api/setup/complete", {})
            call("/api/sync", {})  # the first read of Reelix's films, rather than waiting up to 15 minutes
        _rapidapi()
        figures = call("/api/stats")
        rapid = call("/api/settings/rapidapi")
    except Exception as e:  # noqa: BLE001
        return _keep("warning", "Not set up", f"Themearr did not take its settings: {_why(e)}"[:200])
    STATE["figures"] = {k: int(figures.get(k) or 0) for k in ("total", "downloaded", "pending", "ignored")}
    if not rapid.get("configured"):
        return _keep("needs_setup", "Needs a RapidAPI key",
                     "Reads your films from Reelix. To fetch theme tunes it needs a RapidAPI key and user name: add them in its settings.")
    return _keep("ok", None, "Reads your films from Reelix and fetches their theme tunes.")


def _folders():
    """The films folder and the way from Reelix's paths to it, added when missing. Fetching themes by itself is given
    the first time and each time the switch in Starboard changes, so a choice made in Themearr's own page stays."""
    s = call("/api/settings")
    paths = list(s.get("libraryPaths") or [])
    maps = list(s.get("pathMappings") or [])
    auto = bool(_settings().get("auto_download", True))
    first = "auto_download" not in _given()
    changed = first or _given().get("auto_download") != auto
    if FILMS not in paths:
        paths.append(FILMS)
        changed = True
    if not any(m.get("source") == REELIX_FILMS for m in maps):
        maps.append({"source": REELIX_FILMS, "target": FILMS})
        changed = True
    if changed:
        new_auto = auto if first or _given().get("auto_download") != auto else bool(s.get("autoDownload"))
        call("/api/settings", {"selectedServers": s.get("selectedServers") or [], "selectedLibraries": s.get("selectedLibraries") or {},
                               "pathMappings": maps, "libraryPaths": paths, "advanced": s.get("advanced") or {},
                               "autoSync": True if first else bool(s.get("autoSync")), "autoDownload": new_auto})
        _give(auto_download=auto)


def _rapidapi():
    """The RapidAPI key and user name from Starboard, given once each time they change. Left empty in Starboard, the
    ones entered in Themearr's own page stay."""
    s = _settings()
    key, user = str(s.get("rapidapi_key") or "").strip(), str(s.get("rapidapi_user") or "").strip()
    if key and user and _given().get("rapidapi") != _print(key, user):
        call("/api/settings/rapidapi", {"key": key, "username": user})
        _give(rapidapi=_print(key, user))


def _keep(state, label, said):
    with _lock:
        if (STATE["state"], STATE["said"]) != (state, said):
            STATE["at"] = int(time.time())
        STATE.update(state=state, label=label, said=said)
    return STATE


def card():
    f = STATE["figures"]
    total, done, pending = f.get("total", 0), f.get("downloaded", 0), f.get("pending", 0)
    if STATE["state"] in ("ok", "needs_setup") and total:
        note = ("Your film has a theme" if total == 1 and not pending else f"All {total:,} films have a theme" if not pending
                else f"{pending:,} of {total:,} films still without a theme")
    else:
        note = STATE["said"]
    out = {"value": done, "label": "films with a theme", "note": note[:80], "status": STATE["state"],
           "updated": STATE["at"] or None}
    if STATE["label"]:
        out["status_label"] = STATE["label"]
    return {k: v for k, v in out.items() if v is not None}


def sign_in():
    """The access token Themearr's own page asks for once in each browser, on the plug-in's tab in Starboard only."""
    return {"type": "list", "title": "Sign in to Themearr",
            "intro": ("Themearr's own page asks for this access token once in each web browser. Copy it into the "
                      "Access token box there. Anyone with it can change Themearr, so keep it private."),
            "items": [{"id": "token", "title": "Access token", "address": TOKEN, "state": "ok", "state_label": "Private",
                       "actions": []}]}


def loop():
    time.sleep(int(os.environ.get("FIRST_SECONDS", "15")))
    while True:
        try:
            connect()
        except Exception as e:  # noqa: BLE001 - keep going; the card says what went wrong
            _keep("warning", "Problem", f"Something went wrong: {e}"[:200])
        time.sleep(EVERY)


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

    def _starboard(self):
        key = _read("key", "")
        return bool(key) and self.headers.get("X-Api-Key", "") == key

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/health":
            return self._send(200, {"ok": True, "state": STATE["state"]})
        if path == "/card":
            return self._send(200, card())
        if path == "/sign-in":
            return self._send(200, sign_in()) if self._starboard() else self._send(403, {"error": "Only Starboard may ask for this"})
        return self._send(404, {"error": "Not found"})

    def do_POST(self):
        path = self.path.split("?")[0]
        n = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(min(n, 65536))
        if path == "/sign-in":
            return self._send(400, {"error": "Nothing here changes: copy the token into Themearr's own page"})
        return self._send(404, {"error": "Not found"})


def main():
    threading.Thread(target=loop, daemon=True).start()
    ThreadingHTTPServer(("", PORT), Handler).serve_forever(poll_interval=60)  # wakes once a minute, not twice a second


if __name__ == "__main__":
    main()
