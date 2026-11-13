#!/usr/bin/env python3
"""Runs each example plug-in's image, hardened as Starboard runs it (read only, no capabilities, its own /data), against
a stand-in for Starboard, Jellyfin (with Playback Reporting), Pi-hole, AdGuard Home, Home Assistant and a webhook on this computer, and checks every card
answer with Starboard's own card check. Nothing real is touched. Needs Docker and Starboard's source (STARBOARD_SRC)."""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.environ.get("STARBOARD_SRC", os.path.expanduser("~/src/starboard")))
from starboard import plugin_cards, plugin_custom  # noqa: E402

STUB = int(os.environ.get("SMOKE_STUB_PORT", "39999"))  # several runs at once each give their own (13 November 2026)
NOW = time.strftime("%Y-%m-%dT%H:%M:%S.0000000Z", time.gmtime(time.time() - 3600))
ANSWERS = {
    "/Sessions": [{"UserName": "Sam", "DeviceName": "Lounge TV", "PlayState": {"PositionTicks": 40, "IsPaused": False},
                   "NowPlayingItem": {"Name": "Dune: Part Two", "RunTimeTicks": 100}}, {"UserName": "Idle"}],
    "/Users": [{"Id": "u1"}, {"Id": "u2"}],
    "/Users/u1/Items": {"Items": [{"Name": "Pilot", "SeriesName": "Slow Horses", "UserData": {"LastPlayedDate": NOW}}]},
    "/Users/u2/Items": {"Items": [{"Name": "Pilot", "SeriesName": "Slow Horses", "UserData": {"LastPlayedDate": NOW}},
                                  {"Name": "Brazil", "UserData": {"LastPlayedDate": NOW}}]},
    "/Items": {"Items": [{"Name": "Brazil", "ProductionYear": 1985, "Overview": "x", "ImageTags": {}},
                         {"Name": "Dune", "ProductionYear": 2021, "Overview": "x", "ImageTags": {"Primary": "a"}, "Type": "Movie",
                          "MediaStreams": [{"Type": "Audio", "Index": 1, "DisplayTitle": "English (Audio Description) - AAC - Stereo"}]}]},
    "/api/v1/downloads": {"items": [{"client": "nzbget", "id": "1", "size": 2_000_000_000, "progress": 50}]},
    "/api/v1/system": {"disks": [{"label": "Pool", "used": 6e12, "total": 1e13}]},
    "/control/stats": {"num_blocked_filtering": 420, "num_dns_queries": 3500},
    "/api/auth": {"session": {"sid": "s"}},
    "/api/stats/summary": {"queries": {"blocked": 4210, "total": 35000}},
    "/api/states/binary_sensor.front_door": {"state": "off", "attributes": {"friendly_name": "Front door"}},
    "/api/states/sensor.lounge": {"state": "20.5", "attributes": {"friendly_name": "Lounge", "unit_of_measurement": "°C"}},
    # Watch statistics (DASH-402): Jellyfin with Playback Reporting, answering its custom query
    "/Plugins": [{"Name": "Playback Reporting", "Status": "Active"}],
    "/user_usage_stats/submit_custom_query": {"colums": ["DateCreated", "UserId", "ItemName", "ItemType", "DeviceName", "ClientName", "PlayDuration"],
                                              "results": [[NOW[:19].replace("T", " "), "Sam", "Slow Horses - s01e01 - Pilot", "Episode", "Lounge TV", "Web", "3120"],
                                                          [NOW[:19].replace("T", " "), "Alex", "Dune", "Movie", "Phone", "Android", "9000"]]},
    # Notifications (DASH-401): a webhook that takes anything, and Starboard's recent list
    "/hook": {"ok": True},
    "/api/v1/recent": {"items": []},
}


# Audio description tracks (DASH-410): Jellyfin's search answers with two films whose files are in a stand-in media
# folder; the plug-in adds a track to the one whose length matches and explains the other.
TRACK_FILMS = [{"Id": "m-dune", "Name": "Dune", "ProductionYear": 2021, "Type": "Movie", "RunTimeTicks": 120_000_000,
                "Path": "/data/media/movies/Dune (2021)/Dune (2021).mkv", "MediaStreams": [{"Type": "Audio", "Title": "English"}]},
               {"Id": "m-brazil", "Name": "Brazil", "ProductionYear": 1985, "Type": "Movie", "RunTimeTicks": 120_000_000,
                "Path": "/data/media/movies/Brazil (1985)/Brazil (1985).mkv", "MediaStreams": [{"Type": "Audio", "Title": "English"}]}]


class Stub(BaseHTTPRequestHandler):
    def _go(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if "searchTerm" in q or "Ids" in q:  # the tracks plug-in's search, or one title by its id
            want = (q.get("searchTerm") or [""])[0].lower()
            items = [f for f in TRACK_FILMS if (want and want in f["Name"].lower()) or f["Id"] in (q.get("Ids") or [""])[0].split(",")]
            data = json.dumps({"Items": items, "TotalRecordCount": len(items)}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(data)
            return
        if self.path.startswith("/Items/") and "/Refresh" in self.path:
            self.send_response(204)
            self.end_headers()
            return
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
    "watch-stats": {"days": 30},
}
# What each plug-in is sent before its cards are read: a path, or (path, JSON body) for an event.
POSTS = {"vpn-check": "/check", "line-speed": "/test", "library-health": "/check",
         "notifications": ["/test/webhook", ("/events", {"event": "app.down", "data": {"app": "Jellyfin", "type": "jellyfin"}}), "/weekly-now"],
         "watch-stats": "/refresh", "remote-access": "/test", "audio-description": "/jobs/scan",
         "audio-description-tracks": "/jobs/look"}
SETTINGS["audio-description"] = {"audiovault_links": True}
# Remote access refuses callers on 127.0.0.1 (visitors through its tunnel arrive there); the host network needs this.
ENV = {"remote-access": {"ALLOW_LOOPBACK": "1"}}
SETTINGS["remote-access"] = {"method": "tailscale"}  # no key: it must say so clearly and start nothing


def _wav(path, seconds):
    """A quiet sound file of the given length, made here: no real track is used."""
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\0\0" * 8000 * seconds)


def tracks_media(run, image):
    """The stand-in media folder for Audio description tracks: two films (made by mkvmerge in its own image from
    quiet sound) and two tracks, one 12 seconds like Dune and one 30 seconds, which matches neither."""
    media = f"{run}/media"
    for d in ("movies/Dune (2021)", "movies/Brazil (1985)", "tv", "audio-description", "src"):
        os.makedirs(f"{media}/{d}")
    _wav(f"{media}/src/twelve.wav", 12)
    _wav(f"{media}/audio-description/Dune (2021).wav", 12)
    _wav(f"{media}/audio-description/Brazil (1985).wav", 30)
    for film in ("Dune (2021)", "Brazil (1985)"):
        subprocess.run(["docker", "run", "--rm", "--network", "none", "-v", f"{media}:/m", "--user", f"{os.getuid()}:{os.getgid()}",
                        "--entrypoint", "mkvmerge", image, "-q", "-o", f"/m/movies/{film}/{film}.mkv", "/m/src/twelve.wav"], check=True, capture_output=True)
    for root, dirs, _ in os.walk(media):
        for d in dirs:
            os.chmod(os.path.join(root, d), 0o777)
    return ["-v", f"{media}/movies:/media/movies", "-v", f"{media}/tv:/media/tv", "-v", f"{media}/audio-description:/media/audio-description"]


def tracks_check(run, image):
    """What came of it: Dune got a described track with the right name, language and flags; Brazil did not."""
    media = f"{run}/media"
    added = f"{media}/movies/Dune (2021)/Dune (2021).Audio Description.eng.mka"
    if not os.path.isfile(added) or os.path.exists(f"{media}/movies/Brazil (1985)/Brazil (1985).Audio Description.eng.mka"):
        raise ValueError("the matching track was not added, or the other one was")
    info = json.loads(subprocess.run(["docker", "run", "--rm", "--network", "none", "-v", f"{media}:/m:ro", "--entrypoint", "mkvmerge", image,
                                      "-J", "/m/movies/Dune (2021)/Dune (2021).Audio Description.eng.mka"], capture_output=True, text=True, check=True).stdout)
    p = info["tracks"][0]["properties"]
    want = {"track_name": "English (Audio Description)", "language": "eng", "flag_visual_impaired": True, "default_track": False}
    got = {k: p.get(k) for k in want}
    if got != want:
        raise ValueError(f"the added track is {got}")
    if not os.path.isfile(f"{media}/audio-description/Dune (2021).wav"):
        raise ValueError("the original was not kept")
    return f"added with {got}; original kept; Brazil not added"


def main():
    threading.Thread(target=ThreadingHTTPServer(("127.0.0.1", STUB), Stub).serve_forever, daemon=True).start()
    failed = 0
    port = int(os.environ.get("SMOKE_FIRST_PORT", "40100"))  # each run its own range (13 November 2026)
    for pid in sorted(os.listdir(ROOT)):
        mf = os.path.join(ROOT, pid, "starboard-plugin.json")
        if not os.path.isfile(mf) or not os.path.isfile(os.path.join(ROOT, pid, "Dockerfile")):
            continue
        m = json.load(open(mf))
        # SMOKE_IMAGE: a local build of the shared image for plug-ins that name its next tag, before it is published.
        if os.environ.get("SMOKE_IMAGE") and "/starboard-plugin-examples:" in m["containers"][0]["image"]:
            m["containers"][0]["image"] = os.environ["SMOKE_IMAGE"]
        port += 1
        run = tempfile.mkdtemp(prefix=f"sb-{pid}-")
        os.makedirs(f"{run}/data")
        os.chmod(f"{run}/data", 0o777)
        json.dump(SETTINGS.get(pid, {}), open(f"{run}/settings.json", "w"))
        json.dump({"url": f"http://127.0.0.1:{STUB}", "api_key": "k"}, open(f"{run}/jellyfin.json", "w"))
        open(f"{run}/key", "w").write("sbk_test")
        json.dump({"url": f"http://127.0.0.1:{STUB}", "api_key": "k"}, open(f"{run}/reelix.json", "w"))
        name = f"smoke-{pid}"
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
        extra = tracks_media(run, m["containers"][0]["image"]) if pid == "audio-description-tracks" else []
        subprocess.run(["docker", "run", "-d", "--name", name, "--network", "host", "--read-only", "--tmpfs", "/tmp",
                        "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true", "--pids-limit", "64",
                        *[x for k, v in (m["containers"][0].get("env") or {}).items() for x in ("-e", f"{k}={v}")], *[x for k, v in ENV.get(pid, {}).items() for x in ("-e", f"{k}={v}")], "-e", f"PORT={port}", "-e", f"STARBOARD_API=http://127.0.0.1:{STUB}/api/v1/",
                        "-v", f"{run}/data:/data", "-v", f"{run}/settings.json:/run/starboard/settings.json:ro",
                        "-v", f"{run}/key:/run/starboard/key:ro", "-v", f"{run}/jellyfin.json:/run/starboard/jellyfin.json:ro",
                        "-v", f"{run}/reelix.json:/run/starboard/reelix.json:ro", *extra,
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
        if pid == "audio-description-tracks":
            try:
                print(f"  {pid} media: {tracks_check(run, m['containers'][0]['image'])}")
            except Exception as e:  # noqa: BLE001
                print(f"  {pid} media: FAILED {e}")
                failed += 1
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
