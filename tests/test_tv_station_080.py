"""Create your own TV channel 0.8.0: the break grids (DASH-537) and where breaks go inside a programme (DASH-538).
FFmpeg tests run only where ffmpeg is installed; they make a short programme of their own."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT  # noqa: E402

TV = os.path.join(ROOT, "tv-station")
sys.path.insert(0, TV)
import breakgrid  # noqa: E402
import breaks  # noqa: E402
import schedule  # noqa: E402
from test_tv_station_020 import App, NOW, episodes  # noqa: E402

FFMPEG = bool(shutil.which("ffmpeg"))


def clip(i, dur, **more):
    return {"id": i, "dur": dur, "title": i, "src": f"x:{i}", **more}


CLIPS = {"idents": [clip("id1", 5), clip("id2", 5)], "bumpers": [clip("b1", 3), clip("b2", 3)], "extras": [clip("ad1", 20)],
         "fillers": [clip("t1", 30), clip("own", 15, role="promo", cid="me", airs=NOW + 9e5), clip("other", 15, role="promo", cid="you", airs=NOW + 9e5)],
         "holding": {"file": "h.png", "still": True, "words": "countdown"}, "sting": None, "random_idents": False}
A = {"start": 1000.0, "content_end": 1600.0, "end": 1900.0, "slot_no": 4, "entry": {"id": "e", "dur": 600}}
OPTS = {"seed": 7, "cid": "me", "cards": True}


def kinds(pieces):
    return [(p.get("role") or p["kind"]) for p in pieces]


class TheGrid(unittest.TestCase):
    def test_modes_and_columns(self):
        g = breakgrid.new_grid("random", count=3)
        self.assertEqual(breakgrid.shown(g), 3)
        self.assertEqual(breakgrid.shown({**g, "mode": "day"}), 7)
        self.assertEqual(breakgrid.shown({**g, "mode": "time"}), 3)
        self.assertEqual(breakgrid.column_names({**g, "mode": "day"})[0], "Monday")
        self.assertEqual(breakgrid.column_names({**g, "mode": "time"}), ["Morning", "Afternoon", "Evening"])
        self.assertEqual(len(g["columns"]), 7)

    def test_a_change_of_mode_loses_nothing(self):
        g = breakgrid.new_grid("random", count=7)
        for c in range(7):
            g = breakgrid.apply(g, {"op": "add", "kind": "bumper", "column": c})
        t = breakgrid.apply(g, {"op": "mode", "mode": "time"})
        self.assertEqual(breakgrid.shown(t), 3)
        back = breakgrid.apply(t, {"op": "mode", "mode": "sequence"})
        self.assertEqual([len(c) for c in back["columns"]], [1] * 7)

    def test_changes(self):
        g = breakgrid.new_grid("random", count=2)
        g = breakgrid.apply(g, {"op": "add", "kind": "promo", "column": 0})
        g = breakgrid.apply(g, {"op": "add", "kind": "ident", "column": 0, "position": 0})
        self.assertEqual([i["kind"] for i in g["columns"][0]], ["ident", "promo"])
        g = breakgrid.apply(g, {"op": "times", "column": 0, "index": 1, "times": 4})
        self.assertEqual(g["columns"][0][1]["times"], 4)
        g = breakgrid.apply(g, {"op": "move", "column": 0, "index": 0, "to_column": 1, "to_position": 0})
        self.assertEqual([len(c) for c in g["columns"][:2]], [1, 1])
        g = breakgrid.apply(g, {"op": "move", "column": 0, "index": 0, "to_column": 1, "to_position": 0})
        self.assertEqual([i["kind"] for i in g["columns"][1]], ["promo", "ident"])
        g = breakgrid.apply(g, {"op": "remove", "column": 1, "index": 0})
        self.assertEqual([i["kind"] for i in g["columns"][1]], ["ident"])
        for bad in ({"op": "add", "kind": "nope", "column": 0}, {"op": "add", "kind": "bumper", "column": 5}, {"op": "count", "count": 9},
                    {"op": "times", "column": 1, "index": 5, "times": 2}, {"op": "x"}):
            with self.assertRaises(breakgrid.GridError):
                breakgrid.apply(g, bad)

    def test_a_holding_item_has_no_count_and_one_per_column(self):
        g = breakgrid.apply(breakgrid.new_grid(), {"op": "add", "kind": "holding", "column": 0, "times": 5})
        self.assertEqual(g["columns"][0][0], {"kind": "holding", "times": 1})
        with self.assertRaises(breakgrid.GridError):
            breakgrid.apply(g, {"op": "add", "kind": "back_soon", "column": 0})
        with self.assertRaises(breakgrid.GridError):
            breakgrid.apply(g, {"op": "times", "column": 0, "index": 0, "times": 2})

    def test_a_damaged_file_is_made_safe(self):
        g = breakgrid.clean({"mode": "zzz", "columns": [[{"kind": "holding"}, {"kind": "back_soon"}, {"kind": "x"}, {"kind": "promo", "times": 99}]]})
        self.assertEqual(g["mode"], "random")
        self.assertEqual([i["kind"] for i in g["columns"][0]], ["holding", "promo"])
        self.assertEqual(g["columns"][0][1]["times"], breakgrid.MOST_TIMES)
        self.assertIsNone(breakgrid.clean("x"))

    def test_choosing_a_column(self):
        g = breakgrid.new_grid("sequence", count=3)
        self.assertEqual([breakgrid.column_index(g, 0, n, 0) for n in range(5)], [0, 1, 2, 0, 1])
        d = {**g, "mode": "day"}
        monday = time.mktime((2026, 11, 23, 12, 0, 0, 0, 0, -1))
        self.assertEqual(breakgrid.column_index(d, monday, 0, 0), 0)
        self.assertEqual(breakgrid.column_index(d, monday + 86400 * 6, 0, 0), 6)
        t = {**g, "mode": "time"}
        day = time.mktime((2026, 11, 23, 0, 0, 0, 0, 0, -1))
        self.assertEqual([breakgrid.column_index(t, day + h * 3600, 0, 0) for h in (6, 11, 12, 17, 18, 23)], [0, 0, 1, 1, 2, 2])
        r = {**g, "mode": "random"}
        self.assertEqual({breakgrid.column_index(r, 0, 0, p) for p in range(30)}, {0, 1, 2})

    def test_the_classic_order_is_the_starting_grid(self):
        g = breakgrid.default_between({"per_break": 4})
        self.assertEqual([(i["kind"], i["times"]) for i in g["columns"][0]],
                         [("bumper", 1), ("promo", 4), ("adverts", 1), ("holding", 1), ("ident", 1)])
        self.assertIsNone(breakgrid.grid_of({}, "between"), "nothing saved: the classic planner is used")
        classic = schedule.plan_break(A, [A], CLIPS, {**OPTS, "fill_most": 4})
        self.assertEqual([k for k in kinds(classic)][0], "bumper")
        self.assertEqual(kinds(classic)[-1], "ident")
        grid = schedule.plan_break_grid(A, [A], CLIPS, OPTS, g["columns"][0])
        self.assertEqual(kinds(grid)[0], "bumper")
        self.assertEqual(kinds(grid)[-1], "ident")
        self.assertIn("holding", kinds(grid))


class ThePlan(unittest.TestCase):
    def test_a_break_fills_the_gap_exactly_and_the_countdown_runs_through_what_follows(self):
        col = [{"kind": "bumper", "times": 1}, {"kind": "holding", "times": 1}, {"kind": "promo", "times": 2}, {"kind": "ident", "times": 1}]
        out = schedule.plan_break_grid(A, [A], CLIPS, OPTS, col)
        self.assertEqual(out[0]["start"], A["content_end"])
        self.assertEqual(out[-1]["end"], A["end"])
        for x, y in zip(out, out[1:]):
            self.assertEqual(x["end"], y["start"])
        h = next(p for p in out if p["kind"] == "holding")
        self.assertEqual(h["until"], A["end"], "the clock counts to the programme's start, through the promos and the ident after it")
        self.assertEqual(h["holding"]["words"], "countdown")
        self.assertEqual(kinds(out).index("holding"), 1)
        self.assertEqual(kinds(out)[-1], "ident")

    def test_back_soon_and_no_holding_item(self):
        out = schedule.plan_break_grid(A, [A], CLIPS, OPTS, [{"kind": "back_soon", "times": 1}])
        self.assertEqual(out[0]["holding"]["words"], "back_soon")
        out = schedule.plan_break_grid(A, [A], CLIPS, OPTS, [{"kind": "bumper", "times": 1}, {"kind": "ident", "times": 1}])
        self.assertEqual(kinds(out)[-1], "ident")
        self.assertEqual(kinds(out)[1], "card", "cards fill the time before the ident")
        self.assertEqual(out[-1]["end"], A["end"])
        out = schedule.plan_break_grid(A, [A], CLIPS, {**OPTS, "cards": False}, [])
        self.assertEqual(kinds(out), ["slate"])

    def test_kinds_draw_from_their_own_pools_and_never_repeat(self):
        col = [{"kind": "other_promo", "times": 3}, {"kind": "coming_promo", "times": 3}, {"kind": "adverts", "times": 2}]
        out = schedule.plan_break_grid(A, [A], CLIPS, OPTS, col)
        ids = [p["clip"]["id"] for p in out if p["kind"] == "clip"]
        self.assertEqual(ids, ["other", "own", "ad1"], "one of each: each clip plays once at most in a break")
        self.assertEqual(schedule.plan_break_grid(A, [A], CLIPS, {**OPTS, "seed": 99}, [{"kind": "bumper", "times": 2}])[0]["clip"]["id"] in ("b1", "b2"), True)

    def test_a_promo_for_a_programme_already_started_is_left_out(self):
        late = {**CLIPS, "fillers": [clip("old", 15, role="promo", cid="me", airs=A["end"] - 1)]}
        out = schedule.plan_break_grid(A, [A], late, OPTS, [{"kind": "coming_promo", "times": 1}, {"kind": "holding", "times": 1}])
        self.assertEqual(kinds(out), ["holding"])

    def test_the_same_airing_gets_the_same_break_and_too_long_goes(self):
        col = [{"kind": "promo", "times": 3}, {"kind": "adverts", "times": 1}, {"kind": "ident", "times": 1}]
        self.assertEqual(schedule.plan_break_grid(A, [A], CLIPS, OPTS, col), schedule.plan_break_grid(A, [A], CLIPS, OPTS, col))
        short = {**A, "end": A["content_end"] + 12.0}
        out = schedule.plan_break_grid(short, [short], CLIPS, OPTS, col)
        self.assertLessEqual(sum(p["end"] - p["start"] for p in out), 12.0 + 1e-6)
        self.assertEqual(out[-1]["end"], short["end"])
        self.assertEqual(kinds(out)[-1], "ident", "the ident is the last to go")

    def test_pieces_at_uses_the_saved_column_by_day(self):
        ch = {"eras": [{"from": NOW - 3600, "lineup": episodes("a", 4, 1500), "seed": 1, "start_on": 30, "break_seconds": 300}]}
        c = schedule.Channel(ch)
        g = breakgrid.new_grid("day")
        for d in range(7):
            g["columns"][d] = [{"kind": "ident", "times": 1}] if d % 2 else [{"kind": "back_soon", "times": 1}]
        a, pieces = schedule.pieces_at(c, NOW, CLIPS, {**OPTS, "grids": {"between": g}})
        wd = time.localtime(pieces[-1]["start"]).tm_wday
        self.assertEqual("holding" in kinds(pieces[1:]), wd % 2 == 0)

    def test_a_break_inside_from_a_grid(self):
        col = [{"kind": "bumper", "times": 1}, {"kind": "promo", "times": 1}, {"kind": "back_soon", "times": 1}, {"kind": "bumper", "times": 1}]
        out = schedule.plan_mid_grid(100.0, 90.0, CLIPS, 5, col, OPTS, A)
        self.assertTrue(all(p["mid"] for p in out))
        self.assertEqual(out[-1]["end"], 190.0)
        self.assertEqual(kinds(out)[0], "bumper")
        self.assertEqual(kinds(out)[-1], "bumper")
        self.assertEqual(next(p for p in out if p["kind"] == "holding")["holding"]["words"], "back_soon")
        self.assertEqual(schedule.plan_mid_grid(100.0, 90.0, {**CLIPS, "holding": None, "fillers": [], "extras": [], "bumpers": []}, 5, col, OPTS, A), [])


class ThePlaces(unittest.TestCase):
    def test_how_many(self):
        self.assertEqual(breaks.count_for(1800, False, 0, 0), 1)
        self.assertEqual(breaks.count_for(3600, False, 0, 0), 2)
        self.assertEqual(breaks.count_for(1800, False, 2, 0), 2)
        self.assertEqual(breaks.count_for(1320, False, 1, 0), 1)
        self.assertEqual(breaks.count_for(3600, False, 3, 0), 6)
        self.assertEqual(breaks.count_for(7200, True, 2, 5), 5)
        self.assertEqual(breaks.count_for(7200, True, 2, 0), 3, "a film's automatic number, not the 30 minute one")

    def test_set_times_and_snapping(self):
        self.assertEqual([round(x) for x in breaks.set_times(3000, 2)], [1000, 2000])
        self.assertEqual(breaks.place(3000, 2), [1000.0, 2000.0])
        self.assertEqual(breaks.place(3000, 2, [(1040, 0.0), (1990, 0.0), (1500, 0.0)]), [1040.0, 1990.0], "snapped to the nearest places")
        self.assertEqual(breaks.place(3000, 2, [(1500, 0.0)]), [1000.0, 2000.0], "a place too far from a set time is not used: it goes to its set time")
        self.assertEqual(breaks.place(3000, 2, [(1040, 0.0), (1100, 2.0)]), [1100.0, 2000.0], "a better place wins")
        got = breaks.place(7200, 6)
        self.assertEqual(len(got), 6)
        self.assertTrue(all(b - a >= 60 for a, b in zip(got, got[1:])))
        self.assertTrue(all(0.2 * 7200 <= x <= 0.85 * 7200 for x in got))

    def test_manual_marks_win(self):
        self.assertEqual(breaks.place(3000, 2, [(1040, 1.0)], manual=[500, 2500, 9999]), [500.0, 2500.0])
        with tempfile.TemporaryDirectory() as d:
            f = breaks.Found(os.path.join(d, "breaks.json"))
            e = {"id": "x", "dur": 3000, "kind": "Episode"}
            f.put_survey("x", {"sil": [[1000.0, 2.0, 1]], "scn": [1020.0]})
            self.assertEqual(f.places(e, "silence")[0], 1000.0)
            self.assertEqual(f.places(e, "scene")[0], 1020.0)
            self.assertEqual(f.places(e, "times"), [1000.0, 2000.0][:1] + f.places(e, "times")[1:])
            f.set_manual("x", [700, 2100])
            self.assertEqual(f.places(e, "silence"), [700.0, 2100.0])
            self.assertEqual(f.places(e, "times"), [700.0, 2100.0])
            f.set_manual("x", [])
            self.assertEqual(f.places(e, "silence")[0], 1000.0)

    def test_what_is_not_searched_for_yet(self):
        with tempfile.TemporaryDirectory() as d:
            f = breaks.Found(os.path.join(d, "breaks.json"))
            e = {"id": "y", "dur": 3000, "kind": "Episode"}
            self.assertEqual(f.places(e, "silence"), [])
            self.assertEqual(f.places(e, "scene"), [])
            self.assertEqual(len(f.places(e, "times")), 2, "set times need no search")
            self.assertEqual(f.places({"id": "s", "dur": 600}, "times"), [], "under 15 minutes: none")
            self.assertTrue(f.has("y", ("times",)))
            self.assertFalse(f.has("y", ("silence",)))
            f.put("y", [900.0], "picture")  # a file of 0.4.0 to 0.7.0 still counts
            self.assertTrue(f.has("y", ("silence",)))
            self.assertEqual(f.places(e, "silence"), [900.0])
            self.assertFalse(f.has("y", ("scene",)))

    @unittest.skipUnless(FFMPEG, "needs ffmpeg")
    def test_the_search_finds_silences_and_scene_ends(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "p.mp4")
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-t", "20", "-i", "testsrc2=r=10:s=160x90", "-f", "lavfi", "-t", "20",
                            "-i", "rgbtestsrc=r=10:s=160x90", "-f", "lavfi", "-t", "40", "-i", "sine=f=300:r=16000", "-filter_complex",
                            "[0:v][1:v]concat=n=2:v=1:a=0[v]", "-map", "[v]", "-map", "2:a", "-af", "volume=0:enable='between(t,19,21)'", "-g", "100",
                            "-c:v", "libx264", "-c:a", "aac", path], check=True)
            breaks.begin()
            got = breaks.survey(path, 40.0, (), ("silence", "scene"), limit=120)
            self.assertTrue(any(abs(s[0] - 20) < 1.5 for s in got["sil"]), got)
            self.assertTrue(any(abs(t - 20) < 1.5 for t in got["scn"]), got)


class TheChannelPage(App):
    def test_the_choices_and_links(self):
        cid = self.channel("Comedy", episodes("a", 6, 1500))
        self.app.channels_post({"action": "choose", "id": f"{cid}:place_how", "value": "scene"}, now=NOW)
        self.app.channels_post({"action": "choose", "id": f"{cid}:breaks_per_30", "value": "2"}, now=NOW)
        self.app.channels_post({"action": "choose", "id": f"{cid}:breaks_per_film", "value": "4"}, now=NOW)
        ch = self.app.find(self.app.state(), cid)
        self.assertEqual((ch["place_how"], ch["breaks_per_30"], ch["breaks_per_film"]), ("scene", 2, 4))
        self.assertEqual(self.app.place_choice(ch), ("scene", 2, 4))
        self.assertEqual(self.app.place_choice({}), ("silence", 0, 0), "what it always did, unless chosen")
        with self.assertRaises(ValueError):
            self.app.channels_post({"action": "choose", "id": f"{cid}:place_how", "value": "zz"}, now=NOW)
        rows = {it["id"].split(":", 1)[1]: it for it in self.app.channels_page(now=NOW)["items"] if it["id"].startswith(cid)}
        token = self.app.state()["token"]
        self.assertEqual(rows["grid-between"]["link"]["url"], f"http://192.0.2.10:8790/t/{token}/breaks?channel={cid}&grid=between")
        self.assertEqual(rows["grid-inside"]["state_label"], "Standard order")
        self.assertEqual(self.app.grids_page()["items"][0]["link"]["url"].split("/breaks")[0], f"http://192.0.2.10:8790/t/{token}")

    def test_changes_are_kept_and_reach_the_plan(self):
        cid = self.channel("Comedy", episodes("a", 6, 1500))
        st = self.app.breaks_state(cid)
        self.assertFalse(st["grids"][0]["saved"])
        self.assertEqual([i["name"] for i in st["grids"][0]["columns"][0]["items"]], ["Bumper", "Promo", "Adverts", "Holding countdown", "Ident"])
        self.assertNotIn("grids", self.app.break_options(self.app.find(self.app.state(), cid), {"cards": True}))
        st = self.app.breaks_op({"cid": cid, "grid": "inside", "op": {"op": "mode", "mode": "time"}})
        g = st["grids"][1]
        self.assertTrue(g["saved"])
        self.assertEqual([c["name"] for c in g["columns"]], ["Morning", "Afternoon", "Evening"])
        self.assertEqual(len(g["columns"][0]["items"]), 5, "the standard order is kept as the first column")
        ch = self.app.find(self.app.state(), cid)
        self.assertEqual(list(self.app.break_options(ch, {"cards": True})["grids"]), ["inside"])
        with self.assertRaises(ValueError):
            self.app.breaks_op({"cid": cid, "grid": "between", "op": {"op": "add", "kind": "x", "column": 0}})
        st = self.app.breaks_op({"cid": cid, "grid": "inside", "op": {"op": "reset"}})
        self.assertFalse(st["grids"][1]["saved"])

    def test_the_job_searches_once_for_what_the_channels_need(self):
        cid = self.channel("Films", episodes("a", 12, 1500))
        self.app.someone_watching = lambda: False
        looked = []
        self.app.breaks.look = lambda url, key, e, methods=(): (looked.append((e["id"], tuple(methods))) or {"sil": [], "scn": []})
        s = self.app.state()
        ch = self.app.find(s, cid)
        ch["mid_break_seconds"], ch["place_how"] = 120, "times"
        self.app.save(s)
        self.assertIn("Nothing new", self.app.breaks_job(now=NOW)["said"], "set times need no search")
        ch["place_how"] = "scene"
        self.app.save(s)
        self.app.breaks_job(now=NOW, most=100)
        self.assertTrue(looked and all(m == ("scene",) for _, m in looked))
        n = len(looked)
        self.app.breaks_job(now=NOW, most=100)
        self.assertEqual(len(looked), n, "each programme once")

    def test_the_page_and_the_answers(self):
        cid = self.channel("Comedy", episodes("a", 3, 1500))
        token = self.app.state()["token"]
        for f in ("breaks.html", "breaks.js", "breaks.css"):
            self.assertTrue(os.path.isfile(os.path.join(TV, f)))
        html = open(os.path.join(TV, "breaks.html"), encoding="utf-8").read()
        for need in ('role="status"', 'role="alert"', 'lang="en-GB"', "<h1>", 'class="skip"'):
            self.assertIn(need, html)
        self.assertNotIn("role=\"grid\"", open(os.path.join(TV, "breaks.js"), encoding="utf-8").read())
        self.assertEqual(self.app.breaks_state("")["cid"], cid)
        self.assertTrue(token)


if __name__ == "__main__":
    unittest.main()
