"""Create your own TV channel 0.4.0 (owner, 19 November 2026): bumpers that open and close each break, one ident
immediately before the programme, and breaks inside programmes found from their sound and picture.

The FFmpeg tests run only where ffmpeg is installed; they make short clips of their own."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT  # noqa: E402
from test_tv_station import NOW, channel, episodes  # noqa: E402

TV = os.path.join(ROOT, "tv-station")
sys.path.insert(0, TV)
import breaks  # noqa: E402
import pack  # noqa: E402
import schedule  # noqa: E402
import stream  # noqa: E402

FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
BUMPERS = [{"id": "b1", "dur": 2, "title": "bumper01"}, {"id": "b2", "dur": 2, "title": "bumper02"}]
IDENTS = [{"id": "i1", "dur": 8, "title": "ident01"}, {"id": "i2", "dur": 6, "title": "ident02"}]
FILLERS = [{"id": "t1", "dur": 30, "title": "Trailer"}, {"id": "p1", "dur": 15, "title": "Promo"}]
HOLDING = {"file": "/data/holding/station.mp4", "still": False, "words": "countdown"}


def roles(pieces):
    return [p.get("role") or p["kind"] for p in pieces]


def joined_up(test, a, pieces):
    for x, y in zip(pieces, pieces[1:]):
        test.assertAlmostEqual(x["end"], y["start"], places=6)
    test.assertAlmostEqual(pieces[-1]["end"], a["end"], places=6)


class BreakOrder(unittest.TestCase):
    def setUp(self):
        self.sched = schedule.Channel(channel(episodes("a", 3, 1500), start_on=30))  # 5 minute breaks

    def test_bumper_clips_holding_bumper_ident(self):
        clips = {"idents": IDENTS, "fillers": FILLERS, "bumpers": BUMPERS, "holding": HOLDING}
        a, pieces = schedule.pieces_at(self.sched, NOW, clips, {"seed": 3})
        r = roles(pieces)
        self.assertEqual(r[0], "programme")
        self.assertEqual(r[1], "bumper")
        self.assertEqual(r[-3:], ["holding", "bumper", "ident"])
        self.assertTrue(set(r[2:-3]) <= {"filler"})
        self.assertNotEqual(pieces[1]["clip"]["id"], pieces[-2]["clip"]["id"], "two different bumpers when there are two")
        joined_up(self, a, pieces)
        self.assertEqual(schedule.pieces_at(self.sched, NOW, clips, {"seed": 3})[1], pieces, "the same every time")

    def test_cards_when_there_is_no_holding_slide(self):
        clips = {"idents": IDENTS, "fillers": [], "bumpers": BUMPERS}
        a, pieces = schedule.pieces_at(self.sched, NOW, clips, {"seed": 3})
        r = roles(pieces)
        self.assertEqual(r[1], "bumper")
        self.assertEqual(r[-2:], ["bumper", "ident"])
        self.assertTrue(all(x == "card" for x in r[2:-2]))
        joined_up(self, a, pieces)

    def test_a_short_break_keeps_the_ident_first_then_the_bumpers(self):
        for gap, want in ((7, ["ident"]), (10, ["bumper", "bumper", "ident"]), (3, ["bumper"])):
            a = {"start": NOW, "content_end": NOW + 600, "end": NOW + 600 + gap, "slot_no": 1, "entry": {"id": "x"}}
            got = schedule.plan_break(a, [], {"idents": [{"id": "i", "dur": 7}], "bumpers": [{"id": "b", "dur": 1.5}]}, {"seed": 1})
            if gap == 3:  # the ident does not fit; the two bumpers do
                self.assertEqual(roles(got), ["bumper", "slate", "bumper"] if len(got) == 3 else ["bumper", "bumper"])
            else:
                self.assertEqual(roles(got), want)
            self.assertAlmostEqual(got[-1]["end"], a["end"])

    def test_without_bumpers_it_is_as_before_but_the_ident_comes_last(self):
        a, pieces = schedule.pieces_at(self.sched, NOW, {"idents": IDENTS, "fillers": FILLERS}, {"seed": 3})
        self.assertEqual(roles(pieces)[-1], "ident")
        self.assertNotIn("bumper", roles(pieces))
        joined_up(self, a, pieces)


class InsideProgrammes(unittest.TestCase):
    def setUp(self):
        # 25 minute episodes on the half hour: a 5 minute gap to share.
        self.sched = schedule.Channel(channel(episodes("a", 3, 1500), start_on=30))
        self.clips = {"idents": IDENTS, "fillers": FILLERS, "bumpers": BUMPERS, "holding": HOLDING}

    def options(self, points, mid=120):
        return {"seed": 3, "mid_seconds": mid, "breaks_in": lambda e: points}

    def test_a_programme_played_in_parts_round_a_break(self):
        a, pieces = schedule.pieces_at(self.sched, NOW, self.clips, self.options([700.0]))
        progs = [p for p in pieces if p["kind"] == "programme"]
        self.assertEqual(len(progs), 2)
        self.assertEqual((progs[0]["offset"], progs[1]["offset"]), (0.0, 700.0))
        self.assertAlmostEqual(progs[0]["end"] - progs[0]["start"], 700.0)
        self.assertAlmostEqual(progs[1]["end"] - progs[1]["start"], 800.0, "the rest of the programme")
        self.assertEqual(progs[0]["length"], 1500.0)
        mid = pieces[pieces.index(progs[0]) + 1:pieces.index(progs[1])]
        self.assertEqual(roles(mid)[0], "bumper")
        self.assertEqual(roles(mid)[-1], "bumper")
        self.assertTrue(all(p.get("mid") for p in mid))
        self.assertNotIn("holding", roles(mid))
        self.assertLessEqual(mid[-1]["end"] - mid[0]["start"], 120)
        self.assertEqual(roles(pieces)[-3:], ["holding", "bumper", "ident"], "the end break as before")
        joined_up(self, a, pieces)
        self.assertEqual(a["end"], self.sched.airing(NOW)["end"], "the schedule never moves")

    def test_off_no_points_or_no_room_means_one_part(self):
        for opts in ({"seed": 3}, self.options([]), self.options([700.0], mid=0), self.options([30.0, 1480.0])):
            _, pieces = schedule.pieces_at(self.sched, NOW, self.clips, opts)
            self.assertEqual(sum(p["kind"] == "programme" for p in pieces), 1, opts)
        tight = schedule.Channel(channel(episodes("a", 3, 1780), start_on=30))  # 20 seconds to spare
        _, pieces = schedule.pieces_at(tight, NOW, self.clips, self.options([700.0]))
        self.assertEqual(sum(p["kind"] == "programme" for p in pieces), 1, "no time to give")

    def test_left_out_when_no_clip_fits(self):
        clips = {**self.clips, "fillers": [{"id": "long", "dur": 600, "title": "Long"}]}
        _, pieces = schedule.pieces_at(self.sched, NOW, clips, self.options([700.0]))
        self.assertEqual(sum(p["kind"] == "programme" for p in pieces), 1)

    def test_two_breaks_share_the_spare_time(self):
        sched = schedule.Channel(channel(episodes("a", 2, 2700), start_on=60))  # 45 minutes in an hour
        a, pieces = schedule.pieces_at(sched, NOW, self.clips, self.options([900.0, 1800.0], mid=180))
        self.assertEqual(sum(p["kind"] == "programme" for p in pieces), 3)
        joined_up(self, a, pieces)
        end_break = pieces[[i for i, p in enumerate(pieces) if p["kind"] == "programme"][-1] + 1:]
        self.assertGreaterEqual(end_break[-1]["end"] - end_break[0]["start"], 2 * 2 + 8 + schedule.END_ROOM - 0.01)

    def test_the_stream_seeks_each_part(self):
        a, pieces = schedule.pieces_at(self.sched, NOW, self.clips, self.options([700.0]))
        part = [p for p in pieces if p["kind"] == "programme"][1]
        with tempfile.TemporaryDirectory() as d:
            import dog
            ctx = {"W": 640, "H": 360, "kbps": 800, "opts": dog.resolve({"dog_kind": "none"}, None), "names": {"channel": "C", "station": "S"},
                   "logo": None, "jf_url": "http://jf", "jf_key": "k", "ts_offset": 0, "texts": dog.Texts(d), "clip_path": str}
            argv = stream.piece_command(part, part["start"] + 10, ctx)
        self.assertEqual(argv[argv.index("-ss") + 1], "710.000", "part way in: its offset and how far into the part")


class Finding(unittest.TestCase):
    def test_choose(self):
        self.assertEqual(breaks.choose([100, 700, 750, 1290], 1500), [750.0], "one, nearest the middle, inside 20% to 85%")
        self.assertEqual(breaks.choose([900, 1000, 1800, 2000], 2700), [900.0, 1800.0], "two, 8 minutes apart, near thirds")
        self.assertEqual(breaks.choose([1300, 1400], 2700), [1400.0] if abs(1400 - 900) < abs(1300 - 900) else [1300.0])
        self.assertEqual(breaks.choose([], 1500), [])
        self.assertEqual(len(breaks.choose([1000, 1600, 2200, 2800, 3400, 4000], 5000)), 3)

    def test_reading_ffmpeg(self):
        text = "[silencedetect @ 0x1] silence_start: 99.5\n[silencedetect @ 0x1] silence_end: 101.0 | silence_duration: 1.5\n"
        self.assertEqual(breaks.silences(text), [(99.5, 101.0)])
        self.assertEqual(breaks.blacks("[blackdetect @ 0x2] black_start:1.2 black_end:1.9 black_duration:0.7"), [(1.2, 1.9)])

    def test_kept_once(self):
        with tempfile.TemporaryDirectory() as d:
            f = breaks.Found(os.path.join(d, "breaks.json"))
            self.assertFalse(f.known("x"))
            f.put("x", [700.123], "picture")
            self.assertTrue(f.known("x"))
            self.assertEqual(f.points("x"), [700.12])
            f.put("y", [], "picture")
            self.assertEqual(breaks.Found(os.path.join(d, "breaks.json")).count(), (2, 1))

    @unittest.skipUnless(FFMPEG, "ffmpeg is not installed here")
    def test_a_fade_to_black_with_silence_is_found(self):
        with tempfile.TemporaryDirectory() as d:
            # 10 minutes: picture and a tone, with 1.5 seconds of black and silence at 5:00, and silence alone at 3:00.
            path = os.path.join(d, "prog.mkv")
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=160x90:r=10:d=600",
                            "-f", "lavfi", "-i", "sine=f=440:d=600",
                            "-vf", "drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill:enable='between(t,300,301.5)'",
                            "-af", "volume=enable='between(t,300,301.5)+between(t,180,181.5)':volume=0",
                            "-c:v", "libx264", "-preset", "ultrafast", "-g", "10", "-c:a", "aac", "-y", path], check=True)
            breaks.begin()
            got = breaks.detect(path, 600, limit=300)
        self.assertEqual(len(got), 1, got)
        self.assertAlmostEqual(got[0], 300.75, delta=1.0)

    @unittest.skipUnless(FFMPEG, "ffmpeg is not installed here")
    def test_no_fade_means_no_break(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "film.mkv")
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=160x90:r=10:d=300", "-f", "lavfi", "-i", "sine=f=440:d=300",
                            "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-y", path], check=True)
            breaks.begin()
            self.assertEqual(breaks.detect(path, 300, limit=300), [])


@unittest.skipUnless(FFMPEG, "ffmpeg is not installed here")
class PackBumpers(unittest.TestCase):
    def test_a_pack_with_bumpers(self):
        from test_tv_station_pack import small_pack
        shared, _ = small_pack()
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        folder = os.path.join(tmp, "pack")
        shutil.copytree(shared, folder)  # a copy: other tests use the shared pack as it is
        os.makedirs(os.path.join(folder, "bumpers"), exist_ok=True)
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=1920x1080:r=25:d=2", "-f", "lavfi", "-i", "sine=d=2",
                        "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-y", os.path.join(folder, "bumpers", "bumper01.mp4")], check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=1920x1080:r=25:d=12",
                        "-c:v", "libx264", "-preset", "ultrafast", "-y", os.path.join(folder, "bumpers", "bumper02.mp4")], check=True)
        doc = json.load(open(os.path.join(folder, "pack.json")))
        doc["bumpers"] = ["bumper01.mp4", "bumper02.mp4"]
        json.dump(doc, open(os.path.join(folder, "pack.json"), "w"))
        out = pack.check(folder)
        self.assertEqual([b["path"] for b in out["pack"]["bumpers"]], ["bumpers/bumper01.mp4"])
        self.assertFalse(out["pack"]["bumpers"][0]["has_audio"], "a bumper's sound is never played")
        self.assertTrue(any("bumper02.mp4: 12.0 seconds" in p for p in out["problems"]), out["problems"])
        self.assertIn("1 bumper", pack.summary(out["pack"]))
        self.assertEqual(pack.validate({**doc, "bumpers": ["bumper1.mp4"]})[:1] != [], True, "names are checked")


class TheJob(unittest.TestCase):
    """Only channels with the setting on, programmes in the next 48 hours, each once, at most `most` in a run."""

    def test_bounds(self):
        from test_tv_station_020 import App
        t = App("setUp")
        t.setUp()
        try:
            app = t.app
            cid = t.channel("Films", episodes("a", 30, 1500))
            app.someone_watching = lambda: False
            looked = []
            app.breaks.find = lambda url, key, e: (looked.append(e["id"]) or ([700.0], "picture"))
            self.assertIn("Nothing new to check", app.breaks_job(now=NOW)["said"], "off unless chosen")
            s = app.state()
            app.find(s, cid)["mid_break_seconds"] = 120
            app.save(s)
            said = app.breaks_job(now=NOW, most=5)["said"]
            self.assertEqual(len(looked), 5)
            self.assertIn("more in the next quiet hour", said)
            app.breaks_job(now=NOW, most=100)
            self.assertEqual(len(looked), len(set(looked)), "each programme once")
            self.assertEqual(app.found_breaks().points(looked[0]), [700.0])
            app.someone_watching = lambda: True
            self.assertIn("Someone is watching", app.breaks_job(now=NOW)["said"])
            rows = {it["id"].split(":", 1)[1]: it for it in app.channels_page(now=NOW)["items"] if it["id"].startswith(cid)}
            self.assertEqual(rows["mid_break_seconds"]["choice"]["value"], "120")
        finally:
            t.tearDown()


if __name__ == "__main__":
    unittest.main()
