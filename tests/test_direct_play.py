"""Direct play (DASH-425): the rules for each device, the output check, the survey cache, the schedule, the card and
the page. Sample media are made here with ffmpeg, a second or two long and tiny; the tests that need ffmpeg are
skipped when it is not on this computer. Run: python3 -m unittest discover -s tests"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PID = "direct-play"
STARBOARD_SRC = os.environ.get("STARBOARD_SRC", os.path.expanduser("~/src/starboard"))
FFMPEG = shutil.which("ffmpeg") and shutil.which("ffprobe")
sys.dont_write_bytecode = True


def load(values=None):
    tmp = tempfile.mkdtemp(prefix="sb-dp-test-")
    run, data = os.path.join(tmp, "run"), os.path.join(tmp, "data")
    media = {k: os.path.join(tmp, "media", k) for k in ("movies", "tv")}
    for d in (run, data, *media.values()):
        os.makedirs(d)
    with open(os.path.join(run, "settings.json"), "w") as f:
        json.dump(values or {}, f)
    os.environ.update(PLUGIN_RUN=run, PLUGIN_DATA=data, DIRECT_PLAY_MOVIES=media["movies"], DIRECT_PLAY_TV=media["tv"])
    sys.path.insert(0, os.path.join(ROOT, PID))
    for name in ("sbplugin", "app_dp"):
        sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location("app_dp", os.path.join(ROOT, PID, "app.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sys.path.pop(0)
    mod._tmp, mod._media, mod._runp = tmp, media, run
    mod.rescan = lambda old, new: None  # no Reelix or Jellyfin here
    return mod


def set_values(app, **values):
    p = os.path.join(app._runp, "settings.json")
    with open(p) as f:
        v = json.load(f)
    v.update(values)
    with open(p, "w") as f:
        json.dump(v, f)


def manifest():
    with open(os.path.join(ROOT, PID, "starboard-plugin.json"), encoding="utf-8") as f:
        return json.load(f)


def make(path, vcodec="libx264", acodec="aac", channels=2, seconds=2, size="160x90", extra=()):
    """A tiny sample: a test picture and a tone, made with ffmpeg."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc=size={size}:rate=10:duration={seconds}"]
    if acodec:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}", "-ac", str(channels)]
    cmd += ["-c:v", vcodec, *extra]
    if acodec:
        cmd += ["-c:a", acodec]
    if vcodec == "libx264":
        cmd += ["-pix_fmt", "yuv420p", "-preset", "ultrafast"]
    subprocess.run(cmd + [path], check=True, capture_output=True)
    return path


def rec(**kw):
    base = {"path": "/media/movies/A/A.mkv", "size": 10, "mtime": 1, "container": "mkv", "vcodec": "h264", "h": 1080, "w": 1920,
            "tenbit": False, "mbps": 8.0, "audio": ["aac"], "dur": 100}
    return {**base, **kw}


class Rules(unittest.TestCase):
    def setUp(self):
        self.app = load()
        self.opts = {"hevc_to_h264": False, "shrink": True, "caps": {1080: 15, 720: 8, 0: 5}, "keep_originals": False, "when": "weekends"}

    def need(self, r, devices, **opts):
        return self.app.classify(r, self.app.profile(devices), {**self.opts, **opts})[0]

    def test_default_is_mediafix(self):
        self.assertEqual(self.app.chosen(), ["roku_express"])

    def test_roku_express_follows_mediafix(self):
        roku = ["roku_express"]
        self.assertEqual(self.need(rec(), roku), "ok")
        self.assertEqual(self.need(rec(audio=["dts"]), roku), "audio")
        self.assertEqual(self.need(rec(audio=["truehd", "ac3"]), roku), "ok")
        self.assertEqual(self.need(rec(container="avi"), roku), "remux")
        self.assertEqual(self.need(rec(mbps=30), roku), "shrink")
        self.assertEqual(self.need(rec(vcodec="mpeg4"), roku), "reencode")
        self.assertEqual(self.need(rec(tenbit=True), roku), "reencode")
        self.assertEqual(self.need(rec(h=2160, w=3840), roku), "reencode")
        self.assertEqual(self.need(rec(vcodec="hevc"), roku), "hevc")

    def test_hevc_to_h264_only_when_no_device_plays_it(self):
        self.assertEqual(self.need(rec(vcodec="hevc"), ["roku_express"], hevc_to_h264=True), "reencode")
        self.assertEqual(self.need(rec(vcodec="hevc"), ["roku_express", "chromecast"], hevc_to_h264=True), "reencode")
        self.assertEqual(self.need(rec(vcodec="hevc", audio=["ac3"]), ["roku_4k"], hevc_to_h264=True), "ok")
        self.assertEqual(self.need(rec(vcodec="hevc", audio=["ac3"]), ["roku_4k", "shield"], hevc_to_h264=True), "ok")

    def test_hevc_kept_still_gets_its_sound_fixed(self):
        self.assertEqual(self.need(rec(vcodec="hevc", audio=["truehd"]), ["roku_4k"]), "audio")
        self.assertEqual(self.need(rec(vcodec="hevc", audio=["truehd"]), ["shield"]), "ok")

    def test_audio_only_when_a_device_lacks_it(self):
        self.assertEqual(self.need(rec(audio=["dts"]), ["shield"]), "ok")
        self.assertEqual(self.need(rec(audio=["dts"]), ["shield", "fire_tv"]), "audio")
        self.assertEqual(self.need(rec(audio=["ac3"]), ["smart_tv", "apple_tv"]), "ok")
        self.assertEqual(self.need(rec(audio=["ac3"]), ["browser"]), "audio")  # browsers do not play Dolby Digital
        self.assertEqual(self.need(rec(audio=["flac"]), ["chromecast", "browser"]), "ok")
        self.assertEqual(self.need(rec(audio=[]), ["roku_express"]), "ok")  # no sound: nothing to add

    def test_old_formats_play_on_the_shield(self):
        self.assertEqual(self.need(rec(vcodec="vc1", audio=["ac3"]), ["shield"]), "ok")
        self.assertEqual(self.need(rec(vcodec="vc1", audio=["ac3"]), ["shield", "apple_tv"]), "reencode")

    def test_4k_devices_keep_4k(self):
        self.assertEqual(self.need(rec(h=2160, w=3840, mbps=12), ["roku_4k"]), "ok")
        self.assertEqual(self.need(rec(h=2160, w=3840), ["roku_4k", "fire_tv"]), "reencode")

    def test_shrink_settings(self):
        self.assertEqual(self.need(rec(mbps=30), ["shield"], shrink=False), "ok")
        self.assertEqual(self.need(rec(mbps=12, h=720, w=1280), ["shield"]), "shrink")
        self.assertEqual(self.need(rec(mbps=12), ["shield"], caps={1080: 20, 720: 8, 0: 5}), "ok")
        self.assertEqual(self.need(rec(vcodec="hevc", mbps=60, audio=["ac3"]), ["roku_4k"]), "ok")  # only H.264 shrinks

    def test_no_devices_means_nothing(self):
        self.assertIsNone(self.app.profile([]))
        self.assertEqual(self.app.classify(rec(vcodec="mpeg4"), None, self.opts)[0], "ok")
        set_values(self.app, device_roku_express=False)
        self.assertEqual(self.app.chosen(), [])
        self.assertEqual(self.app.why_idle(), "No devices chosen")

    def test_added_track(self):
        self.assertEqual(self.app.new_track(6, self.app.profile(["roku_express"]))[0], "ac3")
        self.assertEqual(self.app.new_track(6, self.app.profile(["roku_express", "browser"]))[0], "aac")
        self.assertEqual(self.app.new_track(2, self.app.profile(["shield"]))[0], "aac")

    def test_order_is_cheapest_first(self):
        recs = [rec(path="/m/d", vcodec="mpeg4"), rec(path="/m/c", mbps=40), rec(path="/m/b", audio=["dts"]), rec(path="/m/a", container="avi")]
        got = [r["bucket"] for r in self.app.todo_list(recs, self.app.profile(["roku_express"]), self.opts, {"failed": {}})]
        self.assertEqual(got, ["remux", "audio", "shrink", "reencode"])

    def test_failed_files_wait_until_they_change(self):
        r = rec(path="/m/x", container="avi")
        state = {"failed": {"/m/x": {"size": 10, "mtime": 1}}}
        self.assertEqual(self.app.todo_list([r], self.app.profile(["shield"]), self.opts, state), [])
        self.assertEqual(len(self.app.todo_list([{**r, "mtime": 2}], self.app.profile(["shield"]), self.opts, state)), 1)


class Check(unittest.TestCase):
    """The output check, on ffprobe answers: mediafix's length, picture, sound and start rules."""

    def setUp(self):
        self.app = load()
        self.prof = self.app.profile(["roku_express"])

    def info(self, dur=100.0, v="h264", a=("ac3",), vs=0.0, as_=0.0, subs=0):
        streams = [{"codec_type": "video", "codec_name": v, "start_time": str(vs)}]
        streams += [{"codec_type": "audio", "codec_name": c, "start_time": str(as_)} for c in a]
        streams += [{"codec_type": "subtitle", "codec_name": "subrip"} for _ in range(subs)]
        return {"format": {"duration": str(dur)}, "streams": streams}

    def test_good(self):
        self.assertIsNone(self.app.check(self.info(a=("dts",)), self.info(), "audio", self.prof))

    def test_length(self):
        self.assertIn("length", self.app.check(self.info(dur=6000), self.info(dur=5960), "remux", self.prof))
        self.assertIsNone(self.app.check(self.info(dur=6000), self.info(dur=5980), "remux", self.prof))  # within 0.5%

    def test_picture(self):
        self.assertIn("picture", self.app.check(self.info(v="mpeg4"), self.info(v="mpeg4"), "reencode", self.prof))
        self.assertIsNone(self.app.check(self.info(v="hevc", a=("dts",)), self.info(v="hevc"), "audio", self.app.profile(["roku_4k"])))

    def test_first_sound_track(self):
        self.assertIn("first sound", self.app.check(self.info(), self.info(a=("dts", "ac3")), "audio", self.prof))

    def test_start_times(self):
        self.assertIn("sound starts", self.app.check(self.info(), self.info(as_=0.8), "remux", self.prof))

    def test_subtitles_kept(self):
        self.assertIn("subtitle", self.app.check(self.info(subs=2), self.info(subs=1), "remux", self.prof))


class Schedule(unittest.TestCase):
    def setUp(self):
        self.app = load()

    def at(self, wday):
        self.app.localtime = lambda t=None: time.struct_time((2026, 11, 14, 10, 0, 0, wday, 318, 0))

    def test_weekends(self):
        self.at(5)
        self.assertTrue(self.app.in_hours("weekends"))
        self.at(6)
        self.assertTrue(self.app.in_hours("weekends"))
        self.at(2)
        self.assertFalse(self.app.in_hours("weekends"))
        self.assertTrue(self.app.in_hours("any"))

    def test_quiet_hours_follow_starboards_job(self):
        self.assertFalse(self.app.in_hours("quiet"))
        self.app.localtime = lambda t=None: time.struct_time((2026, 11, 14, 10, 0, 0, 5, 318, 0))
        self.app.quiet_job()
        self.assertTrue(self.app.in_hours("quiet"))
        t = time.time()
        self.app.now = lambda: t + 66 * 60
        self.assertFalse(self.app.in_hours("quiet"))
        self.assertIn("10:00", self.app.next_run("quiet"))

    def test_waits_outside_its_hours(self):
        self.at(2)
        self.assertEqual(self.app.why_idle(), "Waiting for the weekend")
        self.assertEqual(self.app.work_once(), 0)
        self.assertEqual(self.app.remember("now")["reason"], "Waiting for the weekend")

    def test_pause_and_resume(self):
        self.assertIn("Paused", self.app.pause()["said"])
        self.assertEqual(self.app.why_idle(), "Paused")
        self.assertEqual(self.app.card()["items"][0]["title"], "Paused")
        self.app.resume()
        self.assertFalse(self.app._state()["paused"])

    def test_card_seconds(self):
        self.assertEqual(self.app.card_seconds(), 30)
        set_values(self.app, card_seconds="10")
        self.assertEqual(self.app.card_seconds(), 10)
        set_values(self.app, card_seconds="2")
        self.assertEqual(self.app.card_seconds(), 30)
        self.assertEqual(self.app.card()["refresh_seconds"], 30)


@unittest.skipUnless(FFMPEG, "needs ffmpeg")
class FreeSpace(unittest.TestCase):
    """The free space rule on its own: the file's size and a fifth, plus a tenth of the disk (at most 50 GB)."""

    def test_room_is_the_size_and_a_fifth_plus_the_margin(self):
        app = load({"when": "any"})
        try:
            from unittest import mock
            fake = mock.Mock(f_blocks=1000, f_frsize=1_000_000, f_bavail=0)  # a 1 GB disk: the margin is 100 MB
            with mock.patch("os.statvfs", return_value=fake):
                fake.f_bavail = 220
                self.assertTrue(app.free_enough("/x", 100_000_000))   # 120 MB + 100 MB = 220 MB
                fake.f_bavail = 219
                self.assertFalse(app.free_enough("/x", 100_000_000))
        finally:
            shutil.rmtree(app._tmp, ignore_errors=True)


class WithMedia(unittest.TestCase):
    """Real tiny files, real ffmpeg: the survey cache, each fix, the check, and the card."""

    def setUp(self):
        self.app = load({"when": "any"})
        self.mv = self.app._media["movies"]
        # The free space rule keeps a tenth of the disk free, so on a test computer with less than that the fixes
        # would be refused. It is tested on its own; here the disk always has room.
        self.app.free_enough = lambda folder, size: True

    def tearDown(self):
        shutil.rmtree(self.app._tmp, ignore_errors=True)

    def test_survey_probes_only_new_or_changed(self):
        make(os.path.join(self.mv, "One (2001)", "One (2001).mkv"))
        calls = []
        real = self.app.ffprobe
        self.app.ffprobe = lambda p: calls.append(p) or real(p)
        self.assertEqual(len(self.app.survey()), 1)
        self.assertEqual(len(calls), 1)
        self.app.survey()
        self.assertEqual(len(calls), 1)  # nothing changed, nothing probed
        make(os.path.join(self.mv, "Two (2002)", "Two (2002).mkv"))
        self.app.survey()
        self.assertEqual(len(calls), 2)
        os.utime(os.path.join(self.mv, "One (2001)", "One (2001).mkv"), (1, 1))
        self.app.survey()
        self.assertEqual(len(calls), 3)

    def test_unfinished_copies_and_hidden_folders_are_not_surveyed(self):
        make(os.path.join(self.mv, "One (2001)", ".One (2001).direct-play.mkv"))
        make(os.path.join(self.mv, "One (2001)", "One (2001).mediafix.mkv"))
        make(os.path.join(self.mv, ".direct-play-originals", "Old.mkv"))
        self.assertEqual(self.app.survey(), [])

    def test_remux_an_avi(self):
        src = make(os.path.join(self.mv, "Old (1999)", "Old (1999).avi"), vcodec="libx264", acodec="mp3")
        self.app.survey()
        self.assertEqual([r["bucket"] for r in self.app.todo_list()], ["remux"])
        self.assertEqual(self.app.work_once(), 1)
        out = os.path.join(self.mv, "Old (1999)", "Old (1999).mkv")
        self.assertTrue(os.path.isfile(out))
        self.assertFalse(os.path.exists(src))
        self.assertEqual(self.app.todo_list(), [])
        s = self.app._state()
        self.assertEqual((s["done"], s["last"]["title"]), (1, "Old (1999)"))

    def test_add_a_sound_track_beside_the_original(self):
        make(os.path.join(self.mv, "Loud (2010)", "Loud (2010).mkv"), acodec="flac", channels=6)
        self.app.survey()
        self.assertEqual(self.app.todo_list()[0]["bucket"], "audio")
        self.app.work_once()
        info = self.app.ffprobe(os.path.join(self.mv, "Loud (2010)", "Loud (2010).mkv"))
        audio = [s["codec_name"] for s in info["streams"] if s["codec_type"] == "audio"]
        self.assertEqual(audio, ["ac3", "flac"])  # the new track first, the original kept
        self.assertEqual(info["streams"][1]["disposition"]["default"], 1)

    def test_reencode_an_old_format(self):
        make(os.path.join(self.app._media["tv"], "Show", "Season 1", "Show S01E02.mkv"), vcodec="mpeg4")
        self.app.survey()
        self.assertEqual(self.app.title(self.app.todo_list()[0]["path"]), "Show, series 1 episode 2")
        self.app.work_once()
        info = self.app.ffprobe(os.path.join(self.app._media["tv"], "Show", "Season 1", "Show S01E02.mkv"))
        self.assertEqual(self.app.video_stream(info["streams"])["codec_name"], "h264")

    def test_a_failed_check_keeps_the_original(self):
        src = make(os.path.join(self.mv, "Bad (2000)", "Bad (2000).avi"), acodec="mp3")
        self.app.survey()
        self.app.check = lambda *a: "length 1 seconds, the original 2"
        self.app.work_once()
        self.assertTrue(os.path.isfile(src))
        self.assertFalse(os.path.exists(os.path.join(self.mv, "Bad (2000)", "Bad (2000).mkv")))
        self.assertFalse([f for f in os.listdir(os.path.dirname(src)) if f.startswith(".")])  # no unfinished copy left
        self.assertIn("check failed", self.app._state()["failed"][src]["why"])

    def test_keep_the_originals(self):
        set_values(self.app, keep_originals=True)
        src = make(os.path.join(self.mv, "Kept (2003)", "Kept (2003).avi"), acodec="mp3")
        self.app.survey()
        self.app.work_once()
        self.assertTrue(os.path.isfile(os.path.join(self.mv, ".direct-play-originals", "Kept (2003)", "Kept (2003).avi")))
        self.assertFalse(os.path.exists(src))

    def test_card_shows_next_up_and_totals(self):
        for n in range(6):
            make(os.path.join(self.mv, f"F{n} (200{n})", f"F{n} (200{n}).avi"), acodec="mp3", seconds=1)
        self.app.survey()
        self.app.localtime = lambda t=None: time.struct_time((2026, 11, 11, 10, 0, 0, 2, 315, 0))
        set_values(self.app, when="weekends")
        c = self.app.card()
        self.assertEqual(c["items"][0]["title"], "Waiting for the weekend")
        self.assertEqual(c["items"][0]["detail"], "Next runs on Saturday from midnight")
        self.assertEqual([i["title"] for i in c["items"][1:5]], [f"Next: F{n} (200{n})" for n in range(4)])
        self.assertEqual(c["items"][-1]["detail"], "0 files fixed, 0 bytes saved, 6 files still to do")

    def test_card_while_converting(self):
        r = {"path": os.path.join(self.mv, "Dune (2021)", "Dune (2021).mkv")}
        self.app._current["path"] = r["path"]
        self.app.status(r, "shrink", 34, 3900, force=True)
        c = self.app.card()
        self.assertEqual(c["items"][0], {"title": "Converting now: Dune (2021)", "detail": "Shrink, 34% done, about 1 hour 5 minutes left"})
        self.app._current["path"] = None

    def test_answers_starboard_accepts(self):
        sys.path.insert(0, STARBOARD_SRC)
        try:
            from starboard import plugin_cards, plugin_custom, plugins
        except ImportError:
            self.skipTest("needs Starboard's source")
        make(os.path.join(self.mv, "Old (1999)", "Old (1999).avi"), acodec="mp3")
        self.app.survey()
        plugin_cards.clean("list", self.app.card())
        plugin_cards.clean("stat", self.app.summary_card())
        screen = plugin_custom.clean(self.app.screen())
        self.assertEqual(screen["items"][0]["cells"]["needs"], "Repackage as MKV")
        problems = plugins.check(manifest()) if hasattr(plugins, "check") else []
        self.assertFalse([p for p in problems if "image" not in p], problems)


class Manifest(unittest.TestCase):
    def test_least_permissions_and_never_by_default(self):
        m = manifest()
        self.assertEqual(sorted(m["permissions"]), ["jellyfin:key", "network:lan", "reelix:key"])
        c = m["containers"][0]
        self.assertEqual(sorted(c["volumes"]), ["data", "media/movies", "media/tv"])
        self.assertEqual(c["user"], "media")
        self.assertLessEqual(m["resources"]["main"]["memory"], 512)
        self.assertTrue(m["setup_required"])
        self.assertEqual(m["starboard_api"], ">=1.14 <2.0")
        self.assertEqual(m["cards"][0]["refresh_seconds"], 30)

    def test_every_device_has_a_switch(self):
        app = load()
        keys = {s["key"] for s in manifest()["settings"]}
        self.assertTrue({f"device_{k}" for k in app.DEVICES} <= keys)
        self.assertEqual([c["value"] for s in manifest()["settings"] if s["key"] == "card_seconds" for c in s["choices"]], ["10", "30", "60", "300"])


if __name__ == "__main__":
    unittest.main()
