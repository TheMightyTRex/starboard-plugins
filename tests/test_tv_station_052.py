"""Create your own TV channel 0.5.2 (owner, 19 November 2026): "I want the T-Rex TV logo to also show somewhere in the
promos". Promos made with a channel's own pack, or a plain design, carry the station pack's logo, small, in a corner.

The FFmpeg test runs only where ffmpeg is installed."""
import http.server
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
from test_tv_station_020 import NOW, App  # noqa: E402
from test_tv_station_pack import small_pack  # noqa: E402

TV = os.path.join(ROOT, "tv-station")
sys.path.insert(0, TV)
import dog  # noqa: E402
import pack  # noqa: E402
import promo  # noqa: E402
import schedule  # noqa: E402

FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def airing():
    return {"start": NOW + 86400, "entry": {"id": "c" * 32, "title": "A Film", "dur": 3000}}


class TheCommand(unittest.TestCase):
    def build(self, **how):
        pk = promo.plain_pack("0xad1457")
        with tempfile.TemporaryDirectory() as d:
            return promo.command(pk, airing(), "Late ink", None, 1920, 1080, "http://jf", "k", dog.Texts(d), "/x.mp4", seed=1, **how)[0]

    def test_the_logo_is_laid_in_a_corner_clear_of_the_clip(self):
        argv = self.build(station_logo="/data/packs/station/logo/dog.png")
        self.assertIn("/data/packs/station/logo/dog.png", argv)
        fc = argv[argv.index("-filter_complex") + 1]
        lw = int(1920 * promo.STATION_LOGO_SHARE) // 2 * 2
        self.assertIn(f"scale={lw}:", fc)
        self.assertIn("color=c=0x0e0e14@0.72", fc, "on a dark plate")
        self.assertIn(f"y={pack.TITLE_SAFE[1]}", fc)

    def test_it_stays_clear_of_the_clip_area(self):
        with tempfile.TemporaryDirectory() as d:
            logo = os.path.join(d, "dog.png")
            subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=white:s=520x248", "-frames:v", "1", "-y", logo], check=True)
            argv = self.build(station_logo=logo)
            self.assertEqual(promo.png_size(logo), (520, 248))
        fc = argv[argv.index("-filter_complex") + 1]
        import re
        pw, ph = (int(v) for v in re.search(r"color=c=0x0e0e14@0.72:s=(\d+)x(\d+)", fc).groups())
        clip_top = pack.DEFAULT_LAYOUT["promo"]["clip"][1]
        self.assertLess(pack.TITLE_SAFE[1] + ph, clip_top, "the station's logo stays clear of the clip area")
        self.assertIn(f"overlay=x={1920 - pw - pack.TITLE_SAFE[0]}:y={pack.TITLE_SAFE[1]}", fc)

    def test_without_it_the_promo_is_as_before(self):
        fc = self.build()
        fc = fc[fc.index("-filter_complex") + 1]
        self.assertNotIn("[sl]", fc)


class WhichPromosCarryIt(App):
    def test_only_promos_not_made_with_the_station_pack(self):
        # The example pack is made once and shared with other test files (small_pack): never removed here.
        folder, got = small_pack()
        sp = {**got["pack"], "folder": folder}
        self.app.station_pack = lambda s: sp
        own = {"folder": "/data/packs/ch-a51bd5a8", "dog": "logo/dog.png"}
        want = os.path.join(folder, sp["dog"])
        self.assertEqual(self.app.station_logo_for({}, own, {}), want, "a channel with its own pack")
        self.assertEqual(self.app.station_logo_for({}, promo.plain_pack("0x1f5f99"), {}), want, "a plain promo")
        self.assertIsNone(self.app.station_logo_for({}, sp, {}), "the station's own pack carries it already")
        self.assertIsNone(self.app.station_logo_for({}, own, {"promo_station_logo": False}), "the setting turns it off")
        self.app.station_pack = lambda s: None
        self.assertIsNone(self.app.station_logo_for({}, own, {}), "no station pack, no logo")


@unittest.skipUnless(FFMPEG, "ffmpeg is not installed here")
class MakingOne(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        FakeJellyfin.folder = cls.tmp.name
        subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black:s=640x360:r=25:d=60", "-f", "lavfi", "-i", "sine=f=440:d=60",
                        "-c:v", "libx264", "-preset", "ultrafast", "-g", "25", "-c:a", "aac", "-shortest", "-y", os.path.join(cls.tmp.name, "a1.ts")], check=True)
        cls.logo = os.path.join(cls.tmp.name, "logo.png")
        subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0x00ff00:s=520x248", "-frames:v", "1", "-y", cls.logo], check=True)
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeJellyfin)
        threading.Thread(target=cls.server.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.tmp.cleanup()

    def test_a_real_promo_shows_it(self):
        lineup = [{"id": "a1", "dur": 60, "title": "Pattern Show", "group": "a", "kind": "Episode"}]
        a = schedule.Channel(channel(lineup, start_on=0)).airing(NOW + 86400)
        out = os.path.join(self.tmp.name, "p.mp4")
        with tempfile.TemporaryDirectory() as d:
            argv, seconds = promo.command(promo.plain_pack("0x1a237e"), a, "Late ink", None, 480, 270, self.url, "k", dog.Texts(d), out,
                                          seconds=10, station_logo=self.logo)
            ok, why = promo.run(argv, limit=120)
        self.assertTrue(ok, why)
        frame = subprocess.run(["ffmpeg", "-v", "error", "-ss", "5", "-i", out, "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                               capture_output=True, check=True).stdout
        lw = int(480 * promo.STATION_LOGO_SHARE) // 2 * 2
        pad = max(4, round(lw * 0.06)) // 2 * 2
        x = 480 - (lw + 2 * pad) - int(pack.TITLE_SAFE[0] * 480 / 1920) + pad + lw // 2
        y = int(pack.TITLE_SAFE[1] * 270 / 1080) + pad + 3
        r, g, b = frame[(y * 480 + x) * 3:(y * 480 + x) * 3 + 3]
        self.assertTrue(g > 180 and r < 100 and b < 100, f"the (green) logo is in its corner: {(r, g, b)}")
        r, g, b = frame[(5 * 480 + 5) * 3:(5 * 480 + 5) * 3 + 3]
        self.assertFalse(g > 180 and r < 100, "and nowhere else")


if __name__ == "__main__":
    unittest.main()
