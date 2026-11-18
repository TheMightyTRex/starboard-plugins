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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import as_published  # noqa: E402
import urllib.error
import urllib.parse

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
            if "IncludeItemTypes=Movie" not in path:  # the plug-in list, series and collections: none here
                return [] if path == "/Plugins" else {"Items": [], "TotalRecordCount": 0}
            asked.append(path)
            start = int(re.search(r"StartIndex=(\d+)", path).group(1))
            self.assertIn("Fields=MediaStreams", path)
            self.assertIn("CollapseBoxSetItems=false", path)  # films in the collection are still read one by one
            self.assertIn("Limit=2", path)
            return {"Items": pages[start // 2], "TotalRecordCount": 5}
        app.jellyfin = jf
        app.set_tag = lambda iid, want: None
        said = app.scan()["said"]
        self.assertEqual(len(asked), 3)
        self.assertIn("1 film and 1 series", said)
        r = app.remember("result")
        self.assertEqual([f["name"] for f in r["films"]], ["Dune (2021)"])
        self.assertEqual(r["films"][0], {"id": "m1", "name": "Dune (2021)", "title": "Dune", "year": 2021, "track": "English (AD)"})
        self.assertEqual(r["series"], [{"name": "Slow Horses", "described": 1, "episodes": 2, "track": "Audio Description", "id": "", "year": 0,
                                        "items": [{"id": "", "season": None, "episode": None, "name": "", "track": "Audio Description"}]}])
        self.assertEqual(app.count()["value"], 2)
        self.assertEqual(app.recent()["items"][0]["title"] in ("Dune (2021)", "Slow Horses"), True)
        screen = app.titles()
        self.assertEqual([(i["menu"], i["state_label"]) for i in screen["items"]], [("films", "Described"), ("series:Slow Horses", "Described")])
        self.assertEqual(screen["menus"][2]["detail"], "1 of 2 episodes described. Described track: Audio Description")  # not every episode

    def test_before_the_first_check(self):
        app = load()
        self.assertIn("Not checked yet", app.count()["note"])
        self.assertIn("Not checked yet", app.titles()["intro"])
        self.assertEqual(app.recent()["items"][0]["title"], "None found yet")


class TitlesPage(unittest.TestCase):
    """Titles with audio description (17 November 2026): every film and every described episode by series, with its
    year, track and status in words, Films and Series with their counts, and a link to each in Jellyfin. The same
    page, columns and words as the Jellyfin version's."""

    def scanned(self, app):
        films = [{"Type": "Movie", "Id": "f1", "Name": "Harbour Lights", "ProductionYear": 2019,
                  "MediaStreams": [audio("English"), audio("Audio Description", "English (Audio Description)")]},
                 {"Type": "Movie", "Id": "f2", "Name": "Copper Sky", "ProductionYear": 2021, "MediaStreams": [audio("English")]}]
        eps = [{"Type": "Episode", "Id": f"e{n}", "SeriesId": "s1", "SeriesName": "Quiet Valley", "ParentIndexNumber": 1, "IndexNumber": n,
                "Name": f"Part {n}", "MediaStreams": [audio("English (Described)")] if n != 2 else [audio("English")]} for n in (3, 1, 2)]
        everything = films + eps

        def jf(path, data=None, method=None):
            if path == "/Plugins":
                return []
            if "IncludeItemTypes=Series" in path:
                return {"Items": [{"Id": "s1", "Name": "Quiet Valley", "ProductionYear": 2023, "Tags": []}], "TotalRecordCount": 1}
            if "IncludeItemTypes=Movie" in path:
                return {"Items": everything, "TotalRecordCount": len(everything)}
            return {"Items": [], "TotalRecordCount": 0}
        app.jellyfin = jf
        app.set_tag = lambda iid, want: None
        app.scan()

    def test_films_and_series_with_their_counts_and_links(self):
        app = load({"jellyfin_address": "http://192.168.1.10:8096/"})
        self.scanned(app)
        screen = app.titles()
        self.assertEqual(screen["title"], "Titles with audio description")
        self.assertEqual([(m["id"], m["title"], m.get("detail")) for m in screen["menus"]],
                         [("films", "Films", None), ("series", "Series", "1 series"),
                          ("series:s1", "Quiet Valley (2023)", "2 of 3 episodes described. Described track: English (Described)")])
        film, *eps = screen["items"]
        self.assertEqual((film["title"], film["detail"], film["state_label"]), ("Harbour Lights (2019)", "Described track: English (Audio Description)", "Described"))
        self.assertEqual(film["link"], {"url": "http://192.168.1.10:8096/web/#/details?id=f1", "label": "Open Harbour Lights (2019) in Jellyfin"})
        self.assertEqual([e["title"] for e in eps], ["S1 E1: Part 1", "S1 E3: Part 3"])  # in order, only the described ones
        self.assertEqual(eps[0]["link"]["label"], "Open Quiet Valley S1 E1: Part 1 in Jellyfin")
        self.assertIn("1 film and 2 episodes in 1 series have a described sound track", screen["intro"])
        self.assertIn("opens its page in Jellyfin", screen["intro"])

    def test_no_link_where_a_browser_cannot_open_jellyfin(self):
        app = load()
        with open(os.path.join(os.environ["PLUGIN_RUN"], "jellyfin.json"), "w") as f:
            json.dump({"url": "http://host.docker.internal:8096", "api_key": "jf"}, f)
        self.scanned(app)
        screen = app.titles()
        self.assertFalse(any("link" in i for i in screen["items"]))
        self.assertIn("Jellyfin address for links", screen["intro"])
        app2 = load()  # Starboard's own address works when a browser can open it
        self.assertEqual(app2.jellyfin_page_base(), "http://jellyfin.invalid:8096")

    def test_every_episode_described_and_a_result_from_before(self):
        app = load()
        self.assertEqual(app.series_words({"described": 4, "episodes": 4}), "All 4 episodes described")
        self.assertEqual(app.series_words({"described": 1, "episodes": 1}), "1 of 1 episode described")
        self.assertEqual(app.episode_words({"season": None, "episode": None, "name": "Special"}), "Special")
        app.keep("result", {"at": 1794600000, "total": 3, "films": [{"name": "Dune (2021)", "track": "AD"}],
                            "series": [{"name": "Slow Horses", "described": 2, "episodes": 2, "track": "AD"}]})
        screen = app.titles()  # kept by 1.3.0: no ids, years or episodes yet
        self.assertEqual(screen["items"][0]["title"], "Dune (2021)")
        self.assertNotIn("link", screen["items"][0])
        self.assertIn("Check for described titles now", screen["intro"])

    def test_a_long_list_of_series_opens_by_first_letter(self):
        app = load()
        app.SERIES_MENUS_MAX = 2
        app.keep("result", {"at": 1794600000, "total": 9, "films": [], "series": [
            {"name": n, "id": n, "year": 0, "described": 1, "episodes": 1, "track": "AD",
             "items": [{"id": n + "1", "season": 1, "episode": 1, "name": "One", "track": "AD"}]} for n in ("Alpha", "Bravo", "Beta")]})
        screen = app.titles()
        self.assertEqual([m["title"] for m in screen["menus"][2:]], ["A", "B"])
        self.assertEqual([i["group"] for i in screen["items"]], ["Alpha", "Bravo", "Beta"])


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
        self.assertIn("Activate it under 'Sources'", out["intro"])
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
    """Reelix with a manager key: it may read formats and quality levels, and refuses every write with 403 (issue #144)."""

    def __init__(self, builtin=True, formats=None, profiles=None, profiles_403=False):
        self.builtin, self.formats, self.profiles_403 = builtin, formats if formats is not None else [], profiles_403
        self.profiles = profiles if profiles is not None else [
            {"id": 1, "name": "HD-1080p", "family": "video", "format_items": [{"format_id": 7, "score": -10000}]},
            {"id": 2, "name": "Ultra-HD", "family": "video", "format_items": []},
            {"id": 3, "name": "Audiobooks", "family": "audio", "format_items": [{"format_id": 9, "score": 100}]}]
        self.calls = []

    def __call__(self, path, data=None, method=None):
        self.calls.append((method or "GET", path))
        if method in ("POST", "PUT", "DELETE"):
            raise urllib.error.HTTPError(path, 403, "Forbidden", {}, None)
        if path == "/customformats/builtin/audio_description":
            if self.builtin:
                return {"id": 9, "name": "Audio description"}
            raise urllib.error.HTTPError(path, 404, "No API route", {}, None)
        if path == "/customformats":
            return self.formats
        if path == "/qualityprofiles":
            if self.profiles_403:
                raise urllib.error.HTTPError(path, 403, "Forbidden", {}, None)
            return self.profiles
        raise AssertionError(path)


class Reelix(unittest.TestCase):
    """Issue #144: Reelix lets only an admin key write formats and quality levels, so the plug-in only reads and says
    where the choice is made, and the job never fails for this."""

    def run_with(self, rx, values=None):
        app = load(values)
        app.reelix = rx
        said = app.apply_reelix()["said"]
        self.assertFalse([c for c in rx.calls if c[0] != "GET"])  # never a POST or a PUT
        return said

    def test_no_level_prefers_it_yet_so_it_says_where_to_choose_prefer(self):
        said = self.run_with(FakeReelix())
        self.assertEqual(said, "To prefer releases with audio description, set Audio description to Prefer in Settings, Reelix, Picture quality")

    def test_it_counts_the_video_levels_that_prefer_it(self):
        rx = FakeReelix()
        rx.profiles[0]["format_items"].append({"format_id": 9, "score": 100})
        self.assertEqual(self.run_with(rx), "Reelix prefers releases with audio description in 1 quality level")

    def test_an_older_reelix_without_the_built_in_format(self):
        self.assertEqual(self.run_with(FakeReelix(builtin=False)), "Reelix has no Audio description format yet. It comes with the next Reelix update")
        said = self.run_with(FakeReelix(builtin=False, formats=[{"id": 9, "name": "Audio Description"}]))
        self.assertIn("set Audio description to Prefer in Settings, Reelix, Picture quality", said)

    def test_a_refusal_never_fails_the_job(self):
        said = self.run_with(FakeReelix(profiles_403=True))
        self.assertIn("Settings, Reelix, Picture quality", said)

    def test_deactivated_it_only_says_how_reelix_treats_them(self):
        said = self.run_with(FakeReelix(), {"prefer_in_reelix": False})
        self.assertTrue(said.startswith("Reelix does not prefer releases with audio description"))

    def test_no_reelix_key_is_said_not_failed(self):
        app = load()
        os.remove(os.path.join(os.environ["PLUGIN_RUN"], "reelix.json"))
        self.assertIn("no Reelix key", app.reelix_now()["said"])


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


class FakeJellyfin:
    """Jellyfin's API as the plug-in uses it for Find and tag, the collection and Play the described track."""

    def __init__(self, items, plugins=(), sessions=(), users=(("u1", "Sam"), ("u2", "Alex"))):
        self.items = {i["Id"]: dict(i) for i in items}
        self.plugins, self.sessions, self.users = list(plugins), list(sessions), list(users)
        self.box, self.calls, self.commands = None, [], []

    def __call__(self, path, data=None, method=None):
        self.calls.append((method or "GET", path))
        url = urllib.parse.urlparse(path)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}
        if path == "/Plugins":
            return self.plugins
        if path == "/Users":
            return [{"Id": i, "Name": n, "Policy": {"IsAdministrator": i == "u1"}} for i, n in self.users]
        if url.path == "/Items" and q.get("Ids"):
            return {"Items": [self.items[i] for i in q["Ids"].split(",") if i in self.items]}
        if url.path == "/Items" and q.get("ParentId"):
            got = [{"Id": i} for i in (self.box or {}).get("members", [])]
            return {"Items": got, "TotalRecordCount": len(got)}
        if url.path == "/Items" and q.get("IncludeItemTypes") == "BoxSet":
            return {"Items": [{"Id": "b1", "Name": self.box["name"]}] if self.box else []}
        if url.path == "/Items":
            kinds = q["IncludeItemTypes"].split(",")
            got = [i for i in self.items.values() if i["Type"] in kinds]
            start = int(q.get("StartIndex", 0))
            return {"Items": got[start:start + int(q.get("Limit", 200))], "TotalRecordCount": len(got)}
        m = re.match(r"^/Items/(\w+)$", url.path)
        if m and method == "POST":
            self.items[m.group(1)] = data
            return None
        if m:
            return dict(self.items[m.group(1)])
        if url.path == "/Collections" and method == "POST":
            self.box = {"name": q["Name"], "members": q["Ids"].split(",")}
            return {"Id": "b1"}
        if url.path == "/Collections/b1/Items":
            ids = q["Ids"].split(",")
            self.box["members"] = (self.box["members"] + ids) if method == "POST" else [i for i in self.box["members"] if i not in ids]
            return None
        if url.path.startswith("/Sessions") and method == "POST":
            self.commands.append((url.path, data))
            return None
        if url.path == "/Sessions":
            return self.sessions
        raise AssertionError(path)


def item(iid, kind, streams, tags=(), series=None, name=None):
    out = {"Id": iid, "Type": kind, "Name": name or iid, "MediaStreams": streams, "Tags": list(tags), "Genres": ["Drama"]}
    if series:
        out.update(SeriesId=series, SeriesName=series)
    return out


class FindAndTag(unittest.TestCase):
    def library(self, plugins=()):
        return FakeJellyfin([
            item("m1", "Movie", [audio("English"), audio("English (Audio Description)")], tags=["Favourite"]),
            item("m2", "Movie", [audio("English")], tags=["Audio description"]),  # the track has gone
            item("e1", "Episode", [audio("AD")], series="s1"),
            item("e2", "Episode", [audio("English")], series="s1"),
            item("s1", "Series", []), item("s2", "Series", [], tags=["Audio description"])], plugins=plugins)

    def test_tags_films_episodes_and_series_and_takes_the_tag_off_when_the_track_goes(self):
        app = load()
        jf = self.library()
        app.jellyfin = jf
        said = app.scan()["said"]
        self.assertIn("Tagged 3, took the tag off 2", said)
        self.assertEqual(jf.items["m1"]["Tags"], ["Favourite", "Audio description"])  # other tags kept
        self.assertEqual(jf.items["m1"]["Genres"], ["Drama"])  # the whole item is saved back, as the metadata editor does
        self.assertEqual(jf.items["m2"]["Tags"], [])
        self.assertIn("Audio description", jf.items["e1"]["Tags"])
        self.assertIn("Audio description", jf.items["s1"]["Tags"])
        self.assertEqual(jf.items["s2"]["Tags"], [])
        self.assertNotIn(("POST", "/Items/e2"), jf.calls)  # only what changes is written
        self.assertEqual(sorted(jf.box["members"]), ["m1", "s1"])  # films and series, not episodes
        self.assertEqual(jf.box["name"], "Audio description")
        jf.calls.clear()
        app.scan()
        self.assertFalse([c for c in jf.calls if c[0] != "GET"])  # in step: nothing written

    def test_the_collection_follows_the_tags(self):
        app = load()
        jf = self.library()
        jf.box = {"name": "Audio description", "members": ["m2", "m1"]}
        app.jellyfin = jf
        app.scan()
        self.assertEqual(sorted(jf.box["members"]), ["m1", "s1"])
        self.assertIn(("DELETE", "/Collections/b1/Items?Ids=m2"), jf.calls)

    def test_the_collection_can_be_deactivated(self):
        app = load({"collection": False})
        jf = self.library()
        app.jellyfin = jf
        app.scan()
        self.assertIsNone(jf.box)
        self.assertFalse([c for c in jf.calls if "/Collections" in c[1]])

    def test_idle_beside_the_jellyfin_version(self):
        app = load()
        jf = self.library(plugins=[{"Id": "7a591954-9c27-4ba7-80c3-dc5f0a140692", "Name": "Audio description", "Status": "Active"}])
        app.jellyfin = jf
        said = app.scan()["said"]
        self.assertIn("Idle: Jellyfin's own Audio description plug-in is installed", said)
        self.assertFalse([c for c in jf.calls if c[0] != "GET"])  # it reads for its lists, and writes nothing
        card = app.count()
        self.assertEqual((card["status"], card["status_label"]), ("idle", "Idle"))
        self.assertIn("Idle", card["note"])

    def test_a_deactivated_jellyfin_version_does_not_count(self):
        app = load()
        app.jellyfin = self.library(plugins=[{"Id": "7a5919549c274ba780c3dc5f0a140692", "Status": "Disabled"}])
        self.assertFalse(app.jellyfin_version_installed(force=True))


class PlayTheDescribedTrack(unittest.TestCase):
    def session(self, user, playing, accepts=True, sid="s-1"):
        return {"Id": sid, "UserId": user, "Client": "Jellyfin Web" if accepts else "Some TV app", "DeviceName": "Living room",
                "NowPlayingItem": {"Id": "m1", "Name": "Dune"}, "PlayState": {"AudioStreamIndex": playing},
                "Capabilities": {"SupportedCommands": ["SetAudioStreamIndex"] if accepts else ["DisplayMessage"]}}

    def make(self, *sessions):
        app = load()
        jf = FakeJellyfin([item("m1", "Movie", [dict(audio("English"), Index=1), dict(audio("English (Audio Description)"), Index=2)])], sessions=sessions)
        app.jellyfin = jf
        return app, jf

    def test_inactive_until_chosen(self):
        app, jf = self.make(self.session("u1", 1))
        self.assertEqual(app.on_event({"event": "playback.started"})["said"], "Nobody chose Play the described track")
        self.assertEqual(jf.commands, [])
        self.assertFalse(app.RULES["play_described_track"]["default"])
        self.assertTrue(all(not i["on"] for i in app.play()["items"]))

    def test_the_described_track_is_asked_for_once(self):
        app, jf = self.make(self.session("u1", 1))
        self.assertEqual(app.play({"action": "toggle", "id": "u1"})["said"], "Play the described track activated for Sam")
        app.on_event({"event": "playback.started", "data": {"user": "Sam"}})
        self.assertEqual(jf.commands, [("/Sessions/s-1/Command", {"Name": "SetAudioStreamIndex", "Arguments": {"Index": "2"}})])
        app.on_event({"event": "playback.started"})  # the same start again: the person may have chosen another track
        self.assertEqual(len(jf.commands), 1)

    def test_nothing_for_others_or_when_it_already_plays(self):
        app, jf = self.make(self.session("u2", 1, sid="s-2"), self.session("u1", 2))
        app.play({"action": "toggle", "id": "u1"})
        app.on_event({"event": "playback.started"})
        self.assertEqual(jf.commands, [])

    def test_an_app_that_does_not_accept_it_is_left_alone_and_noted(self):
        app, jf = self.make(self.session("u1", 1, accepts=False))
        app.play({"action": "toggle", "id": "u1"})
        said = app.on_event({"event": "playback.started"})["said"]
        self.assertEqual(jf.commands, [])
        self.assertIn("Some TV app on Living room does not accept the command to change the sound track", said)
        self.assertIn("does not accept", app.play()["intro"])

    def test_idle_beside_the_jellyfin_version(self):
        app, jf = self.make(self.session("u1", 1))
        app.play({"action": "toggle", "id": "u1"})
        jf.plugins = [{"Id": "7a591954-9c27-4ba7-80c3-dc5f0a140692", "Status": "Active"}]
        app._jf["at"] = 0.0
        self.assertIn("Idle", app.on_event({"event": "playback.started"})["said"])
        self.assertEqual(jf.commands, [])
        self.assertEqual(app.play()["notices"][0]["id"], "jellyfin")

    def test_the_rule_on_its_own(self):
        app = load()
        streams = [dict(audio("English"), Index=0), dict(audio("Descriptive audio"), Index=3)]
        self.assertEqual(app.index_to_play(streams, 0), 3)
        self.assertEqual(app.index_to_play(streams, None), 3)
        self.assertIsNone(app.index_to_play(streams, 3))
        self.assertIsNone(app.index_to_play(streams[:1], 0))


class SharedRules(unittest.TestCase):
    def test_the_shared_examples_give_the_same_results_here(self):
        app = load()
        ex = app.RULES["described_track"]["examples"]
        for t in ex["described"]:
            self.assertIsNotNone(app.described_track([audio(t)]), t)
        for t in ex["not_described"]:
            self.assertIsNone(app.described_track([audio(t)]), t)

    def test_both_plug_ins_have_the_same_rules_file(self):
        with open(os.path.join(ROOT, PID, "rules.json"), "rb") as a, open(os.path.join(ROOT, "audio-description-tracks", "rules.json"), "rb") as b:
            self.assertEqual(a.read(), b.read())

    def test_the_image_has_the_rules_file(self):
        with open(os.path.join(ROOT, "Dockerfile"), encoding="utf-8") as f:
            self.assertIn("audio-description/rules.json", f.read())


class Words(unittest.TestCase):
    def test_no_em_dashes_or_contractions_in_what_people_read(self):
        app = load()
        m = manifest()
        app.jellyfin = FakeJellyfin([])
        text = json.dumps([m, app.ELSEWHERE, app.elsewhere(), app.titles(), app.count(), app.recent(), app.audiovault(), app.play(), app.IDLE], ensure_ascii=False)
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
        self.assertEqual(as_published(self.plugins.check(m), m), [])  # published: its image pinned by digest (14 November 2026)
        report = self.tester.report(m, dev=True)
        self.assertTrue(report["accessibility"]["passed"])
        self.assertEqual(report["errors"], 0)
        self.assertEqual(m["containers"][0]["start"], "when_needed")  # rests between uses

    def test_answers_have_the_shapes_starboard_draws(self):
        app = load()
        app.keep("result", {"at": 1794600000, "total": 3, "films": [{"id": "m1", "name": "Dune (2021)", "track": "English (AD)"}],
                            "series": [{"name": "Slow Horses", "described": 2, "episodes": 2, "track": "AD"}]})
        app.jellyfin = FakeJellyfin([])
        self.cards.clean("stat", app.count())
        self.cards.clean("list", app.recent())
        self.assertTrue(self.custom.clean(app.play())["items"])
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
