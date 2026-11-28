"""Create your own TV channel 0.15.0: Shows at set times (DASH-649): rules read from the grid, never stored."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT  # noqa: E402

TV = os.path.join(ROOT, "tv-station")
sys.path.insert(0, TV)
import grid  # noqa: E402
from test_tv_station_grid import FID, FILM, NOW, SID, SID2, eps  # noqa: E402
from test_tv_station_020 import App  # noqa: E402

SHOW = {"id": SID, "name": "Harbour lights"}  # 25 minutes a programme: a slot is 30 minutes


class TheRules(unittest.TestCase):
    def rule(self, doc=None, days=(0, 1, 2, 3, 4), start=19 * 60, n=2, item=SHOW, series=SID, episodes=None):
        return grid.add_rule(doc or grid.empty(), list(days), start, "series", item, n, NOW, episodes or eps(series, 12))

    def test_a_rule_is_slots_one_after_another_on_each_day(self):
        doc, said = self.rule()
        self.assertEqual(len(doc["slots"]), 10)
        self.assertEqual(sorted({s["start"] for s in doc["slots"]}), [19 * 60, 19 * 60 + 30])
        self.assertEqual(said, "Added Harbour lights at 19:00, Monday to Friday, 2 episodes")

    def test_the_slots_read_back_as_the_same_rule(self):
        doc, _ = self.rule()
        got = grid.rules(doc)
        self.assertEqual(len(got), 1)
        self.assertEqual((got[0]["days"], got[0]["start"], got[0]["n"]), ([0, 1, 2, 3, 4], 19 * 60, 2))
        self.assertEqual(got[0]["words"], "Harbour lights, Monday to Friday at 19:00, 2 episodes")

    def test_two_rules_for_one_show_stay_two(self):
        doc, _ = self.rule(days=(0, 1, 2, 3, 4), n=1)
        doc, _ = grid.add_rule(doc, [5, 6], 20 * 60, "series", SHOW, 1, NOW, eps(SID, 12))
        self.assertEqual([r["words"] for r in grid.rules(doc)],
                         ["Harbour lights, Monday to Friday at 19:00, 1 episode", "Harbour lights, Saturday and Sunday at 20:00, 1 episode"])

    def test_a_film_plays_once_a_day(self):
        doc, said = grid.add_rule(grid.empty(), [5, 6], 20 * 60, "film", FILM, 4, NOW)
        self.assertEqual(len(doc["slots"]), 2)
        self.assertEqual(said, "Added A Film at 20:00, Saturday and Sunday")
        self.assertEqual(grid.rules(doc)[0]["words"], "A Film, Saturday and Sunday at 20:00")

    def test_a_clash_refuses_the_whole_rule_and_says_which(self):
        doc, _ = self.rule(days=(0, 1), n=1)
        before = len(doc["slots"])
        with self.assertRaises(grid.GridError) as e:
            grid.add_rule(doc, [0, 1, 2], 19 * 60 + 15, "series", {"id": SID2, "name": "The long field"}, 1, NOW, eps(SID2, 5))
        self.assertIn("would run into Harbour lights", str(e.exception))
        self.assertEqual(len(doc["slots"]), before, "the grid is as it was")

    def test_past_midnight_is_refused_in_words(self):
        with self.assertRaises(grid.GridError) as e:
            self.rule(start=23 * 60 + 30, n=3)
        self.assertIn("would run past midnight", str(e.exception))

    def test_no_day_is_refused(self):
        with self.assertRaises(grid.GridError):
            self.rule(days=())

    def test_removing_a_rule_takes_only_its_slots(self):
        doc, _ = self.rule(n=1)
        doc, _ = grid.add_rule(doc, [5, 6], 20 * 60, "series", SHOW, 1, NOW, eps(SID, 12))
        first = next(r for r in grid.rules(doc) if r["days"] == [0, 1, 2, 3, 4])
        doc, said = grid.remove_rule(doc, first["id"], NOW)
        self.assertEqual([r["days"] for r in grid.rules(doc)], [[5, 6]])
        self.assertIn("Removed Harbour lights, Monday to Friday", said)

    def test_removing_the_last_rule_leaves_an_empty_grid(self):
        doc, _ = self.rule()
        doc, _ = grid.remove_rule(doc, grid.rules(doc)[0]["id"], NOW)
        self.assertEqual((doc["slots"], doc["series"]), ([], {}))

    def test_a_missing_rule_says_so(self):
        with self.assertRaises(grid.GridError):
            grid.remove_rule(grid.empty(), "r00000000", NOW)

    def test_a_grid_made_by_hand_reads_as_rules_and_nothing_is_changed(self):
        doc, sid, _ = grid.add(grid.empty(), 2, 21 * 60, "series", SHOW, NOW, eps(SID, 12))
        doc, _ = grid.stripe(doc, sid, [0, 1, 2, 3, 4], 1, False, NOW)
        before = [dict(s) for s in doc["slots"]]
        got = grid.rules(doc)
        self.assertEqual(got[0]["words"], "Harbour lights, Monday to Friday at 21:00, 1 episode")
        self.assertEqual(doc["slots"], before)

    def test_an_odd_slot_is_its_own_rule(self):
        doc, _ = self.rule(n=1)
        doc, _, _ = grid.add(doc, 6, 11 * 60, "series", SHOW, NOW, eps(SID, 12))
        self.assertEqual(len(grid.rules(doc)), 2)

    def test_the_words(self):
        self.assertEqual(grid.days_words([0, 1, 2, 3, 4, 5, 6]), "every day")
        self.assertEqual(grid.days_words([0, 2, 4]), "Mon, Wed, Fri")
        self.assertEqual(grid.days_words([3]), "Thursday")


class TheOps(App):
    """The page's two changes through the plug-in's own answers, and the rows that say the rules in Starboard's settings."""

    def setUp(self):
        super().setUp()
        self.app.library.lineup = lambda jf, src: eps(SID, 12) if src[0]["kind"] == "series" else [FILM]
        self.cid = self.channel("Comedy")

    def op(self, **body):
        return self.app.grid_op({"cid": self.cid, **body}, now=NOW)

    def test_add_then_remove_a_rule(self):
        got = self.op(op="rule_add", kind="series", id=SID, days=[0, 1, 2, 3, 4], start=19 * 60, n=2)
        self.assertEqual([r["words"] for r in got["rules"]], ["Show A, Monday to Friday at 19:00, 2 episodes"])
        self.assertEqual(got["said"], "Added Show A at 19:00, Monday to Friday, 2 episodes")
        got = self.op(op="rule_remove", rule=got["rules"][0]["id"])
        self.assertEqual((got["rules"], got["slots"]), ([], []))

    def test_a_film(self):
        got = self.op(op="rule_add", kind="film", id=FID, days=[6], start=20 * 60, n=3)
        self.assertEqual([r["words"] for r in got["rules"]], ["A Film, Sunday at 20:00"])

    def test_a_clash_comes_back_as_words_and_changes_nothing(self):
        self.op(op="rule_add", kind="series", id=SID, days=[0], start=19 * 60, n=1)
        with self.assertRaises(self.app.grid.GridError) as e:
            self.op(op="rule_add", kind="film", id=FID, days=[0], start=19 * 60 + 15, n=1)
        self.assertIn("would run into", str(e.exception))
        self.assertEqual(len(self.app.grid_state(self.cid, now=NOW)["rules"]), 1, "the grid is as it was")

    def test_a_bad_id_or_no_day_is_refused(self):
        for body in ({"kind": "series", "id": "no", "days": [0], "start": 0}, {"kind": "series", "id": SID, "days": [], "start": 0},
                     {"kind": "toy", "id": SID, "days": [0], "start": 0}):
            with self.assertRaises(self.app.grid.GridError):
                self.op(op="rule_add", **body)

    def test_starboards_page_puts_the_set_times_first_and_the_grid_as_more(self):
        self.op(op="rule_add", kind="series", id=SID, days=[0, 1, 2, 3, 4], start=19 * 60, n=1)
        page = self.app.schedule_page()
        groups = []
        for it in page["items"]:
            if "menu" not in it and it["group"] not in groups:
                groups.append(it["group"])
        self.assertEqual(groups, ["Shows at set times", "More: plan every slot on a grid"])
        first = page["items"][0]
        self.assertEqual((first["state_label"], first["detail"]), ("1 time", "Show A, Monday to Friday at 19:00, 1 episode"))
        self.assertIn("/times?channel=", first["link"]["url"])

    def test_the_channel_card_has_the_same_row(self):
        self.op(op="rule_add", kind="series", id=SID, days=[5, 6], start=20 * 60, n=1)
        row = next(i for i in self.app.channels_page(now=NOW)["items"] if i["id"] == f"{self.cid}:times")
        self.assertEqual((row["group"], row["state_label"]), ("What plays when", "1 time"))

    def test_a_grid_made_before_shows_as_rules_with_nothing_written(self):
        doc, sid, _ = self.app.grid.add(self.app.grid.empty(), 2, 21 * 60, "series", {"id": SID, "name": "Show A"}, NOW, eps(SID, 12))
        self.app.grid.store(self.app.grid_folder(), self.cid, doc)
        got = self.app.grid_state(self.cid, now=NOW)
        self.assertEqual([r["words"] for r in got["rules"]], ["Show A, Wednesday at 21:00, 1 episode"])


class TheImage(unittest.TestCase):
    """Everything the app imports or serves is in the Dockerfile's COPY line, so the image starts."""

    def test_every_module_and_page_is_copied(self):
        import re
        docker = open(os.path.join(TV, "Dockerfile"), encoding="utf-8").read()
        copied = set()
        for line in re.findall(r"^COPY (.*?) /app/", docker, re.M):
            copied |= set(line.split())
        src = open(os.path.join(TV, "app.py"), encoding="utf-8").read()
        mods = {m + ".py" for m in re.findall(r"^import (\w+)$", src, re.M) if os.path.exists(os.path.join(TV, m + ".py"))}
        served = set(re.findall(r'\("([\w.-]+\.(?:html|js|css|woff2))"', src))
        for name in sorted(mods | {n for n in served if os.path.exists(os.path.join(TV, n))}):
            self.assertIn(name, copied, name)
        for name in ("times.html", "times.js", "times.css", "styles.py", "explain.py"):
            self.assertIn(name, copied, name)


if __name__ == "__main__":
    unittest.main()
