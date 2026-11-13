"""Audio description (DASH-399): track and release name patterns, the library check a page at a time, the Reelix format
and its scores, people's remembered sound tracks, and answers Starboard accepts. Run: python3 -m unittest discover -s tests
(STARBOARD_SRC points at Starboard's source for its own checks; they are skipped without it)."""
import importlib.util
import json
import os
import re
import sys
import tempfile
import unittest
import urllib.error

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PID = "audio-description"
STARBOARD_SRC = os.environ.get("STARBOARD_SRC", os.path.expanduser("~/src/starboard"))


def load(values=None):
    """app.py as a module, with its own settings and /data in a temporary folder, without serving."""
    tmp = tempfile.mkdtemp(prefix="sb-ad-test-")
    run, data = os.path.join(tmp, "run"), os.path.join(tmp, "data")
    os.makedirs(run)
    os.makedirs(data)
    with open(os.path.join(run, "settings.json"), "w") as f:
        json.dump(values or {}, f)
    for name, body in (("jellyfin.json", {"url": "http://jellyfin.invalid:8096", "api_key": "jf"}),
                       ("reelix.json", {"url": "http://reelix.invalid:7878", "api_key": "rx"})):
        with open(os.path.join(run, name), "w") as f:
            json.dump(body, f)
    os.environ["PLUGIN_RUN"], os.environ["PLUGIN_DATA"] = run, data
    sys.path.insert(0, os.path.join(ROOT, "_shared"))
    for name in ("sbplugin", "app_audio_description"):
        sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location("app_audio_description", os.path.join(ROOT, PID, "app.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sys.path.pop(0)
    return mod


def manifest():
    with open(os.path.join(ROOT, PID, "starboard-plugin.json"), encoding="utf-8") as f:
        return json.load(f)


def audio(title="", display="", comment=""):
    return {"Type": "Audio", "Index": 1, "Title": title, "DisplayTitle": display, "Comment": comment}


class TrackNames(unittest.TestCase):
    def setUp(self):
        self.app = load()

    def test_described_tracks_are_found(self):
        for t in ("English (Audio Description)", "AD", "English AD", "[AD] English", "Descriptive Audio", "Described Video",
                  "Audio described", "DVS", "eng.AD"):
            with self.subTest(t):
                self.assertIsNotNone(self.app.described_track([audio(t)]))

    def test_other_tracks_are_not(self):
        for t in ("English - AAC - Stereo - Default", "Director's commentary", "AD commentary", "Adventure mix", "Dolby Digital 5.1",
                  "Madrid", "Head"):
            with self.subTest(t):
                self.assertIsNone(self.app.described_track([audio(t)]))

    def test_only_audio_streams_count(self):
        self.assertIsNone(self.app.described_track([{"Type": "Subtitle", "Title": "English (Audio Description)"}]))

    def test_display_title_is_kept_for_the_list(self):
        got = self.app.described_track([audio("", "English (Audio Description) - AAC - Stereo")])
        self.assertEqual(got["name"], "English (Audio Description) - AAC - Stereo")


class ReleaseNames(unittest.TestCase):
    def setUp(self):
        self.re = re.compile(load().RELEASE_AD)

    def test_described_releases_match(self):
        for n in ("Slow.Horses.S01E01.1080p.WEB-DL.WiTH.AD.DD5.1-GRP", "Film.2023.1080p.BluRay.ENG.AD.x264", "Film.2023.BSL.and.AD.WEB",
                  "Film.2023.Audio.Description.1080p", "Film 2023 AudioDescription", "Film.2023.DVS.720p", "Film.2023.MULTi.AD.1080p",
                  "Film.2023.Descriptive.Audio.WEB"):
            with self.subTest(n):
                self.assertTrue(self.re.search(n))

    def test_others_do_not(self):
        for n in ("Ad.Astra.2019.1080p.BluRay", "A.D.The.Bible.Continues.S01E01", "Mad.Max.2015.1080p", "Film.2023.1080p.AD.x264",
                  "Advert.Breaks.2020", "Film.2023.ADVENTURE.Cut"):
            with self.subTest(n):
                self.assertFalse(self.re.search(n))

    def test_reelix_can_read_it(self):
        # Reelix uses Rust's regex crate: no look-around and no back references.
        for bad in ("(?=", "(?!", "(?<=", "(?<!", "\\1"):
            self.assertNotIn(bad, load().RELEASE_AD)


class Library(unittest.TestCase):
    def test_reads_page_by_page_and_counts_series_together(self):
        app = load()
        app.PAGE = 2
        pages = [[{"Type": "Movie", "Id": "m1", "Name": "Dune", "ProductionYear": 2021, "MediaStreams": [audio("English"), audio("English (AD)")]},
                  {"Type": "Movie", "Id": "m2", "Name": "Brazil", "ProductionYear": 1985, "MediaStreams": [audio("English")]}],
                 [{"Type": "Episode", "SeriesName": "Slow Horses", "MediaStreams": [audio("Audio Description")]},
                  {"Type": "Episode", "SeriesName": "Slow Horses", "MediaStreams": [audio("English")]}],
                 [{"Type": "Episode", "SeriesName": "Taskmaster", "MediaStreams": [audio("English")]}]]
        asked = []

        def jf(path, data=None, method=None):
            asked.append(path)
            start = int(re.search(r"StartIndex=(\d+)", path).group(1))
            self.assertIn("Fields=MediaStreams", path)
            self.assertIn("Limit=2", path)
            return {"Items": pages[start // 2], "TotalRecordCount": 5}
        app.jellyfin = jf
        said = app.scan()["said"]
        self.assertEqual(len(asked), 3)
        self.assertIn("1 film and 1 series", said)
        r = app.remember("result")
        self.assertEqual([f["name"] for f in r["films"]], ["Dune (2021)"])
        self.assertEqual(r["series"], [{"name": "Slow Horses", "described": 1, "episodes": 2, "track": "Audio Description"}])
        self.assertEqual(app.count()["value"], 2)
        self.assertEqual(app.recent()["items"][0]["title"] in ("Dune (2021)", "Slow Horses"), True)
        screen = app.titles()
        self.assertEqual([i["group"] for i in screen["items"]], ["Films", "Series"])
        self.assertEqual(screen["items"][1]["state"], "warning")  # not every episode is described

    def test_before_the_first_check(self):
        app = load()
        self.assertIn("Not checked yet", app.count()["note"])
        self.assertIn("Not checked yet", app.titles()["intro"])
        self.assertEqual(app.recent()["items"][0]["title"], "None found yet")


class AudioVault(unittest.TestCase):
    """DASH-410: a link to AudioVault's own search for each title without audio description; AudioVault is never called."""

    def scanned(self, app, films=(), series=()):
        pages = [list(films) + list(series)]
        app.jellyfin = lambda path, data=None, method=None: {"Items": pages[0], "TotalRecordCount": len(pages[0])}
        app.scan()

    def test_deactivated_until_chosen(self):
        app = load()
        out = app.audiovault()
        self.assertEqual(out["items"], [])
        self.assertIn("Activate it under Sources", out["intro"])
        self.assertFalse(manifest()["settings"][[s["key"] for s in manifest()["settings"]].index("audiovault_links")]["default"])

    def test_links_for_titles_without_a_described_track(self):
        app = load({"audiovault_links": True})
        self.scanned(app, [{"Type": "Movie", "Name": "Dune", "ProductionYear": 2021, "MediaStreams": [audio("English (AD)")]},
                           {"Type": "Movie", "Name": "Amélie & Nino", "ProductionYear": 2001, "MediaStreams": [audio("French")]}],
                     [{"Type": "Episode", "SeriesName": "Slow Horses", "MediaStreams": [audio("AD")]},
                      {"Type": "Episode", "SeriesName": "Slow Horses", "MediaStreams": [audio("English")]}])
        out = app.audiovault()
        films = [i for i in out["items"] if i["group"] == "Films"]
        self.assertEqual([i["title"] for i in films], ["Amélie & Nino (2001)"])  # Dune has one already
        self.assertEqual(films[0]["link"], {"url": "https://audiovault.net/movies?search=Am%C3%A9lie%20%26%20Nino",
                                            "label": "Search AudioVault for Amélie & Nino (2001)"})
        series = [i for i in out["items"] if i["group"] == "Series"]
        self.assertEqual(series[0]["link"]["url"], "https://audiovault.net/shows?search=Slow%20Horses")
        self.assertEqual(series[0]["state_label"], "1 of 2 described")
        self.assertEqual([m["id"] for m in out["menus"]], ["films", "series"])
        self.assertLessEqual(len(out["intro"]), 400)

    def test_a_long_list_opens_by_first_letter(self):
        app = load({"audiovault_links": True})
        names = [f"{c}{i}" for c in "ABC" for i in range(40)] + ["The Zebra", "42"]
        self.scanned(app, [{"Type": "Movie", "Name": n, "MediaStreams": []} for n in names])
        out = app.audiovault()
        letters = [m["title"] for m in out["menus"] if m.get("parent") == "films"]
        self.assertEqual(letters, ["A", "B", "C", "Z", "0 to 9 and others"])
        self.assertTrue(all(i.get("menu") for i in out["items"]))


class YouDescribe(unittest.TestCase):
    """DASH-410: YouDescribe offers no interface for other apps, so each title is a link to its own search."""

    def test_every_title_links_to_its_search(self):
        app = load()
        pages = [[{"Type": "Movie", "Name": "Dune", "ProductionYear": 2021, "MediaStreams": [audio("English (AD)")]},
                  {"Type": "Movie", "Name": "Brazil", "ProductionYear": 1985, "MediaStreams": [audio("English")]},
                  {"Type": "Episode", "SeriesName": "Slow Horses", "MediaStreams": [audio("AD")]},
                  {"Type": "Episode", "SeriesName": "Slow Horses", "MediaStreams": [audio("English")]},
                  {"Type": "Episode", "SeriesName": "Bluey", "MediaStreams": [audio("AD")]}]]
        app.jellyfin = lambda path, data=None, method=None: {"Items": pages[0], "TotalRecordCount": 5}
        app.scan()
        out = app.youdescribe()
        got = [(i["group"], i["title"], i["state_label"], i["link"]["url"]) for i in out["items"]]
        self.assertEqual(got, [("Films", "Brazil (1985)", "No description here", "https://youdescribe.org/search?q=Brazil"),
                               ("Films", "Dune (2021)", "Described here", "https://youdescribe.org/search?q=Dune"),
                               ("Series", "Bluey", "Described here", "https://youdescribe.org/search?q=Bluey"),
                               ("Series", "Slow Horses", "No description here", "https://youdescribe.org/search?q=Slow%20Horses")])
        self.assertLessEqual(len(out["intro"]), 400)

    def test_can_be_deactivated(self):
        app = load({"youdescribe_links": False})
        self.assertEqual(app.youdescribe()["items"], [])


class Apps(unittest.TestCase):
    """DASH-410: MovieReading and Earcatch publish no list of titles that may be read, so a guide and links only."""

    def test_a_guide_with_store_links_and_nothing_fetched(self):
        app = load()
        app.jellyfin = app.reelix = lambda *a, **k: self.fail("nothing is fetched")
        out = app.apps()
        groups = []
        for i in out["items"]:
            if i["group"] not in groups:
                groups.append(i["group"])
        self.assertEqual(groups, ["MovieReading", "Earcatch", "Using one with Jellyfin"])
        links = {i["link"]["label"]: i["link"]["url"] for i in out["items"] if "link" in i}
        self.assertEqual(links["MovieReading on the App Store"], "https://apps.apple.com/app/id460349347")
        self.assertEqual(links["Earcatch on Google Play"], "https://play.google.com/store/apps/details?id=nl.q42.soundfocus")
        self.assertEqual([i["state_label"] for i in out["items"] if i["group"] == "Using one with Jellyfin"],
                         ["Step 1", "Step 2", "Step 3", "Step 4", "Step 5"])
        self.assertTrue(all(len(i["detail"]) <= 200 for i in out["items"]))
        self.assertLessEqual(len(out["intro"]), 400)

    def test_can_be_deactivated(self):
        self.assertEqual(load({"apps_guide": False}).apps()["items"], [])


class FakeReelix:
    def __init__(self, formats=None, profiles=None):
        self.formats = formats if formats is not None else []
        self.profiles = profiles if profiles is not None else [
            {"id": 1, "name": "HD-1080p", "family": "video", "format_items": [{"format_id": 7, "score": -10000}]},
            {"id": 2, "name": "Ultra-HD", "family": "video", "format_items": []},
            {"id": 3, "name": "Audiobooks", "family": "audio", "format_items": []}]
        self.calls = []

    def __call__(self, path, data=None, method=None):
        self.calls.append((method or "GET", path))
        if path == "/customformats" and method == "POST":
            made = {**data, "id": 9}
            self.formats.append(made)
            return made
        if path == "/customformats":
            return self.formats
        if path == "/qualityprofiles":
            return self.profiles
        if path.startswith("/qualityprofiles/") and method == "PUT":
            pid = int(path.rsplit("/", 1)[1])
            self.profiles = [data if p["id"] == pid else p for p in self.profiles]
            return data
        raise AssertionError(path)


class Reelix(unittest.TestCase):
    def test_adds_the_format_and_prefers_it_in_video_levels_only(self):
        app = load({"prefer_in_reelix": True})
        rx = FakeReelix()
        app.reelix = rx
        said = app.apply_reelix()["said"]
        self.assertIn("2 quality levels", said)
        self.assertEqual(rx.formats[0]["name"], "Audio description")
        self.assertEqual(rx.formats[0]["specifications"][0]["type"], "release_title")
        self.assertEqual({p["id"]: p["format_items"] for p in rx.profiles}[1], [{"format_id": 7, "score": -10000}, {"format_id": 9, "score": 100}])
        self.assertNotIn(("PUT", "/qualityprofiles/3"), rx.calls)
        rx.calls.clear()
        app.apply_reelix()  # again: nothing to change, nothing written
        self.assertFalse([c for c in rx.calls if c[0] != "GET"])

    def test_a_score_someone_set_is_kept(self):
        app = load()
        rx = FakeReelix(formats=[{"id": 9, "name": "Audio Description"}],
                        profiles=[{"id": 1, "family": "video", "format_items": [{"format_id": 9, "score": 500}]}])
        app.reelix = rx
        app.apply_reelix()
        self.assertEqual(rx.profiles[0]["format_items"], [{"format_id": 9, "score": 500}])
        self.assertFalse([c for c in rx.calls if c[0] != "GET"])

    def test_deactivated_puts_scores_back_to_neutral_and_adds_nothing(self):
        app = load({"prefer_in_reelix": False})
        rx = FakeReelix(formats=[{"id": 9, "name": "Audio description"}],
                        profiles=[{"id": 1, "family": "video", "format_items": [{"format_id": 9, "score": 100}, {"format_id": 7, "score": 5}]}])
        app.reelix = rx
        self.assertIn("no longer prefers", app.apply_reelix()["said"])
        self.assertEqual(rx.profiles[0]["format_items"], [{"format_id": 7, "score": 5}])
        empty = FakeReelix()
        app.reelix = empty
        app.apply_reelix()
        self.assertEqual(empty.formats, [])


class People(unittest.TestCase):
    def setUp(self):
        self.app = load()
        self.configs = {"u1": {"RememberAudioSelections": False, "AudioLanguagePreference": "eng"}, "u2": {}}
        self.saved = []

        def jf(path, data=None, method=None):
            if path == "/Users":
                return [{"Id": "u1", "Name": "Sam"}, {"Id": "u2", "Name": "Alex"}]
            m = re.match(r"^/Users/(u\d)$", path)
            if m:
                return {"Configuration": self.configs[m.group(1)]}
            m = re.match(r"^/Users/Configuration\?userId=(u\d)$", path)
            if m and method == "POST":
                self.saved.append((m.group(1), data))
                self.configs[m.group(1)] = data
                return None
            raise AssertionError(path)
        self.app.jellyfin = jf

    def test_activating_remembers_tracks_and_deactivating_puts_back(self):
        screen = self.app.people()
        self.assertEqual([(i["title"], i["on"]) for i in screen["items"]], [("Sam", False), ("Alex", False)])
        got = self.app.people({"action": "toggle", "id": "u1"})
        self.assertEqual(got["said"], "Audio description activated for Sam")
        self.assertTrue(self.configs["u1"]["RememberAudioSelections"])
        self.assertEqual(self.configs["u1"]["AudioLanguagePreference"], "eng")  # the rest is kept
        self.assertTrue(next(i for i in got["items"] if i["id"] == "u1")["on"])
        got = self.app.people({"action": "toggle", "id": "u1"})
        self.assertEqual(got["said"], "Audio description deactivated for Sam")
        self.assertFalse(self.configs["u1"]["RememberAudioSelections"])

    def test_older_jellyfin_address(self):
        calls = []
        old = self.app.jellyfin

        def jf(path, data=None, method=None):
            if path.startswith("/Users/Configuration"):
                raise urllib.error.HTTPError(path, 404, "Not found", {}, None)
            if path == "/Users/u2/Configuration":
                calls.append(data)
                return None
            return old(path, data, method)
        self.app.jellyfin = jf
        self.app.people({"action": "toggle", "id": "u2"})
        self.assertTrue(calls[0]["RememberAudioSelections"])

    def test_someone_not_in_jellyfin(self):
        with self.assertRaises(ValueError):
            self.app.people({"action": "toggle", "id": "u9"})


class Words(unittest.TestCase):
    def test_no_em_dashes_or_contractions_in_what_people_read(self):
        app = load()
        m = manifest()
        text = json.dumps([m, app.ELSEWHERE, app.elsewhere(), app.titles(), app.count(), app.recent(), app.audiovault()], ensure_ascii=False)
        app._set_on = load({"audiovault_links": True})
        text += json.dumps([app._set_on.audiovault(), app.youdescribe(), app.apps()], ensure_ascii=False)
        with open(os.path.join(ROOT, PID, "README.md"), encoding="utf-8") as f:
            text += f.read()
        self.assertNotIn("—", text)
        self.assertFalse(re.search(r"\b\w+n't\b|\b(?:it|that|there|you|we)'(?:s|re|ll|ve|d)\b", text, re.I))


@unittest.skipUnless(os.path.isdir(os.path.join(STARBOARD_SRC, "starboard")), "Starboard's source is not here")
class StarboardAccepts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, STARBOARD_SRC)
        from starboard import plugin_cards, plugin_custom, plugin_tester, plugins
        cls.cards, cls.custom, cls.tester, cls.plugins = plugin_cards, plugin_custom, plugin_tester, plugins

    def test_manifest_passes_in_development_and_accessibility(self):
        m = manifest()
        self.assertEqual(self.plugins.check(m, dev=True), [])
        report = self.tester.report(m, dev=True)
        self.assertTrue(report["accessibility"]["passed"])
        self.assertEqual(report["errors"], 0)
        self.assertEqual(m["containers"][0]["start"], "when_needed")  # rests between uses

    def test_answers_have_the_shapes_starboard_draws(self):
        app = load()
        app.keep("result", {"at": 1794600000, "total": 3, "films": [{"id": "m1", "name": "Dune (2021)", "track": "English (AD)"}],
                            "series": [{"name": "Slow Horses", "described": 2, "episodes": 2, "track": "AD"}]})
        self.cards.clean("stat", app.count())
        self.cards.clean("list", app.recent())
        for screen in (app.titles(), app.elsewhere()):
            self.assertTrue(self.custom.clean(screen)["items"])
        self.assertTrue(all(i["link"]["url"].startswith("https://") for i in self.custom.clean(app.elsewhere())["items"]))
        self.custom.clean(app.audiovault())
        self.custom.clean(app.youdescribe())
        self.assertTrue(all(i["state_label"] for i in self.custom.clean(app.apps())["items"]))
        m = manifest()
        for c in m["cards"]:
            self.cards.clean(c["type"], c["example"])


if __name__ == "__main__":
    unittest.main()
