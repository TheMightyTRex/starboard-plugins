"""Create your own TV channel 0.10.3: Packs ready to use (the shared hand-off folder tv-pack: listed with care, copied out first, checked as an
upload, removed only after it is used)."""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT  # noqa: E402

TV = os.path.join(ROOT, "tv-station")
sys.path.insert(0, TV)
import draw  # noqa: E402
import handoff  # noqa: E402
import pack  # noqa: E402

HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def make_zip(path, files):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for n, d in files.items():
            z.writestr(n, d)


def png_bytes(tmp):
    p = os.path.join(tmp, "bg.png")
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x1b8a7f:s=640x360", "-frames:v", "1", p], check=True)
    return open(p, "rb").read()


class Listing(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = os.path.join(self.tmp.name, "tv-pack")
        os.makedirs(self.dir)

    def tearDown(self):
        self.tmp.cleanup()

    def test_only_whole_regular_zips_with_plain_names_are_listed(self):
        make_zip(os.path.join(self.dir, "good.zip"), {"pack.json": "{}"})
        make_zip(os.path.join(self.dir, ".half.zip.part"), {"pack.json": "{}"})
        make_zip(os.path.join(self.dir, ".hidden.zip"), {"pack.json": "{}"})
        open(os.path.join(self.dir, "notes.txt"), "w").write("x")
        open(os.path.join(self.dir, "bad;name.zip"), "w").write("x")
        os.symlink("/etc/passwd", os.path.join(self.dir, "link.zip"))
        os.symlink(os.path.join(self.dir, "good.zip"), os.path.join(self.dir, "alias.zip"))
        os.mkdir(os.path.join(self.dir, "folder.zip"))
        open(os.path.join(self.dir, "empty.zip"), "w").close()
        with open(os.path.join(self.dir, "huge.zip"), "wb") as f:
            f.truncate(pack.MAX_ZIP + 1)
        self.assertEqual([r["name"] for r in handoff.listing(self.dir)], ["good.zip"])

    def test_a_missing_folder_is_an_empty_list(self):
        self.assertEqual(handoff.listing(os.path.join(self.tmp.name, "nope")), [])

    def test_the_licence_is_read_from_the_zip_without_unpacking(self):
        make_zip(os.path.join(self.dir, "a.zip"), {"pack.json": "{}", "LICENCE.txt": "bg.jpg: Alex, CC BY"})
        self.assertEqual(handoff.licence_of(self.dir, "a.zip"), "bg.jpg: Alex, CC BY")
        self.assertEqual(handoff.licence_of(self.dir, "../a.zip"), "")

    def test_take_copies_first_so_a_change_afterwards_is_not_what_is_checked(self):
        make_zip(os.path.join(self.dir, "a.zip"), {"pack.json": "{}"})
        copy = handoff.take("a.zip", os.path.join(self.tmp.name, "work"), self.dir)
        before = open(copy, "rb").read()
        make_zip(os.path.join(self.dir, "a.zip"), {"pack.json": "{\"changed\": true}"})
        self.assertEqual(open(copy, "rb").read(), before)

    def test_take_refuses_odd_names_links_and_big_files(self):
        os.symlink("/etc/passwd", os.path.join(self.dir, "link.zip"))
        for name in ("../a.zip", "a/b.zip", ".a.zip", "a.zip.part", "", "link.zip", "gone.zip"):
            with self.assertRaises(handoff.HandoffError, msg=name):
                handoff.take(name, os.path.join(self.tmp.name, "work"), self.dir)
        with open(os.path.join(self.dir, "huge.zip"), "wb") as f:
            f.truncate(pack.MAX_ZIP + 1)
        with self.assertRaises(handoff.HandoffError):
            handoff.take("huge.zip", os.path.join(self.tmp.name, "work"), self.dir)

    def test_remove_takes_out_only_a_named_zip(self):
        make_zip(os.path.join(self.dir, "a.zip"), {"pack.json": "{}"})
        open(os.path.join(self.dir, "keep.txt"), "w").write("x")
        handoff.remove("a.zip", self.dir)
        self.assertEqual(os.listdir(self.dir), ["keep.txt"])
        with self.assertRaises(handoff.HandoffError):
            handoff.remove("../keep.txt", self.dir)


@unittest.skipUnless(HAS_FFMPEG, "needs FFmpeg")
class Install(unittest.TestCase):
    def setUp(self):
        draw.clear()
        self.tmp = tempfile.TemporaryDirectory()
        self.work = os.path.join(self.tmp.name, "work")
        os.makedirs(self.work)

    def tearDown(self):
        self.tmp.cleanup()

    def test_backgrounds_and_a_licence_without_a_logo_are_installed_with_a_drawn_logo(self):
        z = os.path.join(self.tmp.name, "p.zip")
        make_zip(z, {"pack.json": json.dumps({"pack": 1, "name": "From the library", "made": "today", "author": "Online sources"}),
                     "coming-next/background.png": png_bytes(self.tmp.name), "promo/background.png": png_bytes(self.tmp.name),
                     "LICENCE.txt": "background.png: Alex, CC BY 4.0, https://example.invalid/a, saved 28 November 2026"})
        folder = os.path.join(self.tmp.name, "installed")
        got = handoff.install(z, folder, self.work)
        self.assertTrue(got["ok"], got["problems"])
        self.assertTrue(got["pack"]["dog"])
        self.assertIn("Alex, CC BY 4.0", open(os.path.join(folder, "LICENCE.txt")).read())
        self.assertEqual(pack.load(folder)["name"], "From the library")

    def test_a_zip_that_fails_the_checks_is_not_installed(self):
        z = os.path.join(self.tmp.name, "bad.zip")
        make_zip(z, {"pack.json": json.dumps({"pack": 1, "name": "Bad"}), "evil.sh": "rm -rf /"})
        folder = os.path.join(self.tmp.name, "installed")
        with self.assertRaises(pack.PackError):
            handoff.install(z, folder, self.work)
        self.assertFalse(os.path.exists(folder))

    def test_a_zip_bomb_and_a_path_outside_are_refused_as_for_an_upload(self):
        z = os.path.join(self.tmp.name, "x.zip")
        make_zip(z, {"pack.json": "{}", "../outside.png": b"x"})
        with self.assertRaises(pack.PackError):
            handoff.install(z, os.path.join(self.tmp.name, "i"), self.work)
        make_zip(z, {"pack.json": "{}", "promo/background.png": b"\0" * (300 * 1024 * 1024)})
        with self.assertRaises(pack.PackError):
            handoff.install(z, os.path.join(self.tmp.name, "i2"), self.work)


if __name__ == "__main__":
    unittest.main()
