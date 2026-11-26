"""Immich (DASH-518): the server statistics, storage and job queues read from a made-up Immich that answers as its OpenAPI
description says (current /api/queues and the older /api/jobs), the key sent in x-api-key and never kept, answers kept for a
minute, and the manifest Starboard checks. No real Immich was available."""
import json
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import load, manifest, starboard_cleaners  # noqa: E402

STATS = {"photos": 44870, "videos": 3340, "usage": 412_600_000_000, "usagePhotos": 301_200_000_000, "usageVideos": 111_400_000_000,
         "usageByUser": [{"userId": "1", "userName": "Sam", "photos": 40000, "videos": 3000, "usage": 380_000_000_000, "usagePhotos": 1, "usageVideos": 2},
                         {"userId": "2", "userName": "Alex", "photos": 4870, "videos": 340, "usage": 32_600_000_000}]}
STORAGE = {"diskSize": "4 TB", "diskSizeRaw": 4_000_000_000_000, "diskUse": "1.2 TB", "diskUseRaw": 1_200_000_000_000,
           "diskAvailable": "2.8 TB", "diskAvailableRaw": 2_800_000_000_000, "diskUsagePercentage": 30.0}
IDLE = {"active": 0, "completed": 5, "delayed": 0, "failed": 0, "paused": 0, "waiting": 0}
QUEUES = [{"name": "thumbnailGeneration", "isPaused": False, "statistics": {**IDLE, "active": 2, "waiting": 300}},
          {"name": "smartSearch", "isPaused": False, "statistics": {**IDLE, "active": 1, "waiting": 40}},
          {"name": "library", "isPaused": False, "statistics": IDLE}]
LEGACY = {"thumbnailGeneration": {"jobCounts": {**IDLE, "waiting": 3}, "queueStatus": {"isActive": False, "isPaused": False}},
          "library": {"jobCounts": {**IDLE, "failed": 2}, "queueStatus": {"isActive": False, "isPaused": False}}}


class Immich:
    def __init__(self, **over):
        self.answers = {"/api/server/statistics": STATS, "/api/server/storage": STORAGE, "/api/queues": QUEUES, **over}
        self.seen = []
        me = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                me.seen.append((self.path, self.headers.get("x-api-key")))
                got = me.answers.get(self.path)
                code = got if isinstance(got, int) else 200 if got is not None else 404
                raw = json.dumps({} if isinstance(got, int) or got is None else got).encode()
                self.send_response(code)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


def app(server, **values):
    a = load("immich", {"address": server.url, "api_key": "k-secret-123", **values})
    a.CACHE.clear()
    return a


class Cards(unittest.TestCase):
    def setUp(self):
        self.srv = Immich()
        self.addCleanup(self.srv.stop)

    def test_the_library_card_counts_photos_and_videos(self):
        c = app(self.srv).library()
        self.assertEqual((c["value"], c["label"], c["status"]), (48210, "photos and videos", "ok"))
        self.assertEqual(c["note"], "44,870 photos, 3,340 videos, 412.6 GB")
        self.assertEqual(self.srv.seen[0], ("/api/server/statistics", "k-secret-123"))

    def test_the_storage_card_says_where_the_space_goes_and_how_full_the_disk_is(self):
        c = app(self.srv).disk()
        d = {i["title"]: i["detail"] for i in c["items"]}
        self.assertEqual(d["Photos"], "44,870, 301.2 GB")
        self.assertIn("1.2 TB used of 4.0 TB (30%), 2.8 TB free", d["The disk Immich is on"])
        self.assertEqual([i["title"] for i in c["items"][3:]], ["Sam", "Alex"])  # the most space first
        self.assertEqual(c["status"], "ok")

    def test_a_full_disk_uses_starboards_limits(self):
        for pct, status, label in ((89.9, "ok", None), (90, "warning", "Nearly full"), (98, "problem", "Full")):
            self.srv.answers["/api/server/storage"] = {**STORAGE, "diskUsagePercentage": pct}
            a = app(self.srv)
            c = a.disk()
            self.assertEqual((c["status"], c.get("status_label")), (status, label))

    def test_the_jobs_card_says_what_is_working_and_waiting(self):
        c = app(self.srv).jobs()
        self.assertEqual((c["status"], c["state"]), ("working", "ok"))
        self.assertEqual(c["text"], "Working: Thumbnails, Smart search. 340 waiting.")

    def test_failed_jobs_show_even_when_idle(self):
        self.srv.answers["/api/queues"] = [{"name": "library", "isPaused": False, "statistics": {**IDLE, "failed": 4}}]
        c = app(self.srv).jobs()
        self.assertEqual((c["status"], c["state"]), ("warning", "warning"))
        self.assertIn("4 jobs have failed", c["text"])

    def test_idle_is_idle(self):
        self.srv.answers["/api/queues"] = [{"name": "library", "isPaused": False, "statistics": IDLE}]
        self.assertEqual(app(self.srv).jobs()["status"], "idle")

    def test_an_older_immich_without_queues_is_read_through_jobs(self):
        srv = Immich(**{"/api/queues": None, "/api/jobs": LEGACY})
        self.addCleanup(srv.stop)
        c = app(srv).jobs()
        self.assertEqual(c["status"], "working")
        self.assertIn("3 waiting. 2 failed.", c["text"])
        self.assertEqual([p for p, k in srv.seen], ["/api/queues", "/api/jobs"])

    def test_an_address_ending_in_api_is_accepted(self):
        a = app(self.srv, address=self.srv.url + "/api/")
        self.assertEqual(a.library()["value"], 48210)
        self.assertEqual(self.srv.seen[0][0], "/api/server/statistics")


class Care(unittest.TestCase):
    def test_answers_are_kept_for_a_minute_so_three_cards_make_one_set_of_requests(self):
        srv = Immich()
        self.addCleanup(srv.stop)
        a = app(srv)
        a.library(), a.disk(), a.jobs(), a.library(), a.disk(), a.jobs()
        self.assertEqual(sorted(p for p, k in srv.seen), ["/api/queues", "/api/server/statistics", "/api/server/storage"])
        a.CACHE.clear()
        a.library()
        self.assertEqual(len(srv.seen), 4)

    def test_a_refused_key_is_said_in_words_and_never_shown(self):
        srv = Immich(**{"/api/server/statistics": 401})
        self.addCleanup(srv.stop)
        a = app(srv)
        c = a.library()
        self.assertEqual((c["status"], c["status_label"]), ("problem", "Cannot read it"))
        self.assertIn("refused the API key", c["note"])
        self.assertNotIn("k-secret-123", json.dumps(c))
        self.assertEqual(a.clean("x k-secret-123 y"), "x *** y")

    def test_nothing_is_kept_on_disk_and_nothing_is_asked_before_setup(self):
        srv = Immich()
        self.addCleanup(srv.stop)
        a = load("immich", {})
        self.assertEqual(a.library()["status"], "needs_setup")
        self.assertEqual(a.jobs()["status"], "needs_setup")
        self.assertEqual(srv.seen, [])
        b = app(srv)
        b.library(), b.disk(), b.jobs()
        self.assertEqual(os.listdir(b._data), [])

    def test_a_server_that_is_not_there_is_said(self):
        a = load("immich", {"address": "http://127.0.0.1:1", "api_key": "k"})
        self.assertIn("could not be reached", a.library()["note"])

    def test_odd_answers_do_not_break_it(self):
        srv = Immich(**{"/api/server/statistics": {}, "/api/server/storage": {}, "/api/queues": [None]})
        self.addCleanup(srv.stop)
        a = app(srv)
        self.assertEqual(a.library()["value"], 0)
        self.assertEqual(len(a.disk()["items"]), 3)


class StarboardChecks(unittest.TestCase):
    """Starboard refuses a card answer in the wrong shape, so every card is checked in every state it can be in (the smoke
    test found a stat card with no number before setting up)."""

    def test_every_card_in_every_state_passes_starboards_check(self):
        got = starboard_cleaners()
        if not got:
            self.skipTest("Starboard's source is not on this computer")
        cards, _ = got
        types = {"library": "stat", "storage": "list", "jobs": "status"}
        down = Immich(**{"/api/server/statistics": 401, "/api/server/storage": 500, "/api/queues": 503})
        ok = Immich()
        for srv in (down, ok):
            self.addCleanup(srv.stop)
        for a in (load("immich", {}), app(down), app(ok)):
            for name, kind in types.items():
                self.assertTrue(cards.clean(kind, {k: v for k, v in getattr(a, {"library": "library", "storage": "disk", "jobs": "jobs"}[name])().items()}), name)


class Manifest(unittest.TestCase):
    def test_it_runs_only_when_asked_and_is_light(self):
        m = manifest("immich")
        self.assertEqual(m["version"], "0.1.1")
        self.assertEqual(m["containers"][0]["start"], "when_needed")
        self.assertNotIn("jobs", m)
        self.assertEqual(m["permissions"], ["network:lan"])
        self.assertLessEqual(m["resources"]["main"]["memory"], 48)
        self.assertEqual([s["key"] for s in m["settings"] if s["type"] == "secret"], ["api_key"])

    def test_starboard_accepts_the_cards(self):
        got = starboard_cleaners()
        if not got:
            self.skipTest("Starboard's source is not on this computer")
        cards, _ = got
        for c in manifest("immich")["cards"]:
            self.assertTrue(cards.clean(c["type"], c["example"]), c["id"])


if __name__ == "__main__":
    unittest.main()
