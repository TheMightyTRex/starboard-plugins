"""Picture shrinker (DASH-432): the rules, the check before a picture replaces the original, runs, the schedule, the
card and page, and the update steps. Makes its own small pictures with Pillow in a temporary metadata folder."""
import datetime as dt
import os
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import load, manifest, starboard_cleaners  # noqa: E402

try:
    from PIL import Image
except ImportError:  # the image workflow installs it; skipped where it is missing
    Image = None


def picture(path, size, fmt="JPEG", colour=(200, 120, 40)):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im = Image.blend(Image.new("RGB", size, colour), Image.effect_noise(size, 60).convert("RGB"), 0.5)  # detail, as a photo has
    im.save(path, fmt, **({"quality": 95} if fmt == "JPEG" else {}))
    return path


@unittest.skipIf(Image is None, "Pillow is not installed")
class PictureShrinker(unittest.TestCase):
    def setUp(self):
        self.app = load("picture-shrinker", {})
        self.meta = tempfile.TemporaryDirectory()
        self.app.ROOT = self.meta.name
        self.app._stop.clear()
        self.app.sbplugin._work["hold"] = 0.0

    def tearDown(self):
        t = self.app._job.get("thread")
        if t:
            self.app._stop.set()
            t.join(10)
        self.meta.cleanup()
        self.app._tmp.cleanup()

    def p(self, *parts):
        return os.path.join(self.meta.name, *parts)

    # The rules ------------------------------------------------------------------------------------------------
    def test_rules_follow_the_one_off_shrink(self):
        t = self.app.target
        self.assertEqual(t("poster", (1000, 1500), 900, 400), (600, 900))
        self.assertIsNone(t("poster", (600, 900), 900, 400))
        self.assertEqual(t("person", (800, 1200), 900, 400), (400, 600))
        self.assertIsNone(t("person", (400, 600), 900, 400))
        self.assertIsNone(t(None, (4000, 4000), 900, 400))

    def test_which_pictures_count(self):
        k = self.app.kind_of
        self.assertEqual(k(self.p("library", "ab", "123", "poster.jpg")), "poster")
        self.assertEqual(k(self.p("library", "ab", "123", "Poster.PNG")), "poster")
        self.assertIsNone(k(self.p("library", "ab", "123", "backdrop.jpg")))
        self.assertIsNone(k(self.p("library", "ab", "123", "logo.png")))
        self.assertEqual(k(self.p("People", "S", "Sam Neill", "folder.jpg")), "person")
        self.assertIsNone(k(self.p("People", "S", "Sam Neill", "folder.nfo")))
        self.assertIsNone(k(self.p("library", "ab", "123", ".poster.jpg.picture-shrinker-tmp")))
        self.assertIsNone(k(self.p("collections", "poster.jpg")))

    def test_settings_are_held_to_their_limits(self):
        self.assertEqual(self.app.sizes(), (900, 400))
        self.app._set(poster_height=50, person_width=99999)
        self.assertEqual(self.app.sizes(), (300, 2000))

    # One picture ---------------------------------------------------------------------------------------------
    def test_a_large_jpeg_poster_is_shrunk_and_checked(self):
        path = picture(self.p("library", "ab", "1", "poster.jpg"), (1000, 1500))
        before = os.path.getsize(path)
        got = self.app.shrink_one(path, "poster", 900, 400)
        self.assertEqual(got[0], before)
        self.assertLess(got[1], before)
        with Image.open(path) as im:
            self.assertEqual((im.size, im.format), ((600, 900), "JPEG"))
        self.assertEqual(os.listdir(os.path.dirname(path)), ["poster.jpg"])  # no copy left behind

    def test_png_and_webp_keep_their_format(self):
        for name, fmt in (("poster.png", "PNG"), ("poster.webp", "WEBP")):
            path = picture(self.p("library", "cd", name, name), (800, 1600), fmt)
            self.app.shrink_one(path, "poster", 900, 400)
            with Image.open(path) as im:
                self.assertEqual((im.size, im.format), ((450, 900), fmt))

    def test_a_small_picture_is_left_untouched(self):
        path = picture(self.p("People", "A", "Alex", "folder.jpg"), (300, 450))
        mtime, size = os.stat(path).st_mtime_ns, os.path.getsize(path)
        self.assertIsNone(self.app.shrink_one(path, "person", 900, 400))
        self.assertEqual((os.stat(path).st_mtime_ns, os.path.getsize(path)), (mtime, size))

    def test_a_broken_picture_is_kept_as_it_was(self):
        path = self.p("library", "ef", "1", "poster.jpg")
        os.makedirs(os.path.dirname(path))
        with open(path, "wb") as f:
            f.write(b"\xff\xd8\xff\xe0 not really a picture")
        with self.assertRaises(Exception):
            self.app.shrink_one(path, "poster", 900, 400)
        self.assertEqual(open(path, "rb").read(), b"\xff\xd8\xff\xe0 not really a picture")
        self.assertEqual(os.listdir(os.path.dirname(path)), ["poster.jpg"])

    def test_a_copy_that_fails_its_check_never_replaces_the_original(self):
        path = picture(self.p("library", "gh", "1", "poster.jpg"), (1000, 1500))
        data = open(path, "rb").read()
        real = Image.Image.resize
        try:  # the new picture comes out the wrong size
            Image.Image.resize = lambda im, size, *a, **k: real(im, (size[0] - 1, size[1]), *a, **k)
            with self.assertRaises(ValueError):
                self.app.shrink_one(path, "poster", 900, 400)
        finally:
            Image.Image.resize = real
        self.assertEqual(open(path, "rb").read(), data)
        self.assertEqual(os.listdir(os.path.dirname(path)), ["poster.jpg"])

    # Runs -------------------------------------------------------------------------------------------------------
    def library(self):
        picture(self.p("library", "aa", "1", "poster.jpg"), (1000, 1500))
        picture(self.p("library", "aa", "1", "backdrop.jpg"), (1920, 1080))
        picture(self.p("library", "bb", "2", "poster.jpg"), (500, 750))
        picture(self.p("People", "S", "Sam", "folder.jpg"), (900, 1200))
        os.makedirs(self.p("library", "cc", "3"))
        with open(self.p("library", "cc", "3", "poster.jpg"), "wb") as f:
            f.write(b"broken")
        with open(self.p("library", "aa", "1", ".poster.jpg.picture-shrinker-tmp"), "wb") as f:
            f.write(b"left from a stopped run")

    def test_a_run_counts_and_keeps_the_totals(self):
        self.library()
        backdrop = open(self.p("library", "aa", "1", "backdrop.jpg"), "rb").read()
        rec = self.app.run("now")
        self.assertEqual((rec["seen"], rec["shrunk"], rec["left"], rec["failed"]), (4, 2, 1, 1))
        self.assertGreater(rec["before"], rec["after"])
        self.assertEqual(open(self.p("library", "aa", "1", "backdrop.jpg"), "rb").read(), backdrop)
        self.assertFalse(os.path.exists(self.p("library", "aa", "1", ".poster.jpg.picture-shrinker-tmp")))
        s = self.app._state()
        self.assertEqual((s["shrunk"], len(s["runs"])), (2, 1))
        self.assertIn("Shrank 2 pictures", self.app.summary(rec))
        again = self.app.run("scheduled")  # a second run only opens them
        self.assertEqual((again["shrunk"], again["left"]), (0, 3))

    def test_new_pictures_only_since_the_last_pass(self):
        self.library()
        self.app.run("scheduled")
        since = self.app._state()["new_since"]
        newer = picture(self.p("library", "dd", "4", "poster.jpg"), (1000, 1500))
        os.utime(newer, (since + 5, since + 5))
        self.app.now = lambda: since + 5 + self.app.NEW_AGE + 1
        self.app._set(new_pictures=True)
        said = self.app.job_new()["said"]
        self.assertIn("Shrank 1 picture", said)

    def test_new_pictures_is_deactivated_when_added(self):
        self.assertEqual(manifest("picture-shrinker")["settings"][4]["default"], False)
        self.assertEqual(self.app.job_new()["said"], "Shrinking new pictures is deactivated")

    def test_a_run_stops_at_its_limit_and_the_next_carries_on(self):
        self.library()
        rec = self.app.run("scheduled", limit=-1)
        self.assertEqual(rec["seen"], 0)
        self.assertIn("time limit", rec["stopped"])

    # Schedule -------------------------------------------------------------------------------------------------
    def test_next_run_follows_the_schedule(self):
        sat = dt.datetime(2026, 11, 14, 12, 0).timestamp()  # a Saturday
        self.assertEqual(self.app.next_run(sat), dt.datetime(2026, 11, 15, 3, 30))  # Sunday 03:30 by default
        self.app._set(when={"every": "day", "time": "01:15"})
        self.assertEqual(self.app.next_run(sat), dt.datetime(2026, 11, 15, 1, 15))
        self.app._set(when={"every": "month", "date": 31, "time": "02:00"})
        self.assertEqual(self.app.next_run(sat), dt.datetime(2026, 11, 30, 2, 0))  # November has no 31st

    # Card and page ---------------------------------------------------------------------------------------------
    def test_card_and_page_pass_starboards_checks(self):
        cleaners = starboard_cleaners()
        first = self.app.card()
        self.assertEqual(first["status"], "scheduled")
        self.assertLessEqual(len(first["status_label"]), 24)
        self.library()
        self.app.run("now")
        card, page = self.app.card(), self.app.screen()
        self.assertEqual(card["status"], "scheduled")
        self.assertGreater(card["value"], 0)
        self.assertIn("Could not read", {i["group"] for i in page["items"]})
        if cleaners:
            plugin_cards, plugin_custom = cleaners
            plugin_cards.clean("stat", card, strict=True)
            plugin_custom.clean(page)

    def test_card_while_running(self):
        self.app._job["progress"] = {"seen": 30, "shrunk": 12, "left": 18, "failed": 0, "before": 9_000_000, "after": 3_000_000, "at": time.time()}
        try:
            c = self.app.card()
        finally:
            self.app._job["progress"] = None
        self.assertEqual((c["status"], c["status_label"], c["refresh_seconds"]), ("running", "12 shrunk so far", 30))

    # Updates and health -----------------------------------------------------------------------------------------
    def test_before_update_stops_a_run_after_the_picture_it_is_on(self):
        for i in range(80):
            picture(self.p("library", f"x{i:02d}", "1", "poster.jpg"), (600, 1200))
        self.assertTrue(self.app.start("now"))
        out = self.app.before_update({"from": "1.0.0", "to": "1.1.0"})
        self.assertTrue(out["ok"])
        self.assertFalse(self.app.running())
        self.assertIn("about to be updated", self.app.shrink_now()["said"])
        self.assertTrue(self.app.after_update({"outcome": "updated"})["ok"])
        self.assertFalse(self.app.sbplugin.holding())
        stopped = self.app._state()["runs"][-1]
        self.assertEqual(stopped["stopped"], "Stopped for an update")
        files = [f for f in os.listdir(self.p("library", "x00", "1"))]
        self.assertEqual(files, ["poster.jpg"])

    def test_health_needs_the_metadata_folder(self):
        self.assertEqual(self.app.health(), {"ok": True})
        self.app.ROOT = self.p("missing")
        with self.assertRaises(RuntimeError):
            self.app.health()

    def test_manifest(self):
        m = manifest("picture-shrinker")
        self.assertEqual(m["permissions"], ["jellyfin:metadata"])
        self.assertEqual(m["containers"][0]["volumes"], ["data", "jellyfin-metadata"])
        self.assertEqual(m["containers"][0]["user"], "media")
        self.assertEqual([j.get("schedule") for j in m["jobs"]], ["when", None])
        self.assertTrue(m["jobs"][1]["quiet_hours"])


if __name__ == "__main__":
    unittest.main()
