"""Create your own TV channel 0.10.2: Lottie import (the JSON checked before anything is drawn, the colours swapped, the render only where
rlottie is in the image)."""
import copy
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT  # noqa: E402

TV = os.path.join(ROOT, "tv-station")
sys.path.insert(0, TV)
import draw  # noqa: E402
import lottie  # noqa: E402
import pack  # noqa: E402

HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def sample():
    def fill(c):
        return {"ty": "fl", "c": {"a": 0, "k": c}, "o": {"a": 0, "k": 100}, "r": 1, "nm": "Fill"}

    def tr():
        return {"ty": "tr", "p": {"a": 0, "k": [0, 0]}, "a": {"a": 0, "k": [0, 0]}, "s": {"a": 0, "k": [100, 100]}, "r": {"a": 0, "k": 0}, "o": {"a": 0, "k": 100}}

    def layer(shape, colour, pos):
        return {"ty": 4, "nm": "l", "ip": 0, "op": 150, "st": 0, "sr": 1,
                "ks": {"o": {"a": 0, "k": 100}, "r": {"a": 0, "k": 0}, "p": {"a": 0, "k": pos}, "a": {"a": 0, "k": [0, 0, 0]}, "s": {"a": 0, "k": [100, 100, 100]}},
                "shapes": [{"ty": "gr", "it": [shape, fill(colour), tr()], "nm": "g"}]}
    return {"v": "5.7.0", "fr": 25, "ip": 0, "op": 150, "w": 1920, "h": 1080, "nm": "measure", "ddd": 0, "assets": [],
            "layers": [layer({"ty": "el", "d": 1, "s": {"a": 0, "k": [300, 300]}, "p": {"a": 0, "k": [0, 0]}}, [1, 0.835, 0.31, 1], [960, 540, 0]),
                       layer({"ty": "rc", "d": 1, "s": {"a": 0, "k": [1400, 220]}, "p": {"a": 0, "k": [0, 0]}, "r": {"a": 0, "k": 40}}, [0.106, 0.541, 0.498, 1], [960, 540, 0]),
                       layer({"ty": "rc", "d": 1, "s": {"a": 0, "k": [100, 100]}, "p": {"a": 0, "k": [0, 0]}, "r": {"a": 0, "k": 0}}, [0.106, 0.541, 0.498, 1], [100, 100, 0])]}


def raw(doc):
    return json.dumps(doc).encode()


class Checks(unittest.TestCase):
    def test_a_good_animation_passes_with_its_size_and_length(self):
        doc, info = lottie.check(raw(sample()))
        self.assertEqual(info, {"w": 1920, "h": 1080, "dur": 6.0, "fps": 25.0})
        self.assertEqual(len(doc["layers"]), 3)

    def test_each_refusal_says_why_in_one_sentence(self):
        cases = []
        big = raw(sample()) + b" " * lottie.MAX_BYTES
        cases.append((big, "over 1 MB"))
        cases.append((b"not json", "not a Lottie file"))
        cases.append((b"[1]", "not a Lottie file"))
        d = sample(); d["w"] = 4000; cases.append((raw(d), "4000 by 1080"))
        d = sample(); d["op"] = 1000; cases.append((raw(d), "seconds long"))
        d = sample(); d["fr"] = 120; cases.append((raw(d), "frames a second"))
        d = sample(); d["layers"][0]["ks"]["p"] = {"a": 1, "k": [], "x": "var $bm_rt = time * 100;"}; cases.append((raw(d), "expressions"))
        d = sample(); d["nm"] = "https://example.invalid/x"; cases.append((raw(d), "link"))
        d = sample(); d["layers"][0]["nm"] = "javascript:alert(1)"; cases.append((raw(d), "link"))
        d = sample(); d["assets"] = [{"id": "i", "w": 1, "h": 1, "p": "data:image/png;base64,AAAA", "e": 1}]; cases.append((raw(d), "link or an embedded file"))
        d = sample(); d["assets"] = [{"id": "i", "w": 1, "h": 1, "p": "img.png", "u": "images/"}]; cases.append((raw(d), "pictures"))
        d = sample(); d["layers"][0]["ty"] = 5; cases.append((raw(d), "text"))
        d = sample(); d["layers"][0]["ty"] = 2; cases.append((raw(d), "a picture"))
        d = sample(); d["layers"] = d["layers"] * 30; cases.append((raw(d), "layers. The most is"))
        deep = {"a": 1}
        node = deep
        for _ in range(60):
            node["b"] = {}
            node = node["b"]
        d = sample(); d["extra"] = deep; cases.append((raw(d), "nests"))
        for data, words in cases:
            with self.assertRaises(lottie.LottieError, msg=words) as e:
                lottie.check(data)
            self.assertIn(words, str(e.exception))
            self.assertNotIn("'", str(e.exception).replace("plug-in's", "").replace("server's", ""))

    def test_a_plain_name_with_no_link_in_it_is_fine(self):
        d = sample(); d["nm"] = "Title: my channel"; d["layers"][0]["nm"] = "ratio 16:9"
        lottie.check(raw(d))


class Colours(unittest.TestCase):
    def test_the_most_used_colour_becomes_the_main_colour_and_the_rest_the_second(self):
        doc = sample()
        self.assertEqual(lottie.colours_of(doc)[0], [0.106, 0.541, 0.498])  # used twice
        new = lottie.recolour(doc, "#112233", "#FF0000")
        k = [lay["shapes"][0]["it"][1]["c"]["k"] for lay in new["layers"]]
        self.assertEqual(k[0], [1.0, 0.0, 0.0, 1])  # the amber circle, used once
        self.assertEqual(k[1], [0x11 / 255, 0x22 / 255, 0x33 / 255, 1])  # the teal bars
        self.assertEqual(k[2], k[1])
        self.assertEqual(doc, sample())  # the original is left alone

    def test_animated_colours_and_alpha_are_kept(self):
        d = sample()
        c = d["layers"][0]["shapes"][0]["it"][1]["c"]
        c.update({"a": 1, "k": [{"t": 0, "s": [1, 0, 0, 0.5]}, {"t": 10, "s": [0, 0, 1, 0.25]}]})
        new = lottie.recolour(d, "#00FF00", "#0000FF")
        kf = new["layers"][0]["shapes"][0]["it"][1]["c"]["k"]
        self.assertEqual([k["s"][3] for k in kf], [0.5, 0.25])
        for k in kf:
            self.assertEqual(k["s"][:3], [0.0, 0.0, 1.0])

    def test_an_animation_with_no_fills_is_returned_as_it_is(self):
        d = sample()
        for lay in d["layers"]:
            lay["shapes"] = []
        self.assertEqual(lottie.recolour(d, "#112233", "#FF0000"), d)


@unittest.skipUnless(HAS_FFMPEG and lottie.available(), "needs FFmpeg and rlottie")
class Drawn(unittest.TestCase):
    def setUp(self):
        draw.clear()

    def test_it_renders_over_a_colour_and_the_pack_check_accepts_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc, info = lottie.check(raw(sample()))
            dst = os.path.join(tmp, "ident.mp4")
            lottie.render(lottie.recolour(doc, "#10202C", "#FFD54F"), info, dst, tmp, "Evening TV", "#FFFFFF", "#10202C")
            i = pack.probe(dst)
            self.assertEqual((i["video"]["width"], i["video"]["height"]), (1920, 1080))
            self.assertAlmostEqual(i["duration"], 6.0, delta=0.3)


def _pillow():
    try:
        import PIL.Image  # noqa: F401
        return True
    except ImportError:
        return False


@unittest.skipUnless(HAS_FFMPEG and _pillow(), "needs FFmpeg and Pillow")
class Pipeline(unittest.TestCase):
    """The encoding path with a stand-in for rlottie (a moving bar drawn by Pillow), so it is tested wherever FFmpeg and Pillow are."""

    def setUp(self):
        import types

        from PIL import Image, ImageDraw

        class FakeAnimation:
            @classmethod
            def from_data(cls, data):
                return cls()

            def lottie_animation_get_size(self):
                return (640, 360)

            def lottie_animation_get_totalframe(self):
                return 50

            def lottie_animation_get_framerate(self):
                return 25.0

            def render_pillow_frame(self, i):
                img = Image.new("RGBA", (640, 360), (0, 0, 0, 0))
                ImageDraw.Draw(img).rectangle([i * 10, 100, i * 10 + 80, 200], fill=(255, 213, 79, 255))
                return img
        self.saved = sys.modules.get("rlottie_python")
        sys.modules["rlottie_python"] = types.SimpleNamespace(LottieAnimation=FakeAnimation)
        draw.clear()
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        if self.saved is None:
            sys.modules.pop("rlottie_python", None)
        else:
            sys.modules["rlottie_python"] = self.saved
        self.tmp.cleanup()

    def info(self):
        return {"w": 640, "h": 360, "dur": 2.0, "fps": 25.0}

    def test_a_title_clip_is_made_over_a_colour_with_the_name(self):
        dst = os.path.join(self.tmp.name, "ident.mp4")
        lottie.render({}, self.info(), dst, self.tmp.name, "Evening TV", "#FFFFFF", "#10202C")
        i = pack.probe(dst)
        self.assertEqual((i["video"]["width"], i["video"]["height"]), (1920, 1080))
        self.assertAlmostEqual(i["duration"], 2.0, delta=0.2)
        self.assertEqual(i["video"]["codec_name"], "h264")

    def test_a_bumper_has_no_name_and_transparency_can_be_kept(self):
        dst = os.path.join(self.tmp.name, "bumper.webm")
        lottie.render({}, self.info(), dst, self.tmp.name, "", "#FFFFFF", "#10202C", keep_alpha=True)
        self.assertTrue(pack.alpha_video(pack.probe(dst)))

    def test_a_channel_starting_to_play_stops_it(self):
        draw.stop()
        try:
            with self.assertRaises(draw.Stopped):
                lottie.render({}, self.info(), os.path.join(self.tmp.name, "x.mp4"), self.tmp.name, "N", "#FFFFFF", "#10202C")
        finally:
            draw.clear()

    def test_the_name_is_never_part_of_a_command(self):
        dst = os.path.join(self.tmp.name, "ident.mp4")
        lottie.render({}, self.info(), dst, self.tmp.name, "a:b'c,d;e", "#FFFFFF", "#10202C")
        self.assertTrue(os.path.getsize(dst) > 0)

    def test_an_animation_larger_than_it_says_is_refused(self):
        bad = dict(self.info(), w=320)
        with self.assertRaises(lottie.LottieError):
            lottie.render({}, bad, os.path.join(self.tmp.name, "x.mp4"), self.tmp.name, "N", "#FFFFFF", "#10202C")


class InAKit(unittest.TestCase):
    def test_roles_and_guess_for_an_animation(self):
        import kit
        self.assertEqual(kit.roles_for("lottie"), ["ident", "bumper", "skip"])
        self.assertEqual(kit.guess_role("a.json", {"kind": "lottie", "dur": 6.0}), "ident")
        self.assertEqual(kit.guess_role("a.json", {"kind": "lottie", "dur": 1.5}), "bumper")

    def test_a_bad_json_is_refused_by_the_kit_with_the_reason(self):
        import kit
        with tempfile.TemporaryDirectory() as tmp:
            d = sample()
            d["layers"][0]["ks"]["p"] = {"a": 1, "k": [], "x": "var $bm_rt = time;"}
            path = os.path.join(tmp, "a.json")
            open(path, "w").write(json.dumps(d))
            with self.assertRaises(kit.KitError) as e:
                kit.inspect(path)
            self.assertIn("expressions", str(e.exception))

    def test_without_rlottie_a_good_file_is_refused_in_a_sentence(self):
        import kit
        if lottie.available():
            self.skipTest("rlottie is here")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a.json")
            open(path, "w").write(json.dumps(sample()))
            with self.assertRaises(kit.KitError) as e:
                kit.inspect(path)
            self.assertIn("rlottie", str(e.exception))


class Honest(unittest.TestCase):
    def test_without_rlottie_it_says_so(self):
        if lottie.available():
            self.skipTest("rlottie is here")
        with self.assertRaises(lottie.LottieError) as e:
            lottie.render({}, {"w": 1, "h": 1, "fps": 25}, "/x.mp4", "/tmp", "N", "#FFFFFF", "#000000")
        self.assertIn("rlottie", str(e.exception))


if __name__ == "__main__":
    unittest.main()
