"""Remote access: Starboard, Jellyfin and Audiobookshelf away from home through Tailscale or Cloudflare Tunnel, with no
port opened on your router. Never the download apps.

How it works (DASH-403, 13 November 2026):
- One small Python helper (this file) runs the way the person chose: tailscaled in userspace networking (no device,
  no capability, no kernel change) or cloudflared with a tunnel token. Only one runs at a time; none when nothing is
  chosen or the key is missing.
- Shared apps are reached through small forwarders on 127.0.0.1 inside this container: 8095 to Starboard, 8096 to
  Jellyfin, 13378 to Audiobookshelf. Tailscale delivers its visitors to those ports; a Cloudflare route must point at
  them. Nothing else is forwarded, so the download apps can never be reached this way.
- Cloudflare: the routes are set in Cloudflare's dashboard, so the helper reads them from cloudflared and stops the
  tunnel if any route leads anywhere but the three forwarders, or if Starboard's route is not behind Cloudflare Access.
- Keys and tokens are read from settings.json when needed and handed over in a file in /tmp (memory only) or in the
  child's environment, never on a command line or in the log.
"""
import asyncio
import base64
import hashlib
import http.client
import json
import os
import re
import socket
import subprocess
import threading
import time
import urllib.parse
from collections import deque

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from sbplugin import DATA, keep, remember, setting, starboard

APPS = [("starboard", "Starboard", 8095), ("jellyfin", "Jellyfin", 8096), ("audiobookshelf", "Audiobookshelf", 13378)]
NAMES = {a: n for a, n, _ in APPS}
PORTS = {a: p for a, _, p in APPS}
LISTEN = os.environ.get("FORWARD_HOST", "127.0.0.1")
TS_SOCK = os.environ.get("TS_SOCKET", "/tmp/tailscaled.sock")
TS_KEY_FILE = "/tmp/ts-auth-key"
CF_METRICS = "127.0.0.1:20241"
TICK = 10  # seconds between the helper's own looks; nothing else runs on a timer
TAILSCALED = os.environ.get("TAILSCALED", "tailscaled")
TAILSCALE = os.environ.get("TAILSCALE", "tailscale")
CLOUDFLARED = os.environ.get("CLOUDFLARED", "cloudflared")

lock = threading.RLock()
state = {"method": "", "phase": "off", "text": "", "fatal": False, "auth_url": "", "ips": [], "dns": "",
         "routes": [], "started": 0.0, "checked": {}}
child = {"proc": None, "up": None, "want": None, "log": deque(maxlen=40), "next_try": 0.0, "tries": 0}
targets = {}  # app -> (host, port), read from Starboard's apps


# Settings ----------------------------------------------------------------------------------------------------------

def method():
    m = str(setting("method", "none") or "none").lower()
    return m if m in ("tailscale", "cloudflare") else "none"


def shared():
    """The apps this plug-in may share, by the person's switches. Starboard is shared unless deactivated."""
    out = []
    for app, _, _ in APPS:
        if setting(f"share_{app}", True) in (True, "true", 1):
            out.append(app)
    return out


def _fingerprint(*parts):
    return hashlib.sha256("\x00".join(str(p) for p in parts).encode()).hexdigest()[:16]


def wanted():
    """What should be running, as a small tuple; a change means stop and start again. Secrets are fingerprinted."""
    m = method()
    if m == "tailscale":
        return (m, str(setting("tailscale_sign_in", "key")), _fingerprint(setting("tailscale_key", "")),
                str(setting("device_name", "starboard")))
    if m == "cloudflare":
        return (m, _fingerprint(setting("cloudflare_token", "")))
    return (m,)


def check_tailscale_key(key):
    key = (key or "").strip()
    if not key:
        return "missing"
    if not re.match(r"^tskey-(auth|client)-[A-Za-z0-9_-]{8,200}$", key):
        return "That is not a Tailscale auth key. Auth keys start with tskey-auth-: make one in Tailscale's admin page, Settings, Keys, and paste it whole."
    return ""


def clean_token(token):
    """People often paste the whole command Cloudflare shows (cloudflared tunnel run --token eyJ...): keep the token."""
    words = (token or "").split()
    return max(words, key=len) if words else ""


def check_cloudflare_token(token):
    token = clean_token(token)
    if not token:
        return "missing"
    try:
        raw = base64.b64decode(token + "=" * (-len(token) % 4), validate=False)
        data = json.loads(raw)
        if isinstance(data, dict) and all(isinstance(data.get(k), str) and data.get(k) for k in ("a", "t", "s")):
            return ""
    except (ValueError, TypeError):
        pass
    return ("That is not a Cloudflare tunnel token. In Cloudflare's dashboard, open Networks, Tunnels, your tunnel, "
            "and copy the long token after --token, without the words before it.")


# The forwarders ----------------------------------------------------------------------------------------------------

def read_targets():
    """Where each shared app really is: Starboard from its API address, the others from Starboard's apps list."""
    api = urllib.parse.urlparse(os.environ.get("STARBOARD_API", "http://starboard:8095/api/v1/"))
    found = {"starboard": (api.hostname or "starboard", api.port or 8095)}
    try:
        items = (starboard("apps") or {}).get("items") or []
    except Exception as e:  # noqa: BLE001 - Starboard may be starting; try again next time
        with lock:
            child["log"].append(f"Could not read Starboard's apps: {e}")
        items = []
    for it in items:
        kind = str(it.get("type") or "").lower()
        name = re.sub(r"[^a-z]", "", str(it.get("name") or "").lower())
        app = "jellyfin" if kind == "jellyfin" else "audiobookshelf" if (kind == "audiobookshelf" or name == "audiobookshelf") else ""
        if not app or app in found or it.get("enabled") is False:
            continue
        u = urllib.parse.urlparse(str(it.get("url") or ""))
        if u.scheme not in ("http", "https") or not u.hostname:
            continue
        host = "host.docker.internal" if u.hostname in ("localhost", "127.0.0.1", "::1") else u.hostname
        found[app] = (host, u.port or (443 if u.scheme == "https" else 80))
    with lock:
        targets.clear()
        targets.update(found)


async def _pipe(reader, writer):
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except (OSError, asyncio.CancelledError):
        pass
    finally:
        try:
            if writer.can_write_eof():
                writer.write_eof()
        except OSError:
            pass


async def _handle(app, cr, cw):
    with lock:
        target = targets.get(app) if app in shared() else None
    if not target:
        cw.close()
        return
    try:
        ur, uw = await asyncio.wait_for(asyncio.open_connection(*target), 5)
    except (OSError, asyncio.TimeoutError):
        cw.close()
        return
    await asyncio.gather(_pipe(cr, uw), _pipe(ur, cw), return_exceptions=True)
    for w in (uw, cw):
        w.close()


_forwarding = threading.Event()


def start_forwarders():
    """One thread, one event loop, a listener per app: no thread per connection (pids are limited to 64). Started
    the first time a tunnel starts, so nothing listens while remote access is not set up."""
    if _forwarding.is_set():
        return
    _forwarding.set()

    async def main():
        for app, _, port in APPS:
            try:
                await asyncio.start_server(lambda r, w, a=app: _handle(a, r, w), LISTEN, port, reuse_address=True)
            except OSError as e:
                with lock:
                    child["log"].append(f"Could not listen for {NAMES[app]} on {LISTEN}:{port}: {e}")
        await asyncio.Event().wait()
    threading.Thread(target=lambda: asyncio.run(main()), daemon=True).start()


# Tailscale ---------------------------------------------------------------------------------------------------------

class _UnixHTTP(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(TS_SOCK)


def ts_status():
    c = _UnixHTTP("local-tailscaled.sock", timeout=3)
    try:
        c.request("GET", "/localapi/v0/status?peers=false", headers={"Host": "local-tailscaled.sock"})
        r = c.getresponse()
        return json.loads(r.read(1 << 20) or b"{}")
    finally:
        c.close()


def explain_tailscale(text):
    t = text.lower()
    if "invalid key" in t or "authkey" in t and ("not valid" in t or "expired" in t) or "api key does not exist" in t or "unauthorized" in t:
        return ("Tailscale did not accept the auth key: it may be expired, used already or deleted. Make a new one in "
                "Tailscale's admin page, Settings, Keys, and paste it again.", True)
    if "no such host" in t or "dial tcp" in t or "timeout" in t or "deadline" in t:
        return ("Tailscale's servers could not be reached. Check this computer's internet connection; the plug-in tries again by itself.", False)
    return ((text.strip().splitlines() or ["Tailscale stopped"])[-1][:200], False)


def start_tailscale(want):
    _, how, _, device = want
    key = str(setting("tailscale_key", "") or "").strip()
    if how != "link":
        problem = check_tailscale_key(key)
        if problem == "missing":
            return set_phase("needs-key", "Paste a Tailscale auth key in Remote access, Settings, or choose Sign in with a link.", fatal=True)
        if problem:
            return set_phase("wrong-key", problem, fatal=True)
    start_forwarders()
    os.makedirs(os.path.join(DATA, "tailscale"), exist_ok=True)
    proc = subprocess.Popen([TAILSCALED, "--tun=userspace-networking", f"--statedir={os.path.join(DATA, 'tailscale')}",
                             f"--socket={TS_SOCK}", "--port=0", "--no-logs-no-support"],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
    child["proc"] = proc
    _drain(proc)
    for _ in range(50):
        if os.path.exists(TS_SOCK):
            break
        time.sleep(0.2)
    name = re.sub(r"[^a-z0-9-]", "-", device.lower()).strip("-")[:63] or "starboard"
    args = [TAILSCALE, f"--socket={TS_SOCK}", "up", f"--hostname={name}", "--accept-dns=false", "--accept-routes=false"]
    if how != "link":
        fd = os.open(TS_KEY_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(key)
        args.append(f"--auth-key=file:{TS_KEY_FILE}")  # used only when Tailscale needs to sign in
        if remember("ts_key") not in (None, _fingerprint(key)):
            args.append("--force-reauth")  # a new key: sign in again with it
    up = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
    child["up"] = up

    def watch_up():
        out = up.communicate()[0] or ""
        try:
            os.remove(TS_KEY_FILE)
        except OSError:
            pass
        if up.returncode == 0:
            if how != "link":
                keep("ts_key", _fingerprint(key))
            return
        if up.returncode < 0:
            return  # stopped by us
        text, fatal = explain_tailscale(out)
        with lock:
            child["log"].append(out.strip()[-300:])
        set_phase("wrong-key" if fatal else "error", text, fatal=fatal)
    threading.Thread(target=watch_up, daemon=True).start()
    set_phase("starting", "Tailscale is starting.")


def look_tailscale():
    try:
        st = ts_status()
    except OSError:
        return
    backend = st.get("BackendState", "")
    me = st.get("Self") or {}
    with lock:
        state["ips"] = [ip for ip in me.get("TailscaleIPs") or [] if "." in ip] or list(me.get("TailscaleIPs") or [])
        state["dns"] = (me.get("DNSName") or "").rstrip(".")
        state["auth_url"] = st.get("AuthURL") or ""
    if backend == "Running":
        set_phase("connected", "Connected to your tailnet.")
    elif backend == "NeedsLogin" and state["auth_url"]:
        set_phase("sign-in", "Open the sign-in link on any device and sign in to Tailscale. The plug-in carries on by itself.")
    elif backend == "NeedsMachineAuth":
        set_phase("approve", "Approve this device in Tailscale's admin page, Machines.")
    elif backend in ("Starting", "NoState", "NeedsLogin") and state["phase"] not in ("wrong-key", "error"):
        set_phase("starting", "Tailscale is starting.")


# Cloudflare Tunnel -------------------------------------------------------------------------------------------------

def explain_cloudflare(text):
    t = text.lower()
    if any(w in t for w in ("token is not valid", "invalid tunnel secret", "unauthorized", "tunnel not found", "failed to get tunnel")):
        return ("Cloudflare did not accept the tunnel token: the tunnel may have been deleted or its token changed. "
                "Copy the token again from Cloudflare's dashboard, Networks, Tunnels.", True)
    if "no such host" in t or "dial tcp" in t or "failed to dial" in t or "timeout" in t:
        return ("Cloudflare could not be reached. Check this computer's internet connection; the plug-in tries again by itself.", False)
    return ((text.strip().splitlines() or ["Cloudflare Tunnel stopped"])[-1][:200], False)


def start_cloudflare(want):
    token = clean_token(str(setting("cloudflare_token", "") or ""))
    problem = check_cloudflare_token(token)
    if problem == "missing":
        return set_phase("needs-key", "Paste your Cloudflare tunnel token in Remote access, Settings.", fatal=True)
    if problem:
        return set_phase("wrong-key", problem, fatal=True)
    start_forwarders()
    env = {k: v for k, v in os.environ.items() if not k.startswith("TUNNEL_")}
    env["TUNNEL_TOKEN"] = token  # in the child's environment, never on its command line
    env["NO_AUTOUPDATE"] = "true"
    proc = subprocess.Popen([CLOUDFLARED, "tunnel", "--no-autoupdate", "--metrics", CF_METRICS, "run"], env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
    child["proc"] = proc
    _drain(proc)
    set_phase("starting", "Cloudflare Tunnel is starting.")


ALLOWED = {f"http://{h}:{p}": app for app, _, p in APPS for h in ("localhost", "127.0.0.1")}


def judge_routes(ingress):
    """Each route as {hostname, app, access, problem}; problem stops the tunnel."""
    out = []
    for rule in ingress or []:
        service = str(rule.get("service") or "").rstrip("/").lower()
        host = str(rule.get("hostname") or "")
        if service.startswith("http_status:"):
            continue  # the catch-all that answers 404
        app = ALLOWED.get(service)
        access = bool(((rule.get("originRequest") or {}).get("access") or {}).get("required"))
        problem = ""
        if not app:
            problem = (f"The route {host or 'with no name'} leads to {service or 'nothing'}, which is not Starboard, "
                       "Jellyfin or Audiobookshelf. Point it at http://localhost:8095, 8096 or 13378, or delete it.")
        elif app not in shared():
            problem = f"The route {host} leads to {NAMES[app]}, which is not shared. Share it in Settings or delete the route."
        elif app == "starboard" and not access:
            problem = (f"The route {host} leads to Starboard without Cloudflare Access, so anyone could try to sign in. "
                       "Protect it with an Access application and tick Protect with Access on the route.")
        out.append({"hostname": host, "app": app or "", "access": access, "problem": problem})
    return out


def look_cloudflare():
    with lock:
        log = "\n".join(child["log"])
    if "register tunnel error" in log.lower():
        text, fatal = explain_cloudflare(log)
        if fatal:  # cloudflared keeps retrying a token Cloudflare refused; stop it and say so
            stop_child()
            return set_phase("wrong-key", text, fatal=True)
    try:
        c = http.client.HTTPConnection(CF_METRICS, timeout=2)
        c.request("GET", "/ready")
        ready = json.loads(c.getresponse().read() or b"{}")
        c.request("GET", "/config")
        conf = json.loads(c.getresponse().read() or b"{}")
        c.close()
    except (OSError, ValueError):
        return
    routes = judge_routes(((conf.get("config") or {}).get("ingress")) if isinstance(conf, dict) else [])
    with lock:
        state["routes"] = routes
    bad = [r["problem"] for r in routes if r["problem"]]
    if bad:
        stop_child()
        return set_phase("unsafe", "Stopped the tunnel to keep your apps safe. " + bad[0], fatal=True)
    if int(ready.get("readyConnections") or 0) > 0:
        if not routes:
            return set_phase("no-routes", "Connected, but the tunnel has no routes yet. Add a public hostname in Cloudflare's dashboard pointing at http://localhost:8095.")
        set_phase("connected", f"Connected to Cloudflare with {ready.get('readyConnections')} connections.")


# Running the chosen way ------------------------------------------------------------------------------------------

def set_phase(phase, text, fatal=False):
    with lock:
        if state["phase"] != phase or state["text"] != text:
            state["phase"], state["text"], state["fatal"] = phase, text, fatal
            keep("state", {"phase": phase, "text": text, "at": time.time()})


def _drain(proc):
    def read():
        for line in proc.stdout:
            line = line.strip()
            if line and not re.search(r"tskey-|token", line, re.I):  # never keep a secret
                with lock:
                    child["log"].append(line[-300:])
    threading.Thread(target=read, daemon=True).start()


def stop_child():
    for k in ("up", "proc"):
        p = child.get(k)
        if p and p.poll() is None:
            p.terminate()
            try:
                p.wait(5)
            except subprocess.TimeoutExpired:
                p.kill()
        child[k] = None
    try:
        os.remove(TS_SOCK)
    except OSError:
        pass


def supervise_once():
    want = wanted()
    if want != child["want"]:
        stop_child()
        with lock:
            child["want"], child["tries"], child["next_try"] = want, 0, 0.0
            state.update({"method": want[0], "auth_url": "", "ips": [], "dns": "", "routes": [], "fatal": False, "checked": {}})
        if want[0] == "none":
            set_phase("off", "Choose Tailscale or Cloudflare Tunnel in Remote access, Settings.")
            return
        read_targets()
        state["started"] = time.time()
        (start_tailscale if want[0] == "tailscale" else start_cloudflare)(want)
        return
    if want[0] == "none" or state["fatal"]:
        return
    proc = child["proc"]
    if proc and proc.poll() is not None:
        with lock:
            log = "\n".join(child["log"])
        text, fatal = (explain_tailscale if want[0] == "tailscale" else explain_cloudflare)(log)
        set_phase("wrong-key" if fatal else "error", text, fatal=fatal)
        child["proc"] = None
        child["tries"] += 1
        child["next_try"] = time.time() + min(300, 15 * 2 ** child["tries"])
        return
    if not proc and time.time() >= child["next_try"]:
        (start_tailscale if want[0] == "tailscale" else start_cloudflare)(want)
        return
    (look_tailscale if want[0] == "tailscale" else look_cloudflare)()


def supervisor():
    ticks = 0
    while True:
        try:
            supervise_once()
            ticks += 1
            if ticks % 30 == 0:  # every 5 minutes: an app's address may have changed
                read_targets()
        except Exception as e:  # noqa: BLE001 - the helper keeps running and says what went wrong
            with lock:
                child["log"].append(f"{type(e).__name__}: {e}")
        time.sleep(TICK)


# What Starboard asks ------------------------------------------------------------------------------------------------

def address(app):
    with lock:
        if state["phase"] != "connected":
            return ""
        if state["method"] == "tailscale" and state["ips"]:
            return f"http://{state['ips'][0]}:{PORTS[app]}"
        for r in state["routes"]:
            if r["app"] == app and r["hostname"] and not r["problem"]:
                return f"https://{r['hostname']}"
    return ""


def card():
    with lock:
        phase, text, m = state["phase"], state["text"], state["method"]
    if phase == "connected":
        where = address("starboard") or address("jellyfin")
        how = "Tailscale" if m == "tailscale" else "Cloudflare Tunnel"
        return {"state": "ok", "text": f"Away from home: {where} ({how})" if where else f"Connected through {how}"}
    if phase in ("off",):
        return {"state": "warning", "text": "Not set up: choose Tailscale or Cloudflare Tunnel in its settings"}
    if phase in ("starting", "sign-in", "approve", "no-routes"):
        return {"state": "warning", "text": text}
    return {"state": "problem", "text": text or "Not connected"}


def _reach(app):
    with lock:
        target = targets.get(app)
    if not target:
        return False, f"{NAMES[app]} is not in Starboard's apps, so it is not shared."
    try:
        with socket.create_connection(target, timeout=3):
            pass
        return True, f"{NAMES[app]} answers."
    except OSError:
        return False, f"{NAMES[app]} did not answer at {target[0]}:{target[1]}."


def _starboard_name_ok(host):
    """Starboard answers only to names it knows: ask it as the visitor's browser would."""
    t = targets.get("starboard")
    if not t or not host:
        return True
    try:
        c = http.client.HTTPConnection(*t, timeout=3)
        c.request("GET", "/healthz", headers={"Host": host})
        ok = c.getresponse().status != 421
        c.close()
        return ok
    except OSError:
        return True


def test(only=None):
    read_targets()
    said = []
    with lock:
        phase, text = state["phase"], state["text"]
    if phase != "connected":
        said.append(text or "Not connected.")
    for app in only or shared():
        ok, words = _reach(app)
        if ok and app == "starboard" and state["method"] == "cloudflare":
            host = next((r["hostname"] for r in state["routes"] if r["app"] == "starboard"), "")
            if host and not _starboard_name_ok(host):
                ok, words = False, (f"Starboard does not answer to the name {host} yet. Add it to STARBOARD_ALLOWED_HOSTS "
                                    "in Starboard's settings file (read Put Starboard behind a reverse proxy).")
        with lock:
            state["checked"][app] = {"ok": ok, "text": words, "at": time.time()}
        said.append(words)
    return {"said": " ".join(said)[:160]}


def restart():
    with lock:
        child["want"] = None
    supervise_once()
    return {"said": "Starting again with the saved settings."}


def screen():
    with lock:
        phase, text, m = state["phase"], state["text"], state["method"]
        auth_url, dns, checked = state["auth_url"], state["dns"], dict(state["checked"])
    how = {"tailscale": "Tailscale", "cloudflare": "Cloudflare Tunnel"}.get(m, "Nothing chosen")
    tone = "ok" if phase == "connected" else "warning" if phase in ("off", "starting", "sign-in", "approve", "no-routes") else "problem"
    items = [{"id": "connection", "title": f"Connection: {how}", "detail": text[:200], "state": tone, "group": "Connection"}]
    if auth_url and phase == "sign-in":
        items.append({"id": "sign-in", "title": "Sign-in link for Tailscale", "address": auth_url, "state": "warning", "group": "Connection",
                      "detail": "Open this link on any device, sign in to your own Tailscale account and approve this computer."})
    for app in [a for a, _, _ in APPS]:
        is_shared = app in shared()
        where = address(app)
        c = checked.get(app)
        if not is_shared:
            detail, st = "Not shared: activate it in Settings to share it.", "off"
        elif app not in targets:
            detail, st = f"Not shared: {NAMES[app]} is not in Starboard's apps.", "off"
        elif where:
            detail = "Use this address away from home." + (f" {c['text']}" if c else "")
            if app == "starboard" and m == "tailscale" and dns:
                detail += f" The name {dns} works only once it is in STARBOARD_ALLOWED_HOSTS."
            st = "problem" if c and not c["ok"] else "ok"
        else:
            detail, st = ("No address yet: connect first." if m != "cloudflare" or phase != "connected"
                          else f"No route in Cloudflare leads to {NAMES[app]} yet. Point one at http://localhost:{PORTS[app]}."), "unknown"
        items.append({"id": app, "title": NAMES[app], "address": where, "detail": detail[:200], "state": st,
                      "group": "Shared apps", "actions": ["test"] if is_shared else []})
    items.append({"id": "download-apps", "title": "Download apps", "state": "off", "group": "Never shared",
                  "detail": "qBittorrent, NZBGet, SABnzbd, Reelix and the rest stay on your home network."})
    notices = []
    if m == "cloudflare" and "jellyfin" in shared():
        notices.append({"id": "video", "tone": "warning", "title": "Watching through Cloudflare",
                        "text": "Cloudflare's terms limit how much video its free service carries. To watch Jellyfin away from home, Tailscale is the safer choice."})
    return {"type": "list", "title": "Addresses away from home",
            "intro": "The addresses to use when you are out, through " + how + ". Download apps are never shared.",
            "items": items, "notices": notices}


def handle_screen(body):
    action, aid = body.get("action"), body.get("id")
    if action == "test":
        said = test([aid] if aid in NAMES else None)["said"]
    elif action == "test_all":
        said = test()["said"]
    else:
        return {**screen(), "said": "Nothing to change here: use the settings above."}
    return {**screen(), "said": said}


ROUTES = {("GET", "/health"): lambda b: {"ok": True}, ("GET", "/card"): lambda b: card(), ("GET", "/screen"): lambda b: screen(),
          ("POST", "/screen"): handle_screen, ("POST", "/test"): lambda b: test(), ("POST", "/restart"): lambda b: restart()}


class Handler(BaseHTTPRequestHandler):
    def _answer(self, method):
        if self.client_address[0].startswith(("127.", "::1", "::ffff:127.")) and not ALLOW_LOOPBACK:
            return self._send(403, {"error": "Only Starboard may ask"})  # a visitor through the tunnel arrives on 127.0.0.1
        fn = ROUTES.get((method, urllib.parse.urlparse(self.path).path))
        if not fn:
            return self._send(404, {"error": "Not found"})
        body = {}
        if method == "POST":
            n = min(int(self.headers.get("Content-Length") or 0), 65536)
            try:
                body = json.loads(self.rfile.read(n) or b"{}") if n else {}
            except ValueError:
                body = {}
        try:
            return self._send(200, fn(body if isinstance(body, dict) else {}))
        except Exception as e:  # noqa: BLE001 - Starboard shows the message
            return self._send(502, {"error": f"{e}"[:200]})

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


# The helper's port answers Starboard on its network. A visitor through the tunnel arrives from 127.0.0.1, so loopback is
# refused (the smoke test, on the host network, allows it with ALLOW_LOOPBACK=1).
BIND = "0.0.0.0"  # nosec B104 - inside its own container
ALLOW_LOOPBACK = os.environ.get("ALLOW_LOOPBACK") == "1"

if __name__ == "__main__":
    threading.Thread(target=supervisor, daemon=True).start()
    port = int(os.environ.get("PORT", 8080))
    print(f"Listening on {BIND}:{port}", flush=True)
    ThreadingHTTPServer((BIND, port), Handler).serve_forever()
