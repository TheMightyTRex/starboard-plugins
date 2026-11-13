"""Audio description tracks (DASH-410): names, where films are, lengths, adding next to the film, the person's say,
zips, uploads and answers Starboard accepts. Every outside thing is a stand-in: Jellyfin answers from a dictionary,
mkvmerge is replaced, and the folders are temporary. Run: python3 -m unittest discover -s tests
(STARBOARD_SRC points at Starboard's source, plug-in API 1.12 or later, for its own checks)."""
import importlib.util
import io
import json
import os
import re
import socket
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
import zipfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PID = "audio-description-tracks"
STARBOARD_SRC = os.environ.get("STARBOARD_SRC", os.path.expanduser("~/src/starboard"))
sys.dont_write_bytecode = True


def load(values=None):
    """app.py with its own sbplugin, settings, /data and media folders in a temporary folder, without serving."""
    tmp = tempfile.mkdtemp(prefix="sb-adt-test-")
    run, data = os.path.join(tmp, "run"), os.path.join(tmp, "data")
    media = {k: os.path.join(tmp, "media", k) for k in ("movies", "tv", "audio-description")}
    for d in (run, data, *media.values()):
        os.makedirs(d)
    with open(os.path.join(run, "settings.json"), "w") as f:
        json.dump(values or {}, f)
    with open(os.path.join(run, "jellyfin.json"), "w") as f:
        json.dump({"url": "http://jellyfin.invalid:8096", "api_key": "jf"}, f)
    os.environ.update(PLUGIN_RUN=run, PLUGIN_DATA=data, TRACKS_INBOX=media["audio-description"], TRACKS_MOVIES=media["movies"], TRACKS_TV=media["tv"])
    sys.path.insert(0, os.path.join(ROOT, PID))
    for name in ("sbplugin", "app_adt"):
        sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location("app_adt", os.path.join(ROOT, PID, "app.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sys.path.pop(0)
    mod._tmp, mod._media = tmp, media
    return mod


def manifest():
    with open(os.path.join(ROOT, PID, "starboard-plugin.json"), encoding="utf-8") as f:
        return json.load(f)


class Done:
    def __init__(self, code=0, out="", err=""):
        self.returncode, self.stdout, self.stderr = code, out, err


class Stand:
    """Jellyfin and mkvmerge, answering from what each test gives: `lengths` by file name, in seconds."""

    def __init__(self, app, films=(), lengths=None):
        self.app, self.films, self.lengths, self.asked, self.cmds, self.made = app, list(films), dict(lengths or {}), [], [], {}
        app.jellyfin = self.jellyfin
        app.run = self.run

    def jellyfin(self, path, data=None, method=None):
        self.asked.append((method or "GET", path))
        if "/Refresh" in path:
            return None
        if "Ids=" in path:
            want = re.search(r"Ids=([^&]+)", path).group(1)
            return {"Items": [f for f in self.films if f["Id"] == want]}
        if "IncludeItemTypes=Series" in path:
            return {"Items": [{"Id": "s1", "Name": "Slow Horses"}]} if "Slow" in path else {"Items": []}
        if "/Shows/s1/Episodes" in path:
            return {"Items": [f for f in self.films if f.get("Type") == "Episode"]}
        term = urllib.request.unquote(re.search(r"searchTerm=([^&]*)", path).group(1)).replace("+", " ").lower()
        return {"Items": [f for f in self.films if f.get("Type", "Movie") == "Movie" and term.split()[0] in f["Name"].lower()]}

    def run(self, cmd, **kw):
        self.cmds.append(cmd)
        self.app_assert(cmd[0] == "mkvmerge", cmd)
        if cmd[1] == "-J":
            n = self.made.get(cmd[2], os.path.basename(cmd[2]))
            if n not in self.lengths:
                return Done(2, json.dumps({"errors": ["unsupported"]}))
            video = n.endswith((".mkv", ".mp4"))
            return Done(0, json.dumps({"container": {"properties": {"duration": int(self.lengths[n] * 1e9) if (video or cmd[2] in self.made) else None}},
                                       "tracks": [{"id": 0, "type": "video"}] * video + [{"id": int(video), "type": "audio"}]}))
        out = cmd[cmd.index("-o") + 1]
        with open(out, "wb") as f:
            f.write(b"matroska")
        self.made[out] = os.path.basename(cmd[-1])
        return Done(0)

    @staticmethod
    def app_assert(ok, cmd):
        if not ok:
            raise AssertionError(cmd)


def film(app, name, year, folder=None, streams=None, fid="m1"):
    folder = folder or f"{name} ({year})"
    os.makedirs(os.path.join(app._media["movies"], folder), exist_ok=True)
    path = os.path.join(app._media["movies"], folder, f"{name} ({year}).mkv")
    open(path, "wb").close()
    return {"Id": fid, "Name": name, "ProductionYear": year, "Type": "Movie", "RunTimeTicks": 0,
            "Path": f"/data/media/movies/{folder}/{name} ({year}).mkv", "MediaStreams": streams or [{"Type": "Audio", "Title": "English"}]}


def drop(app, name, data=b"ID3"):
    with open(os.path.join(app._media["audio-description"], name), "wb") as f:
        f.write(data)


class Names(unittest.TestCase):
    def setUp(self):
        self.app = load()

    def test_films_and_episodes(self):
        p = self.app.parse_name
        self.assertEqual(p("Dune (2021).mp3"), {"kind": "film", "name": "Dune", "year": 2021})
        self.assertEqual(p("Dune.2021.Audio.Description.mp3"), {"kind": "film", "name": "Dune", "year": 2021})
        self.assertEqual(p("[AD] The Bourne Identity.m4a"), {"kind": "film", "name": "The Bourne Identity", "year": 0})
        self.assertEqual(p("2012 (2009).mp3"), {"kind": "film", "name": "2012", "year": 2009})
        self.assertEqual(p("Slow Horses S01E03 - Bad Tradecraft.mp3"), {"kind": "episode", "name": "Slow Horses", "season": 1, "episode": 3})
        self.assertEqual(p("Taskmaster 12x04.mp3"), {"kind": "episode", "name": "Taskmaster", "season": 12, "episode": 4})

    def test_lengths_in_words(self):
        self.assertEqual(self.app.length_words(7082), "1 hour 58 minutes 2 seconds")
        self.assertEqual(self.app.length_words(208), "3 minutes 28 seconds")
        self.assertEqual(self.app.length_words(0.2), "0 seconds")


class WhereFilmsAre(unittest.TestCase):
    def test_jellyfins_path_is_found_under_movies(self):
        app = load()
        f = film(app, "Dune", 2021)
        self.assertEqual(app.local_path(f["Path"]), os.path.realpath(os.path.join(app._media["movies"], "Dune (2021)", "Dune (2021).mkv")))
        self.assertIsNone(app.local_path("/elsewhere/films/Dune.mkv"))

    def test_no_way_out_through_a_link(self):
        app = load()
        outside = os.path.join(app._tmp, "secret.mkv")
        open(outside, "wb").close()
        os.symlink(outside, os.path.join(app._media["movies"], "sneaky.mkv"))
        self.assertIsNone(app.local_path("/data/media/movies/sneaky.mkv"))
        self.assertIsNone(app.local_path("/data/media/movies/../../secret.mkv"))


class Adding(unittest.TestCase):
    def setUp(self):
        self.app = load()

    def test_a_matching_track_is_added_next_to_the_film_and_kept(self):
        f = film(self.app, "Dune", 2021)
        s = Stand(self.app, [f], {"Dune (2021).mp3": 9302.4, "Dune (2021).mkv": 9300.0})
        drop(self.app, "Dune (2021).mp3")
        said = self.app.look()["said"]
        self.assertEqual(said, "Checked 1 new file, added 1 track")
        out = os.path.join(self.app._media["movies"], "Dune (2021)", "Dune (2021).Audio Description.eng.mka")
        self.assertTrue(os.path.isfile(out))
        mk = next(c for c in s.cmds if "-o" in c)
        for part in ("0:eng", "0:English (Audio Description)", "--visual-impaired-flag", "0:1", "--default-track-flag", "0:0", "--no-global-tags"):
            self.assertIn(part, mk)
        self.assertFalse([n for n in os.listdir(self.app._media["audio-description"]) if n.startswith(".")])  # no working copies left
        self.assertTrue(os.path.isfile(os.path.join(self.app._media["audio-description"], "Dune (2021).mp3")))  # kept
        self.assertIn(("POST", "/Items/m1/Refresh?MetadataRefreshMode=Default&ImageRefreshMode=None&ReplaceAllMetadata=false&ReplaceAllImages=false"), s.asked)
        row = self.app.inbox()["items"][0]
        self.assertEqual((row["state_label"], row["group"]), ("Added", "Added: check each plays in step"))
        self.assertEqual([o[0] for o in row["choice"]["options"]], ["wait", "right", "undo"])
        self.assertEqual(self.app.look()["said"], "No new files in the folder")  # looked at once only

    def test_a_different_cut_is_explained_and_not_added(self):
        f = film(self.app, "Dune", 2021)
        Stand(self.app, [f], {"Dune (2021).mp3": 9508.0, "Dune (2021).mkv": 9300.0})
        drop(self.app, "Dune (2021).mp3")
        self.app.look()
        self.assertFalse(any(n.endswith(".mka") for n in os.listdir(os.path.join(self.app._media["movies"], "Dune (2021)"))))
        row = self.app.inbox()["items"][0]
        self.assertEqual(row["state_label"], "Lengths differ")
        self.assertIn("3 minutes 28 seconds longer than the film", row["detail"])
        self.assertIn("another cut", row["detail"])
        self.assertFalse([n for n in os.listdir(self.app._media["audio-description"]) if n.startswith(".")])  # its check copy removed
        self.assertEqual(row["link"]["url"], "https://audiovault.net/movies?search=Dune")
        self.assertLessEqual(len(row["detail"]), 200)

    def test_the_tolerance_setting_is_used(self):
        app = load({"tolerance": 30})
        f = film(app, "Dune", 2021)
        Stand(app, [f], {"Dune (2021).mp3": 9325.0, "Dune (2021).mkv": 9300.0})
        drop(app, "Dune (2021).mp3")
        self.assertIn("added 1 track", app.look()["said"])

    def test_a_film_with_a_described_track_or_one_added_already_is_left_alone(self):
        f = film(self.app, "Dune", 2021, streams=[{"Type": "Audio", "DisplayTitle": "English (Audio Description) - AAC"}])
        s = Stand(self.app, [f], {"Dune (2021).mp3": 9300.0, "Dune (2021).mkv": 9300.0})
        drop(self.app, "Dune (2021).mp3")
        self.app.look()
        self.assertEqual(self.app.inbox()["items"][0]["state_label"], "Already described")
        self.assertFalse([c for c in s.cmds if "-o" in c])
        app = load()
        f = film(app, "Brazil", 1985)
        existing = os.path.join(app._media["movies"], "Brazil (1985)", "Brazil (1985).Audio Description.eng.mka")
        with open(existing, "wb") as fh:
            fh.write(b"theirs")
        Stand(app, [f], {"Brazil (1985).mp3": 8000.0, "Brazil (1985).mkv": 8000.0})
        drop(app, "Brazil (1985).mp3")
        app.look()
        self.assertEqual(app.inbox()["items"][0]["state_label"], "Already added")
        with open(existing, "rb") as fh:
            self.assertEqual(fh.read(), b"theirs")  # never replaced

    def test_choosing_between_two_titles(self):
        a, b = film(self.app, "Heat", 1995, fid="m1"), film(self.app, "Heat", 1986, fid="m2")
        Stand(self.app, [a, b], {"Heat.mp3": 6000.0, "Heat (1986).mkv": 6002.0, "Heat (1995).mkv": 10200.0})
        drop(self.app, "Heat.mp3")
        self.app.look()
        row = self.app.inbox()["items"][0]
        self.assertEqual(row["state_label"], "Choose the title")
        self.assertEqual(row["choice"]["options"][0], ["", "Choose one"])
        out = self.app.inbox({"action": "choose", "id": "Heat.mp3", "value": "m2"})
        self.assertEqual(out["said"], "Added to Heat (1986). Play it in Jellyfin to check it")
        with self.assertRaises(ValueError):
            self.app.inbox({"action": "choose", "id": "Gone.mp3", "value": "m2"})

    def test_episodes_are_found_by_series_and_number(self):
        os.makedirs(os.path.join(self.app._media["tv"], "Slow Horses", "Season 1"))
        open(os.path.join(self.app._media["tv"], "Slow Horses", "Season 1", "S01E03.mkv"), "wb").close()
        ep = {"Id": "e3", "Type": "Episode", "SeriesName": "Slow Horses", "ParentIndexNumber": 1, "IndexNumber": 3,
              "Path": "/data/media/tv/Slow Horses/Season 1/S01E03.mkv", "MediaStreams": []}
        Stand(self.app, [ep], {"Slow Horses S01E03.mp3": 2900.0, "S01E03.mkv": 2901.0})
        drop(self.app, "Slow Horses S01E03.mp3")
        self.app.look()
        self.assertTrue(os.path.isfile(os.path.join(self.app._media["tv"], "Slow Horses", "Season 1", "S01E03.Audio Description.eng.mka")))
        drop(self.app, "Slow Horses S01E09.mp3")
        self.app.look()
        rows = {r["id"]: r for r in self.app.inbox()["items"]}
        self.assertIn("not series 1 episode 9", rows["Slow Horses S01E09.mp3"]["detail"])

    def test_a_film_outside_the_media_folders_is_said_plainly(self):
        f = {**film(self.app, "Dune", 2021), "Path": "/mnt/other/Dune (2021).mkv"}
        Stand(self.app, [f], {"Dune (2021).mp3": 9300.0})
        drop(self.app, "Dune (2021).mp3")
        self.app.look()
        self.assertEqual(self.app.inbox()["items"][0]["state_label"], "Out of reach")


class ThePersonsSay(unittest.TestCase):
    def test_yes_puts_the_original_away_and_no_takes_the_track_off(self):
        app = load()
        f = film(app, "Dune", 2021)
        Stand(app, [f], {"Dune (2021).mp3": 9300.0, "Dune (2021).mkv": 9300.0, "Brazil (1985).mp3": 8000.0, "Brazil (1985).mkv": 8000.0})
        drop(app, "Dune (2021).mp3")
        app.look()
        out = app.inbox({"action": "choose", "id": "Dune (2021).mp3", "value": "right"})
        self.assertIn("Confirmed for Dune (2021)", out["said"])
        inbox = app._media["audio-description"]
        self.assertTrue(os.path.isfile(os.path.join(inbox, "Confirmed", "Dune (2021).mp3")))
        self.assertEqual(out["items"][0]["state_label"], "Confirmed")
        app.look()
        self.assertEqual(app.inbox()["items"][0]["state_label"], "Confirmed")  # still listed after the next look
        b = film(app, "Brazil", 1985, fid="m2")
        Stand(app, [b], {"Brazil (1985).mp3": 8000.0, "Brazil (1985).mkv": 8000.0})
        drop(app, "Brazil (1985).mp3")
        app.look()
        out = app.inbox({"action": "choose", "id": "Brazil (1985).mp3", "value": "undo"})
        self.assertIn("Taken off Brazil (1985)", out["said"])
        self.assertTrue(os.path.isfile(os.path.join(inbox, "Taken off", "Brazil (1985).Audio Description.eng.mka")))
        self.assertTrue(os.path.isfile(os.path.join(inbox, "Brazil (1985).mp3")))  # the original stays
        self.assertFalse(os.path.exists(os.path.join(app._media["movies"], "Brazil (1985)", "Brazil (1985).Audio Description.eng.mka")))


class ZipsAndUploads(unittest.TestCase):
    def test_a_zip_is_unpacked_by_names_only_and_kept(self):
        app = load()
        Stand(app, [], {})
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("Show/Slow Horses S01E01.mp3", b"a")
            z.writestr("../../escape.mp3", b"b")
            z.writestr("notes.txt", b"c")
        drop(app, "Slow Horses.zip", buf.getvalue())
        app.look()
        inbox = app._media["audio-description"]
        self.assertEqual(sorted(n for n in os.listdir(inbox) if os.path.isfile(os.path.join(inbox, n))), ["Slow Horses S01E01.mp3", "escape.mp3"])
        self.assertTrue(os.path.isfile(os.path.join(inbox, "Unzipped", "Slow Horses.zip")))
        self.assertFalse(os.path.exists(os.path.join(app._tmp, "escape.mp3")))

    def test_an_upload_is_streamed_into_the_folder(self):
        app = load()
        Stand(app, [], {})
        app.look_soon = lambda: None
        out = app.upload("Dune (2021).mp3", "", 5, io.BytesIO(b"ID3ab"))
        self.assertIn("Uploaded Dune (2021).mp3", out["said"])
        with open(os.path.join(app._media["audio-description"], "Dune (2021).mp3"), "rb") as f:
            self.assertEqual(f.read(), b"ID3ab")
        self.assertIn("Uploaded Dune (2021) (2).mp3", app.upload("Dune (2021).mp3", "", 2, io.BytesIO(b"xy"))["said"])
        for name, size in (("film.exe", 3), (".hidden.mp3", 3), ("big.mp3", 61 * 1024 * 1024)):
            with self.assertRaises(ValueError):
                app.upload(name, "", size, io.BytesIO(b"abc"))
        with self.assertRaisesRegex(ValueError, "stopped before the end"):
            app.upload("short.mp3", "", 10, io.BytesIO(b"abc"))
        self.assertFalse([n for n in os.listdir(app._media["audio-description"]) if n.endswith(".part")])

    def test_the_server_streams_a_file_route(self):
        app = load()
        got = {}

        def take(name, item, length, stream):
            got.update(name=name, item=item, data=stream.read(length))
            return {"type": "list", "items": []}
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        os.environ["PORT"] = str(port)
        threading.Thread(target=app.serve, args=({("FILE", "/inbox/file"): take},), daemon=True).start()
        for _ in range(40):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1)
                break
            except OSError:
                time.sleep(0.05)
        req = urllib.request.Request(f"http://127.0.0.1:{port}/inbox/file?name=Dune%20(2021).mp3&id=x", data=b"sound", method="POST",
                                     headers={"Content-Type": "application/octet-stream"})
        self.assertEqual(json.loads(urllib.request.urlopen(req, timeout=5).read()), {"type": "list", "items": []})
        self.assertEqual(got, {"name": "Dune (2021).mp3", "item": "x", "data": b"sound"})
        os.environ.pop("PORT")


class Words(unittest.TestCase):
    def test_no_em_dashes_or_contractions_in_what_people_read(self):
        app = load()
        text = json.dumps([manifest(), app.inbox(), app.count(), app.GROUPS, app.OUTCOME], ensure_ascii=False)
        rows = [{"status": s, "item": {"id": "m1", "title": "Dune (2021)", "kind": "film", "search": "Dune"}, "track_seconds": 10, "film_seconds": 300,
                 "parsed": {"kind": "film", "name": "Dune"}} for s in ("added", "confirmed", "taken_off", "lengths", "choose", "no_match", "described",
                                                                        "exists", "out_of_reach", "unreadable", "unreadable_film", "new", "problem")]
        text += json.dumps([app._row("x.mp3", r) for r in rows])
        for name in ("README.md", "CHANGELOG.md"):
            with open(os.path.join(ROOT, PID, name), encoding="utf-8") as f:
                text += f.read()
        self.assertNotIn("—", text)
        self.assertFalse(re.search(r"\b\w+n't\b|\b(?:it|that|there|you|we)'(?:s|re|ll|ve|d)\b", text, re.I))
        for r in rows:
            row = app._row("x.mp3", r)
            self.assertLessEqual(len(row.get("detail", "")), 200, r["status"])
            self.assertLessEqual(len(row.get("state_label", "")), 30, r["status"])
            for _, words in (row.get("choice") or {}).get("options", []):
                self.assertLessEqual(len(words), 40)


@unittest.skipUnless(os.path.isdir(os.path.join(STARBOARD_SRC, "starboard")), "Starboard's source is not here")
class StarboardAccepts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, STARBOARD_SRC)
        from starboard import plugin_cards, plugin_custom, plugin_tester, plugins
        cls.cards, cls.custom, cls.tester, cls.plugins = plugin_cards, plugin_custom, plugin_tester, plugins
        if not cls.plugins._range_ok(manifest()["starboard_api"], cls.plugins.API_VERSION):
            raise unittest.SkipTest(f"Starboard at {STARBOARD_SRC} has plug-in API {cls.plugins.API_VERSION}; this needs 1.12")

    def test_manifest_passes_in_development_and_accessibility(self):
        m = manifest()
        self.assertEqual(self.plugins.check(m, dev=True), [])
        report = self.tester.report(m, dev=True)
        self.assertTrue(report["accessibility"]["passed"])
        self.assertEqual(report["errors"], 0)
        self.assertEqual(m["containers"][0]["start"], "when_needed")
        self.assertEqual(m["containers"][0]["user"], "media")
        warning = self.plugins.install_warning(m)
        self.assertTrue(any(c.startswith("Files in your media folder under audio-description") for c in warning["change"]))  # plug-in API 1.13 adds what it can do there

    def test_answers_have_the_shapes_starboard_draws(self):
        app = load()
        f = film(app, "Dune", 2021)
        Stand(app, [f], {"Dune (2021).mp3": 9508.0, "Dune (2021).mkv": 9300.0})
        drop(app, "Dune (2021).mp3")
        app.look()
        screen = self.custom.clean(app.inbox())
        self.assertTrue(screen["add"]["file_only"])
        self.assertEqual(screen["items"][0]["link"]["label"], "Search AudioVault for Dune")
        self.assertEqual(screen["items"][0]["state_label"], "Lengths differ")
        self.cards.clean("stat", app.count())
        for c in manifest()["cards"]:
            self.cards.clean(c["type"], c["example"])


if __name__ == "__main__":
    unittest.main()
