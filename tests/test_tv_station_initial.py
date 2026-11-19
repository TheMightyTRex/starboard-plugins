"""Create your own TV channel 0.3.2 (owner, 19 November 2026): "There is no way to create a schedule from the channel
list once you add items - can you put a Create initial schedule to put something together to edit in the schedule
grid." """
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT  # noqa: E402
from test_tv_station_020 import NOW, App, episodes  # noqa: E402

TV = os.path.join(ROOT, "tv-station")
sys.path.insert(0, TV)
import grid  # noqa: E402
import schedule  # noqa: E402
import suggest  # noqa: E402

A, B, F = "a" * 32, "b" * 32, "f" * 32


def film(fid, mins=100):
    return {"id": fid, "dur": mins * 60, "title": f"Film {fid[:2]}", "group": fid, "kind": "Movie"}


class FromTheLineUp(unittest.TestCase):
    def info(self, sid):
        return {"id": sid, "name": f"Show {sid[:2]}", "episodes": episodes(sid[:2], 20, 1500), "unwatched": 0}

    def test_every_series_and_film_watched_or_not(self):
        pool = [("series", A, "Show aa"), ("series", B, "Show bb"), ("film", F, "Film ff")]
        hours = suggest.parse_hours({"weekdays": ["18:00", "20:00"], "weekends": ["19:00", "23:00"]})
        doc, notes = suggest.propose(None, [], NOW, self.info, lambda fid: film(fid), source="channel", pool=pool, hours=hours)
        refs = {s["ref"] for s in doc["slots"]}
        self.assertEqual(refs, {f"s:{A}", f"s:{B}", f"f:{F}"}, "no watch history needed")
        weekdays = [s for s in doc["slots"] if s["day"] < 5]
        self.assertEqual(sorted({s["day"] for s in weekdays}), [0, 1, 2, 3, 4], "series every weekday")
        monday = sorted((s["start"], s["ref"]) for s in doc["slots"] if s["day"] == 0)
        self.assertEqual(monday[0], (18 * 60, f"s:{A}"), "in the channel's order, from the start of the hours")
        self.assertTrue(all(s["ref"].startswith("f:") for s in doc["slots"] if s["day"] >= 5), "films at the weekend")
        self.assertTrue(all(18 * 60 <= s["start"] < 20 * 60 for s in weekdays))
        self.assertTrue(notes)

    def test_nothing_on_the_channel(self):
        doc, notes = suggest.propose(None, [], NOW, self.info, lambda fid: None, source="channel", pool=[],
                                     hours=suggest.parse_hours({"weekdays": ["18:00", "23:00"]}))
        self.assertEqual(doc["slots"], [])
        self.assertIn("What it shows", notes[-1])


class TheButton(App):
    def make(self, lineup):
        cid = self.channel("Comedy", lineup)
        calls = []

        def fake(s, ch, now, source="history", hours=None):
            calls.append((source, hours))
            pool = []
            for e in ch["eras"][-1]["lineup"]:
                kind = "film" if e.get("kind") == "Movie" else "series"
                key = (kind, e["id"] if kind == "film" else e.get("group") or e["id"])
                if key not in [(k, i) for k, i, _ in pool]:
                    pool.append((key[0], key[1], e.get("title") or ""))
            info = lambda sid: {"id": sid, "name": "Show", "episodes": [e for e in ch["eras"][-1]["lineup"] if e.get("group") == sid],  # noqa: E731
                                "unwatched": 0}
            return suggest.propose(None, [], now, info, lambda fid: film(fid), source=source, pool=pool, hours=hours)
        self.app.suggest_for = fake
        return cid, calls

    def test_the_row_and_its_form(self):
        cid, _ = self.make(episodes("aa", 6, 1500))
        rows = {it["id"]: it for it in self.app.channels_page(now=NOW)["items"]}
        it = rows[f"{cid}:initial"]
        self.assertEqual(it["title"], "Create initial schedule")
        self.assertEqual(it["group"], "What it shows")
        self.assertEqual(it["actions"], ["attach"])
        self.assertEqual(it["attach"]["label"], "Create initial schedule")
        self.assertEqual(it["attach"]["value"], "Weekdays 18:00 to 23:00, weekends 12:00 to 23:00")
        self.assertIn(f"/grid?channel={cid}", it["link"]["url"])
        self.assertLessEqual(len(it["detail"]), 200)

    def test_it_makes_an_unsaved_week_to_change_in_the_grid(self):
        lineup = episodes("aa", 30, 1500) + [film(F)]
        cid, calls = self.make(lineup)
        page = self.app.channels_post({"action": "attach", "id": f"{cid}:initial", "value": "Weekdays 19:00 to 22:00, weekends 14:00 to 23:00"}, now=NOW)
        self.assertIn("Made a schedule of", page["said"])
        self.assertEqual(calls[0][0], "channel")
        self.assertEqual(calls[0][1], {"weekdays": (19 * 60, 22 * 60), "weekends": (14 * 60, 23 * 60)})
        draft = self.app.grid_doc(cid, "draft")
        self.assertTrue(draft["slots"])
        self.assertIsNone(self.app.grid_doc(cid), "nothing saved until the owner saves it in the grid")
        st = self.app.grid_state(cid)
        self.assertEqual(st["suggest_from"], "channel")
        self.assertEqual(st["suggest_hours"], {"weekdays": ["19:00", "22:00"], "weekends": ["14:00", "23:00"]})
        row = {it["id"]: it for it in self.app.channels_page(now=NOW)["items"]}[f"{cid}:initial"]
        self.assertEqual(row["state_label"], "Waiting to be saved")
        self.assertEqual(row["attach"]["value"], "Weekdays 19:00 to 22:00, weekends 14:00 to 23:00", "the hours are remembered")

    def test_a_saved_grid_stays_until_the_new_one_is_saved(self):
        lineup = episodes("aa", 30, 1500)
        cid, _ = self.make(lineup)
        saved = grid.empty()
        saved["slots"] = [{"id": "x1", "day": 2, "start": 600, "ref": "f:" + F}]
        saved["films"] = {F: film(F)}
        self.app.grid.store(self.app.grid_folder(), cid, saved)
        page = self.app.channels_post({"action": "attach", "id": f"{cid}:initial", "value": "Weekdays 18:00 to 23:00"}, now=NOW)
        self.assertIn("Your saved grid stays as it is until then", page["said"])
        self.assertEqual(self.app.grid_doc(cid)["slots"][0]["id"], "x1")

    def test_words_it_refuses(self):
        cid, _ = self.make(episodes("aa", 6, 1500))
        with self.assertRaises(ValueError) as e:
            self.app.channels_post({"action": "attach", "id": f"{cid}:initial", "value": "evenings"}, now=NOW)
        self.assertIn("start and an end", str(e.exception))
        with self.assertRaises(ValueError) as e:
            self.app.channels_post({"action": "attach", "id": f"{cid}:initial", "value": "Weekdays 23:00 to 18:00"}, now=NOW)
        self.assertIn("end time after the start time", str(e.exception))
        empty = self.channel("Empty")
        with self.assertRaises(ValueError) as e:
            self.app.channels_post({"action": "attach", "id": f"{empty}:initial", "value": "Weekdays 18:00 to 23:00"}, now=NOW)
        self.assertIn("shows nothing yet", str(e.exception))

    def test_the_real_line_up_is_read_in_order_once_each(self):
        lineup = episodes("aa", 4, 1500) + [film(F), {**film("e" * 32), "title": "Film ff"}] + episodes("bb", 4, 1500)
        cid = self.channel("Films", lineup)
        got = {}
        import suggest as sg
        real = sg.propose
        sg.propose = lambda *a, **k: (got.setdefault("pool", k.get("pool")), (grid.empty(), ["none"]))[1]
        try:
            self.app.jf = lambda path, *a, **k: {}
            self.app.suggest_for(self.app.state(), self.app.find(self.app.state(), cid), NOW, "channel", None)
        finally:
            sg.propose = real
        self.assertEqual([(k, n) for k, _, n in got["pool"]], [("series", "Show aa"), ("film", "Film ff"), ("series", "Show bb")],
                         "in the channel's order; a second copy of a film is left out")
        s = self.app.state()
        self.app.find(s, cid)["order"] = "shuffle"
        self.app.save(s)
        orders = set()
        for day in range(6):
            sg.propose = lambda *a, **k: (got.__setitem__("pool", k.get("pool")), (grid.empty(), ["none"]))[1]
            try:
                self.app.suggest_for(self.app.state(), self.app.find(self.app.state(), cid), NOW + day * 86400, "channel", None)
            finally:
                sg.propose = real
            orders.add(tuple(n for _, _, n in got["pool"]))
        self.assertGreater(len(orders), 1, "a shuffled channel gets a shuffled week")

    def test_reading_the_hours(self):
        h = self.app.initial_hours
        self.assertEqual(h("Weekdays 18:00 to 23:00, weekends 12:00 to 23:00"), {"weekdays": ["18:00", "23:00"], "weekends": ["12:00", "23:00"]})
        self.assertEqual(h("19.30 to 22.00"), {"weekdays": ["19:30", "22:00"], "weekends": ["19:30", "22:00"]})
        self.assertEqual(h("weekends 10:00 to 14:00"), {"weekdays": None, "weekends": ["10:00", "14:00"]})
        self.assertEqual(h("weekdays 9:00 to 11:00"), {"weekdays": ["09:00", "11:00"], "weekends": None})


if __name__ == "__main__":
    unittest.main()
