"""Calibre library maker (DASH-590): a new Calibre library made from the books folder, never changing it, with what it
will do said first, progress in words, files it could not read listed, and safe to run again."""
import io
import json
import os
import sys
import unittest
import zipfile
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT, STARBOARD_SRC, load, manifest, starboard_cleaners  # noqa: E402


def epub(path, ok=True):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if ok:
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("mimetype", "application/epub+zip")
    else:
        with open(path, "wb") as f:
            f.write(b"PK\x03\x04 cut short")


class Maker(unittest.TestCase):
    def setUp(self):
        self.app = load("calibre-library")
        self.books = os.path.join(self.app._tmp.name, "books")
        self.lib = os.path.join(self.app._tmp.name, "books-library")
        self.app.SOURCE, self.app.LIBRARY = self.books, self.lib
        epub(os.path.join(self.books, "Author One", "One.epub"))
        epub(os.path.join(self.books, "Author Two", "Two.epub"))
        epub(os.path.join(self.books, "Author Two", "Broken.epub"), ok=False)
        os.makedirs(os.path.join(self.books, ".hidden"))
        with open(os.path.join(self.books, ".hidden", "no.epub"), "wb") as f:
            f.write(b"x")
        with open(os.path.join(self.books, "Author One", "cover.jpg"), "wb") as f:
            f.write(b"x")

    def tearDown(self):
        self.app._tmp.cleanup()

    def test_it_finds_only_book_files_and_leaves_hidden_folders_out(self):
        names = [os.path.relpath(p, self.books) for p, _s in self.app.scan()]
        self.assertEqual(names, ["Author One/One.epub", "Author Two/Broken.epub", "Author Two/Two.epub"])

    def test_a_damaged_file_is_named_not_added(self):
        broken = os.path.join(self.books, "Author Two", "Broken.epub")
        self.assertIn("damaged or cut short", self.app.unreadable(broken, os.path.getsize(broken)))
        good = os.path.join(self.books, "Author One", "One.epub")
        self.assertEqual(self.app.unreadable(good, os.path.getsize(good)), "")
        self.assertEqual(self.app.unreadable(good, 0), "the file is empty")
        pdf = os.path.join(self.books, "x.pdf")
        with open(pdf, "wb") as f:
            f.write(b"not a pdf at all")
        self.assertEqual(self.app.unreadable(pdf, 16), "it is not a PDF file")

    def test_the_plan_says_what_it_will_do_before_anything_is_copied(self):
        p = self.app.plan()
        self.assertEqual((p["found"], p["new_count"]), (3, 3))
        self.assertTrue(p["enough"])
        self.assertGreater(p["seconds"], 6)
        self.assertFalse(os.path.exists(self.lib))  # nothing is made by looking
        with mock.patch.object(self.app, "free_space", return_value=1):
            self.assertFalse(self.app.plan()["enough"])

    def test_not_enough_room_refuses_and_says_how_much(self):
        with mock.patch.object(self.app, "free_space", return_value=10):
            said = self.app.start()["said"]
        self.assertIn("not enough room", said)
        self.assertFalse(self.app._lock.locked())

    def run_now(self, calibre):
        with mock.patch.object(self.app, "calibredb", calibre), mock.patch.object(self.app, "nameless", return_value=[]):
            self.app.run_all(self.app.plan()["new"])
        return self.app.sb.remember("run")

    def test_a_run_adds_what_it_can_lists_what_it_cannot_and_remembers(self):
        seen = []

        def calibre(files):
            seen.append([os.path.relpath(f, self.books) for f in files])
            return [1, 2], []
        run = self.run_now(calibre)
        self.assertEqual(seen, [["Author One/One.epub", "Author Two/Two.epub"]])  # the damaged one never went to Calibre
        self.assertEqual((run["state"], run["added"], run["done"], run["total"]), ("ok", 2, 3, 3))
        self.assertEqual(run["left_out"][0]["file"], "Author Two/Broken.epub")
        self.assertIn("1 file could not be read and was left out", run["said"])
        self.assertEqual(len(self.app.sb.remember("done")), 2)

    def test_running_again_adds_only_what_arrived_since(self):
        self.run_now(lambda files: ([1, 2], []))
        epub(os.path.join(self.books, "Author Three", "Three.epub"))
        calls = []
        run = self.run_now(lambda files: (calls.append(files) or [3], []))
        self.assertEqual([os.path.relpath(f, self.books) for f in calls[0]], ["Author Three/Three.epub"])
        self.assertEqual(run["added"], 1)
        self.assertEqual(self.app.plan()["new_count"], 1)  # only the damaged file is still waiting, as it may be mended

    def test_a_batch_that_fails_is_listed_and_the_run_carries_on(self):
        def calibre(files):
            raise RuntimeError("Calibre stopped: database is locked")
        run = self.run_now(calibre)
        self.assertEqual(run["state"], "ok")
        self.assertEqual(len(run["left_out"]), 3)
        self.assertEqual(self.app.sb.remember("done", []), [])  # nothing is marked as handled, so a later run tries again

    def test_stop_ends_the_run_after_the_batch_and_says_so(self):
        for i in range(self.app.BATCH + 1):
            epub(os.path.join(self.books, "Many", f"{i}.epub"))
        self.app._stop.set()
        run = self.run_now(lambda files: ([1], []))
        self.assertEqual(run["state"], "stopped")
        self.assertIn("Run it again to carry on", run["said"])

    def test_the_command_never_goes_through_a_shell_and_names_the_library(self):
        with mock.patch.object(self.app.subprocess, "run") as run:
            run.return_value = mock.Mock(returncode=0, stdout="Added book ids: 4, 5\n", stderr="")
            ids, skipped = self.app.calibredb(["/media/books/a.epub", "/media/books/-odd.epub"])
        cmd = run.call_args[0][0]
        self.assertEqual(cmd[:4], ["calibredb", "add", "--with-library", self.lib])
        self.assertEqual(cmd[4], "--")  # a file name that starts with a dash is a file name
        self.assertEqual(ids, [4, 5])
        self.assertNotIn("shell", run.call_args[1])

    def test_books_already_in_the_library_are_counted_not_added(self):
        out = ("The following books were not added as they already exist in the database (see --duplicates option):\n"
               "  A title\n    /media/books/a.epub\nAdded book ids: 7\n")
        with mock.patch.object(self.app.subprocess, "run", return_value=mock.Mock(returncode=0, stdout=out, stderr="")):
            ids, skipped = self.app.calibredb(["/media/books/a.epub", "/media/books/b.epub"])
        self.assertEqual((ids, skipped), ([7], ["/media/books/a.epub"]))

    def test_the_screen_says_it_plainly_and_starboard_accepts_it(self):
        screen = self.app.screen()
        text = json.dumps(screen)
        self.assertIn("never changed", text)
        self.assertIn("3 book files", text)
        self.assertNotRegex(text, r"\b(can't|don't|won't|isn't|doesn't|it's)\b")
        self.assertNotIn("—", text)
        cleaners = starboard_cleaners()
        if cleaners and hasattr(cleaners[1], "clean_screen"):
            self.assertTrue(cleaners[1].clean_screen(screen))

    def test_a_run_cut_off_by_a_restart_is_said_not_shown_as_running(self):
        self.app.sb.keep("run", {"state": "running", "total": 9, "done": 3, "added": 3, "already": 0, "left_out": [], "no_details": [], "started": "x"})
        screen = self.app.screen()
        self.assertIn("It was interrupted", json.dumps(screen))
        self.assertEqual(self.app.sb.remember("run")["state"], "stopped")


class Manifest(unittest.TestCase):
    def setUp(self):
        self.m = manifest("calibre-library")

    def test_it_asks_for_nothing_and_rests_when_not_used(self):
        self.assertEqual(self.m["permissions"], [])
        c = self.m["containers"][0]
        self.assertEqual(c["start"], "when_needed")
        self.assertEqual(c["volumes"], ["data", "media/books:ro", "media/books-library"])  # the books are read only
        self.assertEqual(c.get("network", "default"), "default")  # no way out to the internet
        self.assertNotIn("user", c)  # not root, and not a different owner from Calibre-Web's, so it can read the library

    def test_it_has_no_dashboard_card_that_would_wake_it(self):
        self.assertNotIn("cards", self.m)
        self.assertNotIn("health", self.m)

    def test_it_passes_starboards_own_check(self):
        if not os.path.isdir(os.path.join(STARBOARD_SRC, "starboard")):
            self.skipTest("Starboard's source is not here (STARBOARD_SRC)")
        sys.path.insert(0, STARBOARD_SRC)
        from starboard import plugins
        from helpers import as_published
        self.assertEqual(as_published(plugins.check(self.m), self.m), [])

    def test_the_dockerfile_keeps_the_image_small_and_checks_calibredb(self):
        with open(os.path.join(ROOT, "calibre-library", "Dockerfile"), encoding="utf-8") as f:
            text = f.read()
        self.assertRegex(text, r"FROM debian:bookworm-slim@sha256:[0-9a-f]{64}")
        self.assertIn("libqt6webenginecore6", text)  # taken out again, in the same step
        self.assertIn("calibredb --version", text)
        self.assertIn("USER 10001:10001", text)


if __name__ == "__main__":
    unittest.main()
