#!/usr/bin/env python3
"""Runs each example plug-in's image, hardened as Starboard runs it (read only, no capabilities, its own /data), against
a stand-in for Starboard, Jellyfin, Pi-hole, AdGuard Home, Home Assistant and a webhook on this computer, and checks every card
answer with Starboard's own card check. Nothing real is touched. Needs Docker and Starboard's source (STARBOARD_SRC)."""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.environ.get("STARBOARD_SRC", os.path.expanduser("~/src/starboard")))
from starboard import plugin_cards, plugin_custom  # noqa: E402

STUB = 39999
NOW = time.strftime("%Y-%m-%dT%H:%M:%S.0000000Z", time.gmtime(time.time() - 3600))
ANSWERS = {
    "/Sessions": [{"UserName": "Sam", "DeviceName": "Lounge TV", "PlayState": {"PositionTicks": 40, "IsPaused": False},
                   "NowPlayingItem": {"Name": "Dune: Part Two", "RunTimeTicks": 100}}, {"UserName": "Idle"}],
    "/Users": [{"Id": "u1"}, {"Id": "u2"}],
    "/Users/u1/Items": {"Items": [{"Name": "Pilot", "SeriesName": "Slow Horses", "UserData": {"LastPlayedDate": NOW}}]},
    "/Users/u2/Items": {"Items": [{"Name": "Pilot", "SeriesName": "Slow Horses", "UserData": {"LastPlayedDate": NOW}},
                                  {"Name": "Brazil", "UserData": {"LastPlayedDate": NOW}}]},
    "/Items": {"Items": [{"Name": "Brazil", "ProductionYear": 1985, "Overview": "x", "ImageTags": {}},
                         {"Name": "Dune", "ProductionYear": 2021, "Overview": "x", "ImageTags": {"Primary": "a"}}]},
    "/api/v1/downloads": {"items": [{"client": "nzbget", "id": "1", "size": 2_000_000_000, "progress": 50}]},
    "/api/v1/system": {"disks": [{"label": "Pool", "used": 6e12, "total": 1e13}]},
    "/control/stats": {"num_blocked_filtering": 420, "num_dns_queries": 3500},
    "/api/auth": {"session": {"sid": "s"}},
    "/api/stats/summary": {"queries": {"blocked": 4210, "total": 35000}},
    "/api/states/binary_sensor.front_door": {"state": "off", "attributes": {"friendly_name": "Front door"}},
    "/api/states/sensor.lounge": {"state": "20.5", "attributes": {"friendly_name": "Lounge", "unit_of_measurement": "°C"}},
    # Notifications (DASH-401): a webhook that takes anything, and Starboard's recent list
    "/hook": {"ok": True},
    "/api/v1/recent": {"items": []},
}


class Stub(BaseHTTPRequestHandler):
    def _go(self):
        body = ANSWERS.get(self.path.split("?")[0])
        data = json.dumps(body if body is not None else {}).encode()
        self.send_response(200 if body is not None else 404)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(data)
    do_GET = do_POST = do_DELETE = _go

    def log_message(self, *a):
        pass


SETTINGS = {
    "vpn-check": {"minutes": 15}, "line-speed": {"hour": 4, "megabytes": 5},
    "dns-blocking": {"kind": "Pi-hole", "address": f"http://127.0.0.1:{STUB}", "password": "x"},
    "home-assistant": {"address": f"http://127.0.0.1:{STUB}", "token": "t", "entities": ["binary_sensor.front_door", "sensor.lounge"]},
    "outside-services": {"addresses": ["Stand-in http://127.0.0.1:%d/Users" % STUB, "Nowhere http://127.0.0.1:1"], "minutes": 1},
    "notifications": {"webhook_active": True, "webhooks": f"http://127.0.0.1:{STUB}/hook", "send_apps": True},
}
# What each plug-in is sent before its cards are read: a path, or (path, JSON body) for an event.
POSTS = {"vpn-check": "/check", "line-speed": "/test", "library-health": "/check",
         "notifications": ["/test/webhook", ("/events", {"event": "app.down", "data": {"app": "Jellyfin", "type": "jellyfin"}}), "/weekly-now"]}


def main():
    threading.Thread(target=ThreadingHTTPServer(("127.0.0.1", STUB), Stub).serve_forever, daemon=True).start()
    failed = 0
    port = 40100
    for pid in sorted(os.listdir(ROOT)):
        mf = os.path.join(ROOT, pid, "starboard-plugin.json")
        if not os.path.isfile(mf) or not os.path.isfile(os.path.join(ROOT, pid, "Dockerfile")):
            continue
        m = json.load(open(mf))
        port += 1
        run = tempfile.mkdtemp(prefix=f"sb-{pid}-")
        os.makedirs(f"{run}/data")
        os.chmod(f"{run}/data", 0o777)
        json.dump(SETTINGS.get(pid, {}), open(f"{run}/settings.json", "w"))
        json.dump({"url": f"http://127.0.0.1:{STUB}", "api_key": "k"}, open(f"{run}/jellyfin.json", "w"))
        open(f"{run}/key", "w").write("sbk_test")
        name = f"smoke-{pid}"
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
        subprocess.run(["docker", "run", "-d", "--name", name, "--network", "host", "--read-only", "--tmpfs", "/tmp",
                        "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true", "--pids-limit", "64",
                        *[x for k, v in (m["containers"][0].get("env") or {}).items() for x in ("-e", f"{k}={v}")], "-e", f"PORT={port}", "-e", f"STARBOARD_API=http://127.0.0.1:{STUB}/api/v1/",
                        "-v", f"{run}/data:/data", "-v", f"{run}/settings.json:/run/starboard/settings.json:ro",
                        "-v", f"{run}/key:/run/starboard/key:ro", "-v", f"{run}/jellyfin.json:/run/starboard/jellyfin.json:ro",
                        m["containers"][0]["image"], *(m["containers"][0].get("command") or [])], check=True, capture_output=True)
        base = f"http://127.0.0.1:{port}"
        for _ in range(40):
            try:
                urllib.request.urlopen(base + "/health", timeout=1)
                break
            except OSError:
                time.sleep(0.25)
        for post in ([POSTS[pid]] if isinstance(POSTS.get(pid), str) else POSTS.get(pid) or []):
            path, body = (post, None) if isinstance(post, str) else post
            try:
                r = urllib.request.urlopen(urllib.request.Request(base + path, method="POST", data=json.dumps(body).encode() if body else b"",
                                                                  headers={"Content-Type": "application/json"}), timeout=60)
                ans = json.loads(r.read())
                print(f"  {pid} {path}: {ans.get('said') or ans}")
                if body and ans.get("failed"):
                    raise ValueError(f"not sent: {ans['failed']}")
            except Exception as e:  # noqa: BLE001
                print(f"  {pid} {path}: FAILED {e}")
                failed += 1
        time.sleep(7)  # the background jobs' first run
        for c in m.get("cards") or []:
            try:
                ans = json.loads(urllib.request.urlopen(base + c["path"], timeout=20).read())
                print(f"  {pid} {c['id']}: {json.dumps(plugin_cards.clean(c['type'], ans), ensure_ascii=False)[:150]}")
            except Exception as e:  # noqa: BLE001
                print(f"  {pid} {c['id']}: FAILED {e}")
                failed += 1
        for st in [x for x in m.get("settings") or [] if x["type"] == "custom"]:  # read-only tables and other screens
            try:
                ans = plugin_custom.clean(json.loads(urllib.request.urlopen(base + st["choices"], timeout=20).read()))
                print(f"  {pid} {st['key']}: {len(ans['items'])} rows, {', '.join(c['label'] for c in ans.get('columns') or [])}")
            except Exception as e:  # noqa: BLE001
                print(f"  {pid} {st['key']}: FAILED {e}")
                failed += 1
        stats = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", name], capture_output=True, text=True).stdout.strip()
        print(f"{pid}: memory {stats}")
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    print("FAILED" if failed else "All passed", failed)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
