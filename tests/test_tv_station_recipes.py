"""Create your own TV channel 0.10.0: Make a style here (the recipes, the colours made readable, one FFmpeg thread, a still to look at first,
the pack that passes every check, never while a channel is watched)."""
import io
import json
import os
import re
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT  # noqa: E402
from test_tv_station_pack import load_app  # noqa: E402

TV = os.path.join(ROOT, "tv-station")
sys.path.insert(0, TV)
import draw  # noqa: E402
import pack  # noqa: E402
import recipes  # noqa: E402

HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


class Rules(unittest.TestCase):
    def test_four_to_six_styles_each_with_a_plain_name_and_line(self):
        self.assertTrue(4 <= len(recipes.STYLES) <= 6)
        for k, v in recipes.STYLES.items():
            self.assertTrue(v["name"] and v["blurb"], k)
            for word in (v["name"] + " " + v["blurb"]).split():
                self.assertNotIn(word.lower().strip(".,"), ("ident", "idents", "see", "look", "promo", "activate"))
            self.assertNotIn("'", v["blurb"])

    def test_the_name_is_at_least_72_pixels_and_inside_the_title_safe_area(self):
        for n in ("A", "Evening TV", "x" * 40):
            size = recipes.text_size(n)
            self.assertGreaterEqual(size, 72)
            self.assertLessEqual(size, 170)
            if size > 72:
                self.assertLessEqual(0.56 * size * len(n), recipes.SAFE_W)
        self.assertLessEqual(0.56 * 72 * 40, recipes.SAFE_W)

    def test_the_words_reach_seven_to_one_on_every_colour_they_sit_on(self):
        for style in recipes.STYLES:
            for c1, c2 in (("#10202C", "#1B8A7F"), ("#FFFF00", "#FFFFFF"), ("#808080", "#7F7F7F"), ("#FF0000", "#00FF00"), ("#000000", "#000000")):
                look = recipes.plan(style, "Evening TV", c1, c2)
                for key in recipes._carry(style):
                    self.assertGreaterEqual(draw.contrast(look["ink"], look[key]), 7.0, (style, c1, c2, key))

    def test_a_colour_that_already_reads_is_left_alone_and_one_that_does_not_is_said(self):
        self.assertEqual(recipes.plan("plain", "X", "#10202C", "#1B8A7F")["adjusted"], [])
        self.assertEqual(recipes.plan("clean", "X", "#10202C", "#1B8A7F")["adjusted"], ["c2"])

    def test_nothing_moves_faster_than_the_rules(self):
        for style in recipes.STYLES:
            chain = recipes.title_filters(style, "/x/words.txt", "Evening TV", "#10202C", "#1B8A7F", 0)
            self.assertIsNone(re.search(r"[^A-Za-z]t/0\.[1-4]", chain), style)  # no ramp quicker than a 0.5 second fade, and slides take a second
            self.assertNotIn("blink", chain)
            self.assertNotIn("random", chain)

    def test_a_still_variant_has_no_movement(self):
        for style in recipes.STYLES:
            chain = recipes.title_filters(style, "/x/words.txt", "Evening TV", "#10202C", "#1B8A7F", 0, still=True)
            self.assertIsNone(re.search(r"[^A-Za-z]t/", chain), style)
            self.assertIn("alpha='1'", chain)

    def test_the_text_file_way_is_used_so_a_name_is_never_part_of_a_command(self):
        chain = recipes.title_filters("clean", "/x/words.txt", "a:b'c,d", "#10202C", "#1B8A7F", 0)
        self.assertIn("textfile=/x/words.txt", chain)
        self.assertNotIn("a:b", chain)

    def test_the_licence_is_mit_and_has_no_ai_line(self):
        text = recipes.licence("Evening TV", "clean", "28 November 2026", False)
        self.assertIn("MIT License", text)
        self.assertNotIn("AI tool", text)
        self.assertNotIn("CC0", text)


@unittest.skipUnless(HAS_FFMPEG, "needs FFmpeg")
class Drawn(unittest.TestCase):
    def setUp(self):
        draw.clear()
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_still_is_a_picture_the_right_shape(self):
        for part in ("title", "bumper", "card"):
            dst = os.path.join(self.tmp.name, f"{part}.png")
            recipes.title_still("bold", "Evening TV", "#10202C", "#1B8A7F", dst, self.tmp.name, part=part)
            info = pack.probe(dst)
            self.assertEqual((info["video"]["width"], info["video"]["height"]), (960, 540))

    def test_a_style_makes_a_pack_that_passes_every_check_and_nothing_flashes(self):
        out = os.path.join(self.tmp.name, "p")
        steps = []
        recipes.make(out, "clean", "Evening TV", ["#10202C", "#1B8A7F"], "28 November 2026", progress=lambda a, b, w: steps.append((a, b)))
        self.assertEqual(steps[-1][0], steps[-1][1])
        got = pack.install_folder(out, os.path.join(self.tmp.name, "installed"))
        self.assertTrue(got["ok"], got["problems"])
        p = got["pack"]
        self.assertEqual(len(p["idents"]), 4)
        self.assertEqual(len(p["bumpers"]), 2)
        self.assertTrue(p["coming_next"] and p["promo"] and p["dog"])
        for i in p["idents"]:
            self.assertTrue(4 <= i["dur"] <= 8, i)
        for b in p["bumpers"]:
            self.assertTrue(1 <= b["dur"] <= 2, b)
        self.assertFalse([n for n in got["notes"] if "flashes" in n], got["notes"])
        self.assertIn("MIT License", open(os.path.join(self.tmp.name, "installed", "LICENCE.txt")).read())

    def test_an_added_logo_is_used(self):
        logo = os.path.join(self.tmp.name, "logo.png")
        draw.text_logo("My logo", "#FFFFFF", "#10202C", logo, self.tmp.name)
        out = os.path.join(self.tmp.name, "p")
        recipes.make(out, "plain", "X", ["#10202C", "#1B8A7F"], "today", logo=logo, still=True)
        got = pack.check(out)
        self.assertTrue(got["ok"], got["problems"])
        self.assertIn("The on-screen logo is a picture the owner added", open(os.path.join(out, "LICENCE.txt")).read())

    def test_every_command_uses_one_thread(self):
        seen = []
        real = draw.ff
        draw.ff = lambda *a, **k: (seen.append(a), real(*a, **k))[1]
        try:
            recipes.make(os.path.join(self.tmp.name, "p"), "retro", "Evening TV", ["#10202C", "#1B8A7F"], "today")
        finally:
            draw.ff = real
        videos = [a for a in seen if "libx264" in a]
        self.assertEqual(len(videos), 6)
        for a in videos:
            self.assertEqual(a[a.index("-threads") + 1], "1")
            self.assertIn("threads=1:lookahead-threads=1", " ".join(a))


@unittest.skipUnless(HAS_FFMPEG, "needs FFmpeg")
class Page(unittest.TestCase):
    def setUp(self):
        draw.clear()
        self.tmp = tempfile.TemporaryDirectory()
        self.app = load_app(self.tmp.name)
        import stylepage
        self.sp = stylepage

    def tearDown(self):
        self.tmp.cleanup()

    def wait(self, kid):
        for _ in range(240):
            st = self.sp.state_of(kid)
            if not st["job"].get("running"):
                return st
            time.sleep(0.5)
        self.fail("the style did not finish")

    def test_preview_first_then_make_then_use(self):
        png = self.sp.preview({"style": "evening", "name": "Evening TV", "c1": "#10202C", "c2": "#1B8A7F", "part": "title"})
        self.assertTrue(png.startswith(b"\x89PNG"))
        kid = self.sp.op({"op": "new"})["kit"]["id"]
        self.sp.op({"op": "set", "kit": kid, "mode": "make", "style": "evening", "name": "Evening TV", "colours": ["#10202C", "#1B8A7F"]})
        self.sp.op({"op": "build", "kit": kid})
        with self.assertRaises(ValueError):
            self.sp.op({"op": "build", "kit": kid})  # one job at a time
        st = self.wait(kid)
        self.assertTrue(st["result"]["ok"], st)
        o = self.sp.op({"op": "use", "kit": kid, "to": "station"})
        self.assertIn("Evening TV is now the branding", o["said"])
        self.assertEqual(self.app.load_pack("station")["name"], "Evening TV")

    def test_no_preview_and_no_job_while_a_channel_is_watched(self):
        self.sp.bind(playing=lambda: {"abc": 1})
        with self.assertRaises(ValueError) as e:
            self.sp.preview({"style": "clean", "name": "X", "c1": "#10202C", "c2": "#1B8A7F", "part": "title"})
        self.assertIn("nobody is watching", str(e.exception))
        kid = self.sp.op({"op": "new"})["kit"]["id"]
        self.sp.op({"op": "set", "kit": kid, "mode": "make", "style": "clean", "name": "X"})
        with self.assertRaises(ValueError):
            self.sp.op({"op": "build", "kit": kid})

    def test_a_bad_style_or_part_is_refused(self):
        with self.assertRaises(ValueError):
            self.sp.preview({"style": "nope", "name": "X", "c1": "#10202C", "c2": "#1B8A7F", "part": "title"})
        with self.assertRaises(ValueError):
            self.sp.preview({"style": "clean", "name": "X", "c1": "#10202C", "c2": "#1B8A7F", "part": "../x"})


if __name__ == "__main__":
    unittest.main()
