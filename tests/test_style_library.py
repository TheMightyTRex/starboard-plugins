"""The style library (DASH-622): empty until the owner has read a style; only MIT, credits, checksums."""
import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import check_style_library as c  # noqa: E402


class Library(unittest.TestCase):
    def test_the_real_index_is_fine_and_empty(self):
        self.assertEqual(c.problems(), [])
        self.assertEqual(json.load(open(c.ROOT + "/index.json"))["styles"], [])

    def make(self, **change):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        os.makedirs(d + "/packs")
        os.makedirs(d + "/previews")
        with zipfile.ZipFile(d + "/packs/one.zip", "w") as z:
            z.writestr("pack.json", "{}")
            z.writestr("LICENCE.txt", "MIT, by Sam")
        open(d + "/previews/one.png", "wb").write(b"x")
        data = open(d + "/packs/one.zip", "rb").read()
        s = {"id": "one", "kind": "pack", "name": "One", "maker": "Sam", "licence": "MIT", "credits": "Sam", "file": "packs/one.zip", "preview": "previews/one.png",
             "size": len(data), "sha256": hashlib.sha256(data).hexdigest(), "reviewed": {"by": "owner", "on": "2026-11-30"}, **change}
        json.dump({"styles": [s]}, open(d + "/index.json", "w"))
        return d

    def test_a_good_entry(self):
        self.assertEqual(c.problems(self.make()), [])

    def test_what_is_refused(self):
        for change, word in (({"licence": "CC BY 4.0"}, "MIT"), ({"credits": ""}, "credits"), ({"sha256": "0" * 64}, "sha256"), ({"size": 5}, "size"),
                             ({"reviewed": None}, "not been read"), ({"file": "../x.zip"}, "zip"), ({"preview": "x.png"}, "preview"), ({"id": "Bad Id"}, "id")):
            self.assertTrue(any(word in p for p in c.problems(self.make(**change))), change)

    def test_a_link_is_never_hosted(self):
        self.assertEqual(c.problems(self.make(kind="link", link="https://example.org/a", file=None)) and [], [])
        self.assertTrue(c.problems(self.make(kind="link", link="https://example.org/a")))
        self.assertTrue(c.problems(self.make(kind="link", link="http://example.org/a", file=None)))


if __name__ == "__main__":
    unittest.main()
