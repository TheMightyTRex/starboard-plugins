"""Create your own TV channel 0.10.0: Import a kit (the files checked by what they are, not their names; a still picture made into a
short title clip; the Where did this come from step writing LICENCE.txt and kit.json; the strict pack checks reused) and the page's
server side (one build at a time, never while a channel is watched)."""
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT  # noqa: E402
from test_tv_station_pack import load_app  # noqa: E402

TV = os.path.join(ROOT, "tv-station")
sys.path.insert(0, TV)
import draw  # noqa: E402
import kit  # noqa: E402
import pack  # noqa: E402

HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def ffm(*args):
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", *args], check=True)


def make_files(folder):
    ffm("-f", "lavfi", "-i", "color=c=0x1b8a7f:s=640x360", "-frames:v", "1", os.path.join(folder, "title.png"))
    ffm("-f", "lavfi", "-i", "gradients=s=320x180:r=25:d=3", "-pix_fmt", "yuv420p", os.path.join(folder, "wipe.mp4"))
    ffm("-f", "lavfi", "-i", "sine=frequency=300:duration=6", os.path.join(folder, "tune.mp3"))


class Words(unittest.TestCase):
    def test_names_are_made_safe(self):
        self.assertEqual(kit.safe_name("../../etc/pass wd.png"), "pass wd.png")
        self.assertEqual(kit.safe_name("a<b>:c.mp4"), "a_b__c.mp4"[:80])
        self.assertEqual(kit.safe_name(""), "file")

    def test_guess_role(self):
        self.assertEqual(kit.guess_role("tune.mp3", {"kind": "audio", "dur": 9}), "music")
        self.assertEqual(kit.guess_role("my-logo.png", {"kind": "still", "dur": 0}), "logo")
        self.assertEqual(kit.guess_role("pop.mp4", {"kind": "video", "dur": 1.5}), "bumper")
        self.assertEqual(kit.guess_role("intro.mp4", {"kind": "video", "dur": 6}), "ident")

    def test_kit_json_keeps_only_what_is_safe(self):
        got = kit.read_kit_json(json.dumps({"name": "Evening\u0007 TV" + "x" * 80, "colours": ["#112233", "#GGGGGG"],
                                             "files": {"a.png": {"origin": "stock", "link": "https://example.invalid/a"}, "b.png": {"origin": "stolen"},
                                                       "c.png": {"origin": "made", "link": "javascript:alert(1)"}}}))
        self.assertEqual(len(got["name"]), 40)
        self.assertNotIn("colours", got)
        self.assertEqual(got["files"]["a.png"], {"origin": "stock", "link": "https://example.invalid/a"})
        self.assertNotIn("b.png", got["files"])
        self.assertEqual(got["files"]["c.png"]["link"], "")
        with self.assertRaises(kit.KitError):
            kit.read_kit_json("[1]")
        with self.assertRaises(kit.KitError):
            kit.read_kit_json("x" * 70000)
        self.assertEqual(kit.read_kit_json(json.dumps({"colours": ["#112233", "#445566"]}))["colours"], ["#112233", "#445566"])

    def test_the_licence_says_where_each_file_came_from_and_reminds_for_something_else(self):
        files = [{"name": "a.png", "role": "ident", "origin": "made", "link": ""},
                 {"name": "b.mp3", "role": "music", "origin": "stock", "link": "https://example.invalid/m"},
                 {"name": "c.png", "role": "logo", "origin": "other", "link": ""},
                 {"name": "d.png", "role": "skip", "origin": "made"}]
        text = kit.licence_text("Evening TV", files, "28 November 2026")
        self.assertIn("a.png (short title clip)\n  Came from: I made it", text)
        self.assertIn("Came from: A free stock site, https://example.invalid/m", text)
        self.assertIn(kit.REMINDER, text)
        self.assertEqual(text.count(kit.REMINDER), 1)
        self.assertNotIn("d.png", text)
        self.assertNotIn("AI", text)

    def test_the_words_have_no_banned_forms(self):
        for t in list(kit.ROLES.values()) + list(kit.ORIGINS.values()) + [kit.REMINDER]:
            self.assertNotIn("'", t)
            self.assertNotIn("\u2014", t)
            self.assertNotRegex(t, r"\b(See|Look)\b")


class ZipRules(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = os.path.join(self.tmp.name, "in")
        os.makedirs(self.out)

    def tearDown(self):
        self.tmp.cleanup()

    def zip(self, members):
        path = os.path.join(self.tmp.name, "k.zip")
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            for name, data in members.items():
                if isinstance(data, zipfile.ZipInfo):
                    z.writestr(data, b"x")
                else:
                    z.writestr(name, data)
        return path

    def test_loose_files_are_unpacked_and_the_rest_skipped(self):
        got = kit.unzip_into(self.zip({"a.png": b"x", "__MACOSX/._a.png": b"x", "notes.txt": b"x", "kit.json": b"{}", "deep/b.mp3": b"x"}), self.out)
        self.assertEqual(sorted(got["saved"]), ["a.png", "b.mp3"])
        self.assertEqual(got["kit"], "{}")
        self.assertEqual(len(got["skipped"]), 1)

    def test_a_path_outside_a_link_and_a_password_are_refused(self):
        for name in ("../a.png", "/a.png", "C:/a.png", "a\\b.png"):
            with self.assertRaises(kit.KitError, msg=name):
                kit.unzip_into(self.zip({name: b"x"}), self.out)
        link = zipfile.ZipInfo("a.png")
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        with self.assertRaises(kit.KitError):
            kit.unzip_into(self.zip({"a.png": link}), self.out)

    def test_a_zip_bomb_and_too_many_files_are_refused(self):
        with self.assertRaises(kit.KitError):
            kit.unzip_into(self.zip({"a.png": b"\0" * (300 * 1024 * 1024)}), self.out)
        with self.assertRaises(kit.KitError):
            kit.unzip_into(self.zip({f"f{i}.png": b"x" for i in range(pack.MAX_FILES + 1)}), self.out)

    def test_not_a_zip(self):
        p = os.path.join(self.tmp.name, "n.zip")
        open(p, "wb").write(b"nope")
        with self.assertRaises(kit.KitError):
            kit.unzip_into(p, self.out)

    def test_a_ready_pack_is_told_apart(self):
        self.assertTrue(kit.has_pack_json(self.zip({"Pack/pack.json": b"{}", "Pack/logo/dog.png": b"x"})))
        self.assertFalse(kit.has_pack_json(self.zip({"a.png": b"x"})))


@unittest.skipUnless(HAS_FFMPEG, "needs FFmpeg")
class Files(unittest.TestCase):
    def setUp(self):
        draw.clear()  # a channel starting to play in another test sets the stop
        self.tmp = tempfile.TemporaryDirectory()
        self.src = os.path.join(self.tmp.name, "in")
        os.makedirs(self.src)
        make_files(self.src)

    def tearDown(self):
        self.tmp.cleanup()

    def test_a_file_is_known_by_what_it_is_not_its_name(self):
        self.assertEqual(kit.inspect(os.path.join(self.src, "title.png"))["kind"], "still")
        self.assertEqual(kit.inspect(os.path.join(self.src, "wipe.mp4"))["kind"], "video")
        self.assertEqual(kit.inspect(os.path.join(self.src, "tune.mp3"))["kind"], "audio")
        shutil.copy(os.path.join(self.src, "title.png"), os.path.join(self.src, "fake.mp4"))
        with self.assertRaises(kit.KitError) as e:
            kit.inspect(os.path.join(self.src, "fake.mp4"))
        self.assertIn("its name says", str(e.exception))
        open(os.path.join(self.src, "junk.mp4"), "wb").write(b"not a video")
        with self.assertRaises(kit.KitError):
            kit.inspect(os.path.join(self.src, "junk.mp4"))
        open(os.path.join(self.src, "x.svg"), "w").write("<svg onload='x()'/>")
        with self.assertRaises(kit.KitError) as e:
            kit.inspect(os.path.join(self.src, "x.svg"))
        self.assertIn("SVG", str(e.exception))

    def test_a_kit_becomes_a_pack_that_passes_the_pack_checks(self):
        files = []
        for n in sorted(os.listdir(self.src)):
            i = kit.inspect(os.path.join(self.src, n))
            files.append({"name": n, "kind": i["kind"], "role": {"title.png": "ident", "wipe.mp4": "bumper", "tune.mp3": "music"}[n],
                          "origin": {"title.png": "made", "wipe.mp4": "template", "tune.mp3": "other"}[n], "link": ""})
        out = os.path.join(self.tmp.name, "pack")
        steps = []
        kit.build(self.src, out, "Evening TV", ["#10202C", "#1B8A7F"], files, "28 November 2026", progress=lambda a, b, w: steps.append((a, b)))
        self.assertEqual(steps[-1][0], steps[-1][1])
        got = pack.install_folder(out, os.path.join(self.tmp.name, "installed"))
        self.assertTrue(got["ok"], got["problems"])
        p = got["pack"]
        self.assertEqual(len(p["idents"]), 1)
        self.assertAlmostEqual(p["idents"][0]["dur"], 5.0, delta=0.3)  # a still became a 5 second clip
        self.assertEqual(len(p["bumpers"]), 1)
        self.assertTrue(p["dog"])  # none was given, so the name was drawn
        inst = os.path.join(self.tmp.name, "installed")
        self.assertIn("Came from: A template or kit from a design tool", open(os.path.join(inst, "LICENCE.txt")).read())
        self.assertIn(kit.REMINDER, open(os.path.join(inst, "LICENCE.txt")).read())
        k = json.load(open(os.path.join(inst, "kit.json")))
        self.assertEqual(k["name"], "Evening TV")
        self.assertEqual(k["files"]["tune.mp3"]["origin"], "other")
        self.assertEqual(pack.validate(json.load(open(os.path.join(inst, "pack.json")))), [])

    def test_a_clip_with_no_known_role_left_makes_nothing(self):
        with self.assertRaises(kit.KitError):
            kit.build(self.src, os.path.join(self.tmp.name, "p"), "X", [], [{"name": "title.png", "kind": "still", "role": "skip"}], "today")

    def test_loud_sound_in_an_imported_ident_is_brought_to_minus_23_by_the_pack_check(self):
        ffm("-f", "lavfi", "-i", "color=c=0x10202c:s=320x180:r=25:d=3", "-f", "lavfi", "-i", "sine=frequency=440:duration=3", "-af", "volume=8", "-t", "3",
            "-pix_fmt", "yuv420p", os.path.join(self.src, "loud.mp4"))
        out = os.path.join(self.tmp.name, "pack")
        kit.build(self.src, out, "Loud", [], [{"name": "loud.mp4", "kind": "video", "role": "ident", "origin": "made", "link": ""}], "today")
        got = pack.check(out)
        self.assertTrue(got["ok"], got["problems"])
        self.assertLess(got["pack"]["idents"][0]["gain"], -3)
        self.assertTrue(any("LUFS" in n for n in got["notes"]))


@unittest.skipUnless(HAS_FFMPEG, "needs FFmpeg")
class Page(unittest.TestCase):
    def setUp(self):
        draw.clear()
        self.tmp = tempfile.TemporaryDirectory()
        self.app = load_app(self.tmp.name)
        import stylepage
        self.sp = stylepage
        self.src = os.path.join(self.tmp.name, "src")
        os.makedirs(self.src)
        make_files(self.src)

    def tearDown(self):
        self.tmp.cleanup()

    def add(self, name, kid=""):
        data = open(os.path.join(self.src, name), "rb").read()
        return self.sp.upload(kid, name, len(data), io.BytesIO(data))

    def wait(self, kid):
        for _ in range(240):
            st = self.sp.state_of(kid)
            if not st["job"].get("running"):
                return st
            time.sleep(0.5)
        self.fail("the build did not finish")

    def test_the_whole_way_through(self):
        o = self.add("title.png")
        kid = o["kit"]["id"]
        self.add("tune.mp3", kid)
        names = [f["name"] for f in self.sp.state_of(kid)["files"]]
        self.assertEqual(names, ["title.png", "tune.mp3"])
        with self.assertRaises(ValueError) as e:
            self.sp.op({"op": "build", "kit": kid})
        self.assertIn("Give the channel a name", str(e.exception))
        self.sp.op({"op": "set", "kit": kid, "name": "Evening TV", "colours": ["#10202c", "#1b8a7f"]})
        with self.assertRaises(ValueError) as e:
            self.sp.op({"op": "build", "kit": kid})
        self.assertIn("Say where title.png came from", str(e.exception))
        self.sp.op({"op": "set", "kit": kid, "files": [{"name": "title.png", "origin": "made"}, {"name": "tune.mp3", "origin": "bogus"}]})
        with self.assertRaises(ValueError):
            self.sp.op({"op": "build", "kit": kid})
        self.sp.op({"op": "set", "kit": kid, "files": [{"name": "tune.mp3", "origin": "stock", "link": "https://example.invalid/m"}]})
        self.sp.op({"op": "build", "kit": kid})
        with self.assertRaises(ValueError):  # a second build while one runs
            self.sp.op({"op": "build", "kit": kid})
        st = self.wait(kid)
        self.assertTrue(st["result"]["ok"], st)
        self.assertTrue(any("music is not used" in n for n in st["result"]["notes"]))
        o = self.sp.op({"op": "use", "kit": kid, "to": "station"})
        self.assertIn("Evening TV is now the branding", o["said"])
        s = self.app.state()
        self.assertEqual(s["station_pack"], "station")
        got = self.app.load_pack("station")
        self.assertEqual(got["name"], "Evening TV")
        self.assertTrue(os.path.exists(os.path.join(self.app.pack_dir("station"), "LICENCE.txt")))
        self.assertFalse(os.path.exists(os.path.join(self.sp.root(), kid)))

    def test_nothing_is_made_while_a_channel_is_watched(self):
        kid = self.add("title.png")["kit"]["id"]
        self.sp.op({"op": "set", "kit": kid, "name": "X", "files": [{"name": "title.png", "origin": "made"}]})
        self.sp.bind(playing=lambda: {"abc": 1})
        with self.assertRaises(ValueError) as e:
            self.sp.op({"op": "build", "kit": kid})
        self.assertIn("nobody is watching", str(e.exception))

    def test_bad_files_are_refused_with_a_sentence(self):
        self.assertRaises(ValueError, self.sp.upload, "", "x.mp4", 0, io.BytesIO(b""))
        with self.assertRaises(ValueError) as e:
            self.sp.upload("", "x.mp4", 11, io.BytesIO(b"not a video"))
        self.assertIn("FFmpeg cannot read it", str(e.exception))
        with self.assertRaises(ValueError) as e:
            self.sp.upload("", "big.mp4", 91 * 1024 * 1024, io.BytesIO(b""))
        self.assertIn("over 90 MB", str(e.exception))
        with self.assertRaises(ValueError):
            self.sp.kit_dir("../../etc")

    def test_a_channel_starting_to_play_stops_the_work(self):
        import draw
        draw.stop()
        try:
            with self.assertRaises(draw.Stopped):
                draw.ff("-f", "lavfi", "-i", "color=c=black:s=64x64:d=1", os.path.join(self.tmp.name, "x.mp4"))
        finally:
            draw.clear()

    def test_ffmpeg_is_told_one_thread(self):
        import draw
        self.assertIn("-threads", draw.H264)
        self.assertEqual(draw.H264[draw.H264.index("-threads") + 1], "1")
        self.assertIn("threads=1", " ".join(draw.H264))

    def test_text_colour_reaches_seven_to_one_or_says_not(self):
        import draw
        self.assertEqual(draw.text_colour("#10202C", "#1B8A7F")[0], "#FFFFFF")
        ink, ok, ratio = draw.text_colour("#FFFF00", "#FFFFFF")
        self.assertEqual(ink, "#000000")
        self.assertTrue(ok)
        self.assertFalse(draw.text_colour("#808080", "#808080")[1])


if __name__ == "__main__":
    unittest.main()
