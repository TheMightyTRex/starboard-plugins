"""Backups watch (DASH-513): Backrest's and Kopia's answers as recorded samples, overdue and failed alerts raised once and
cleared, the password never kept, and the manifest Starboard checks. Neither tool was available to try: the samples
follow each tool's published API (Backrest's service.proto, Kopia's serverapi.go), not a real answer."""
import json
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import load, manifest, starboard_cleaners  # noqa: E402

NOW = 1_795_000_000
BACKREST = {"planSummaries": [
    {"id": "documents", "backupsFailed30days": "1", "backupsWarningLast30days": "0", "backupsSuccessLast30days": "29", "protectedBytes": "41200000000",
     "nextBackupTimeMs": str((NOW + 3600) * 1000),
     "recentBackups": {"flowId": ["1", "2", "3"], "timestampMs": [str((NOW - 3 * 86400) * 1000), str((NOW - 2 * 86400) * 1000), str((NOW - 3600) * 1000)],
                       "durationMs": ["10", "10", "10"], "status": ["STATUS_SUCCESS", "STATUS_ERROR", "STATUS_SUCCESS"],
                       "bytesAdded": ["500", "0", "800"]}},
    {"id": "photos", "backupsFailed30days": "3", "protectedBytes": "900",
     "recentBackups": {"timestampMs": [str((NOW - 5 * 86400) * 1000), str((NOW - 40 * 3600) * 1000)], "status": ["STATUS_SUCCESS", "STATUS_ERROR"], "bytesAdded": ["7", "0"]}}]}
KOPIA = {"localUsername": "sam", "localHost": "server", "sources": [
    {"source": {"host": "server", "userName": "sam", "path": "/media/docs"}, "status": "IDLE", "nextSnapshotTime": "2026-11-23T03:00:00Z",
     "lastSnapshot": {"startTime": "2026-11-22T03:00:00Z", "endTime": "2026-11-22T03:04:30.123456789Z", "stats": {"totalSize": 5200000000, "errorCount": 0}}},
    {"source": {"host": "server", "userName": "sam", "path": "/media/old"}, "status": "IDLE",
     "lastSnapshot": {"startTime": "2026-11-01T03:00:00Z", "endTime": "2026-11-01T03:01:00Z", "stats": {"totalSize": 10, "errorCount": 4}}}]}


def app(**values):
    a = load("backups-watch", {"tool": "backrest", "address": "http://192.0.2.10:9898", "user": "sam", "password": "s3cret-pass", **values})
    a.sent = []
    a.send_alert = lambda key, state, title, message, level="problem": a.sent.append((key, state, title)) or True
    return a


class Reading(unittest.TestCase):
    def test_backrest_plans(self):
        a = app()
        docs, photos = a.read_backrest(BACKREST)
        self.assertEqual((docs["name"], docs["last"], docs["last_ok"], docs["last_failed"], docs["failures"], docs["size"]),
                         ("documents", NOW - 3600, NOW - 3600, False, 1, 41_200_000_000))
        self.assertEqual([r["ok"] for r in docs["runs"]], [True, False, True])
        self.assertTrue(photos["last_failed"])
        self.assertEqual(photos["last_ok"], NOW - 5 * 86400)

    def test_kopia_sources(self):
        a = app(tool="kopia")
        docs, old = a.read_kopia(KOPIA)
        self.assertEqual(docs["name"], "sam@server:/media/docs")
        self.assertEqual((docs["last"] > 0, docs["last_failed"], docs["size"]), (True, False, 5_200_000_000))
        self.assertTrue(old["last_failed"])
        self.assertEqual((old["failures"], old["last_ok"]), (4, 0))

    def test_odd_answers_do_not_break_it(self):
        a = app()
        self.assertEqual(a.read_backrest({}), [])
        self.assertEqual(a.read_kopia({"sources": [{"source": {}}]})[0]["last"], 0)
        self.assertEqual(a._epoch("garbage"), 0)


class Alerts(unittest.TestCase):
    def test_overdue_and_failed_are_raised_once_and_cleared(self):
        a = app(overdue_hours=24)
        backups = a.read_backrest(BACKREST)
        a.alert(backups, NOW)
        self.assertEqual(sorted(k for k, s, t in a.sent if s == "raised"), ["failed:photos", "overdue:photos"])
        a.alert(backups, NOW + 60)
        self.assertEqual(len(a.sent), 2)  # nothing twice
        fixed = a.read_backrest(BACKREST)
        fixed[1].update(last_failed=False, last_ok=NOW)
        a.alert(fixed, NOW + 120)
        self.assertEqual(sorted(k for k, s, t in a.sent if s == "cleared"), ["failed:photos", "overdue:photos"])
        self.assertEqual(a.remember("raised"), {})

    def test_the_hours_are_the_owners_choice(self):
        a = app(overdue_hours=200)
        self.assertEqual([k for k in a.problems(a.read_backrest(BACKREST), NOW)], ["failed:photos"])

    def test_alerts_can_be_switched_off(self):
        a = app(alerts=False)
        a.alert(a.read_backrest(BACKREST), NOW)
        self.assertEqual(a.sent, [])

    def test_a_starboard_without_alerts_is_said_once_an_hour(self):
        a = load("backups-watch", {"address": "http://x"})
        calls = []
        a._post_starboard = lambda path, body: calls.append(path) or 404
        self.assertFalse(a.send_alert("k", "raised", "t", "m"))
        self.assertFalse(a.send_alert("k", "raised", "t", "m"))
        self.assertEqual(len(calls), 1)


class Job(unittest.TestCase):
    def test_check_keeps_the_answer_and_cards_read_it(self):
        a = app()
        a.read_tool = lambda: a.read_backrest(BACKREST)
        self.assertIn("Checked 2 backups", a.check()["said"])
        card = a.card()
        self.assertEqual(card["status"], "problem")
        self.assertIn("photos", card["text"])
        items = a.runs_list()["items"]
        self.assertEqual([i["title"] for i in items], ["documents", "photos"])
        self.assertIn("41.2 GB", items[0]["detail"])
        series = a.sizes()["series"]
        self.assertEqual(series[0]["points"], [500, None, 800])

    def test_a_failed_check_says_why_and_keeps_the_last_good_answer(self):
        a = app()
        a.read_tool = lambda: a.read_backrest(BACKREST)
        a.check()
        import urllib.error

        def boom():
            raise urllib.error.HTTPError("http://x", 401, "no", {}, None)
        a.read_tool = boom
        self.assertIn("refused the user name or password", a.check()["said"])
        self.assertEqual(a.card()["status"], "problem")
        self.assertTrue(a.remember("state")["backups"])

    def test_before_setup_the_card_says_what_to_do(self):
        a = load("backups-watch", {})
        self.assertEqual(a.card()["status"], "needs_setup")

    def test_the_password_is_never_kept_or_shown(self):
        a = app()

        def boom():
            raise ValueError("bad s3cret-pass for sam")
        a.read_tool = boom
        a.check()
        for name in os.listdir(a._data):
            self.assertNotIn("s3cret-pass", open(os.path.join(a._data, name)).read())
        self.assertNotIn("s3cret-pass", json.dumps(a.card()))
        self.assertEqual(a.clean("x s3cret-pass y"), "x *** y")

    def test_sign_in_is_basic(self):
        a = app()
        self.assertTrue(a._headers()["Authorization"].startswith("Basic "))
        self.assertNotIn("Authorization", load("backups-watch", {})._headers())


class Manifest(unittest.TestCase):
    def test_it_rests_and_runs_hourly(self):
        m = manifest("backups-watch")
        self.assertEqual(m["version"], "0.1.0")
        self.assertEqual(m["containers"][0]["start"], "when_needed")
        self.assertEqual(m["jobs"][0]["every_hours"], 1)
        self.assertIn("alerts:send", m["permissions"])
        self.assertEqual([s["key"] for s in m["settings"] if s["type"] == "secret"], ["password"])
        self.assertEqual({c["type"] for c in m["cards"]}, {"status", "list", "sparkline"})

    def test_starboard_accepts_the_manifest_and_the_cards(self):
        got = starboard_cleaners()
        if not got:
            self.skipTest("Starboard's source is not on this computer")
        cards, _ = got
        m = manifest("backups-watch")
        for c in m["cards"]:
            self.assertTrue(cards.clean(c["type"], c["example"]), c["id"])


if __name__ == "__main__":
    unittest.main()
