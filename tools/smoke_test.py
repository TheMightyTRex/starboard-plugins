#!/usr/bin/env python3
"""Runs each example plug-in's image, hardened as Starboard runs it (read only, no capabilities, its own /data), against
a stand-in for Starboard, Jellyfin (with Playback Reporting), Pi-hole, AdGuard Home, Home Assistant and a webhook on this computer, and checks every card
answer with Starboard's own card check. Nothing real is touched. Needs Docker and Starboard's source (STARBOARD_SRC).

Then the update from each plug-in's last published version (plug-in API 1.14, 15 November 2026): the old image, from
the manifest at the commit in tools/previous-versions.json, runs and keeps its data; its settings move with Starboard's
own migration code; the new image starts on the same data and must answer its health path within the update's health
wait; its after step and its cards are checked, and then its before step must say it is ready. Then Roll back (DASH-423):
the old image again on the same data with the settings kept from before, which must start, answer its cards and have
its settings as they were.

A local build of a plug-in's own image, before it is published: SMOKE_IMAGE_<ID> (such as SMOKE_IMAGE_PICTURE_SHRINKER),
or SMOKE_IMAGE for the shared image. SMOKE_UPDATE=0 leaves the update pass out; SMOKE_ONLY=<id>,<id> runs only those.

App plug-ins whose helper runs in the official Python image from the manifest's files (Themearr and Checkrr): the
helper runs as Starboard runs it, against stand-ins for the app's own API, and its cards, pages and buttons are checked."""
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
from starboard import plugin_cards, plugin_custom, plugin_update  # noqa: E402

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


# Library clean-up (DASH-406): Jellyfin with a Films and a Series library at its own paths, one film everyone watched
# 200 days ago and one series that ended, all watched; Reelix following both. The stand-in media folder has small
# made-up files at the same places, so the move, the holding folder and Put back are real, on a copy.
OLD = time.strftime("%Y-%m-%dT%H:%M:%S.0000000Z", time.gmtime(time.time() - 200 * 86400))
LC_ITEMS = {"lc-films": [{"Id": "lc-a", "Name": "Old Film", "ProductionYear": 2001, "DateCreated": OLD, "ProviderIds": {"Tmdb": "111"},
                          "Path": "/data/media/movies/Old Film (2001)/Old Film (2001).mkv", "UserData": {"Played": True, "LastPlayedDate": OLD}}],
            "lc-series": [{"Id": "lc-s", "Name": "Harbour Lights", "ProductionYear": 2019, "DateCreated": OLD, "Status": "Ended",
                           "ProviderIds": {"Tvdb": "9000"}, "Path": "/data/media/tv/Harbour Lights (2019)", "UserData": {"Played": True}}]}
LC_ANSWERS = {"/Library/VirtualFolders": [{"Name": "Films", "ItemId": "lc-films", "CollectionType": "movies", "Locations": ["/data/media/movies"]},
                                          {"Name": "Series", "ItemId": "lc-series", "CollectionType": "tvshows", "Locations": ["/data/media/tv"]}],
              "/UserItems/Resume": {"Items": [], "TotalRecordCount": 0},
              "/movies": {"items": [{"id": 7, "tmdb_id": 111, "monitored": True}], "total": 1},
              "/series": {"items": [{"id": 30, "tvdb_id": 9000, "monitored": True}], "total": 1},
              "/series/30/episodes": [{"id": 301, "season_number": 1, "monitored": True}]}
LC_TOLD = []


class Stub(BaseHTTPRequestHandler):
    def _go(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        here = urllib.parse.urlparse(self.path).path
        lc = None
        if (q.get("ParentId") or [""])[0] in LC_ITEMS:
            lc = {"Items": LC_ITEMS[q["ParentId"][0]], "TotalRecordCount": 1}
        elif (q.get("IncludeItemTypes") or [""])[0] in ("BoxSet", "Episode"):
            lc = {"Items": [], "TotalRecordCount": 0}
        elif here in LC_ANSWERS:
            lc = LC_ANSWERS[here]
        elif here == "/Library/Media/Updated" or (self.command in ("PUT", "POST") and here.startswith(("/movies", "/series", "/episodes"))):
            n = int(self.headers.get("Content-Length") or 0)
            LC_TOLD.append((self.command, here, json.loads(self.rfile.read(n) or b"null")))
            lc = {}
        if lc is not None:
            data = json.dumps(lc).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(data)
            return
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
        known = self.path.split("?")[0] in ANSWERS
        data = json.dumps(body if known else {}).encode()
        self.send_response(200 if known else 404)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(data)
    do_GET = do_POST = do_DELETE = do_PUT = _go

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
POSTS = {"picture-shrinker": "/jobs/shrink", "vpn-check": "/check", "line-speed": "/test", "library-health": "/check",
         "notifications": ["/test/webhook", ("/events", {"event": "app.down", "data": {"app": "Jellyfin", "type": "jellyfin"}}), "/weekly-now"],
         "watch-stats": "/refresh", "remote-access": "/test", "audio-description": "/jobs/scan",
         "audio-description-tracks": "/jobs/look"}
SETTINGS["audio-description"] = {"audiovault_links": True}
# App plug-ins with a helper in the official Python image (17 November 2026): the helper runs against stand-ins for
# Themearr's and Checkrr's own APIs here, as it would against the app beside it. Run by app_helpers() below.
ANSWERS.update({
    "/api/settings/radarr": {"source": "radarr", "url": f"http://127.0.0.1:{STUB}/radarr", "configured": True},
    "/api/settings": {"selectedServers": [], "selectedLibraries": {}, "pathMappings": [], "libraryPaths": [],
                      "advanced": {"maxSearchDirs": 20000, "searchDepth": 4}, "autoDownload": True, "autoSync": True},
    "/api/setup/status": {"setupComplete": False}, "/api/setup/complete": {"setupComplete": True}, "/api/sync": {"started": True},
    "/api/settings/rapidapi": {"configured": True},
    "/api/stats": {"total": 450, "downloaded": 412, "pending": 38, "ignored": 0},
    "/api/stats/current": {"filesChecked": 8214, "running": False, "unknownFileCount": 2},
    "/api/files/bad": [{"Path": "/media/movies/Broken (2002)/Broken (2002).mkv",
                        "Data": {"fileExt": ".mkv", "reacquire": False, "service": "unknown", "date": 1794926812, "reason": "not recognized"}},
                       {"Path": "/media/tv/Show/Season 01/Show S01E02.mkv",
                        "Data": {"fileExt": ".mkv", "reacquire": False, "service": "unknown", "date": 1794926812, "reason": "File ended prematurely"}}],
    "/api/schedule": "2026-11-22 03:30:00 +0000 UTC", "/api/run": None,
})
HELPER_URL = {"themearr": "THEMEARR_URL", "checkrr": "CHECKRR_URL"}  # where each helper finds its app
POSTS["library-cleanup"] = "/jobs/move"  # DASH-406: activated here, on a stand-in media folder of made-up files
SETTINGS["library-cleanup"] = {"active": True}
SETTINGS["picture-shrinker"] = {"originals": "keep"}  # 1.2.0: nothing is shrunk until the backup is chosen
# Remote access refuses callers on 127.0.0.1 (visitors through its tunnel arrive there); the host network needs this.
ENV = {"remote-access": {"ALLOW_LOOPBACK": "1"}}
SETTINGS["remote-access"] = {"method": "tailscale"}
SETTINGS["direct-play"] = {"when": "any", "device_roku_express": True}
ENV["direct-play"] = {"DIRECT_PLAY_FIRST": "1"}  # no key: it must say so clearly and start nothing


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


def dp_media(run, image):
    """The stand-in media folder for Direct play (DASH-425): an AVI to repackage and an episode with FLAC 5.1 only,
    each a second long, made by ffmpeg in the plug-in's own image."""
    media = f"{run}/media"
    for d in ("movies/Old (1999)", "tv/Show/Season 1"):
        os.makedirs(f"{media}/{d}")
    for out, audio in (("movies/Old (1999)/Old (1999).avi", ["-c:a", "mp3"]), ("tv/Show/Season 1/Show S01E01.mkv", ["-ac", "6", "-c:a", "flac"])):
        subprocess.run(["docker", "run", "--rm", "--network", "none", "-v", f"{media}:/m", "--user", f"{os.getuid()}:{os.getgid()}",
                        "--entrypoint", "ffmpeg", image, "-v", "error", "-f", "lavfi", "-i", "testsrc=size=160x90:rate=10:duration=1",
                        "-f", "lavfi", "-i", "sine=duration=1", "-c:v", "libx264", "-pix_fmt", "yuv420p", *audio, f"/m/{out}"],
                       check=True, capture_output=True)
    for root, dirs, _ in os.walk(media):
        for d in dirs:
            os.chmod(os.path.join(root, d), 0o777)
    return ["-v", f"{media}/movies:/media/movies", "-v", f"{media}/tv:/media/tv"]


def dp_check(run, image):
    """What came of it: the AVI is an MKV, the episode has a Dolby Digital track first with its FLAC kept."""
    media = f"{run}/media"
    for _ in range(60):
        if os.path.isfile(f"{media}/movies/Old (1999)/Old (1999).mkv") and not os.path.exists(f"{media}/movies/Old (1999)/Old (1999).avi"):
            break
        time.sleep(1)
    else:
        raise ValueError("the AVI was not repackaged")
    for _ in range(60):
        info = json.loads(subprocess.run(["docker", "run", "--rm", "--network", "none", "-v", f"{media}:/m:ro", "--entrypoint", "ffprobe", image,
                                          "-v", "error", "-print_format", "json", "-show_streams", "/m/tv/Show/Season 1/Show S01E01.mkv"],
                                         capture_output=True, text=True, check=True).stdout)
        audio = [x["codec_name"] for x in info["streams"] if x["codec_type"] == "audio"]
        if audio == ["ac3", "flac"]:
            return "AVI repackaged as MKV; Dolby Digital added before the FLAC, which was kept"
        time.sleep(1)
    raise ValueError(f"the episode's sound is {audio}")


def ps_media(run, image):
    """The stand-in metadata folder for Picture shrinker (DASH-432): a large poster, a small one, a backdrop and a large
    photo of a person, made by Pillow in the plug-in's own image."""
    meta = f"{run}/metadata"
    os.makedirs(meta)
    os.chmod(meta, 0o777)
    script = ("from PIL import Image\nimport os\n"
              "for p, size in (('library/aa/1/poster.jpg', (1000, 1500)), ('library/aa/1/backdrop.jpg', (1920, 1080)),"
              " ('library/bb/2/poster.jpg', (500, 750)), ('People/S/Sam/folder.jpg', (900, 1200))):\n"
              "    os.makedirs(os.path.dirname('/m/' + p), exist_ok=True)\n"
              "    Image.effect_noise(size, 60).convert('RGB').save('/m/' + p, 'JPEG', quality=95)\n")
    subprocess.run(["docker", "run", "--rm", "--network", "none", "-v", f"{meta}:/m", "--user", f"{os.getuid()}:{os.getgid()}",
                    "--entrypoint", "python3", image, "-c", script], check=True, capture_output=True)
    for root, dirs, _ in os.walk(meta):
        for d in dirs:
            os.chmod(os.path.join(root, d), 0o777)
    return ["-v", f"{meta}:/metadata"]


def ps_check(run, image):
    """What came of Shrink pictures: the large poster is 900 tall, the photo 400 wide, the rest as they were."""
    out = subprocess.run(["docker", "run", "--rm", "--network", "none", "-v", f"{run}/metadata:/m:ro", "--entrypoint", "python3", image, "-c",
                          "from PIL import Image\nfor p in ('library/aa/1/poster.jpg', 'library/aa/1/backdrop.jpg', 'library/bb/2/poster.jpg', 'People/S/Sam/folder.jpg'):\n"
                          "    print(Image.open('/m/' + p).size)"], capture_output=True, text=True, check=True).stdout.split("\n")
    want = ["(600, 900)", "(1920, 1080)", "(500, 750)", "(400, 533)"]
    if out[:4] != want:
        raise ValueError(f"the pictures are {out[:4]}, not {want}")
    return "poster to 600 by 900, photo to 400 by 533; the backdrop and the small poster as they were"


def lc_media(run, image):
    """The stand-in media folder for Library clean-up: a film and a series as small made-up files, owned by anyone."""
    media = f"{run}/media"
    for path, size in (("movies/Old Film (2001)/Old Film (2001).mkv", 4096), ("movies/Old Film (2001)/Old Film (2001).en.srt", 64),
                       ("tv/Harbour Lights (2019)/Season 01/Harbour Lights S01E01.mkv", 8192), ("movies/Keep Me (2010)/Keep Me (2010).mkv", 100)):
        os.makedirs(os.path.dirname(f"{media}/{path}"), exist_ok=True)
        with open(f"{media}/{path}", "wb") as f:
            f.write(b"x" * size)
    for root, dirs, _ in os.walk(media):
        os.chmod(root, 0o777)
    return ["-v", f"{media}:/media"]


def lc_check(run, base):
    """What came of the move: both went to the holding folder keeping their folders, Reelix and Jellyfin were told,
    the other film stayed; then Put back returns the film and Reelix follows it again."""
    media, hold = f"{run}/media", f"{run}/media/.holding/library-cleanup"
    for _ in range(60):
        if os.path.isfile(f"{hold}/movies/Old Film (2001)/Old Film (2001).en.srt") and os.path.isdir(f"{hold}/tv/Harbour Lights (2019)/Season 01"):
            break
        time.sleep(1)
    else:
        raise ValueError("the film and the series did not reach the holding folder")
    if os.path.exists(f"{media}/movies/Old Film (2001)") or not os.path.isfile(f"{media}/movies/Keep Me (2010)/Keep Me (2010).mkv"):
        raise ValueError("the wrong things moved")
    told = {(m, p) for m, p, _ in LC_TOLD}
    for want in (("PUT", "/movies/7"), ("PUT", "/series/30"), ("POST", "/Library/Media/Updated")):
        if want not in told:
            raise ValueError(f"{want} was not called")
    held = json.loads(urllib.request.urlopen(base + "/held", timeout=20).read())
    film = next(i for i in held["items"] if i["title"].startswith("Old Film"))
    out = post(base, "/held", {"action": "restore", "id": film["id"]})
    if not os.path.isfile(f"{media}/movies/Old Film (2001)/Old Film (2001).mkv") or ("PUT", "/movies/7", {"monitored": True}) not in LC_TOLD:
        raise ValueError(f"Put back did not return it: {out.get('said')}")
    return f"film and series moved keeping their folders, Reelix and Jellyfin told; Put back said: {out.get('said')}"


def image_for(pid, m):
    """The image to run: a local build named in SMOKE_IMAGE_<ID>, or SMOKE_IMAGE for the shared image, else the manifest's."""
    image = m["containers"][0]["image"]
    if os.environ.get("SMOKE_IMAGE") and "/starboard-plugin-examples:" in image:
        image = os.environ["SMOKE_IMAGE"]
    return os.environ.get("SMOKE_IMAGE_" + pid.upper().replace("-", "_")) or image


def start(pid, m, run, port, image, extra=()):
    name = f"smoke-{pid}"
    subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    subprocess.run(["docker", "run", "-d", "--name", name, "--network", "host", "--read-only", "--tmpfs", "/tmp",
                    "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true", "--pids-limit", "64", "--memory", "512m",
                    *[x for k, v in (m["containers"][0].get("env") or {}).items() for x in ("-e", f"{k}={v}")],
                    *[x for k, v in ENV.get(pid, {}).items() for x in ("-e", f"{k}={v}")], "-e", f"PORT={port}",
                    "-e", f"STARBOARD_API=http://127.0.0.1:{STUB}/api/v1/",
                    "-v", f"{run}/data:/data", "-v", f"{run}/settings.json:/run/starboard/settings.json:ro",
                    "-v", f"{run}/key:/run/starboard/key:ro", "-v", f"{run}/jellyfin.json:/run/starboard/jellyfin.json:ro",
                    "-v", f"{run}/reelix.json:/run/starboard/reelix.json:ro", *extra,
                    image, *(m["containers"][0].get("command") or [])], check=True, capture_output=True)
    return name


def healthy(base, wait):
    """Seconds until /health answers 200, or None after `wait` seconds (as Starboard asks: every 3 seconds at most)."""
    began = time.monotonic()
    while time.monotonic() - began < wait:
        try:
            if urllib.request.urlopen(base + "/health", timeout=2).status == 200:
                return round(time.monotonic() - began, 1)
        except OSError:
            pass
        time.sleep(0.5)
    return None


def post(base, path, body=None, timeout=60):
    r = urllib.request.urlopen(urllib.request.Request(base + path, method="POST", data=json.dumps(body).encode() if body is not None else b"",
                                                      headers={"Content-Type": "application/json"}), timeout=timeout)
    return json.loads(r.read() or b"{}")


def update_pass(port, only=()):
    """Each plug-in from its last published version to this one, on the same data (only those in SMOKE_ONLY, when it is
    given). Returns how many failed."""
    prev = json.load(open(os.path.join(ROOT, "tools", "previous-versions.json")))
    failed = 0
    for pid, old_row in sorted(prev["plugins"].items()):
        mf = os.path.join(ROOT, pid, "starboard-plugin.json")
        if not os.path.isfile(os.path.join(ROOT, pid, "Dockerfile")) or (only and pid not in only):
            continue
        new = json.load(open(mf))
        if "network:port" in (new.get("permissions") or []):
            continue  # an app plug-in: tools/app_check.py
        old = json.loads(subprocess.run(["git", "-C", ROOT, "show", f"{prev['commit']}:{pid}/starboard-plugin.json"],
                                        capture_output=True, check=True).stdout)
        port += 1
        run = tempfile.mkdtemp(prefix=f"sb-up-{pid}-")
        os.makedirs(f"{run}/data")
        os.chmod(f"{run}/data", 0o777)
        defaults = {s["key"]: s["default"] for s in old.get("settings") or [] if "default" in s}
        values = {**defaults, **SETTINGS.get(pid, {})}
        json.dump(values, open(f"{run}/settings.json", "w"))
        json.dump({"url": f"http://127.0.0.1:{STUB}", "api_key": "k"}, open(f"{run}/jellyfin.json", "w"))
        json.dump({"url": f"http://127.0.0.1:{STUB}", "api_key": "k"}, open(f"{run}/reelix.json", "w"))
        open(f"{run}/key", "w").write("sbk_test")
        base, words = f"http://127.0.0.1:{port}", []
        extra = tracks_media(run, image_for(pid, new)) if pid == "audio-description-tracks" else []
        try:
            name = start(pid, old, run, port, old["containers"][0]["image"], extra)
            if healthy(base, 20) is None:
                raise ValueError(f"{old['version']} did not start")
            for p in ([POSTS[pid]] if isinstance(POSTS.get(pid), str) else POSTS.get(pid) or []):
                path, body = (p, None) if isinstance(p, str) else p
                try:
                    post(base, path, body)
                except OSError:
                    pass  # the old version's own result is not what is tested here
            time.sleep(7)
            if (old.get("update") or {}).get("before"):
                said = post(base, old["update"]["before"]["path"], {"from": old["version"], "to": new["version"]})
                if not said.get("ok", True):
                    raise ValueError(f"the before step said {said}")
            subprocess.run(["docker", "rm", "-f", name], capture_output=True)
            moved, notes = plugin_update.migrate(old, new, values)
            json.dump(moved, open(f"{run}/settings.json", "w"))
            info = plugin_update.update_info(new)
            name = start(pid, new, run, port, image_for(pid, new), extra)
            took = healthy(base, info["health_wait_seconds"] or 60)
            if took is None:
                raise ValueError(f"{new['version']} did not answer its health path within {info['health_wait_seconds']} seconds")
            words.append(f"healthy in {took}s")
            if info["after"]:
                said = post(base, info["after"]["path"], {"from": old["version"], "to": new["version"], "outcome": "updated"})
                if said.get("ok") is not True:
                    raise ValueError(f"the after step said {said}")
                words.append(f"after: {said.get('said')}")
            time.sleep(2)
            for c in new.get("cards") or []:
                ans = plugin_cards.clean(c["type"], json.loads(urllib.request.urlopen(base + c["path"], timeout=20).read()), strict=True)
                if not ans.get("status") and c["type"] != "status":
                    raise ValueError(f"card {c['id']} has no status")
                words.append(f"{c['id']} {ans.get('status') or ans.get('state')}")
            if info["before"]:
                said = post(base, info["before"]["path"], {"from": new["version"], "to": new["version"]})
                if said.get("ok") is not True:
                    raise ValueError(f"the next update's before step said {said}")
                post(base, info["after"]["path"], {"from": new["version"], "to": new["version"], "outcome": "rolled_back"})
                words.append("before: ready")
            # Roll back (DASH-423), as Starboard does it (plugin_life.rollback): the old image again on the same data,
            # with the settings file kept from before the update put back whole. It must start, answer its cards, and
            # find its settings as they were.
            subprocess.run(["docker", "rm", "-f", name], capture_output=True)
            json.dump(values, open(f"{run}/settings.json", "w"))
            name = start(pid, old, run, port, old["containers"][0]["image"], extra)
            took = healthy(base, 30)
            if took is None:
                raise ValueError(f"after Roll back, {old['version']} did not start on the data {new['version']} left")
            for c in old.get("cards") or []:
                plugin_cards.clean(c["type"], json.loads(urllib.request.urlopen(base + c["path"], timeout=20).read()), strict=False)
            if json.load(open(f"{run}/settings.json")) != values:
                raise ValueError("after Roll back, the settings were not as they were")
            words.append(f"rolled back to {old['version']}: healthy in {took}s, settings as they were")
            print(f"{pid} update {old['version']} to {new['version']}: " + "; ".join(words + [f"settings: {', '.join(notes) or 'as they were'}"]))
        except Exception as e:  # noqa: BLE001
            print(f"{pid} update {old_row['version']} to {new['version']}: FAILED {e}")
            failed += 1
        finally:
            subprocess.run(["docker", "rm", "-f", f"smoke-{pid}"], capture_output=True)
    return failed


def app_helpers(port, only):
    """Each app plug-in's helper (a first container with files and a command, 17 November 2026), run in its image as
    Starboard runs it, with its files written into its folder, against the stand-ins: its health, cards, custom pages
    and buttons must answer, and pass Starboard's own checks. Returns how many failed."""
    failed = 0
    for pid in sorted(os.listdir(ROOT)):
        mf = os.path.join(ROOT, pid, "starboard-plugin.json")
        if not os.path.isfile(mf) or (only and pid not in only):
            continue
        m = json.load(open(mf))
        c = (m.get("containers") or [{}])[0]
        if "network:port" not in (m.get("permissions") or []) or not (c.get("files") and c.get("command")):
            continue
        port += 1
        run = tempfile.mkdtemp(prefix=f"sb-app-{pid}-")
        folder = next(v.split(":", 1)[1] for v in c["volumes"] if v.startswith("data:"))
        os.makedirs(f"{run}/data")
        for fname, text in c["files"].items():
            with open(f"{run}/data/{fname}", "w") as f:
                f.write(text)
        os.chmod(f"{run}/data", 0o777)
        json.dump({}, open(f"{run}/settings.json", "w"))
        json.dump({"url": f"http://127.0.0.1:{STUB}", "api_key": "k"}, open(f"{run}/jellyfin.json", "w"))
        json.dump({"url": f"http://127.0.0.1:{STUB}", "api_key": "k"}, open(f"{run}/reelix.json", "w"))
        open(f"{run}/key", "w").write("sbk_test")
        env = {k: ("s" * 32 if "{secret:" in str(v) else v) for k, v in (c.get("env") or {}).items()}
        env.update({HELPER_URL.get(pid, "APP_URL"): f"http://127.0.0.1:{STUB}", "PORT": str(port), "FIRST_SECONDS": "1"})
        name = f"smoke-{pid}"
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
        base, words = f"http://127.0.0.1:{port}", []
        try:
            subprocess.run(["docker", "run", "-d", "--name", name, "--network", "host", "--read-only", "--tmpfs", "/tmp",
                            "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true", "--pids-limit", "64",
                            "--memory", f"{(m.get('resources') or {}).get(c['name'], {}).get('memory', 64)}m", "--user", c.get("user") or "10001:10001",
                            *[x for k, v in env.items() for x in ("-e", f"{k}={v}")],
                            "-v", f"{run}/data:{folder}", "-v", f"{run}/settings.json:/run/starboard/settings.json:ro",
                            "-v", f"{run}/key:/run/starboard/key:ro", "-v", f"{run}/reelix.json:/run/starboard/reelix.json:ro",
                            c["image"], *c["command"]], check=True, capture_output=True)
            took = healthy(base, 30)
            if took is None:
                raise ValueError("its helper did not answer /health within 30 seconds")
            words.append(f"healthy in {took}s")
            time.sleep(4)  # its first round with the app
            for card in m.get("cards") or []:
                ans = plugin_cards.clean(card["type"], json.loads(urllib.request.urlopen(base + card["path"], timeout=3).read()), strict=True)
                if not ans.get("status"):
                    raise ValueError(f"card {card['id']} has no status")
                words.append(f"{card['id']} {ans.get('status')}: {ans.get('value')} {ans.get('label')}, {ans.get('note')}")
            for st in [x for x in m.get("settings") or [] if x["type"] == "custom"]:
                req = urllib.request.Request(base + st["choices"], headers={"X-Api-Key": "sbk_test"})
                ans = plugin_custom.clean(json.loads(urllib.request.urlopen(req, timeout=20).read()))
                words.append(f"{st['key']}: {len(ans['items'])} rows")
            for a in m.get("actions") or []:
                said = post(base, a["path"])
                words.append(f"{a['id']}: {said.get('said') or said}")
            print(f"{pid} (app plug-in helper): " + "; ".join(words))
        except Exception as e:  # noqa: BLE001
            logs = subprocess.run(["docker", "logs", "--tail", "20", name], capture_output=True, text=True)
            print(f"{pid} (app plug-in helper): FAILED {e}\n{logs.stdout}{logs.stderr}")
            failed += 1
        finally:
            subprocess.run(["docker", "rm", "-f", name], capture_output=True)
    return failed


def main():
    threading.Thread(target=ThreadingHTTPServer(("127.0.0.1", STUB), Stub).serve_forever, daemon=True).start()
    failed = 0
    port = int(os.environ.get("SMOKE_FIRST_PORT", "40100"))  # each run its own range (13 November 2026)
    only = set(filter(None, os.environ.get("SMOKE_ONLY", "").split(",")))  # such as SMOKE_ONLY=library-cleanup
    for pid in sorted(os.listdir(ROOT)):
        mf = os.path.join(ROOT, pid, "starboard-plugin.json")
        if not os.path.isfile(mf) or not os.path.isfile(os.path.join(ROOT, pid, "Dockerfile")) or (only and pid not in only):
            continue
        m = json.load(open(mf))
        if "network:port" in (m.get("permissions") or []):
            # An app plug-in (DASH-411): its app and database are run and measured by tools/app_check.py instead.
            print(f"{pid}: an app plug-in, checked by tools/app_check.py")
            continue
        m["containers"][0]["image"] = image_for(pid, m)  # a local build before it is published
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
        # SMOKE_DIRECT_PLAY_IMAGE: a local build of Direct play's image before it is published (DASH-425).
        if pid == "direct-play" and os.environ.get("SMOKE_DIRECT_PLAY_IMAGE"):
            m["containers"][0]["image"] = os.environ["SMOKE_DIRECT_PLAY_IMAGE"]
        extra = tracks_media(run, m["containers"][0]["image"]) if pid == "audio-description-tracks" else []
        extra = dp_media(run, m["containers"][0]["image"]) if pid == "direct-play" else extra
        extra = ps_media(run, m["containers"][0]["image"]) if pid == "picture-shrinker" else extra
        extra = lc_media(run, m["containers"][0]["image"]) if pid == "library-cleanup" else extra
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
        if pid == "direct-play":
            try:
                print(f"  {pid} media: {dp_check(run, m['containers'][0]['image'])}")
            except Exception as e:  # noqa: BLE001
                print(f"  {pid} media: FAILED {e}")
                failed += 1
        if pid == "picture-shrinker":
            try:
                print(f"  {pid} pictures: {ps_check(run, m['containers'][0]['image'])}")
            except Exception as e:  # noqa: BLE001
                print(f"  {pid} pictures: FAILED {e}")
                failed += 1
        if pid == "library-cleanup":
            try:
                print(f"  {pid} media: {lc_check(run, base)}")
            except Exception as e:  # noqa: BLE001
                print(f"  {pid} media: FAILED {e}")
                failed += 1
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
    failed += app_helpers(port + 30, only)
    if os.environ.get("SMOKE_UPDATE", "1") != "0":
        failed += update_pass(port + 50, only)
    print("FAILED" if failed else "All passed", failed)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
