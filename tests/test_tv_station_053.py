"""Create your own TV channel 0.5.3 (owner, 19 November 2026): a pack's logo was refused as having "no transparent
parts" when the check itself could not run because the plug-in was busy. The same file was accepted a moment later."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT  # noqa: E402
from test_tv_station_pack import small_pack  # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "tv-station"))
import pack  # noqa: E402

FFMPEG = bool(shutil.which("ffmpeg"))


class Answer:
    def __init__(self, out):
        self.stdout = out


class Transparency(unittest.TestCase):
    def test_a_check_that_could_not_run_is_not_a_solid_logo(self):
        with mock.patch.object(pack.subprocess, "run", return_value=Answer(b"")), mock.patch.object(pack.time, "sleep"):
            self.assertIsNone(pack.has_transparency("/x.png"))
        with mock.patch.object(pack.subprocess, "run", side_effect=OSError("no more processes")), mock.patch.object(pack.time, "sleep"):
            self.assertIsNone(pack.has_transparency("/x.png"))
        with mock.patch.object(pack.subprocess, "run", side_effect=subprocess.TimeoutExpired("ffmpeg", 30)), mock.patch.object(pack.time, "sleep"):
            self.assertIsNone(pack.has_transparency("/x.png"))

    def test_it_is_tried_again(self):
        answers = [Answer(b""), Answer(bytes([10, 10, 10, 0]) * 4)]
        with mock.patch.object(pack.subprocess, "run", side_effect=answers), mock.patch.object(pack.time, "sleep") as slept:
            self.assertTrue(pack.has_transparency("/x.png"))
        self.assertEqual(slept.call_count, 1)

    @unittest.skipUnless(FFMPEG, "ffmpeg is not installed here")
    def test_real_pictures(self):
        with tempfile.TemporaryDirectory() as d:
            clear, solid = os.path.join(d, "clear.png"), os.path.join(d, "solid.png")
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=red@0.0:s=200x100,format=rgba", "-frames:v", "1", "-y", clear], check=True)
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=red:s=200x100,format=rgba", "-frames:v", "1", "-y", solid], check=True)
            self.assertTrue(pack.has_transparency(clear))
            self.assertFalse(pack.has_transparency(solid))


    @unittest.skipUnless(FFMPEG, "ffmpeg is not installed here")
    def test_the_pack_check_says_what_happened(self):
        folder, _ = small_pack()
        with mock.patch.object(pack, "has_transparency", return_value=None):
            said = pack.check(folder)["problems"]
        self.assertIn("logo/dog.png: could not be read at the moment (the plug-in was busy). Upload the pack again in a minute", said)
        self.assertFalse(any("no transparent parts" in x for x in said))


if __name__ == "__main__":
    unittest.main()
