"""Jellystat plug-in (DASH-411): Jellyfin's address and key handed to Jellystat once, only while it has none; a
restore that only takes a pg_dump file from the restore folder, by name; and a screen and card Starboard accepts."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import load, starboard_cleaners  # noqa: E402


class Connect(unittest.TestCase):
    def setUp(self):
        self.app = load("jellystat")
        self.calls = []

    def fake(self, state):
        def fetch(url, data=None, method=None, **kw):
            self.calls.append((url, data, method))
            return {"state": state} if url.endswith("/auth/isConfigured") else []
        return fetch

    def test_hands_over_only_while_jellystat_has_no_jellyfin(self):
        with mock.patch.object(self.app.sb, "fetch", self.fake(0)):
            self.app.connect()
        posted = [c for c in self.calls if c[2] == "POST"]
        self.assertEqual(posted[0][1], {"JF_HOST": "http://jellyfin.invalid:8096", "JF_API_KEY": "jf-key"})
        self.assertTrue(posted[0][0].endswith("/auth/configSetup"))
        for state in (1, 2):
            self.calls = []
            with mock.patch.object(self.app.sb, "fetch", self.fake(state)):
                self.app.connect()
            self.assertFalse([c for c in self.calls if c[2] == "POST"])
            self.assertTrue(self.app.sb.remember("connect")["ok"])

    def test_no_key_is_said_plainly(self):
        app = load("jellystat", jellyfin={"url": "", "api_key": ""})
        with mock.patch.object(app.sb, "fetch", lambda url, **kw: {"state": 0}):
            app.connect()
        self.assertIn("Settings, Apps", app.sb.remember("connect")["said"])
        self.assertEqual(app.status_card()["state"], "warning")


class Restore(unittest.TestCase):
    def setUp(self):
        self.app = load("jellystat")
        os.makedirs(self.app.RESTORE_DIR, exist_ok=True)

    def put(self, name, data):
        with open(os.path.join(self.app.RESTORE_DIR, name), "wb") as f:
            f.write(data)

    def test_only_a_name_in_the_restore_folder(self):
        for bad in ("../secrets.json", "/etc/passwd", "", ".."):
            with self.assertRaises(ValueError):
                self.app.restore(bad)
        with self.assertRaises(ValueError):
            self.app.restore("missing.pgdump")

    def test_a_json_backup_is_refused_in_words(self):
        self.put("backup.json", b'{"jf_libraries": []}')
        with self.assertRaises(ValueError) as e:
            self.app.restore("backup.json")
        self.assertIn("pg_dump -Fc", str(e.exception))

    def test_the_swap_keeps_the_database_before(self):
        self.put("jfstat.pgdump", b"PGDMP\x01\x0e")
        said, run = [], mock.Mock(return_value=mock.Mock(returncode=0, stderr="", stdout=""))
        with mock.patch.object(self.app.subprocess, "run", run), \
             mock.patch.object(self.app, "psql", lambda sql, db="postgres", timeout=60: said.append(sql) or "12"):
            out = self.app.restore("jfstat.pgdump", stamp="20261113_120000")
        self.assertIn('CREATE DATABASE "jfstat_restore_20261113_120000"', said[0])
        self.assertTrue(any('RENAME TO "jfstat_before_20261113_120000"' in s for s in said))
        self.assertIn('ALTER DATABASE "jfstat_restore_20261113_120000" RENAME TO "jfstat"', said[-1])
        self.assertFalse(any("DROP" in s.upper() for s in said))
        self.assertIn("kept as jfstat_before_20261113_120000", out)

    def test_a_failed_restore_changes_nothing(self):
        self.put("jfstat.pgdump", b"PGDMP\x01\x0e")
        said = []
        results = iter([mock.Mock(returncode=0, stderr=""), mock.Mock(returncode=1, stderr="ERROR: bad")])
        with mock.patch.object(self.app.subprocess, "run", lambda *a, **k: next(results)), \
             mock.patch.object(self.app, "psql", lambda sql, db="postgres", timeout=60: said.append(sql) or ""):
            with self.assertRaises(RuntimeError) as e:
                self.app.restore("jfstat.pgdump", stamp="x1")
        self.assertIn("nothing was changed", str(e.exception))
        self.assertFalse(any('RENAME TO "jfstat_before' in s for s in said))

    def test_screen_and_card_pass_starboards_checks(self):
        self.put("jfstat.pgdump", b"PGDMP")
        cleaners = starboard_cleaners()
        if not cleaners:
            self.skipTest("Starboard's source is not here")
        cards, custom = cleaners
        screen = custom.clean(self.app.screen())
        self.assertEqual([i["title"] for i in screen["items"]], ["jfstat.pgdump"])
        self.assertEqual(cards.clean("status", self.app.status_card())["state"], "warning")

    def test_restore_needs_a_name_first(self):
        self.assertIn("Backup file to restore", self.app.restore_in_background()["said"])


if __name__ == "__main__":
    unittest.main()
