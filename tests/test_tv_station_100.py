"""Create your own TV channel 0.10.0: the flash guard (a plain warning for fast brightness jumps on every clip made, added or
imported, never a refusal), and the loudness step beside it."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT  # noqa: E402

TV = os.path.join(ROOT, "tv-station")
sys.path.insert(0, TV)
import flash  # noqa: E402
import pack  # noqa: E402

HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def strobe(path, hz, seconds=3, size="160x90"):
    """A clip whose whole picture goes black and white `hz` times a second."""
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=white:s={size}:r=25:d={seconds}",
                    "-vf", f"geq=lum='if(lt(mod(T*{hz}\\,1)\\,0.5)\\,255\\,0)':cb=128:cr=128", "-t", str(seconds), "-pix_fmt", "yuv420p", path], check=True)


def calm(path, seconds=3, size="160x90"):
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", f"gradients=s={size}:c0=0x10202c:c1=0x1b8a7f:speed=0.02:r=25:d={seconds}",
                    "-t", str(seconds), "-pix_fmt", "yuv420p", path], check=True)


class Rules(unittest.TestCase):
    def test_a_jump_is_ten_percent_with_the_darker_frame_below_point_eight(self):
        self.assertEqual(flash.jumps([0.0, 0.09, 0.0]), [])
        self.assertEqual(flash.jumps([0.0, 0.10, 0.0]), [(1, 1), (2, -1)])
        self.assertEqual(flash.jumps([0.85, 0.99, 0.85]), [])  # both frames very light: not counted
        self.assertEqual(flash.jumps([0.5, 0.9]), [(1, 1)])

    def test_a_fade_is_not_a_flash(self):
        self.assertEqual(flash.flashes([i * 0.15 for i in range(7)])[0], 0)
        self.assertEqual(flash.flashes([0.0, 0.5, 1.0, 0.5, 0.0])[0], 1)

    def test_more_than_three_flashes_in_a_second_is_a_warning(self):
        three = [0.0 if i % 2 == 0 else 0.5 for i in range(7)] + [0.0] * 40  # 6 jumps: 3 flashes
        four = [0.0 if i % 2 == 0 else 0.5 for i in range(9)] + [0.0] * 40  # 8 jumps: 4 flashes
        self.assertFalse(flash.judge({"all": three})["warn"])
        got = flash.judge({"all": four})
        self.assertTrue(got["warn"])
        self.assertEqual(got["flashes"], 4)

    def test_flashes_spread_over_more_than_a_second_are_not_counted_together(self):
        slow = []
        for _ in range(8):  # one flash every 30 frames
            slow += [0.0, 0.5] + [0.0] * 28
        self.assertFalse(flash.judge({"all": slow})["warn"])

    def test_a_flash_in_one_quarter_of_the_picture_counts(self):
        w, h = flash.GRID
        frames = b""
        for i in range(12):
            level = 128 if i % 2 else 0
            frame = bytearray(w * h)
            for y in range(0, 4):
                for x in range(0, 8):
                    frame[y * w + x] = level
            frames += bytes(frame)
        got = flash.judge(flash.frame_series(frames))
        self.assertTrue(got["warn"])
        self.assertEqual(got["where"], "left top")
        self.assertIn("in the left top of the picture", flash.words(got))

    def test_the_words_are_plain(self):
        said = flash.words({"warn": True, "flashes": 5, "at": 3.2, "where": "all"})
        self.assertEqual(said, "it flashes 5 times in one second, from 0:03. Fast flashing can make some people ill. Choose another clip, or keep it if you are sure")
        self.assertEqual(flash.words({"warn": False}), "")
        self.assertEqual(flash.words(None), "")
        self.assertNotIn("'", said)

    def test_a_clip_that_cannot_be_read_says_nothing(self):
        self.assertIsNone(flash.check("/nonexistent/clip.mp4"))
        old = flash.ENABLED
        flash.ENABLED = False
        try:
            self.assertIsNone(flash.check("/nonexistent/clip.mp4"))
        finally:
            flash.ENABLED = old


@unittest.skipUnless(HAS_FFMPEG, "needs FFmpeg")
class RealClips(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_strobe_is_found_and_a_gradient_is_not(self):
        s, c = os.path.join(self.tmp.name, "s.mp4"), os.path.join(self.tmp.name, "c.mp4")
        strobe(s, 6)
        calm(c)
        got = flash.check(s)
        self.assertTrue(got["warn"], got)
        self.assertGreaterEqual(got["flashes"], 4)
        self.assertFalse(flash.check(c)["warn"])

    def test_the_pack_check_notes_a_strobe_ident_and_still_passes_it(self):
        folder = os.path.join(self.tmp.name, "p")
        for sub in ("logo", "idents"):
            os.makedirs(os.path.join(folder, sub))
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x1b8a7f:s=480x270:d=1", "-vf",
                        "format=rgba,geq=r=27:g=138:b=127:a='if(lt(hypot(X-W/2\\,Y-H/2)\\,100)\\,255\\,0)'", "-frames:v", "1",
                        os.path.join(folder, "logo", "dog.png")], check=True)
        strobe(os.path.join(folder, "idents", "ident01.mp4"), 6, seconds=3, size="480x270")
        pack.validate  # noqa: B018 - the schema is used by check()
        import json
        json.dump({"pack": 1, "name": "Strobe", "logo": {"dog": "logo/dog.png"}, "idents": ["ident01.mp4"]}, open(os.path.join(folder, "pack.json"), "w"))
        got = pack.check(folder)
        self.assertTrue(got["ok"], got["problems"])
        self.assertTrue(any("ident01.mp4: it flashes" in n for n in got["notes"]), got["notes"])


class LoudnessStep(unittest.TestCase):
    def test_the_target_and_the_most_gain_are_the_broadcast_ones(self):
        self.assertEqual(pack.LOUDNESS, -23.0)
        self.assertEqual(pack.gain_for(-23.0), 0.0)
        self.assertEqual(pack.gain_for(-14.0), -9.0)
        self.assertEqual(pack.gain_for(-50.0), 12.0)  # never more than 12 dB
        self.assertEqual(pack.gain_for(None), 0.0)


@unittest.skipUnless(HAS_FFMPEG, "needs FFmpeg")
class LoudClip(unittest.TestCase):
    def test_an_ident_with_loud_sound_is_brought_to_minus_23(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = os.path.join(tmp, "p")
            os.makedirs(os.path.join(folder, "logo"))
            os.makedirs(os.path.join(folder, "idents"))
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x1b8a7f:s=480x270:d=1", "-vf",
                            "format=rgba,geq=r=27:g=138:b=127:a='if(lt(hypot(X-W/2\\,Y-H/2)\\,100)\\,255\\,0)'", "-frames:v", "1",
                            os.path.join(folder, "logo", "dog.png")], check=True)
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x10202c:s=480x270:r=25:d=3",
                            "-f", "lavfi", "-i", "sine=frequency=440:duration=3", "-af", "volume=8", "-t", "3", "-pix_fmt", "yuv420p",
                            os.path.join(folder, "idents", "ident01.mp4")], check=True)
            import json
            json.dump({"pack": 1, "name": "Loud", "logo": {"dog": "logo/dog.png"}, "idents": ["ident01.mp4"]}, open(os.path.join(folder, "pack.json"), "w"))
            got = pack.check(folder)
            self.assertTrue(got["ok"], got["problems"])
            self.assertLess(got["pack"]["idents"][0]["gain"], -3)
            self.assertTrue(any("LUFS" in n and "quieter" in n for n in got["notes"]), got["notes"])


if __name__ == "__main__":
    unittest.main()
