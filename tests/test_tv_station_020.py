"""Create your own TV channel 0.2.0 (owner, 19 November 2026): the schedule grid opening, changes answered for one
channel, Choose from your library, music for promos, the holding slide, the channels page in cards, logos shown,
Suggest a schedule's sources, Jellyfin's guide status and the tuner taking the station's new name.

The FFmpeg tests run only where ffmpeg is installed; they make short clips of their own."""
import io
import json
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
import dog  # noqa: E402
import grid  # noqa: E402
import promo  # noqa: E402
import schedule  # noqa: E402
import stream  # noqa: E402
import suggest  # noqa: E402

NOW = 1794600123.0  # Tuesday 18 November 2026, evening
SID = "a" * 32
FID = "c" * 32
FFMPEG = bool(shutil.which("ffmpeg"))


def episodes(series, n, dur):
    return [{"id": f"{series}{i}", "dur": dur, "title": f"Show {series}", "group": series, "s": 1, "e": i, "ep": f"Part {i}",
             "plot": "", "kind": "Episode", "premiere": "2020-01-01", "art": f"{series}{i}", "backdrop": series} for i in range(1, n + 1)]


def make(path, args):
    subprocess.run(["ffmpeg", "-loglevel", "error", *args, "-y", path], check=True)
    return path


class App(unittest.TestCase):
    """The app with its own /data and settings, and Jellyfin answered by `self.answers` (path start: answer)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        run, data = os.path.join(self.tmp.name, "run"), os.path.join(self.tmp.name, "data")
        os.makedirs(run)
        os.makedirs(data)
        json.dump({"station_name": "Home TV"}, open(os.path.join(run, "settings.json"), "w"))
        json.dump({"url": "http://jellyfin.invalid:8096", "api_key": "k"}, open(os.path.join(run, "jellyfin.json"), "w"))
        open(os.path.join(run, "key"), "w").write("sbk_test")
        os.environ["PLUGIN_RUN"], os.environ["PLUGIN_DATA"] = run, data
        os.environ["STARBOARD_HOME_ADDRESS"] = "http://192.0.2.10:8790"
        for m in ("sbplugin", "app"):
            sys.modules.pop(m, None)
        import app
        self.app = app
        self.asked = []
        self.answers = {}

        def jf(path, method=None, data=None):
            self.asked.append((method or "GET", path, data))
            for start, answer in self.answers.items():
                if path.startswith(start):
                    return answer(path, data) if callable(answer) else answer
            return {}
        app.jf = jf
        app.later_jellyfin = lambda: None
        app.refresh_soon = lambda cid: None
        self.app._req.can = frozenset()

    def tearDown(self):
        os.environ.pop("STARBOARD_HOME_ADDRESS", None)
        self.tmp.cleanup()

    def channel(self, name="Comedy", lineup=None):
        page = self.app.channels_post({"action": "add", "value": name}, now=NOW)
        cid = [m for m in page["menus"] if not m.get("parent")][-1]["id"]
        if lineup:
            s = self.app.state()
            ch = self.app.find(s, cid)
            ch["eras"] = schedule.new_era(ch, lineup, NOW)
            self.app.save(s)
        return cid

    def can(self, *what):
        self.app._req.can = frozenset(what)


class TheGridOpens(App):
    """The bug (owner, 19 November 2026: "The Schedule grid is not appearing")."""

    def test_the_link_goes_to_the_grid_on_the_plugins_own_port(self):
        cid = self.channel()
        it = self.app.schedule_page()["items"][0]
        token = self.app.state()["token"]
        self.assertEqual(it["link"]["url"], f"http://192.0.2.10:8790/t/{token}/grid?channel={cid}")
        self.assertIn("Open the schedule grid", it["link"]["label"])
        self.assertIn("Open the schedule grid", self.app.schedule_page()["intro"])

    def test_with_no_channels_the_grid_has_every_field_its_page_draws(self):
        got = self.app.grid_state("")
        for key in ("channels", "cid", "days", "slots", "series", "today", "draft", "can_undo", "said"):
            self.assertIn(key, got)
        self.assertEqual(got["slots"], [])
        self.assertIn("Add a channel first", got["said"])

    def test_the_home_page_says_where_the_grid_is(self):
        self.assertIn("Schedule grid", self.app.HOME)


class SavedInPlace(App):
    def test_a_change_answers_with_that_channel_only_when_starboard_can_take_it(self):
        one = self.channel("Comedy")
        self.channel("Films")
        full = self.app.channels_post({"action": "choose", "id": f"{one}:dog-corner", "value": "bottom_left"}, now=NOW)
        self.assertNotIn("partial", full)
        self.assertEqual(len(full["menus"]), 4, "each channel and its More about breaks; an older Starboard gets the whole list, as before")
        self.can("partial")
        part = self.app.channels_post({"action": "choose", "id": f"{one}:dog-corner", "value": "top_left"}, now=NOW)
        self.assertEqual(part["partial"], {"menus": [one, f"{one}~breaks"]})
        self.assertEqual([m["id"] for m in part["menus"]], [one, f"{one}~breaks"])
        self.assertTrue(all(it["menu"] in (one, f"{one}~breaks") for it in part["items"]))
        self.assertEqual(part["said"], "Corner: Top left. Saved for Comedy", "it says what was saved")

    def test_moving_a_channel_answers_with_every_channel(self):
        self.channel("Comedy")
        two = self.channel("Films")
        self.can("partial")
        page = self.app.channels_post({"action": "up", "id": f"{two}:on"}, now=NOW)
        self.assertNotIn("partial", page, "numbers change for every channel")
        self.assertTrue(page["menus"][0]["title"].startswith("1  Films"))


class InCards(App):
    def test_an_opened_channel_has_a_card_for_each_part_with_a_sentence(self):
        cid = self.channel(lineup=episodes("a", 3, 1500))
        self.can("cards", "picker")
        page = self.app.channels_page(now=NOW)
        self.assertEqual(page["layout"], "cards")
        groups = []
        for it in page["items"]:
            if it["group"] not in groups:
                groups.append(it["group"])
        self.assertEqual(groups, ["Name and number", "What it shows", "Breaks", "Corner logo and branding", "Animation",
                                  "Waiting screen and coming-up trailers", "Today and tomorrow", "Played on this channel"])
        for g in groups:
            self.assertTrue(page["hints"][g].endswith("."), g)
            self.assertLessEqual(len(g), 40)
        self.assertTrue(any(it["id"] == f"{cid}:pick" for it in page["items"]))
        self.assertFalse(any(it["id"].endswith(":add-series") for it in page["items"]), "the picker replaces the search boxes")

    def test_an_older_starboard_gets_the_search_boxes(self):
        cid = self.channel()
        ids = [it["id"] for it in self.app.channels_page(now=NOW)["items"]]
        self.assertIn(f"{cid}:add-series", ids)
        self.assertIn(f"{cid}:add-decade", ids)
        self.assertNotIn(f"{cid}:pick", ids)
        self.assertNotIn("layout", self.app.channels_page(now=NOW))

    def test_pages_keep_to_starboards_limits(self):
        self.channel(lineup=episodes("a", 3, 1500))
        self.can("cards", "picker", "partial")
        for page in (self.app.channels_page(now=NOW), self.app.clips_page(), self.app.guide_page(now=NOW)):
            for it in page["items"]:
                self.assertLessEqual(len(it["title"]), 120, it["title"])
                self.assertLessEqual(len(it.get("detail", "")), 200, it["id"])
                if "choice" in it:
                    self.assertLessEqual(len(it["choice"]["options"]), 12)
                    self.assertTrue(all(len(o[1]) <= 40 for o in it["choice"]["options"]), it["choice"])


class ChooseFromYourLibrary(App):
    def setUp(self):
        super().setUp()
        items = [{"Id": f"{k:032x}", "Name": f"Show {k}", "ProductionYear": 2000 + k} for k in range(1, 4)]
        self.answers = {"/Items?Ids=": {"Items": items}, "/Items?": {"Items": items, "TotalRecordCount": 250},
                        "/Genres?": {"Items": [{"Name": "Comedy"}, {"Name": "Drama"}], "TotalRecordCount": 2},
                        "/Years?": {"Items": [{"Name": "1984"}, {"Name": "1989"}, {"Name": "2003"}]}}

    def test_every_kind_is_listed_a_page_at_a_time_with_whats_added_already(self):
        cid = self.channel()
        s = self.app.state()
        self.app.find(s, cid)["sources"].append({"kind": "series", "id": f"{1:032x}", "name": "Show 1"})
        self.app.save(s)
        got = self.app.channels_post({"action": "browse", "id": f"{cid}:pick", "value": "", "filter": "series", "start": 0})
        self.assertEqual(got["type"], "picker")
        self.assertEqual(got["total"], 250)
        self.assertTrue(got["more"])
        self.assertEqual([it["on"] for it in got["items"]], [True, False, False], "the one on the channel shows as added")
        self.assertIn("StartIndex=0", self.asked[-1][1])
        self.assertNotIn("SearchTerm", self.asked[-1][1], "with no words, every one is listed")
        got = self.app.channels_post({"action": "browse", "id": f"{cid}:pick", "value": "", "filter": "decade"})
        self.assertEqual([it["title"] for it in got["items"]], ["The 2000s", "The 1980s"])
        got = self.app.channels_post({"action": "browse", "id": f"{cid}:pick", "value": "com", "filter": "genre"})
        self.assertIn("SearchTerm=com", self.asked[-1][1])

    def test_several_ticked_are_added_at_once(self):
        cid = self.channel()
        page = self.app.channels_post({"action": "pick", "id": f"{cid}:pick", "ids": [f"series:{1:032x}", f"film:{2:032x}", "genre:Comedy",
                                                                                         "decade:1980", "decade:../x", "nonsense"]})
        self.assertEqual(page["said"][:28], "Added 4 to Comedy: Show 1 (2")
        kinds = [(src["kind"], src["name"]) for src in self.app.find(self.app.state(), cid)["sources"]]
        self.assertEqual(kinds, [("series", "Show 1 (2001)"), ("film", "Show 2 (2002)"), ("genre", "Comedy"), ("decade", "The 1980s")])
        with self.assertRaises(ValueError):
            self.app.channels_post({"action": "pick", "id": f"{cid}:pick", "ids": [f"series:{1:032x}"]})


class Holding(unittest.TestCase):
    def test_the_slide_fills_the_break_to_the_next_start_after_the_promos(self):
        ch = {"id": "abcd1234", "order": "in_order", "run": 1, "start_on": 30, "break_seconds": 0, "seed": 7, "eras": []}
        ch["eras"] = schedule.new_era(ch, episodes("a", 3, 1300), NOW)
        c = schedule.Channel(ch)
        promo_clip = {"id": "p1", "dur": 15, "title": "Promo", "src": "promo:1", "airs": NOW + 10 ** 6}
        slide = {"file": "/x.png", "still": True, "words": "countdown"}
        a, pieces = schedule.pieces_at(c, NOW, {"idents": [], "fillers": [promo_clip], "holding": slide}, {"seed": 7, "cards": True})
        kinds = [p["kind"] for p in pieces]
        self.assertEqual(kinds[0], "programme")
        self.assertEqual(kinds[-1], "holding")
        self.assertNotIn("card", kinds, "the slide takes the cards' place")
        self.assertEqual(pieces[-1]["end"], a["end"], "it ends exactly as the next programme starts")
        self.assertEqual(pieces[-1]["airing"]["start"], a["end"])
        _, plain = schedule.pieces_at(c, NOW, {"idents": [], "fillers": []}, {"seed": 7, "cards": True})
        self.assertIn("card", [p["kind"] for p in plain], "with no slide, breaks are as before")

    def test_countdown_words(self):
        t = dog.countdown_text(272.5)
        self.assertTrue(t.startswith("Next programme in %{eif:"))
        self.assertIn("272.500", t)
        with tempfile.TemporaryDirectory() as d:
            texts = dog.Texts(d)
            self.assertEqual(dog.holding_chain(1280, 720, texts, "none"), [])
            back = dog.holding_chain(1280, 720, texts, "back_soon")
            self.assertEqual(len(back), 1)
            self.assertIn("expansion=none", back[0])
            count = dog.holding_chain(1280, 720, texts, "countdown", "Show A: Series 1, episode 2", 60)
            self.assertEqual(len(count), 2)
            self.assertIn("expansion=normal", count[0])

    @unittest.skipUnless(FFMPEG, "ffmpeg is not installed here")
    def test_a_frame_of_the_slide_with_its_countdown(self):
        with tempfile.TemporaryDirectory() as d:
            pic = make(os.path.join(d, "slide.png"), ["-f", "lavfi", "-i", "testsrc2=s=640x360:d=1", "-frames:v", "1"])
            nxt = {"start": NOW + 300, "entry": {"title": "Show A", "s": 1, "e": 2, "ep": "Part 2"}}
            piece = {"kind": "holding", "start": NOW, "end": NOW + 272, "holding": {"file": pic, "still": True, "words": "countdown"}, "airing": nxt}
            ctx = {"W": 640, "H": 360, "kbps": 800, "opts": dog.resolve({}, {"dog": {"kind": "station_name"}}), "names": {"channel": "C", "station": "S"},
                   "ts_offset": 1.0, "texts": dog.Texts(os.path.join(d, "t")), "still": True}
            r = subprocess.run(stream.piece_command(piece, NOW, ctx), capture_output=True, timeout=60, check=False)
            self.assertEqual(r.returncode, 0, r.stderr[-400:])
            self.assertTrue(r.stdout.startswith(b"\x89PNG"))
            argv = stream.piece_command(piece, NOW, {**ctx, "still": False})
            self.assertEqual(argv[len(argv) - 1 - argv[::-1].index("-t") + 1], "272.000", "the stream piece lasts exactly to the next programme")


class Uploads(App):
    @unittest.skipUnless(FFMPEG, "ffmpeg is not installed here")
    def test_music_is_checked_listed_and_removed(self):
        d = self.tmp.name
        good = make(os.path.join(d, "bed.m4a"), ["-f", "lavfi", "-i", "sine=f=330:d=6", "-c:a", "aac"])
        short = make(os.path.join(d, "blip.ogg"), ["-f", "lavfi", "-i", "sine=f=330:d=2", "-c:a", "libvorbis"])
        fake = os.path.join(d, "fake.mp3")
        open(fake, "wb").write(b"not music at all" * 100)

        def send(path, item="add:music"):
            data = open(path, "rb").read()
            return self.app.clips_file(os.path.basename(path), item, len(data), io.BytesIO(data))
        page = send(good)
        self.assertIn("Added bed.m4a, 6 seconds", page["said"])
        tracks = self.app.state()["music"]
        self.assertEqual(len(tracks), 1)
        self.assertIn("gain", tracks[0])
        with self.assertRaisesRegex(ValueError, "5 seconds to 10 minutes"):
            send(short)
        with self.assertRaisesRegex(ValueError, "no sound"):
            send(fake)
        with self.assertRaisesRegex(ValueError, "ending"):
            self.app.clips_file("bed.wma", "add:music", 10, io.BytesIO(b"0" * 10))
        self.assertEqual(len(self.app.music_files(self.app.state()["music"])), 1)
        cid = self.channel()
        self.assertEqual(self.app.promo_design(self.app.state(), self.app.find(self.app.state(), cid))["name"], "Plain",
                         "with music and no pack promo, plain promos on the channel's colour")
        self.app.clips_post({"action": "remove", "id": f"music:{tracks[0]['id']}"})
        self.assertEqual(self.app.state()["music"], [])
        self.assertFalse(os.path.exists(os.path.join(self.app.sbplugin.DATA, "music", "station", "bed.m4a")))
        self.assertIsNone(self.app.promo_design(self.app.state(), self.app.find(self.app.state(), cid)))

    @unittest.skipUnless(FFMPEG, "ffmpeg is not installed here")
    def test_a_holding_slide_for_a_channel_and_the_station(self):
        d = self.tmp.name
        cid = self.channel(lineup=episodes("a", 3, 1300))
        clip = make(os.path.join(d, "loop.mp4"), ["-f", "lavfi", "-i", "testsrc2=s=320x180:d=3", "-c:v", "libx264", "-preset", "ultrafast"])
        long = make(os.path.join(d, "long.mp4"), ["-f", "lavfi", "-i", "testsrc2=s=160x90:r=5:d=125", "-c:v", "libx264", "-preset", "ultrafast"])
        fine = make(os.path.join(d, "fine.mp4"), ["-f", "lavfi", "-i", "testsrc2=s=160x90:r=5:d=100", "-c:v", "libx264", "-preset", "ultrafast"])
        pic = make(os.path.join(d, "slide.png"), ["-f", "lavfi", "-i", "testsrc2=s=320x180:d=1", "-frames:v", "1"])

        def send(path, item):
            data = open(path, "rb").read()
            return self.app.channels_file(os.path.basename(path), item, len(data), io.BytesIO(data))
        with self.assertRaisesRegex(ValueError, "up to 120 seconds"):  # 120 seconds from 0.2.1 (owner, 19 November 2026)
            send(long, f"{cid}:holding-own")
        send(fine, f"{cid}:holding-own")  # 100 seconds is fine now
        self.assertEqual(self.app.HOLDING_MOST, 90 * 1024 * 1024)
        with self.assertRaisesRegex(ValueError, "up to 90 MB"):
            self.app.add_holding(f"ch-{cid}", "big.mp4", 91 * 1024 * 1024, io.BytesIO(b""))
        self.can("partial")
        page = send(clip, f"{cid}:holding-own")
        self.assertEqual(page["partial"], {"menus": [cid, f"{cid}~breaks"]})
        s = self.app.state()
        h = self.app.holding_for(s, self.app.find(s, cid))
        self.assertFalse(h["still"])
        self.assertEqual(h["words"], "countdown")
        data = open(pic, "rb").read()
        self.app.clips_file("slide.png", "holding", len(data), io.BytesIO(data))
        self.app.clips_post({"action": "choose", "id": "holding-words", "value": "back_soon"})
        s = self.app.state()
        self.assertTrue(self.app.holding_for(s, self.app.find(s, cid))["file"].endswith(f"ch-{cid}.mp4"), "its own first")
        self.app.channels_post({"action": "detach", "id": f"{cid}:holding-own"})
        s = self.app.state()
        h = self.app.holding_for(s, self.app.find(s, cid))
        self.assertTrue(h["still"], "then the station's")
        self.assertEqual(h["words"], "back_soon")
        self.app.channels_post({"action": "choose", "id": f"{cid}:holding_mode", "value": "none"})
        s = self.app.state()
        self.assertIsNone(self.app.holding_for(s, self.app.find(s, cid)))
        self.assertIsNone(self.app.clips_for(s, self.app.find(s, cid))["holding"])

    @unittest.skipUnless(FFMPEG, "ffmpeg is not installed here")
    def test_an_uploaded_logo_shows_as_a_picture_with_words(self):
        cid = self.channel()
        pic = make(os.path.join(self.tmp.name, "logo.png"), ["-f", "lavfi", "-i", "color=c=red:s=300x300:d=1", "-frames:v", "1"])
        data = open(pic, "rb").read()
        page = self.app.channels_file("logo.png", f"{cid}:logo", len(data), io.BytesIO(data))
        row = next(it for it in page["items"] if it["id"] == f"{cid}:logo")
        self.assertTrue(row["image"]["src"].startswith("data:image/png;base64,"))
        self.assertEqual(row["image"]["alt"], "Comedy's logo")
        self.assertLess(len(row["image"]["src"]), 64 * 1024)


class MusicForPromos(unittest.TestCase):
    def test_which_music_a_promo_chooses_from(self):
        pk = [{"path": "promo/music/a.m4a", "gain": 1.0}]
        own, station = [{"file": "/own.m4a", "gain": 0}], [{"file": "/station.m4a", "gain": 0}]
        files = lambda pool: [m["file"] for m in pool]  # noqa: E731
        self.assertEqual(files(promo.music_pool(pk, "/p", own, station)), ["/own.m4a", "/p/promo/music/a.m4a"])
        self.assertEqual(files(promo.music_pool(pk, "/p", [], station)), ["/station.m4a", "/p/promo/music/a.m4a"])
        self.assertEqual(files(promo.music_pool(pk, "/p", [], station, "mine")), ["/station.m4a"])
        self.assertEqual(files(promo.music_pool(pk, "/p", [], station, "pack")), ["/p/promo/music/a.m4a"])
        self.assertEqual(files(promo.music_pool([], "", [], station, "pack")), ["/station.m4a"], "never no music when there is some")
        self.assertIsNone(promo.pick_music([], 1))

    def test_a_plain_promo_is_drawn_on_the_channels_colour(self):
        pk = promo.plain_pack("0x2e7d32")
        a = {"start": NOW + 86400, "entry": {"id": FID, "title": "A Film", "dur": 6000}}
        with tempfile.TemporaryDirectory() as d:
            argv, seconds = promo.command(pk, a, "Films", {"file": "/music/bed.m4a", "gain": -2.0}, 640, 360, "http://jf", "k", dog.Texts(d), "/x.mp4")
        joined = " ".join(argv)
        self.assertIn("color=c=0x2e7d32", joined)
        self.assertIn("/music/bed.m4a", argv)
        self.assertEqual(seconds, 15)


class SuggestFrom(unittest.TestCase):
    def info(self, sid):
        return {"id": sid, "name": f"Series {sid[:4]}", "episodes": episodes(sid[:4], 20, 1500), "unwatched": 0}

    def film(self, fid):
        return {"id": fid, "dur": 6000, "title": f"Film {fid[:4]}", "group": fid, "kind": "Movie"}

    def test_each_source(self):
        pool = [("series", "b" * 32, "B"), ("series", "d" * 32, "D"), ("film", FID, "C"), ("film", "e" * 32, "E")]
        plays = [{"at": NOW - 3600, "kind": "series", "id": SID, "name": "A"}]
        doc, _ = suggest.propose({"z" * 32}, plays, NOW, self.info, self.film, source="history")
        self.assertEqual(doc["slots"], [], "Watch history keeps to the channel's own")
        doc, _ = suggest.propose({"z" * 32}, plays, NOW, self.info, self.film, source="everyone")
        self.assertEqual({s["ref"] for s in doc["slots"]}, {f"s:{SID}"}, "General watch history ignores the channel's settings")
        doc, notes = suggest.propose(None, plays, NOW, self.info, self.film, source="tv", pool=pool)
        self.assertTrue(all(s["ref"].startswith("s:") for s in doc["slots"]))
        self.assertEqual(doc["slots"][0]["ref"], f"s:{SID}", "the most watched first")
        self.assertEqual(sorted({s["day"] for s in doc["slots"]}), list(range(7)), "All TV: every day")
        self.assertIn("from your library", " ".join(notes))
        doc, _ = suggest.propose(None, plays, NOW, self.info, self.film, source="films", pool=pool)
        self.assertTrue(all(s["ref"].startswith("f:") for s in doc["slots"]))
        self.assertEqual(len(doc["slots"]), 2)
        doc, _ = suggest.propose(None, [], NOW, self.info, self.film, source="both", pool=pool)
        kinds = {s["ref"][0] for s in doc["slots"]}
        self.assertEqual(kinds, {"s", "f"})
        self.assertEqual(list(suggest.SOURCES.values()), ["This channel's line-up", "Watch history", "General watch history", "All TV", "All films", "TV and Films"])


class SuggestRemembered(App):
    def test_the_choice_is_kept_for_the_channel(self):
        cid = self.channel()
        self.app.suggest_for = lambda s, ch, now, source, hours=None: (grid.empty(), [f"made from {source}"])
        self.assertEqual(self.app.grid_state(cid)["suggest_hours"], {"weekdays": ["18:00", "23:00"], "weekends": ["12:00", "23:00"]})
        got = self.app.grid_op({"cid": cid, "op": "suggest", "from": "films",
                                "hours": {"weekdays": ["19:00", "24:00"], "weekends": None}}, now=NOW)
        self.assertEqual(got["suggest_from"], "films")
        self.assertEqual(self.app.grid_state(cid)["suggest_from"], "films")
        self.assertEqual(self.app.grid_state(cid)["suggest_hours"], {"weekdays": ["19:00", "24:00"], "weekends": None})
        with self.assertRaises(grid.GridError):
            self.app.grid_op({"cid": cid, "op": "suggest", "from": "films", "hours": {"weekdays": ["20:00", "19:00"]}}, now=NOW)
        with self.assertRaises(grid.GridError):
            self.app.grid_op({"cid": cid, "op": "suggest", "from": "anything"}, now=NOW)


class JellyfinsGuide(App):
    def test_the_guide_page_says_when_jellyfin_last_read_it(self):
        self.assertIn("has not read the guide yet", self.app.guide_page(now=NOW)["notices"][0]["text"])
        self.app.sbplugin.keep("guide_read", {"at": int(NOW - 600), "programmes": 204, "channels": 2, "days": 7})
        text = self.app.guide_page(now=NOW)["notices"][0]["text"]
        self.assertIn("Jellyfin last read the guide today at", text)
        self.assertIn("204 programmes on 2 channels", text)

    def test_renaming_the_station_renames_its_tuner(self):
        token = self.app.state()["token"]
        tuner = {"Id": "t1", "Url": f"http://192.0.2.10:8790/t/{token}/channels.m3u", "FriendlyName": "Home TV", "Type": "m3u"}
        self.answers = {"/System/Configuration/livetv": {"TunerHosts": [tuner], "ListingProviders": [
            {"Path": f"http://192.0.2.10:8790/t/{token}/guide.xml"}]}, "/ScheduledTasks?": []}
        self.app.connect_jellyfin()
        self.assertFalse([a for a in self.asked if a[0] == "POST"], "nothing to change")
        self.assertFalse(self.app.renamed())
        json.dump({"station_name": "T-Rex TV"}, open(os.path.join(os.environ["PLUGIN_RUN"], "settings.json"), "w"))
        self.assertTrue(self.app.renamed())
        self.app.connect_jellyfin()
        post = [a for a in self.asked if a[0] == "POST" and a[1] == "/LiveTv/TunerHosts"]
        self.assertEqual(post[0][2]["FriendlyName"], "T-Rex TV")
        self.assertEqual(post[0][2]["Id"], "t1", "the same tuner, changed in place")
        self.assertFalse(self.app.renamed())


if __name__ == "__main__":
    unittest.main()
