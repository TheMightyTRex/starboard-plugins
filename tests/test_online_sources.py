"""Online sources (DASH-621, private draft): Openverse and Pexels results kept with their maker and licence, a saved file checked by what
it really is, a pack with a LICENCE.txt put in the hand-off folder, and the manifest Starboard checks. Nothing here reaches the
internet: Starboard's fetch is replaced by made-up answers."""
import base64
import json
import os
import sys
import unittest
import zipfile
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import load, manifest, starboard_cleaners  # noqa: E402

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 40
MP3 = b"ID3\x03" + b"0" * 40


def answer(obj):
    raw = json.dumps(obj).encode()
    return {"ok": True, "status": 200, "host": "x", "size": len(raw), "body_base64": base64.b64encode(raw).decode()}


OPENVERSE_IMAGES = {"results": [
    {"id": "abc-1", "title": "Rain on glass", "creator": "Sam Maker", "license": "by", "license_version": "4.0", "license_url": "https://creativecommons.org/licenses/by/4.0/",
     "foreign_landing_url": "https://example.org/rain", "url": "https://elsewhere.example/rain.jpg", "provider": "flickr"},
    {"id": "abc-2", "title": "Field", "creator": "Al", "license": "cc0", "license_version": "1.0", "license_url": "", "foreign_landing_url": "https://example.org/f", "url": ""}]}
OPENVERSE_AUDIO = {"results": [
    {"id": "au-1", "title": "Soft rain", "creator": "Rae", "license": "cc0", "license_version": "1.0", "license_url": "", "foreign_landing_url": "https://freesound.org/s/1",
     "url": "https://cdn.freesound.org/previews/1/1.mp3", "provider": "freesound"},
    {"id": "au-2", "title": "Other site", "creator": "Jo", "license": "by", "license_version": "4.0", "license_url": "", "foreign_landing_url": "https://example.org/a",
     "url": "https://not-listed.example/a.mp3", "provider": "x"}]}
PEXELS = {"photos": [{"id": 7, "alt": "City at night", "photographer": "Pat", "url": "https://www.pexels.com/photo/7/", "src": {"large2x": "https://images.pexels.com/photos/7/p.jpeg"}},
                     {"id": 8, "alt": "Bad host", "photographer": "Q", "url": "https://www.pexels.com/photo/8/", "src": {"large2x": "https://evil.example/p.jpeg"}}]}


class Online(unittest.TestCase):
    def setUp(self):
        self.m = load("online-sources", {"pexels_key": "PXKEY", "pack_name": "Rainy night"})
        self.addCleanup(self.m._tmp.cleanup)
        self.m.HANDOFF = os.path.join(self.m._tmp.name, "handoff")
        self.calls = []

    def fake(self, saved=None):
        def f(url, what, headers=None, save_as=None, max_bytes=None):
            self.calls.append((url, what, headers, save_as))
            if save_as:
                os.makedirs(self.m.INBOX, exist_ok=True)
                with open(os.path.join(self.m.INBOX, save_as), "wb") as fh:
                    fh.write(saved)
                return {"ok": True, "status": 200, "saved": save_as}
            if "api.pexels.com" in url:
                return answer(PEXELS)
            return answer(OPENVERSE_AUDIO if "/audio/" in url else OPENVERSE_IMAGES)
        return mock.patch.object(self.m, "starboard_fetch", side_effect=f)

    def test_search_keeps_maker_and_licence_and_uses_only_listed_sites(self):
        with self.fake():
            self.m.run_search("pictures", "rain")
        items = {i["id"]: i for i in self.m.result_items("pictures")[0]}
        self.assertEqual(set(items), {"ov-abc-1", "ov-abc-2", "px-7"})  # the Pexels photo on another host is dropped
        self.assertIn("Sam Maker, CC BY 4.0, Openverse", items["ov-abc-1"]["detail"])
        self.assertEqual(items["px-7"]["state_label"], "Free to use")
        for url, what, headers, _ in self.calls:
            self.assertRegex(url, r"^https://(api\.openverse\.org|api\.pexels\.com)/")
        self.assertNotIn("PXKEY", json.dumps([c[1] for c in self.calls]))  # a key never goes in the words saying what it is for
        self.assertIn("license_type=commercial", self.calls[0][0])
        self.m._set(show_all=True)
        self.calls.clear()
        with self.fake():
            self.m.run_search("pictures", "rain")
        self.assertNotIn("license_type", self.calls[0][0])

    def test_music_never_asks_jamendo_and_only_saves_from_listed_hosts(self):
        with self.fake():
            self.m.run_search("music", "rain")
        self.assertIn("source=freesound%2Cwikimedia_audio", self.calls[0][0])
        self.assertNotIn("jamendo", self.calls[0][0].lower())
        by = {i["id"]: i for i in self.m.result_items("music")[0]}
        self.assertIn("choice", by["ov-au-1"])
        self.assertNotIn("choice", by["ov-au-2"])
        self.assertIn("Starboard may not fetch it", by["ov-au-2"]["detail"])
        self.assertTrue(all(h in manifest("online-sources")["fetch"] for h in self.m.MUSIC_HOSTS))

    def test_a_short_search_and_a_missing_key_are_said_in_words(self):
        with self.assertRaises(ValueError):
            self.m.run_search("pictures", "a")
        self.m._set(pexels_key="", sources="pexels")
        with self.assertRaises(RuntimeError) as c:
            self.m.run_search("pictures", "rain")
        self.assertIn("free key", str(c.exception))

    def test_save_checks_what_the_file_is_and_one_background_for_each_place(self):
        with self.fake():
            self.m.run_search("pictures", "rain")
        with self.fake(JPEG):
            self.m.save_result("pictures", "px-7", "coming")
            self.m.save_result("pictures", "ov-abc-1", "coming")  # replaces the first
        items = self.m._read("items.json", [])
        self.assertEqual([(i["id"], i["slot"]) for i in items], [("ov-abc-1", "coming")])
        self.assertEqual(len(os.listdir(self.m.FILES)), 1)
        with self.fake(b"<html>not a picture</html>"):
            with self.assertRaises(ValueError):
                self.m.save_result("pictures", "px-7", "promo")
        self.assertEqual(len(self.m._read("items.json", [])), 1)
        self.assertEqual(os.listdir(self.m.INBOX), [])  # nothing half kept
        with self.assertRaises(ValueError):
            self.m.save_result("pictures", "ov-abc-1", "music")
        with self.assertRaises(ValueError):
            self.m.save_result("pictures", "nope", "promo")

    def test_the_pack_has_the_files_and_a_licence_that_says_where_each_came_from(self):
        with self.fake():
            self.m.run_search("pictures", "rain")
            self.m.run_search("music", "rain")
        with self.fake(JPEG):
            self.m.save_result("pictures", "px-7", "promo")
        with self.fake(MP3):
            self.m.save_result("music", "ov-au-1", "music")
        path, n = self.m.build_pack()
        self.assertEqual((n, os.path.dirname(path)), (2, self.m.HANDOFF))
        self.assertEqual([f for f in os.listdir(self.m.HANDOFF) if f.startswith(".")], [])
        with zipfile.ZipFile(path) as z:
            names = sorted(z.namelist())
            self.assertEqual(names[0:2], ["LICENCE.txt", "pack.json"])
            self.assertTrue(any(x.startswith("promo/background.") for x in names) and any(x.startswith("promo/music/") for x in names))
            self.assertEqual(json.loads(z.read("pack.json"))["name"], "Rainy night")
            text = z.read("LICENCE.txt").decode()
        for want in ("Made by: Pat", "Made by: Rae", "Pexels licence", "CC0 (public domain)", "https://freesound.org/s/1", "sha256"):
            self.assertIn(want, text)
        self.assertNotIn("PXKEY", text)
        self.assertNotRegex(text.lower(), r"\bai\b|made with an ai")  # David, 28 November 2026: no AI label line
        self.m.remove_item("px-7")
        self.assertEqual(len(self.m._read("items.json", [])), 1)
        self.assertEqual(len(os.listdir(self.m.FILES)), 1)

    def test_the_style_library_lists_only_mit_packs_with_credits_and_checks_the_checksum(self):
        import hashlib
        import io
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("pack.json", '{"pack":1,"name":"Sample"}')
        zdata = buf.getvalue()
        good = {"id": "sample-one", "kind": "pack", "name": "Sample one", "maker": "Sam", "licence": "MIT", "credits": "Sam made all of it", "preview": "previews/sample-one.png",
                "file": "packs/sample-one.zip", "size": len(zdata), "sha256": hashlib.sha256(zdata).hexdigest()}
        index = {"styles": [good, {**good, "id": "cc-by", "licence": "CC BY 4.0"}, {**good, "id": "no-credits", "credits": ""}, {**good, "id": "Bad Id"},
                            {**good, "id": "huge", "size": 10 ** 9}, {**good, "id": "bad-sum", "sha256": "z"},
                            {"id": "some-lottie", "kind": "link", "name": "A Lottie", "maker": "Lee", "licence": "MIT", "credits": "Lee", "link": "https://example.org/lee"},
                            {"id": "http-link", "kind": "link", "name": "x", "maker": "y", "licence": "MIT", "credits": "y", "link": "http://example.org"}]}
        self.assertEqual([s["id"] for s in self.m.clean_index(index)], ["sample-one", "some-lottie"])
        with mock.patch.object(self.m, "starboard_fetch", return_value=answer(index)) as f:
            self.m.refresh_library()
        self.assertIn("raw.githubusercontent.com", f.call_args[0][0])
        page = self.m.styles_page()
        self.assertEqual([r["state_label"] for r in page["items"]], ["MIT licence", "Link only"])
        self.assertIn("This page is for a computer screen", page["notices"][0]["title"])

        def served(data):
            def f(url, what, headers=None, save_as=None, max_bytes=None):
                os.makedirs(self.m.INBOX, exist_ok=True)
                with open(os.path.join(self.m.INBOX, save_as), "wb") as fh:
                    fh.write(data)
                return {"ok": True, "status": 200}
            return mock.patch.object(self.m, "starboard_fetch", side_effect=f)
        with served(zdata):
            self.m.use_style("sample-one")
        self.assertTrue(os.path.exists(os.path.join(self.m.HANDOFF, "style-sample-one.zip")))
        os.unlink(os.path.join(self.m.HANDOFF, "style-sample-one.zip"))
        with served(zdata + b"x"):  # not what was read and listed
            with self.assertRaises(ValueError):
                self.m.use_style("sample-one")
        self.assertFalse(os.path.exists(os.path.join(self.m.HANDOFF, "style-sample-one.zip")))
        self.assertEqual(os.listdir(self.m.INBOX), [])
        with self.assertRaises(ValueError):
            self.m.use_style("some-lottie")  # a link is never fetched

    def test_sharing_makes_a_zip_and_an_index_entry_and_posts_nothing(self):
        with self.fake():
            self.m.run_search("pictures", "rain")
        with self.fake(JPEG):
            self.m.save_result("pictures", "px-7", "promo")
        said = self.m.share_action()["said"]
        self.assertIn("unknown source", said)
        share = os.path.join(self.m._data, "share")
        self.assertEqual(sorted(os.listdir(share)), ["index-entry.json", "online-sources-Rainy-night.zip"])
        self.assertFalse(os.path.exists(self.m.HANDOFF) and os.listdir(self.m.HANDOFF))  # not offered to the TV channel plug-in
        entry = json.load(open(os.path.join(share, "index-entry.json")))
        self.assertEqual((entry["licence"], entry["kind"]), ("MIT", "pack"))

    def test_the_ai_page_is_names_and_links_only(self):
        page = self.m.ai_page()
        self.assertGreater(len(page["items"]), 10)
        self.assertTrue(all(i["link"]["url"].startswith("https://") and i["state_label"] == "Link only" for i in page["items"]))
        self.assertEqual({i["group"] for i in page["items"]}, {"Online tools", "Programs on your own computer"})
        self.assertIn("computer screen", page["notices"][0]["title"])
        text = open(os.path.join(os.path.dirname(__file__), "..", "online-sources", "ai-sources.json")).read().lower()
        self.assertNotIn("made with an ai tool", text)
        self.assertNotIn("\"template\"", text)  # the prompts themselves belong on the TV channel plug-in's page

    def test_nothing_to_send_is_said(self):
        with self.assertRaises(ValueError):
            self.m.build_pack()

    def test_pages_are_in_starboards_shape(self):
        cleaners = starboard_cleaners()
        if not cleaners:
            self.skipTest("Starboard's source is not here")
        _, custom = cleaners
        with self.fake():
            self.m.run_search("pictures", "rain")
        self.assertTrue(self.m.result_items("pictures")[0])
        for page in (self.m.find_page("pictures"), self.m.find_page("music"), self.m.pack_page()):
            got = custom.clean(page)
            self.assertEqual(len(got["items"]), len(page["items"]))
            self.assertEqual(got.get("add"), page.get("add") and got.get("add"))

    def test_the_manifest_passes_starboards_check(self):
        m = manifest("online-sources")
        self.assertEqual(m["permissions"], ["fetch", "handoff:send"])
        self.assertEqual(m["containers"][0]["network"], "default")  # no way out of its own
        self.assertNotIn("jamendo", json.dumps(m).lower())
        self.assertNotIn("canva", json.dumps(m).lower())
        src = os.environ.get("STARBOARD_SRC", os.path.expanduser("~/src/starboard"))
        sys.path.insert(0, src)
        try:
            from starboard import plugins
            if tuple(map(int, plugins.API_VERSION.split("."))) < (1, 25, 0):
                self.skipTest("this Starboard is older than plug-in API 1.25")
            self.assertEqual(plugins.check(m), [])
        finally:
            sys.path.pop(0)


if __name__ == "__main__":
    unittest.main()
