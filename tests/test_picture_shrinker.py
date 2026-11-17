"""Picture shrinker (DASH-432): the rules, the check before a picture replaces the original, runs, the schedule, the
card and page, and the update steps. Makes its own small pictures with Pillow in a temporary metadata folder."""
import datetime as dt
import hashlib
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
import urllib.parse

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
        self.app = load("picture-shrinker", {"originals": "keep"})
        self.meta = tempfile.TemporaryDirectory()
        self.app.ROOT = self.meta.name
        self.app.BACKUP = os.path.join(self.app._data, "originals")
        self.jellyfin_plugins = []
        self.app._jellyfin = lambda path, method="GET": self.jellyfin_plugins  # Jellyfin's /Plugins, as the test sets it
        self.app._jf.update(at=0.0, installed=False)
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
        self.assertEqual(k(self.p("library", "ab", "123", "backdrop.jpg")), "backdrop")  # rules 1.2: every picture type
        self.assertEqual(k(self.p("library", "ab", "123", "logo.png")), "logo")
        self.assertIsNone(k(self.p("library", "ab", "123", "box.jpg")))
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
        self.app._set(shrink_all=False, backdrops=False)  # a type left out is only opened, never written
        backdrop = open(self.p("library", "aa", "1", "backdrop.jpg"), "rb").read()
        rec = self.app.run("now")
        self.assertEqual((rec["seen"], rec["shrunk"], rec["left"], rec["failed"]), (4, 2, 1, 1))
        self.assertEqual((rec["backed_up"], rec["not_backed_up"]), (2, 0))
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
        self.assertEqual(next(x for x in manifest("picture-shrinker")["settings"] if x["key"] == "new_pictures")["default"], False)
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
        self.assertNotIn("status_label", first)  # the band says Scheduled; the next run is in the note (no time on a chip)
        self.library()
        self.app.run("now")
        card, page = self.app.card(), self.app.screen()
        self.assertEqual(card["status"], "scheduled")
        self.assertGreater(card["value"], 0)
        self.assertIn("Not shrunk", {i["group"] for i in page["items"]})
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
        self.assertEqual(c["status"], "scheduled")  # only the figures change while it runs
        self.assertIn("12 pictures shrunk of 30", c["note"])

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
        self.assertEqual(m["permissions"], ["jellyfin:metadata", "jellyfin:key", "network:lan"])
        self.assertEqual(m["containers"][0]["network"], "lan")
        self.assertEqual(m["containers"][0]["volumes"], ["data", "jellyfin-metadata"])
        self.assertEqual(m["containers"][0]["user"], "media")
        self.assertEqual([j.get("schedule") for j in m["jobs"]], ["when", None])
        self.assertTrue(m["jobs"][1]["quiet_hours"])


SHARED = os.path.join(os.path.dirname(os.path.abspath(__file__)), "picture-shrinker-shared")


def hashes(top):
    out = {}
    for folder, _, names in os.walk(top):
        for n in names:
            path = os.path.join(folder, n)
            out[os.path.relpath(path, top)] = hashlib.sha256(open(path, "rb").read()).hexdigest()
    return out


@unittest.skipIf(Image is None, "Pillow is not installed")
class InStepWithTheJellyfinVersion(unittest.TestCase):
    """Rules 1.1 (DASH-433): the rules file, the shared test pictures, backup and restore, the space figures, Delete
    backup, staying idle when the Jellyfin version is installed, and a run that finishes quietly."""

    tearDown = PictureShrinker.tearDown

    def setUp(self):
        PictureShrinker.setUp(self)
        shutil.copytree(os.path.join(SHARED, "metadata"), self.meta.name, dirs_exist_ok=True)

    # The rules file ---------------------------------------------------------------------------------------------
    def test_the_code_follows_the_rules_file(self):
        rules = json.load(open(os.path.join(os.path.dirname(SHARED), "..", "picture-shrinker", "rules.json")))
        self.assertEqual(self.app.RULES, rules)
        self.assertEqual(rules["rules_version"], "1.2")
        self.assertEqual(self.app.QUALITY, rules["quality"]["default"])
        self.assertEqual(self.app.EXTS, set(rules["extensions"]))
        self.assertEqual(self.app.TMP, rules["temp_suffix"])
        self.assertEqual(self.app.RUN_LIMIT, rules["run_limit_minutes"] * 60)
        self.assertEqual(self.app.NEW_AGE, rules["new_pictures"]["min_age_seconds"])
        self.assertEqual(self.app.sizes(), (rules["kinds"]["poster"]["default"], rules["kinds"]["person"]["default"]))
        self.assertIsNone(rules["backup"]["default"])  # rules 1.2: no default, people choose
        settings = {x["key"]: x for x in manifest("picture-shrinker")["settings"]}
        for key, rule in (("poster_height", rules["kinds"]["poster"]), ("person_width", rules["kinds"]["person"]), ("quality", rules["quality"])):
            self.assertEqual((settings[key]["default"], settings[key]["min"], settings[key]["max"]), (rule["default"], rule["min"], rule["max"]))
        self.assertNotIn("default", settings["originals"])
        self.assertTrue(settings["originals"]["required"])
        self.assertEqual([c["value"] for c in settings["originals"]["choices"]], rules["backup"]["choices"])
        self.assertEqual(self.app.ASIDE, rules["start_again"]["aside_suffix"])
        self.assertEqual(self.app.PUT_BACK_AFTER, rules["start_again"]["put_back_after_hours"] * 3600)
        self.assertEqual(settings["new_pictures"]["default"], rules["new_pictures"]["default"])
        self.assertEqual(manifest("picture-shrinker")["version"].split(".")[:2], rules["rules_version"].split("."))

    def test_the_shared_pictures_give_the_expected_results(self):
        before = hashes(self.meta.name)
        sizes = {k: os.path.getsize(os.path.join(self.meta.name, k)) for k in before}
        rec = self.app.run("now")
        expected = json.load(open(os.path.join(SHARED, "expected.json")))["pictures"]
        after = hashes(self.meta.name)
        failed = {f["file"] for f in rec["failures"]}
        for rel, e in expected.items():
            path = os.path.join(self.meta.name, rel)
            if e["outcome"] == "shrunk":
                with Image.open(path) as im:
                    self.assertEqual((im.size, im.format), ((e["width"], e["height"]), e["format"]), rel)
                self.assertLess(os.path.getsize(path), sizes[rel], rel)
                self.assertTrue(os.path.exists(os.path.join(self.app.BACKUP, rel)), rel)
            else:
                self.assertEqual(before[rel], after[rel], rel)
                self.assertEqual(e["outcome"] == "failed", rel in failed, rel)
                self.assertFalse(os.path.exists(os.path.join(self.app.BACKUP, rel)), rel)
        self.assertEqual(rec["shrunk"], sum(e["outcome"] == "shrunk" for e in expected.values()))
        self.assertEqual((rec["failed"], rec["left"]), (2, 2))

    # Backup and restore -----------------------------------------------------------------------------------------
    def test_no_backup_means_no_replace(self):
        blocker = os.path.join(self.app._data, "a-file")
        open(blocker, "w").write("not a folder")
        self.app.BACKUP = os.path.join(blocker, "originals")
        before = hashes(self.meta.name)
        rec = self.app.run("now")
        self.assertEqual((rec["shrunk"], rec["not_backed_up"]), (0, 10))
        self.assertIn("could not be backed up", rec["stopped"])
        self.assertEqual(hashes(self.meta.name), before)

    def test_short_of_space_means_no_replace(self):
        before = hashes(self.meta.name)
        real = shutil.disk_usage
        try:
            self.app.shutil.disk_usage = lambda p: real(p)._replace(free=1000)
            rec = self.app.run("now")
        finally:
            self.app.shutil.disk_usage = real
        self.assertEqual(rec["shrunk"], 0)
        self.assertTrue(any("backup disk has only" in f["why"] for f in rec["failures"]))
        self.assertEqual(hashes(self.meta.name), before)

    def test_an_existing_backup_is_never_overwritten(self):
        rel = os.path.join("library", "0a", "0a1b", "poster.jpg")
        copy = os.path.join(self.app.BACKUP, rel)
        os.makedirs(os.path.dirname(copy))
        open(copy, "w").write("the first original")
        self.assertIsNotNone(self.app.shrink_one(os.path.join(self.meta.name, rel), "poster", 900, 400))
        self.assertEqual(open(copy).read(), "the first original")

    def test_restore_puts_back_byte_identical_files(self):
        original = hashes(self.meta.name)
        self.app.run("now")
        self.assertNotEqual(hashes(self.meta.name), original)
        rec = self.app.restore()
        self.assertEqual(rec["restored"], 10)
        self.assertEqual(hashes(self.meta.name), original)
        self.assertEqual((self.app.measure()["saved"], self.app.measure()["shrunk"]), (0, 0))  # nothing saved once all are back
        self.assertEqual(self.app.restore()["already"], 10)  # the backup is kept

    def test_backup_deactivated_shrinks_without_backup(self):
        self.app._set(originals="none")
        self.assertEqual(self.app.run("now")["shrunk"], 10)
        self.assertFalse(os.path.exists(self.app.BACKUP))
        self.assertIn("nobackup", {n["id"] for n in self.app.screen()["notices"]})

    # Space and deleting the backup ------------------------------------------------------------------------------
    def test_space_is_measured(self):
        start = self.app.measure()
        self.assertEqual((start["live_count"], start["backup_count"]), (14, 0))
        rec = self.app.run("now")
        end = self.app.measure()
        self.assertEqual((end["backup_count"], end["backup_bytes"]), (10, rec["before"]))
        self.assertEqual(end["saved"], rec["before"] - rec["after"])
        self.assertEqual(end["live_bytes"], start["live_bytes"] - end["saved"])
        self.assertEqual(self.app.remember("space")["backup_bytes"], rec["before"])  # kept for the card after the run

    def test_delete_backup_deletes_only_inside_the_backup_folder(self):
        self.app.run("now")
        size = self.app.measure()["backup_bytes"]
        outside = os.path.join(self.app._data, "keep-me.jpg")
        open(outside, "w").write("outside")
        not_ours = os.path.join(self.app.BACKUP, "notes.txt")
        open(not_ours, "w").write("not a picture the shrinker made")
        os.symlink(outside, os.path.join(self.app.BACKUP, "library", "link.jpg"))
        os.symlink(self.meta.name, os.path.join(self.app.BACKUP, "People", "linked-folder"))
        live = hashes(self.meta.name)
        said = self.app.delete_backup()["said"]
        self.assertIn("11 original pictures", said)  # ten originals and the link itself
        self.assertIn(self.app.size_words(size), said)
        self.assertEqual(open(outside).read(), "outside")
        self.assertTrue(os.path.exists(not_ours))
        self.assertEqual(hashes(self.meta.name), live)
        self.assertFalse(os.path.exists(os.path.join(self.app.BACKUP, "library", "0a")))
        self.assertEqual(self.app.measure()["backup_count"], 0)

    def test_delete_backup_is_refused_during_a_run(self):
        self.app.run("now")
        self.app._job["thread"] = threading.Thread(target=time.sleep, args=(2,))
        self.app._job["thread"].start()
        self.assertIn("running", self.app.delete_backup()["said"])
        self.app._job["thread"].join()
        self.assertEqual(self.app.measure()["backup_count"], 10)

    # The Jellyfin version ---------------------------------------------------------------------------------------
    def test_idle_while_the_jellyfin_version_is_installed(self):
        self.jellyfin_plugins = [{"Name": "Picture shrinker", "Id": "80bf9325d2994e24ac74c087aeec3011", "Status": "Active"}]
        before = hashes(self.meta.name)
        self.assertIn("Idle", self.app.job_shrink()["said"])
        self.assertIn("Idle", self.app.shrink_now()["said"])
        self.app._set(new_pictures=True)
        self.assertIn("Idle", self.app.job_new()["said"])
        self.assertEqual(hashes(self.meta.name), before)
        self.assertEqual(self.app.card()["status"], "idle")
        self.assertIn("jellyfin", {n["id"] for n in self.app.screen()["notices"]})

    def test_a_deactivated_jellyfin_version_does_not_count(self):
        self.jellyfin_plugins = [{"Name": "Picture shrinker", "Id": "80bf9325-d299-4e24-ac74-c087aeec3011", "Status": "Disabled"}]
        self.assertFalse(self.app.jellyfin_version_installed(force=True))

    def test_no_key_means_it_carries_on(self):
        def no_key(path):
            raise LookupError("Starboard has no Jellyfin key to give yet")
        self.app._jellyfin = lambda path, method="GET": no_key(path)
        self.assertFalse(self.app.jellyfin_version_installed(force=True))

    # Quiet runs -------------------------------------------------------------------------------------------------
    def test_a_finished_run_raises_no_notification(self):
        calls = []
        self.app.sbplugin.fetch = lambda *a, **k: calls.append(a) or {}
        self.app.sbplugin.starboard = lambda *a, **k: calls.append(a) or {}
        self.app.job_shrink()
        self.assertEqual(calls, [])  # no event sent to Starboard, so the Notifications plug-in hears nothing
        self.assertEqual(self.app.card()["status"], "scheduled")
        self.app.keep("_error", {"at": time.time(), "text": "OSError: the disk went away"})
        self.assertEqual(self.app.card()["status"], "scheduled")  # an error shows on the page, not as an alert
        self.assertIn("error", {n["id"] for n in self.app.screen()["notices"]})


if __name__ == "__main__":
    unittest.main()


class ChooseTheBackupAndStartAgain(unittest.TestCase):
    """Rules 1.2: nothing is shrunk until Keep a backup copy or Shrink without a backup is chosen, after install and after the
    update from 1.1; Start again deletes the backup and the records, and has Jellyfin download the pictures again,
    keeping each poster and photo aside until a new one comes, and putting it back after a day without one."""

    tearDown = PictureShrinker.tearDown
    p = PictureShrinker.p

    def setUp(self):
        PictureShrinker.setUp(self)
        shutil.copytree(os.path.join(SHARED, "metadata"), self.meta.name, dirs_exist_ok=True)
        self.app.REFRESH_PAUSE = 0
        self.calls, self.fail_refresh, self.libraries = [], set(), [{"Name": "Films", "ItemId": "lib1"}, {"Name": "TV", "ItemId": "lib2"}]
        self.jellyfin_up = True

        def fake(path, method="GET"):
            if not self.jellyfin_up:
                raise OSError("no answer")
            self.calls.append((method, path))
            if path.startswith("/Plugins"):
                return self.jellyfin_plugins
            if path.startswith("/Persons/"):
                name = urllib.parse.unquote(path.split("/")[2])
                return None if name == "Dan Example" else {"Id": "person-" + name.split()[0].lower()}
            if path == "/Library/VirtualFolders":
                return self.libraries
            if "/Refresh?" in path and path.split("/")[2] in self.fail_refresh:
                raise OSError("refused")
            return {}
        self.app._jellyfin = fake
        self.t = time.time()
        self.app.now = lambda: self.t

    def refreshes(self):
        return [(p.split("/")[2], urllib.parse.parse_qs(p.split("?")[1])) for m, p in self.calls if m == "POST"]

    # The choice -----------------------------------------------------------------------------------------------
    def test_nothing_is_shrunk_until_it_is_chosen(self):
        self.app._set(originals=None, new_pictures=True)
        self.assertIsNone(self.app.backup_choice())
        for said in (self.app.shrink_now(), self.app.job_shrink(), self.app.job_new()):
            self.assertEqual(said["said"], self.app.CHOOSE)
        self.assertFalse(self.app.running())
        self.assertEqual(self.app.card()["status"], "needs_setup")
        self.assertIn("choose", {n["id"] for n in self.app.screen()["notices"]})

    def test_the_update_from_1_1_asks_again_and_keeps_the_backup(self):
        self.app.run("now")
        kept = len(list(self.app._backups()))
        m = manifest("picture-shrinker")
        self.assertIn({"version": "1.2.0", "remove": ["backup"]}, m["update"]["migrations"])
        self.app._set(originals=None, backup=True)  # what Starboard leaves after the step: the old key gone, no choice
        self.assertIsNone(self.app.backup_choice())
        self.assertEqual(len(list(self.app._backups())), kept)

    def test_keep_and_none(self):
        self.app._set(originals="keep")
        self.assertTrue(self.app.backup_on())
        self.app._set(originals="none")
        self.assertFalse(self.app.backup_on())

    # Start again: posters and photos --------------------------------------------------------------------------
    def test_posters_and_photos_are_moved_aside_and_downloaded_again(self):
        self.app.run("now")
        self.assertTrue(list(self.app._backups()))
        rec = self.app.start_again("again_pictures")
        self.assertEqual(list(self.app._backups()), [])
        s = self.app._state()
        self.assertEqual((s["runs"], s["shrunk"]), ([], 0))
        self.assertEqual(s["last_start_again"]["kind"], "again_pictures")
        self.assertEqual(self.app.backup_choice(), "keep")  # the choice is kept
        asked = dict(self.refreshes())
        self.assertIn("0a1b", asked)
        self.assertIn("person-alice", asked)
        self.assertNotIn("x", asked)  # collections are not touched
        for q in asked.values():
            self.assertEqual((q["ReplaceAllImages"], q["ImageRefreshMode"], q["Recursive"]), (["false"], ["FullRefresh"], ["false"]))
        self.assertEqual(rec["not_found"], 1)  # Dan Example: Jellyfin does not know him, so his photo stays
        self.assertTrue(os.path.exists(self.p("People", "D", "Dan Example", "folder.jpg")))
        self.assertFalse(os.path.exists(self.p("library", "0a", "0a1b", "poster.jpg")))
        self.assertTrue(os.path.exists(self.p("library", "0a", "0a1b", ".poster.jpg" + self.app.ASIDE)))
        self.assertTrue(os.path.exists(self.p("library", "0a", "0a1b", ".backdrop.jpg" + self.app.ASIDE)))  # every type it shrinks
        self.assertEqual(len(self.app._aside()["files"]), rec["moved"])

    def test_a_refused_refresh_puts_the_pictures_straight_back(self):
        self.fail_refresh = {"0a1b"}
        rec = self.app.start_again("again_pictures")
        self.assertTrue(os.path.exists(self.p("library", "0a", "0a1b", "poster.jpg")))
        self.assertFalse(os.path.exists(self.p("library", "0a", "0a1b", ".poster.jpg" + self.app.ASIDE)))
        self.assertEqual(rec["failed"], 1)

    def test_settling_deletes_or_puts_back(self):
        self.app.start_again("again_pictures")
        new = picture(self.p("library", "0a", "0a1b", "poster.jpg"), (600, 900))  # Jellyfin downloaded a new one
        self.assertTrue(self.app.settle())
        self.assertFalse(os.path.exists(self.p("library", "0a", "0a1b", ".poster.jpg" + self.app.ASIDE)))
        self.assertTrue(os.path.exists(new))
        waiting = self.app._aside()["files"]
        link_old = self.p("library", "3a", "3a4b", ".poster.jpg" + self.app.ASIDE)
        if os.path.exists(link_old):
            os.remove(link_old)
            os.symlink(self.p("library", "0a", "0a1b", "poster.jpg"), link_old)
        self.t += self.app.PUT_BACK_AFTER
        self.assertEqual(self.app.settle(), 0)
        a = self.app._aside()
        self.assertEqual(a["files"], [])
        self.assertEqual(a["replaced"], 1)
        self.assertEqual(a["put_back"], len(waiting) - 1)
        self.assertTrue(os.path.exists(self.p("People", "A", "Alice Example", "folder.jpg")))
        self.assertTrue(os.path.islink(link_old))  # a link is never followed or moved
        self.assertTrue(os.path.exists(new))

    # Start again: every picture -------------------------------------------------------------------------------
    def test_every_picture_refreshes_each_library_and_person(self):
        rec = self.app.start_again("again_all")
        asked = self.refreshes()
        libs = {i: q for i, q in asked if i.startswith("lib")}
        self.assertEqual(set(libs), {"lib1", "lib2"})
        for q in libs.values():
            self.assertEqual((q["Recursive"], q["ReplaceAllImages"]), (["true"], ["true"]))
        people = {i: q for i, q in asked if i.startswith("person-")}
        self.assertEqual(set(people), {"person-alice", "person-bob", "person-cara"})
        for q in people.values():
            self.assertEqual((q["Recursive"], q["ReplaceAllImages"]), (["false"], ["true"]))
        self.assertEqual(rec["not_found"], 1)
        self.assertEqual(self.app._aside()["files"], [])  # nothing is moved aside

    # When it may start ----------------------------------------------------------------------------------------
    def test_start_again_is_refused_during_a_run(self):
        hold = threading.Event()
        self.app._job["thread"] = threading.Thread(target=hold.wait, daemon=True)
        self.app._job["thread"].start()
        try:
            self.assertIn("shrinker is running", self.app.start_again_now("again_pictures")["said"])
        finally:
            hold.set()
            self.app._job["thread"].join(5)
        self.assertEqual(self.refreshes(), [])

    def test_no_jellyfin_means_nothing_is_changed(self):
        self.app.run("now")
        before = hashes(self.meta.name)
        self.jellyfin_up = False
        self.assertIn("Jellyfin did not answer", self.app.start_again_now("again_pictures")["said"])
        self.assertEqual(hashes(self.meta.name), before)
        self.assertTrue(list(self.app._backups()))

    def test_idle_beside_the_jellyfin_version(self):
        self.jellyfin_plugins = [{"Name": "Picture shrinker", "Id": "80bf9325d2994e24ac74c087aeec3011", "Status": "Active"}]
        self.app._jellyfin = lambda path, method="GET": self.jellyfin_plugins
        self.assertIn("Jellyfin's own Picture shrinker", self.app.start_again_now("again_all")["said"])

    def test_the_actions_ask_first(self):
        acts = {a["id"]: a for a in manifest("picture-shrinker")["actions"]}
        for aid in ("start-again-pictures", "start-again-all"):
            self.assertLessEqual(len(acts[aid]["confirm"]), 300)
            self.assertIn(("POST", acts[aid]["path"]), self.app.ROUTES)


@unittest.skipIf(Image is None, "Pillow is not installed")
class EveryPictureType(unittest.TestCase):
    """Rules 1.2: every picture type Jellyfin saves under library (backdrops asked for in the Jellyfin version's issue
    #2), each with its own size and all activated when it is added, and Shrink all picture types."""

    tearDown = PictureShrinker.tearDown
    p = PictureShrinker.p

    def setUp(self):
        PictureShrinker.setUp(self)

    def test_each_type_is_found_by_its_name(self):
        k = self.app.kind_of
        for name, kind in (("backdrop.jpg", "backdrop"), ("backdrop3.jpg", "backdrop"), ("landscape.jpg", "thumb"),
                           ("logo.png", "logo"), ("banner.jpg", "banner"), ("disc.png", "disc"), ("clearart.png", "clearart"),
                           ("poster.jpg", "poster")):
            self.assertEqual(k(self.p("library", "ab", "123", name)), kind, name)
        self.assertIsNone(k(self.p("library", "ab", "123", "box.jpg")))

    def test_every_type_is_shrunk_when_added(self):
        self.assertEqual(self.app.included(), set(self.app.KINDS))
        self.assertEqual(len(self.app.KINDS), 8)

    def test_shrink_all_overrides_the_ticks_and_the_ticks_apply_without_it(self):
        self.app._set(backdrops=False, logos=False)
        self.assertEqual(self.app.included(), set(self.app.KINDS))
        self.app._set(shrink_all=False)
        self.assertEqual(self.app.included(), set(self.app.KINDS) - {"backdrop", "logo"})

    def test_a_backdrop_and_a_logo_are_shrunk_to_their_widths(self):
        b = picture(self.p("library", "ab", "123", "backdrop.jpg"), (3840, 2160))
        logo = picture(self.p("library", "ab", "123", "logo.png"), (2000, 776), "PNG")
        rec = self.app.run("now")
        self.assertEqual(rec["shrunk"], 2)
        with Image.open(b) as im:
            self.assertEqual(im.size, (1920, 1080))
        with Image.open(logo) as im:
            self.assertEqual((im.size, im.format), ((800, 310), "PNG"))

    def test_a_type_left_out_is_left_alone(self):
        b = picture(self.p("library", "ab", "123", "backdrop.jpg"), (3840, 2160))
        before = open(b, "rb").read()
        self.app._set(shrink_all=False, backdrops=False)
        self.assertEqual(self.app.run("now")["shrunk"], 0)
        with open(b, "rb") as f:
            self.assertEqual(f.read(), before)

    def test_sizes_follow_the_rules_and_the_settings(self):
        settings = {x["key"]: x for x in manifest("picture-shrinker")["settings"]}
        for kind, r in self.app.KINDS.items():
            s = settings[self.app.SIZE[kind]]
            self.assertEqual((s["default"], s["min"], s["max"]), (r["default"], r["min"], r["max"]), kind)
            self.assertEqual(settings[self.app.SWITCH[kind]]["default"], r["shrink_by_default"], kind)
        self.assertEqual(settings["shrink_all"]["default"], self.app.RULES["shrink_all"]["default"])
        self.assertEqual({settings[k]["group"] for k in ("originals", "shrink_all", "logos")}, {"What to shrink"})

    def test_start_again_covers_every_type_whatever_the_ticks(self):
        self.tearDown()
        ChooseTheBackupAndStartAgain.setUp(self)  # its Jellyfin stand-in and the shared pictures
        picture(self.p("library", "ab", "abcd", "logo.png"), (900, 300), "PNG")
        self.app._set(shrink_all=False, logos=False)
        self.app.start_again("again_pictures")
        self.assertTrue(os.path.exists(self.p("library", "ab", "abcd", ".logo.png" + self.app.ASIDE)))
        new = picture(self.p("library", "ab", "abcd", "logo.png"), (900, 300), "PNG")
        self.app.settle()
        self.assertFalse(os.path.exists(self.p("library", "ab", "abcd", ".logo.png" + self.app.ASIDE)))
        self.assertTrue(os.path.exists(new))
