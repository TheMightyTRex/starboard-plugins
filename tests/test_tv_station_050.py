"""Create your own TV channel 0.5.0 (owner, 19 November 2026): "Breaks should play bumper, promos (as per setting),
holding slide, bumper. Not an ident, idents are only at the start of a new program. New program would play bumper,
promos (as per setting), holding slide, ident", "up to 2, 3, 4 or 6 promos and clips per break; the holding slide fills
the rest", and extra videos, as many as wanted, one played at random after the promos.

The FFmpeg tests run only where ffmpeg is installed; they make short clips of their own."""
import io
import os
import shutil
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT  # noqa: E402
from test_tv_station import NOW, channel, episodes  # noqa: E402
from test_tv_station_020 import App, make  # noqa: E402

TV = os.path.join(ROOT, "tv-station")
sys.path.insert(0, TV)
import schedule  # noqa: E402

FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
BUMPERS = [{"id": "b1", "dur": 2, "title": "bumper01"}, {"id": "b2", "dur": 2, "title": "bumper02"}]
IDENTS = [{"id": "i1", "dur": 8, "title": "ident01"}]
PROMOS = [{"id": f"p{k}", "dur": 15, "title": f"Promo {k}"} for k in range(3)]
EXTRAS = [{"id": "x1", "dur": 40, "title": "Extra 1"}, {"id": "x2", "dur": 50, "title": "Extra 2"}]
HOLDING = {"file": "/data/holding/station.mp4", "still": False, "words": "countdown"}


def roles(pieces):
    return [p.get("role") or p["kind"] for p in pieces]


class TheOrder(unittest.TestCase):
    def setUp(self):
        self.sched = schedule.Channel(channel(episodes("a", 3, 1500), start_on=30))  # 5 minute breaks
        self.clips = {"idents": IDENTS, "fillers": PROMOS, "extras": EXTRAS, "bumpers": BUMPERS, "holding": HOLDING}

    def test_between_programmes(self):
        for most in (2, 3, 4, 6):
            a, pieces = schedule.pieces_at(self.sched, NOW, self.clips, {"seed": 5, "fill_most": most})
            r = roles(pieces)
            want = min(most, len(PROMOS))
            self.assertEqual(r, ["programme", "bumper"] + ["filler"] * want + ["extra", "holding", "ident"], most)
            ids = [p["clip"]["id"] for p in pieces if p.get("role") == "filler"]
            self.assertEqual(len(ids), len(set(ids)), "each once")
            self.assertAlmostEqual(pieces[-1]["end"], a["end"])
            self.assertAlmostEqual(pieces[-2]["end"] - pieces[-2]["start"], 300 - 2 - 15 * want - pieces[-3]["clip"]["dur"] - 8,
                                   msg="the holding slide fills the rest")

    def test_the_extra_video_is_chosen_at_random(self):
        seen = set()
        t = NOW
        for _ in range(12):
            _, pieces = schedule.pieces_at(self.sched, t, self.clips, {"seed": 5, "fill_most": 3})
            seen |= {p["clip"]["id"] for p in pieces if p.get("role") == "extra"}
            t = self.sched.airing(t)["end"] + 1
        self.assertEqual(seen, {"x1", "x2"})

    def test_no_extras_and_no_holding_slide(self):
        clips = {**self.clips, "extras": [], "holding": None}
        _, pieces = schedule.pieces_at(self.sched, NOW, clips, {"seed": 5, "fill_most": 2})
        r = roles(pieces)
        self.assertEqual(r[:4], ["programme", "bumper", "filler", "filler"])
        self.assertEqual(r[-1], "ident")
        self.assertTrue(all(x == "card" for x in r[4:-1]))

    def test_inside_a_programme(self):
        opts = {"seed": 5, "fill_most": 2, "mid_seconds": 120, "breaks_in": lambda e: [700.0]}
        a, pieces = schedule.pieces_at(self.sched, NOW, self.clips, opts)
        mid = [p for p in pieces if p.get("mid")]
        self.assertEqual(roles(mid), ["bumper", "filler", "filler", "extra", "holding", "bumper"])
        self.assertEqual(mid[4]["holding"]["words"], "back_soon")
        self.assertIsNone(mid[4]["airing"])
        self.assertAlmostEqual(mid[-1]["end"] - mid[0]["start"], 120)
        self.assertNotEqual(mid[0]["clip"]["id"], mid[-1]["clip"]["id"])
        self.assertEqual(roles(pieces)[-2:], ["holding", "ident"])
        self.assertAlmostEqual(pieces[-1]["end"], a["end"])
        # No words on the slide stays no words.
        clips = {**self.clips, "holding": {**HOLDING, "words": "none"}}
        _, pieces = schedule.pieces_at(self.sched, NOW, clips, opts)
        self.assertEqual([p for p in pieces if p.get("mid") and p["kind"] == "holding"][0]["holding"]["words"], "none")

    def test_inside_with_nothing_to_play_carries_on(self):
        opts = {"seed": 5, "fill_most": 2, "mid_seconds": 120, "breaks_in": lambda e: [700.0]}
        _, pieces = schedule.pieces_at(self.sched, NOW, {**self.clips, "fillers": [], "extras": []}, opts)
        self.assertEqual(sum(p["kind"] == "programme" for p in pieces), 1)


class Settings(App):
    def test_the_breaks_card(self):
        cid = self.channel("Films", episodes("a", 3, 1500))
        rows = {it["id"].split(":", 1)[1]: it for it in self.app.channels_page(now=NOW)["items"] if it["id"].startswith(cid)}
        self.assertEqual(rows["per_break"]["choice"]["value"], "3")
        self.assertEqual([o[0] for o in rows["per_break"]["choice"]["options"]], ["2", "3", "4", "6"])
        self.assertEqual(rows["extras"]["choice"]["value"], "both")
        self.assertIn("add-extra", rows)
        self.app.channels_post({"action": "choose", "id": f"{cid}:per_break", "value": "6"}, now=NOW)
        self.app.channels_post({"action": "choose", "id": f"{cid}:extras", "value": "own"}, now=NOW)
        ch = self.app.find(self.app.state(), cid)
        self.assertEqual((ch["per_break"], ch["extras"]), (6, "own"))
        opts = self.app.opts_for(self.app.state(), ch)
        self.assertEqual(self.app.break_options(ch, opts)["fill_most"], 6)

    @unittest.skipUnless(FFMPEG, "ffmpeg is not installed here")
    def test_extra_videos_for_the_station_and_a_channel(self):
        cid = self.channel("Films", episodes("a", 3, 1500))
        paths = [make(os.path.join(self.tmp.name, f"extra{k}.mp4"), ["-f", "lavfi", "-i", "testsrc2=s=320x180:r=25:d=3",
                                                                     "-c:v", "libx264", "-preset", "ultrafast"]) for k in range(3)]

        def up(fn, item, path):
            data = open(path, "rb").read()
            return fn(os.path.basename(path), item, len(data), io.BytesIO(data))
        up(self.app.clips_file, "add:extras", paths[0])
        page = up(self.app.clips_file, "add:extras", paths[1])
        self.assertEqual(sum(it["id"].startswith("extras:") for it in page["items"]), 2)
        up(self.app.channels_file, f"{cid}:add-extra", paths[2])
        s = self.app.state()
        ch = self.app.find(s, cid)
        got = self.app.clips_for(s, ch)["extras"]
        self.assertEqual(sorted(c["title"] for c in got), ["extra0.mp4", "extra1.mp4", "extra2.mp4"], "both, unless changed")
        ch["extras"] = "shared"
        self.assertEqual(len(self.app.clips_for(s, ch)["extras"]), 2)
        ch["extras"] = "none"
        self.assertEqual(self.app.clips_for(s, ch)["extras"], [])
        own = ch["own"]["extras"][0]["id"]
        self.app.channels_post({"action": "remove", "id": f"{cid}:clip-{own}"}, now=NOW)
        self.assertEqual(self.app.find(self.app.state(), cid)["own"]["extras"], [])
        sid = self.app.state()["shared"]["extras"][0]["id"]
        self.app.clips_post({"action": "remove", "id": f"extras:{sid}"})
        self.assertEqual(len(self.app.state()["shared"]["extras"]), 1)


if __name__ == "__main__":
    unittest.main()
