"""Create your own TV channel 0.3.0, promos (owner, 19 November 2026: "include audio from the video, pick a few clips
when creating the promo, reduce the background music to about 20%, allow me to add more than one background loop, as
well as set the length of the promo").

The FFmpeg tests run only where ffmpeg is installed; they make short clips of their own."""
import http.server
import io
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT  # noqa: E402
from test_tv_station import FakeJellyfin, channel  # noqa: E402
from test_tv_station_020 import NOW, App, make  # noqa: E402
from test_tv_station_030 import evaluate  # noqa: E402
from test_tv_station_pack import small_pack  # noqa: E402

TV = os.path.join(ROOT, "tv-station")
sys.path.insert(0, TV)
import dog  # noqa: E402
import pack  # noqa: E402
import promo  # noqa: E402
import schedule  # noqa: E402

FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
FID = "c" * 32


def airing(dur=3000):
    return {"start": NOW + 86400, "entry": {"id": FID, "title": "A Film", "dur": dur}}


class Choosing(unittest.TestCase):
    """How many clips, where from, and how loud the music is under them."""

    def test_more_clips_for_a_longer_promo(self):
        self.assertEqual([promo.clip_count(s) for s in (10, 15, 20, 30, 45, 60)], [2, 3, 4, 6, 6, 6])
        self.assertEqual(promo.clip_count(30, 2), 2, "the setting comes first")
        self.assertEqual(promo.clip_count(15, 9), 6, "never more than 6")

    def test_clips_are_spread_clear_of_the_titles_and_credits(self):
        for seed in range(20):
            starts = promo.clip_starts(3000, 4, seed)
            self.assertEqual(starts, sorted(starts), "in the programme's order")
            self.assertGreaterEqual(starts[0], 3000 * promo.SPREAD[0])
            self.assertLessEqual(starts[-1], 3000 * promo.SPREAD[1])
        self.assertEqual(promo.clip_starts(3000, 4, 7), promo.clip_starts(3000, 4, 7), "the same promo, the same clips")
        self.assertNotEqual(promo.clip_starts(3000, 4, 7), promo.clip_starts(3000, 4, 8))

    def test_the_music_level(self):
        self.assertEqual(promo.music_level(20), 0.2)
        self.assertEqual(promo.music_level("50"), 0.5)
        self.assertEqual(promo.music_level(None), 0.2)
        self.assertEqual(promo.music_level("loud"), 0.2)
        self.assertEqual(promo.music_level(0.01), 0.05)

    def test_the_music_falls_under_the_programmes_sound_and_rises_again(self):
        expr = promo.duck(0.2, 1.0, 14.0)
        at = lambda t: evaluate(expr, t, min=min)  # noqa: E731
        self.assertAlmostEqual(at(0.0), 1.0)
        self.assertAlmostEqual(at(0.6), 1.0)
        self.assertAlmostEqual(at(0.8), 0.6, places=2)
        for t in (1.0, 5.0, 14.0):
            self.assertAlmostEqual(at(t), 0.2, places=3)
        self.assertAlmostEqual(at(14.4), 1.0)
        self.assertAlmostEqual(at(15.0), 1.0)


class TheCommand(unittest.TestCase):
    def build(self, **how):
        pk = promo.plain_pack("0x1f5f99")
        with tempfile.TemporaryDirectory() as d:
            return promo.command(pk, airing(), "Films", {"file": "/music/bed.m4a", "gain": -2.0}, 640, 360, "http://jf", "k",
                                 dog.Texts(d), "/x.mp4", seed=3, **how)

    def test_the_programmes_sound_with_the_music_under_it(self):
        argv, seconds = self.build(seconds=20, level=0.2)
        self.assertEqual(seconds, 20)
        fc = argv[argv.index("-filter_complex") + 1]
        self.assertEqual(sum("/Videos/" in a for a in argv), 4, "four clips for 20 seconds")
        self.assertIn("loudnorm=I=-23", fc, "the programme's sound at the same loudness as the rest")
        self.assertIn("amix=inputs=2", fc)
        self.assertIn("1-0.800*clip(", fc, "the music at 20% under it")
        self.assertIn("concat=n=4:v=0:a=1", fc)

    def test_without_the_programmes_sound(self):
        argv, _ = self.build(clip_sound=False)
        fc = argv[argv.index("-filter_complex") + 1]
        self.assertNotIn("amix", fc)
        self.assertNotIn(":a]", fc.replace("[4:a]", "").replace("[3:a]", "").split("[bg]")[0])

    def test_the_length_setting(self):
        self.assertEqual(self.build()[1], 15, "the pack's, 15")
        self.assertEqual(self.build(seconds=45)[1], 45)
        self.assertEqual(self.build(seconds=5)[1], 10)
        self.assertEqual(self.build(seconds=600)[1], 60)

    def test_an_uploaded_background_loop_is_used(self):
        argv, _ = self.build(background={"file": "/data/promo-backgrounds/station/loop.mp4", "still": False})
        self.assertIn("/data/promo-backgrounds/station/loop.mp4", argv)
        self.assertNotIn("color=c=0x1f5f99", " ".join(argv))
        argv, _ = self.build(background={"file": "/data/promo-backgrounds/station/card.png", "still": True})
        i = argv.index("/data/promo-backgrounds/station/card.png")
        self.assertIn("-loop", argv[i - 8:i])

    def test_a_background_is_chosen_from_the_pool(self):
        pool = [{"file": "/a"}, {"file": "/b"}, None]
        got = {str(promo.pick_background(pool, seed)) for seed in range(40)}
        self.assertEqual(len(got), 3, "each loop is used")
        self.assertEqual(promo.pick_background(pool, 5), promo.pick_background(pool, 5))
        self.assertIsNone(promo.pick_background([], 1))


class BackgroundLoops(App):
    """Uploaded for the station and for one channel, listed, chosen from and removed."""

    def upload(self, fn, item, name, path):
        data = open(path, "rb").read()
        return fn(name, item, len(data), io.BytesIO(data))

    @unittest.skipUnless(FFMPEG, "ffmpeg is not installed here")
    def test_loops_for_the_station_and_a_channel(self):
        cid = self.channel()
        loop = make(os.path.join(self.tmp.name, "loop.mp4"), ["-f", "lavfi", "-i", "testsrc2=s=320x180:r=25:d=4", "-c:v", "libx264", "-preset", "ultrafast"])
        card = make(os.path.join(self.tmp.name, "card.png"), ["-f", "lavfi", "-i", "color=c=navy:s=320x180", "-frames:v", "1"])
        long_one = make(os.path.join(self.tmp.name, "long.mp4"), ["-f", "lavfi", "-i", "testsrc2=s=160x90:r=5:d=70", "-c:v", "libx264", "-preset", "ultrafast"])
        page = self.upload(self.app.clips_file, "add:back", "loop.mp4", loop)
        self.assertIn("Added loop.mp4, 4 seconds", page["said"])
        self.assertIn("back:", " ".join(it["id"] for it in page["items"]))
        with self.assertRaises(ValueError) as e:
            self.upload(self.app.clips_file, "add:back", "long.mp4", long_one)
        self.assertIn("2 to 60 seconds", str(e.exception))
        page = self.upload(self.app.channels_file, f"{cid}:add-back", "card.png", card)
        self.assertIn("a picture", page["said"])
        s = self.app.state()
        ch = self.app.find(s, cid)
        self.assertEqual(len(ch["promo_backgrounds"]), 1)
        self.assertTrue(ch["promo_backgrounds"][0]["still"])
        design = self.app.promo_design(s, ch)
        self.assertEqual(design["name"], "Plain", "a loop alone is enough for promos")
        pool = self.app.backgrounds_for(s, ch, design)
        self.assertEqual([os.path.basename(b["file"]) for b in pool], ["card.png", "loop.mp4"], "the channel's first, then the station's")
        rows = {it["id"].split(":", 1)[1]: it for it in self.app.channels_page(now=NOW)["items"] if it["id"].startswith(cid)}
        bid = ch["promo_backgrounds"][0]["id"]
        self.assertIn(f"back-{bid}", rows)
        self.assertIn("add-back", rows)
        for it in rows.values():
            self.assertLessEqual(len(it.get("detail", "")), 200)
        self.app.channels_post({"action": "remove", "id": f"{cid}:back-{bid}"}, now=NOW)
        self.assertEqual(self.app.find(self.app.state(), cid)["promo_backgrounds"], [])
        self.assertFalse(os.path.exists(os.path.join(os.environ["PLUGIN_DATA"], "promo-backgrounds", f"ch-{cid}", "card.png")))
        sid = self.app.state()["promo_backgrounds"][0]["id"]
        self.app.clips_post({"action": "remove", "id": f"back:{sid}"})
        self.assertEqual(self.app.state()["promo_backgrounds"], [])

    def test_the_length_setting_is_read(self):
        self.assertIsNone(self.app.promo_seconds({}))
        self.assertIsNone(self.app.promo_seconds({"promo_seconds": ""}))
        self.assertEqual(self.app.promo_seconds({"promo_seconds": "30"}), 30)
        self.assertEqual(self.app.promo_seconds({"promo_seconds": "900"}), 60)
        self.assertIsNone(self.app.promo_seconds({"promo_seconds": "soon"}))

    def test_the_settings(self):
        import json
        doc = json.load(open(os.path.join(TV, "starboard-plugin.json")))
        keys = {}

        def walk(o):
            if isinstance(o, dict):
                if "key" in o:
                    keys[o["key"]] = o
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(doc)
        self.assertEqual(keys["promo_music_level"]["default"], "20")
        self.assertEqual([c["value"] for c in keys["promo_seconds"]["choices"]], ["", "10", "15", "20", "30", "45", "60"])
        self.assertTrue(keys["promo_sound"]["default"])
        for k in ("promo_seconds", "promo_clips", "promo_sound", "promo_music_level"):
            self.assertEqual(keys[k]["group"], "Coming-up trailers")


@unittest.skipUnless(FFMPEG, "ffmpeg is not installed here")
class MakingOne(unittest.TestCase):
    """A real 20 second promo, from the small example pack and a stand-in Jellyfin's clip with a tone for its sound."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        FakeJellyfin.folder = cls.tmp.name
        subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=25:d=60", "-f", "lavfi", "-i", "sine=f=440:d=60",
                        "-c:v", "libx264", "-preset", "ultrafast", "-g", "25", "-c:a", "aac", "-shortest", "-y",
                        os.path.join(cls.tmp.name, "a1.ts")], check=True)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=25:d=60",
                        "-c:v", "libx264", "-preset", "ultrafast", "-g", "25", "-y", os.path.join(cls.tmp.name, "quiet.ts")], check=True)
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeJellyfin)
        threading.Thread(target=cls.server.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}"
        cls.folder, got = small_pack()
        cls.pack = {**got["pack"], "folder": cls.folder}
        cls.music = os.path.join(cls.tmp.name, "bed.m4a")
        subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "sine=f=220:d=30", "-c:a", "aac", "-y", cls.music], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.tmp.cleanup()

    def make(self, item, **how):
        lineup = [{"id": item, "dur": 60, "title": "Pattern Show", "group": "a", "kind": "Episode"}]
        a = schedule.Channel(channel(lineup, start_on=0)).airing(NOW + 86400)
        out = os.path.join(self.tmp.name, f"{item}-{len(how)}.mp4")
        with tempfile.TemporaryDirectory() as d:
            argv, seconds = promo.command(self.pack, a, "Comedy", {"file": self.music, "gain": 0}, 480, 270, self.url, "k", dog.Texts(d),
                                          out, seed=1, **how)
            ok, why = promo.run(argv, limit=120)
        return ok, why, out, seconds

    def test_twenty_seconds_with_the_programmes_sound(self):
        ok, why, out, seconds = self.make("a1", seconds=20)
        self.assertTrue(ok, why)
        info = pack.probe(out)
        self.assertTrue(info["audio"])
        self.assertAlmostEqual(info["duration"], 20, delta=0.6)
        # The programme's 440 Hz tone is in the middle; the music's 220 Hz is at the start, before the first clip.
        def strongest(start):
            r = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(start), "-t", "0.5", "-i", out, "-ac", "1", "-ar", "8000",
                                "-f", "s16le", "-"], capture_output=True, check=True).stdout
            import array
            import math
            x = array.array("h", r)
            best = {}
            for f in (220, 440):
                c = sum(v * math.cos(2 * math.pi * f * i / 8000) for i, v in enumerate(x))
                s = sum(v * math.sin(2 * math.pi * f * i / 8000) for i, v in enumerate(x))
                best[f] = math.hypot(c, s)
            return best
        start, middle = strongest(0.3), strongest(9.0)
        self.assertGreater(start[220], start[440], "music before the first clip")
        self.assertGreater(middle[440], middle[220] * 2, "the programme's sound over the music in the middle")

    def test_a_programme_with_no_sound_fails_and_is_made_with_the_music_alone(self):
        ok, why, out, seconds = self.make("quiet", seconds=10)
        self.assertFalse(ok, "no sound to read: the job makes it again without")
        ok, why, out, seconds = self.make("quiet", seconds=10, clip_sound=False)
        self.assertTrue(ok, why)
        self.assertTrue(pack.probe(out)["audio"])


if __name__ == "__main__":
    unittest.main()
