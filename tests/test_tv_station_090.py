"""Create your own TV channel 0.9.0: Fit for Adverts and a break length for each column (DASH-549), and the holding
countdown and Back soon counting what comes after them (DASH-550). Timings are checked on made-up clip lengths."""
import itertools
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT  # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "tv-station"))
import breakgrid  # noqa: E402
import schedule  # noqa: E402
from test_tv_station_020 import App, NOW, episodes  # noqa: E402
from test_tv_station_080 import A, CLIPS, OPTS, clip  # noqa: E402

GAP = A["end"] - A["content_end"]  # 300 seconds


def col(*items):
    return [{"kind": k, "times": n} if not isinstance(n, str) else {"kind": k, "times": 1, "fit": True} for k, n in items]


def with_ads(*lengths):
    return {**CLIPS, "extras": [clip(f"ad{i}", d) for i, d in enumerate(lengths)]}


def contiguous(test, pieces, start, end):
    test.assertAlmostEqual(pieces[0]["start"], start)
    test.assertAlmostEqual(pieces[-1]["end"], end)
    for a, b in zip(pieces, pieces[1:]):
        test.assertAlmostEqual(a["end"], b["start"], msg="no gap and no overlap")


def adverts(pieces):
    return [p for p in pieces if p.get("role") == "extra"]


class TheFitItem(unittest.TestCase):
    def test_fit_is_for_adverts_only_and_survives_cleaning(self):
        g = breakgrid.apply(breakgrid.new_grid(), {"op": "add", "kind": "adverts", "column": 0, "times": "fit"})
        self.assertEqual(g["columns"][0][0], {"kind": "adverts", "times": 1, "fit": True})
        self.assertEqual(breakgrid.clean(g)["columns"][0][0]["fit"], True)
        g = breakgrid.apply(g, {"op": "times", "column": 0, "index": 0, "times": 3})
        self.assertNotIn("fit", g["columns"][0][0])
        g = breakgrid.apply(g, {"op": "times", "column": 0, "index": 0, "times": "fit"})
        self.assertTrue(g["columns"][0][0]["fit"])
        g = breakgrid.apply(g, {"op": "add", "kind": "promo", "column": 0})
        with self.assertRaises(breakgrid.GridError):
            breakgrid.apply(g, {"op": "times", "column": 0, "index": 1, "times": "fit"})
        self.assertEqual(breakgrid.item_words(g["columns"][0][0]), "Your own short videos, fit")

    def test_the_break_length_of_a_column(self):
        g = breakgrid.new_grid(count=3)
        self.assertEqual(breakgrid.length_of(g, 0), 0)
        g = breakgrid.apply(g, {"op": "length", "column": 2, "seconds": 600})
        self.assertEqual((breakgrid.length_of(g, 2), breakgrid.length_of(g, 1)), (600, 0))
        self.assertEqual(breakgrid.clean(g)["lengths"][2], 600)
        self.assertEqual(breakgrid.length_words(120), "2 minutes")
        self.assertEqual(breakgrid.length_words(0), "Automatic")
        self.assertEqual(breakgrid.length_words(1800), "30 minutes")
        for bad in (45, 7200, "x"):
            with self.assertRaises(breakgrid.GridError):
                breakgrid.apply(g, {"op": "length", "column": 0, "seconds": bad})
        self.assertEqual(breakgrid.clean({"mode": "random", "columns": [[]], "lengths": ["x", 5, 400]})["lengths"], [0, 0, 400, 0, 0, 0, 0])

    def test_a_grid_saved_before_has_automatic_lengths(self):
        self.assertEqual(breakgrid.clean({"mode": "random", "columns": [[]]})["lengths"], [0] * 7)

    def test_fit_adverts_never_cuts_and_never_runs_over(self):
        sets = [(), (20,), (500,), (10, 20, 30), (45, 45, 45, 45), (7, 11, 13, 17, 19, 23), (299, 5)]
        for lens, room in itertools.product(sets, (0, 4, 10, 29, 31, 60, 119, 300)):
            ads = [clip(f"a{i}", d) for i, d in enumerate(lens)]
            for turn in range(4):
                got = schedule.fit_adverts(ads, room, turn)
                self.assertLessEqual(sum(float(c["dur"]) for c in got), room + 1e-9, (lens, room, turn))
                self.assertEqual(len({c["id"] for c in got}), len(got), "each once")
                left = room - sum(float(c["dur"]) for c in got)
                self.assertTrue(all(float(c["dur"]) > left for c in ads if c not in got), f"as many as fit {(lens, room, turn)}")

    def test_every_advert_gets_a_turn(self):
        ads = [clip(f"a{i}", 100) for i in range(4)]
        firsts = {schedule.fit_adverts(ads, 150, turn)[0]["id"] for turn in range(4)}
        self.assertEqual(firsts, {"a0", "a1", "a2", "a3"})

    def test_fit_fills_a_break_and_the_countdown_makes_up_the_time(self):
        column = col(("bumper", 1), ("adverts", "fit"), ("holding", 1), ("ident", 1))
        for lens in ((), (20,), (500,), (40, 50), (33, 47, 61), (7, 13)):
            out = schedule.plan_break_grid(A, [A], with_ads(*lens), OPTS, column)
            contiguous(self, out, A["content_end"], A["end"])
            ads = adverts(out)
            for p in ads:
                self.assertAlmostEqual(p["end"] - p["start"], float(p["clip"]["dur"]), msg="an advert is never cut", delta=1.0)
            self.assertEqual(out[-1]["clip"]["id"][:2], "id")
            h = next(p for p in out if p["kind"] == "holding")
            self.assertEqual(h["holding"]["words"], "countdown")
            self.assertEqual(h["until"], A["end"])
            self.assertAlmostEqual(h["end"] + (out[-1]["end"] - out[-1]["start"]), A["end"])
            self.assertEqual(kind_order(out)[0], "bumper")

    def test_with_too_little_left_for_any_advert_the_countdown_has_it(self):
        out = schedule.plan_break_grid(A, [A], with_ads(295), OPTS, col(("bumper", 1), ("adverts", "fit"), ("holding", 1), ("ident", 1)), 0)
        self.assertEqual(adverts(out), [])
        self.assertGreater(next(p for p in out if p["kind"] == "holding")["end"] - next(p for p in out if p["kind"] == "holding")["start"], 250)

    def test_one_very_long_advert_is_left_out_rather_than_cut(self):
        out = schedule.plan_break_grid(A, [A], with_ads(900), OPTS, col(("adverts", "fit"), ("holding", 1)))
        self.assertEqual(kind_order(out), ["holding"])

    def test_no_adverts_at_all(self):
        out = schedule.plan_break_grid(A, [A], {**CLIPS, "extras": []}, OPTS, col(("adverts", "fit"), ("holding", 1)))
        self.assertEqual(kind_order(out), ["holding"])

    def test_fit_takes_what_fixed_items_leave(self):
        for promos in (0, 1, 3):
            column = col(("promo", promos), ("adverts", "fit"), ("holding", 1)) if promos else col(("adverts", "fit"), ("holding", 1))
            out = schedule.plan_break_grid(A, [A], with_ads(10, 20, 30, 40), OPTS, column)
            contiguous(self, out, A["content_end"], A["end"])
            fixed = [p for p in out if p.get("role") == "filler"]
            self.assertEqual(len(fixed), promos, "the other items keep their counts")

    def test_the_break_length_limits_what_plays_and_the_rest_is_the_countdown(self):
        column = col(("adverts", "fit"), ("holding", 1), ("ident", 1))
        for length in (120, 180, 240):
            out = schedule.plan_break_grid(A, [A], with_ads(30, 30, 30, 30, 30, 30, 30, 30, 30, 30), OPTS, column, length)
            contiguous(self, out, A["content_end"], A["end"])
            played = sum(p["end"] - p["start"] for p in out if p["kind"] == "clip")
            self.assertLessEqual(played, length + 1.0, length)
            h = next(p for p in out if p["kind"] == "holding")
            self.assertGreater(h["end"] - h["start"], GAP - length - 1)
        out = schedule.plan_break_grid(A, [A], with_ads(30, 30, 30, 30, 30, 30, 30, 30, 30, 30), OPTS, column, 0)
        self.assertGreaterEqual(len(adverts(out)), 8, "Automatic uses the whole gap")

    def test_a_length_longer_than_the_gap_is_the_gap(self):
        out = schedule.plan_break_grid(A, [A], with_ads(30, 30), OPTS, col(("adverts", "fit"), ("holding", 1)), 1800)
        contiguous(self, out, A["content_end"], A["end"])

    def test_a_break_inside_a_programme_uses_its_columns_length(self):
        column = col(("bumper", 1), ("adverts", "fit"), ("back_soon", 1), ("bumper", 1))
        ads = with_ads(*([20] * 30))
        long = schedule.plan_mid_grid(100.0, 600.0, ads, 5, column, OPTS, A)
        short = schedule.plan_mid_grid(100.0, 600.0, ads, 5, column, OPTS, A, 120)
        self.assertAlmostEqual(short[-1]["end"] - short[0]["start"], 120.0, delta=1.0)
        self.assertAlmostEqual(long[-1]["end"] - long[0]["start"], 600.0, delta=1.0)
        self.assertGreater(len(adverts(long)), len(adverts(short)))
        for out in (long, short):
            self.assertTrue(all(p["mid"] for p in out))

    def test_a_column_a_break_does_not_fit_has_a_warning_and_still_starts_on_time(self):
        g = breakgrid.new_grid("random", [col(("bumper", 2), ("promo", 3), ("ident", 1), ("adverts", "fit"), ("holding", 1))])
        short = {"bumper": 10, "promo": 40, "ident": 15}
        self.assertEqual(breakgrid.minimum_seconds(g["columns"][0], short), 155.0)
        self.assertEqual(breakgrid.warning(g, 0, short), "", "Automatic with no gap known has no warning")
        g = breakgrid.apply(g, {"op": "length", "column": 0, "seconds": 120})
        said = breakgrid.warning(g, 0, short)
        self.assertIn("at least 2 minutes 35 seconds", said)
        self.assertIn("but the break is 2 minutes", said)
        self.assertIn("starts on time", said)
        g = breakgrid.apply(g, {"op": "length", "column": 0, "seconds": 180})
        self.assertEqual(breakgrid.warning(g, 0, short), "")
        # and the plan still ends on the start, whatever it had to leave out
        out = schedule.plan_break_grid(A, [A], with_ads(25), OPTS, col(("bumper", 2), ("promo", 3), ("ident", 1), ("adverts", "fit"), ("holding", 1)), 120)
        contiguous(self, out, A["content_end"], A["end"])

    def test_fixed_items_that_overrun_the_break_still_leave_the_start_on_time(self):
        long_items = {**CLIPS, "fillers": [clip(f"f{i}", 90) for i in range(6)], "extras": [clip("ad", 20)]}
        out = schedule.plan_break_grid(A, [A], long_items, OPTS, col(("promo", 6), ("adverts", "fit"), ("holding", 1), ("ident", 1)), 120)
        contiguous(self, out, A["content_end"], A["end"])
        self.assertEqual(out[-1]["clip"]["id"][:2], "id", "the ident is the last to go")


def kind_order(pieces):
    return [p.get("role") or p["kind"] for p in pieces]


AFTER_KINDS = {"bumper": [clip("b9", 4)], "promo": [clip("p9", 25)], "ident": [clip("i9", 5)], "adverts": [clip("x9", 18)],
               "other_promo": [clip("o9", 22, role="promo", cid="you", airs=9e9)], "coming_promo": [clip("c9", 21, role="promo", cid="me", airs=9e9)]}


class TheCountdownCountsWhatComesAfter(unittest.TestCase):
    def pools(self):
        return {**CLIPS, "bumpers": AFTER_KINDS["bumper"], "idents": AFTER_KINDS["ident"], "extras": AFTER_KINDS["adverts"],
                "fillers": AFTER_KINDS["promo"] + AFTER_KINDS["other_promo"] + AFTER_KINDS["coming_promo"]}

    def test_every_combination_of_kinds_after_the_countdown(self):
        kinds = ["bumper", "promo", "ident", "adverts", "other_promo", "coming_promo"]
        for n in range(0, 4):
            for after in itertools.permutations(kinds, n):
                for which in ("holding", "back_soon"):
                    column = col((which, 1), *[(k, 1) for k in after])
                    out = schedule.plan_break_grid(A, [A], self.pools(), OPTS, column)
                    contiguous(self, out, A["content_end"], A["end"])
                    h = next(p for p in out if p["kind"] == "holding")
                    behind = sum(p["end"] - p["start"] for p in out if p["start"] >= h["end"] - 1e-9 and p is not h)
                    self.assertAlmostEqual(h["until"] - h["end"], behind, msg=f"{which} {after}")
                    self.assertEqual(h["until"], A["end"], "the clock reaches zero as the programme starts")
                    self.assertEqual(h["holding"]["words"], "countdown" if which == "holding" else "back_soon")

    def test_the_classic_break_counts_through_its_ident(self):
        out = schedule.plan_break(A, [A], CLIPS, {"seed": 7, "cards": True, "fill_most": 3})
        h = next(p for p in out if p["kind"] == "holding")
        self.assertEqual(h["until"], A["end"])
        self.assertAlmostEqual(h["until"] - h["end"], out[-1]["end"] - out[-1]["start"])

    def test_the_classic_break_inside_a_programme_counts_through_its_closing_bumper(self):
        out = schedule.plan_mid_break(100.0, 200.0, CLIPS, 5, 3)
        h = next(p for p in out if p["kind"] == "holding")
        self.assertEqual(h["until"], out[-1]["end"])
        self.assertAlmostEqual(h["until"] - h["end"], out[-1]["end"] - out[-1]["start"])

    def test_a_break_inside_a_programme_counts_to_its_return(self):
        for after in ([], [("bumper", 1)], [("promo", 1), ("ident", 1)]):
            column = col(("adverts", 1), ("holding", 1), *after)
            out = schedule.plan_mid_grid(100.0, 300.0, self.pools(), 3, column, OPTS, A)
            h = next(p for p in out if p["kind"] == "holding")
            self.assertAlmostEqual(h["until"], out[-1]["end"])
            self.assertAlmostEqual(h["until"] - h["end"], sum(p["end"] - p["start"] for p in out if p["start"] >= h["end"] - 1e-9 and p is not h))


class WhenALengthCannotBeRead(unittest.TestCase):
    def test_the_length_last_seen_is_used_and_said(self):
        memory = {}
        clips = {"idents": [clip("i", 5)], "bumpers": [clip("b", 3)], "extras": [], "fillers": [], "sting": None}
        self.assertEqual(schedule.remember_lengths(clips, memory), [])
        self.assertEqual(memory, {"i": 5.0, "b": 3.0})
        clips = {"idents": [clip("i", 0)], "bumpers": [clip("b", None), clip("new", 0)], "extras": [], "fillers": [], "sting": None}
        said = schedule.remember_lengths(clips, memory)
        self.assertEqual((clips["idents"][0]["dur"], clips["bumpers"][0]["dur"], clips["bumpers"][1]["dur"]), (5.0, 3.0, 0))
        self.assertEqual(len(said), 2)
        self.assertIn("last seen", said[0])


# The file lists (DASH-546) ---------------------------------------------------------------------------------------------
import filelist  # noqa: E402


def sample_state(n=0):
    shared = {"idents": [], "clips": [], "extras": [{"id": "e1", "src": "file:Sale.mp4", "dur": 30.0, "title": "Sale.mp4", "has_audio": True}], "psa": []}
    own = {"idents": [{"id": "i1", "src": "file:Ident.mp4", "dur": 4.0, "title": "Ident.mp4", "has_audio": False}], "clips": [], "extras": [], "psa": []}
    for i in range(n):
        shared["clips"].append({"id": f"c{i}", "src": f"file:Clip {i:04d}.mp4", "dur": 10.0 + i % 200, "title": f"Clip {i:04d}.mp4", "has_audio": i % 2 == 0})
    return {"shared": shared, "channels": [{"id": "A", "name": "Comedy", "own": own, "idents": "both", "clips": "shared"},
                                           {"id": "B", "name": "Drama", "own": {"idents": [], "clips": []}, "idents": "none", "clips": "none", "extras": "none"}]}


class TheFileLists(unittest.TestCase):
    def test_rows_say_where_a_file_is_kept_and_who_plays_it(self):
        got = {r["key"]: r for r in filelist.rows(sample_state(), {"Sale.mp4": (2048, 1e9)})}
        self.assertEqual(got["extras:e1"]["held"], ["station"])
        self.assertEqual(got["extras:e1"]["used_by"], ["A"], "channel B chose none, A has the default, both")
        self.assertEqual((got["extras:e1"]["size"], got["extras:e1"]["added"]), (2048, 1e9))
        self.assertEqual(got["idents:i1"]["held"], ["A"])
        self.assertEqual(got["idents:i1"]["used_by"], ["A"])
        self.assertIsNone(got["idents:i1"]["size"])

    def test_search_filters_and_sorts(self):
        rows = filelist.rows(sample_state(60))
        self.assertEqual(filelist.query(rows, q="clip 0007")["total"], 1)
        self.assertEqual(filelist.query(rows, kind="idents")["total"], 1)
        self.assertEqual(filelist.query(rows, scope="this", channel="B")["total"], 0)
        self.assertEqual(filelist.query(rows, scope="this", channel="A")["total"], 62)
        self.assertEqual(filelist.query(rows, scope="unused")["total"], 0)
        self.assertEqual(filelist.query(rows, sound="without", kind="clips")["total"], 30)
        self.assertEqual(filelist.query(rows, length="short")["total"], 1)
        self.assertEqual(filelist.query(rows, length="long")["total"], 0)
        by = filelist.query(rows, kind="clips", sort="length", descending=True)["rows"]
        self.assertEqual([r["dur"] for r in by], sorted((r["dur"] for r in by), reverse=True))
        self.assertEqual(filelist.query(rows, sort="size")["total"], 62, "a file with no size still sorts, last")

    def test_a_list_of_thousands_is_one_page_at_a_time(self):
        rows = filelist.rows(sample_state(5000))
        first = filelist.query(rows, kind="clips")
        self.assertEqual((len(first["rows"]), first["total"], first["pages"], first["first"], first["last"]), (50, 5000, 100, 1, 50))
        last = filelist.query(rows, kind="clips", page=999)
        self.assertEqual((last["page"], last["first"], last["last"]), (100, 4951, 5000))
        again = filelist.query(rows, kind="clips", page=2)
        self.assertEqual([r["key"] for r in again["rows"]], [r["key"] for r in filelist.query(rows, kind="clips", page=2)["rows"]], "stable order")
        self.assertEqual(filelist.query(rows, kind="clips", size=10000)["rows"].__len__(), 50, "never more than 50 at once")

    def test_several_files_added_and_removed_together(self):
        st = sample_state(5)
        keys = [f"clips:c{i}" for i in range(5)]
        self.assertEqual(filelist.change(st, keys, "B", "add"), 5)
        self.assertEqual(len(st["channels"][1]["own"]["clips"]), 5)
        self.assertEqual(filelist.change(st, keys, "B", "add"), 0, "nothing is added twice")
        self.assertEqual(filelist.change(st, keys[:2], "B", "remove"), 2)
        self.assertEqual(len(st["shared"]["clips"]), 5, "the station's own list is not touched")
        self.assertEqual(filelist.change(st, keys, "station", "remove"), 5)
        for bad in (([], "B", "add"), (keys, "Z", "add"), (["zz:1"], "B", "add"), (keys, "B", "delete"), (["clips:c0"] * 501, "B", "add")):
            with self.assertRaises(filelist.ListError):
                filelist.change(st, *bad)


# PSA (DASH-545) -----------------------------------------------------------------------------------------------------
class ThePsa(unittest.TestCase):
    def test_psa_is_a_kind_with_a_count_and_plays_in_a_break(self):
        self.assertIn("psa", breakgrid.KINDS)
        g = breakgrid.apply(breakgrid.new_grid(), {"op": "add", "kind": "psa", "column": 0, "times": 2})
        self.assertEqual(g["columns"][0][0], {"kind": "psa", "times": 2})
        clips = {**CLIPS, "psa": [clip("p1", 20), clip("p2", 25), clip("p3", 30)]}
        out = schedule.plan_break_grid(A, [A], clips, OPTS, g["columns"][0] + [{"kind": "holding", "times": 1}])
        got = [p for p in out if p.get("role") == "psa"]
        self.assertEqual(len(got), 2)
        self.assertEqual(len({p["clip"]["id"] for p in got}), 2, "each once in a break")
        contiguous(self, out, A["content_end"], A["end"])

    def test_a_psa_with_no_files_is_left_out(self):
        out = schedule.plan_break_grid(A, [A], CLIPS, OPTS, [{"kind": "psa", "times": 3}, {"kind": "holding", "times": 1}])
        self.assertEqual(kind_order(out), ["holding"])


if __name__ == "__main__":
    unittest.main()


class TheApp(App):
    def test_the_breaks_page_has_lengths_fit_and_warnings(self):
        cid = self.channel("Comedy", episodes("a", 6, 1500))
        self.app.breaks_op({"cid": cid, "grid": "between", "op": {"op": "add", "kind": "adverts", "column": 0, "times": "fit"}})
        st = self.app.breaks_op({"cid": cid, "grid": "between", "op": {"op": "length", "column": 0, "seconds": 300}})
        col = st["grids"][0]["columns"][0]
        self.assertEqual((col["length"], col["length_words"]), (300, "5 minutes"))
        self.assertTrue(any(i["fit"] for i in col["items"]))
        self.assertEqual(st["lengths"][0], {"seconds": 0, "name": "Automatic"})
        self.assertEqual(len(st["lengths"]), 13)
        self.assertEqual(col["warning"], "", "no clips of a kind, so nothing is known to need room")
        with self.assertRaises(self.app.breakgrid.GridError):
            self.app.breaks_op({"cid": cid, "grid": "between", "op": {"op": "length", "column": 0, "seconds": 61}})
        self.assertEqual(self.app.break_options(self.app.find(self.app.state(), cid), {"cards": True})["grids"]["between"]["lengths"][0], 300)

    def test_a_psa_is_kept_in_the_lists_and_played_by_the_channels_that_use_it(self):
        cid = self.channel("Comedy", episodes("a", 6, 1500))
        s = self.app.state()
        s["shared"]["psa"] = [{"id": "p1", "src": "file:Safety.mp4", "dur": 25.0, "title": "Safety.mp4", "has_audio": True}]
        self.app.save(s)
        ch = self.app.find(self.app.state(), cid)
        self.assertEqual([c["id"] for c in self.app.clips_for(self.app.state(), ch)["psa"]], ["p1"])
        self.app.channels_post({"action": "choose", "id": f"{cid}:psa", "value": "none"}, now=NOW)
        self.assertEqual(self.app.clips_for(self.app.state(), self.app.find(self.app.state(), cid))["psa"], [])
        self.assertEqual(self.app.breaks_state(cid)["available"]["psa"], 0)
        ids = [i["id"] for i in self.app.clips_page()["items"]]
        self.assertIn("psa:p1", ids)
        self.assertIn("add:psa", ids)

    def test_the_file_lists_page_and_a_bulk_change(self):
        cid = self.channel("Comedy", episodes("a", 6, 1500))
        s = self.app.state()
        s["shared"]["clips"] = [{"id": f"c{i}", "src": f"file:C{i}.mp4", "dur": 20.0 + i, "title": f"C{i}.mp4", "has_audio": True} for i in range(120)]
        self.app.save(s)
        st = self.app.files_state({"kind": "clips", "channel": cid, "sort": "length", "order": "desc"})
        self.assertEqual((st["total"], len(st["rows"]), st["pages"], st["cid"]), (120, 50, 3, cid))
        self.assertEqual(st["rows"][0]["dur"], 139.0)
        self.assertEqual(st["rows"][0]["held_names"], ["The station"])
        st = self.app.files_state({"q": "c11", "kind": "bad", "sort": "bad", "page": "x"})
        self.assertEqual(st["total"], 11 + 0, "the search matches C11 and C110 to C119")
        said = self.app.files_op({"op": "add", "to": cid, "keys": ["clips:c1", "clips:c2"]})
        self.assertEqual(said["changed"], 2)
        self.assertEqual(len(self.app.find(self.app.state(), cid)["own"]["clips"]), 2)
        self.assertIn("Comedy", said["said"])
        self.assertEqual(self.app.files_op({"op": "remove", "to": cid, "keys": ["clips:c1"]})["changed"], 1)
        item = self.app.files_page()["items"][0]
        self.assertTrue(item["link"]["url"].endswith("/files"))


if __name__ == "__main__":
    unittest.main()
