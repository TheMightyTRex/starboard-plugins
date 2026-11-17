"""Jellyfin 12 with legacy authorisation off (DASH-458): the key in X-Emby-Token alone is refused with 401, so every
plug-in sends it in Authorization too. A stand-in that refuses X-Emby-Token alone still answers each plug-in's calls."""
import importlib.util
import json
import os
import threading
import unittest
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from tests.helpers import ROOT, load

KEY = "jf-key"


class Jellyfin12(BaseHTTPRequestHandler):
    seen = []

    def log_message(self, *a):
        pass

    def _answer(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n:
            self.rfile.read(n)
        self.seen.append((self.command, self.path, dict(self.headers)))
        if self.headers.get("Authorization") != f'MediaBrowser Token="{KEY}"':  # EnableLegacyAuthorization off
            self.send_response(401)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        raw = json.dumps({"Version": "12.4.0"}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    do_GET = do_POST = _answer


class LegacyAuthorisationOff(unittest.TestCase):
    def setUp(self):
        Jellyfin12.seen = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Jellyfin12)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.jf = {"url": f"http://127.0.0.1:{self.server.server_address[1]}", "api_key": KEY}

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def load(self, pid):
        mod = load(pid, jellyfin=self.jf)
        self.addCleanup(mod._tmp.cleanup)
        return mod

    def assert_answered(self, got):
        self.assertEqual(got, {"Version": "12.4.0"})
        self.assertEqual(Jellyfin12.seen[-1][2].get("X-Emby-Token"), KEY)  # kept for older Jellyfin and Emby

    def test_stand_in_refuses_the_legacy_header_alone(self):
        mod = self.load("direct-play")
        with self.assertRaises(urllib.error.HTTPError) as e:
            mod.fetch(self.jf["url"] + "/System/Info", {"X-Emby-Token": KEY})
        self.assertEqual(e.exception.code, 401)

    def test_shared_helper(self):  # Watching now, Most watched, Library health and Watch statistics
        self.assert_answered(self.load("direct-play").sbplugin.jellyfin("/System/Info"))

    def test_every_copy_of_the_helper(self):
        self.load("direct-play")  # PLUGIN_RUN with jellyfin.json for the stand-in
        for pid in sorted(os.listdir(ROOT)):
            path = os.path.join(ROOT, pid, "sbplugin.py")
            if not os.path.isfile(path) or pid == "picture-shrinker":  # Picture shrinker 1.2 has its own fix
                continue
            with self.subTest(pid):
                spec = importlib.util.spec_from_file_location(f"sbplugin_{pid.replace('-', '_')}", path)
                copy = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(copy)
                self.assert_answered(copy.jellyfin("/System/Info"))

    def test_direct_play(self):
        self.assert_answered(self.load("direct-play").jellyfin("/Library/Refresh", method="POST"))

    def test_library_cleanup(self):
        self.assert_answered(self.load("library-cleanup").jf("/System/Info"))

    def test_watch_stats(self):
        self.assert_answered(self.load("watch-stats").jellyfin_post("/user_usage_stats/submit_custom_query", {"CustomQueryString": "SELECT 1"}))

    def test_audio_description(self):
        self.assert_answered(self.load("audio-description").jellyfin("/System/Info"))

    def test_audio_description_tracks(self):
        self.assert_answered(self.load("audio-description-tracks").jellyfin("/System/Info"))


if __name__ == "__main__":
    unittest.main()
