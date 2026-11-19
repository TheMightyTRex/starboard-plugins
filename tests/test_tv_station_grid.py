"""Create your own TV channel (tv-station): the schedule grid (DASH-481). The store, every change and its
alternative to dragging, copy a day, stripe, where a series starts, the week worked out, the guide following the grid,
the suggester with made-up history, and the grid page's answers through the plug-in's own web server."""
import http.server
import json
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT  # noqa: E402

TV = os.path.join(ROOT, "tv-station")
sys.path.insert(0, TV)
import grid  # noqa: E402
import guide  # noqa: E402
import schedule  # noqa: E402
import suggest  # noqa: E402

NOW = 1794600123.0  # Tuesday 18 November 2026, evening
SID = "a" * 32
SID2 = "b" * 32
FID = "c" * 32


def eps(sid, n, dur=1500, title="Show A"):
    return [{"id": f"{sid[:30]}{i:02d}", "dur": dur, "title": title, "group": sid, "kind": "Episode", "s": 1 + (i - 1) // 10,
             "e": 1 + (i - 1) % 10, "ep": f"Part {i}", "plot": "", "art": sid, "backdrop": sid} for i in range(1, n + 1)]


FILM = {"id": FID, "dur": 6000, "title": "A Film", "group": FID, "kind": "Movie", "year": 1999}


def doc_with_series(n=20, day=0, start=20 * 60):
    d, slot, _ = grid.add(grid.empty(), day, start, "series", {"id": SID, "name": "Show A"}, NOW, eps(SID, n))
    return d, slot


def plays_of(view, day=None):
    return [(s["day"], grid.hm(s["start"]), s["detail"]) for s in view["slots"] if day is None or s["day"] == day]


class Store(unittest.TestCase):
    def test_kept_as_a_small_file_and_read_back(self):
        d, _ = doc_with_series()
        with tempfile.TemporaryDirectory() as folder:
            grid.store(folder, "abcd1234", d)
            self.assertLess(os.path.getsize(grid.path(folder, "abcd1234")), 20000)
            self.assertEqual(grid.load(folder, "abcd1234")["slots"], d["slots"])
            self.assertIsNone(grid.load(folder, "nothere"))

    def test_anything_out_of_shape_is_left_out(self):
        d, _ = doc_with_series()
        raw = json.loads(json.dumps(d))
        raw["slots"] += [{"id": "x", "day": 9, "start": 0, "ref": f"s:{SID}"}, {"id": "y", "day": 1, "start": 7, "ref": f"s:{SID}"},
                         {"id": "z", "day": 1, "start": 60, "ref": "s:missing"}, "nonsense"]
        self.assertEqual(len(grid.clean(raw)["slots"]), 1)
        self.assertEqual(grid.clean("not a grid"), grid.empty())


class Changes(unittest.TestCase):
    def test_a_slot_takes_its_longest_programme_rounded_to_15_minutes(self):
        d, _ = doc_with_series()
        self.assertEqual(grid.length(d, f"s:{SID}"), 30)
        d, _, _ = grid.add(d, 5, 20 * 60, "film", FILM, NOW)
        self.assertEqual(grid.length(d, f"f:{FID}"), 105)

    def test_a_clash_is_refused_and_named(self):
        d, _ = doc_with_series()
        with self.assertRaises(grid.GridError) as e:
            grid.add(d, 0, 20 * 60 + 15, "film", FILM, NOW)
        self.assertIn("would run into Show A at Monday 20:00", str(e.exception))
        with self.assertRaises(grid.GridError):
            grid.add(d, 0, 20 * 60 + 5, "film", FILM, NOW)  # not on the quarter hour

    def test_the_week_wraps_round(self):
        d, _, _ = grid.add(grid.empty(), 6, 23 * 60 + 30, "film", FILM, NOW)  # Sunday 23:30 to 01:15
        with self.assertRaises(grid.GridError):
            grid.add(d, 0, 30, "series", {"id": SID, "name": "Show A"}, NOW, eps(SID, 3))

    def test_drag_and_its_alternatives_do_the_same(self):
        """A drag sends move; Move to does too; Move earlier and later nudge; pick then place is a move."""
        d, slot = doc_with_series()
        dragged, said = grid.move(d, slot, 2, 21 * 60, NOW)
        self.assertEqual(said, "Moved Show A to Wednesday 21:00")
        moved_to, _ = grid.move(d, slot, 2, 21 * 60, NOW)
        self.assertEqual(dragged["slots"], moved_to["slots"])
        later, _ = grid.nudge(d, slot, 15, NOW)
        self.assertEqual(grid.find(later, slot)["start"], 20 * 60 + 15)
        d2, s2, _ = grid.add(grid.empty(), 0, 0, "film", FILM, NOW)
        before, said = grid.nudge(d2, s2, -15, NOW)
        self.assertEqual((grid.find(before, s2)["day"], grid.find(before, s2)["start"]), (6, 23 * 60 + 45))
        self.assertIn("Sunday 23:45", said)
        gone, said = grid.remove(d, slot, NOW)
        self.assertEqual(gone["slots"], [])
        self.assertEqual(gone["series"], {}, "a series no slot uses is left out")
        self.assertEqual(d["slots"][0]["start"], 20 * 60, "every change returns a new grid; the old one is untouched")

    def test_copy_a_day_replaces_the_days_copied_to(self):
        d, slot = doc_with_series()
        d, _, _ = grid.add(d, 2, 9 * 60, "film", FILM, NOW)
        d, said = grid.copy_day(d, 0, [1, 2, 3], NOW)
        self.assertEqual(said, "Copied Monday to Tuesday, Wednesday, Thursday, in place of 1 slot there")
        v = grid.view(d, grid.week_start(NOW))
        self.assertEqual([(s["day"], s["start"]) for s in v["slots"]], [(k, 20 * 60) for k in range(4)])
        self.assertEqual([s["detail"][:19] for s in v["slots"]], [f"Series 1, episode {k}" for k in (1, 2, 3, 4)],
                         "the copies carry on with the next episodes")
        with self.assertRaises(grid.GridError):
            grid.copy_day(d, 5, [6], NOW)  # Saturday is empty

    def test_stripe_fills_the_weekdays_with_the_next_episodes(self):
        d, slot = doc_with_series(30)
        d, said = grid.stripe(d, slot, [0, 1, 2, 3, 4], 2, False, NOW)
        self.assertIn("Mon, Tue, Wed, Thu, Fri: 2 episodes a day, 10 slots", said)
        v = grid.view(d, grid.week_start(NOW))
        self.assertEqual(len(v["slots"]), 10)
        self.assertEqual([s["start"] for s in v["slots"] if s["day"] == 3], [20 * 60, 20 * 60 + 30])
        numbers = [(int(s["detail"].split()[1][:-1]), int(s["detail"].split()[3][:-1])) for s in v["slots"]]
        self.assertEqual(numbers, [(1, k) for k in range(1, 11)], "series 1, episodes 1 to 10 in order")
        nxt = grid.view(d, grid.week_start(NOW) + 7 * 86400)
        self.assertTrue(nxt["slots"][0]["detail"].startswith("Series 2, episode 1"), "the next week carries on")
        d2, _ = grid.stripe(d, slot, [0], 1, True, NOW)
        self.assertEqual(sorted({s["day"] for s in d2["slots"]}), [0, 1, 2, 3, 4, 5, 6], "weekends too")

    def test_a_stripe_that_would_clash_changes_nothing(self):
        d, slot = doc_with_series()
        d, _, _ = grid.add(d, 3, 20 * 60, "film", FILM, NOW)
        with self.assertRaises(grid.GridError):
            grid.stripe(d, slot, [0, 1, 2, 3, 4], 1, False, NOW)
        self.assertEqual(len(d["slots"]), 2)


class SeriesStart(unittest.TestCase):
    def test_from_the_first_from_an_episode_and_from_the_next_not_watched(self):
        d, slot = doc_with_series(25)
        monday = grid.week_start(NOW)
        self.assertEqual(grid.view(d, monday)["slots"][0]["detail"], "Series 1, episode 1: Part 1")
        d2, said = grid.set_start(d, SID, "episode", NOW, s=2, e=3)
        self.assertEqual(grid.view(d2, monday)["slots"][0]["detail"], "Series 2, episode 3: Part 13")
        self.assertEqual(said, "Show A: from series 2, episode 3, this week")
        d3, _ = grid.set_start(d, SID, "unwatched", NOW, unwatched_index=6)
        self.assertEqual(grid.view(d3, monday)["slots"][0]["detail"], "Series 1, episode 7: Part 7")
        self.assertEqual(grid.view(d3, monday)["series"][SID]["start"], "From the next episode not watched")
        with self.assertRaises(grid.GridError):
            grid.set_start(d, SID, "episode", NOW, s=9, e=9)

    def test_adding_a_slot_carries_on_and_never_jumps_back(self):
        d, slot = doc_with_series(25)
        later_week = NOW + 3 * 7 * 86400  # three weeks on: episode 4 is due
        self.assertEqual(grid.view(d, grid.week_start(later_week))["slots"][0]["detail"][:19], "Series 1, episode 4")
        d2, _, _ = grid.add(d, 1, 20 * 60, "series", {"id": SID, "name": "Show A"}, later_week)
        v = grid.view(d2, grid.week_start(later_week))
        self.assertEqual([s["detail"][:19] for s in v["slots"]], ["Series 1, episode 4", "Series 1, episode 5"])

    def test_it_goes_round_after_the_last_episode(self):
        d, _ = doc_with_series(3)
        self.assertEqual(grid.view(d, grid.week_start(NOW) + 3 * 7 * 86400)["slots"][0]["detail"][:19], "Series 1, episode 1")


class FollowsTheGrid(unittest.TestCase):
    def setUp(self):
        lineup = [{"id": f"auto{i}", "dur": 1200, "title": f"Auto {i}", "group": f"g{i}", "kind": "Movie"} for i in range(6)]
        self.ch = {"id": "abcd1234", "name": "Comedy", "number": 1, "on": True, "order": "in_order", "run": 1, "start_on": 30,
                   "break_seconds": 0, "seed": 7, "eras": []}
        self.ch["eras"] = schedule.new_era(self.ch, lineup, NOW - 7 * 86400)
        d, _ = doc_with_series()
        self.doc, _ = grid.copy_day(d, 0, [1, 2, 3, 4, 5, 6], NOW)
        self.today_20 = grid.at(grid.week_start(NOW), time.localtime(NOW).tm_wday, 20 * 60)

    def test_fixed_slots_win_and_the_gaps_keep_the_automatic_line_up(self):
        sched = grid.channel_of(self.ch, self.doc)
        a = sched.airing(self.today_20 + 60)
        self.assertEqual(a["entry"]["title"], "Show A")
        self.assertEqual(a["start"], self.today_20)
        before = sched.airing(self.today_20 - 600)
        self.assertTrue(before["entry"]["title"].startswith("Auto"), "the automatic line-up before it")
        self.assertLessEqual(before["content_end"], self.today_20, "only whole programmes that fit")
        self.assertEqual(before["end"], self.today_20, "the rest of the gap is its break")
        after = sched.airing(self.today_20 + 1800 + 60)
        self.assertTrue(after["entry"]["title"].startswith("Auto"))
        plain = grid.channel_of(self.ch, grid.empty())
        self.assertIsInstance(plain, schedule.Channel, "a channel with no slots is as it was")

    def test_the_guide_and_the_breaks_follow_it(self):
        ch = {**self.ch, "_grid": self.doc}
        xml = guide.xmltv([ch], "http://tv/t/x", "Home TV", start=self.today_20 - 3600, days=1)
        when = time.strftime("%Y%m%d%H%M%S", time.gmtime(self.today_20))
        self.assertRegex(xml, rf'<programme start="{when} \+0000"[^>]*>\s*<title>Show A</title>')
        a, pieces = schedule.pieces_at(grid.channel_of(ch), self.today_20 + 60, {"idents": [], "fillers": []}, {"seed": 7})
        self.assertEqual(pieces[0]["kind"], "programme")
        self.assertAlmostEqual(pieces[-1]["end"], a["end"])
        airings = grid.channel_of(ch).airings(self.today_20 - 7200, self.today_20 + 7200)
        for x, y in zip(airings, airings[1:]):
            self.assertEqual(x["end"], y["start"], "no gaps and no overlaps")


class Suggester(unittest.TestCase):
    def plays(self):
        out = []
        day = 86400
        for k in range(20):  # Show A, watched on weekday evenings at 21:00
            t = grid.at(grid.week_start(NOW) - 7 * day * (k // 5), k % 5, 21 * 60 + 10)
            out.append({"at": t, "kind": "series", "id": SID, "name": "Show A"})
        for k in range(5):  # Show B, a few times at 19:30
            out.append({"at": NOW - k * day - 3600, "kind": "series", "id": SID2, "name": "Show B"})
        out += [{"at": NOW - 2 * day, "kind": "film", "id": FID, "name": "A Film"}] * 3
        return out

    def info(self, sid):
        return {"id": sid, "name": "Show A" if sid == SID else "Show B", "episodes": eps(sid, 20, title="Show A" if sid == SID else "Show B"),
                "unwatched": 4}

    def test_series_stripped_at_the_time_they_are_watched_and_films_at_the_weekend(self):
        doc, notes = suggest.propose(None, self.plays(), NOW, self.info, lambda fid: FILM if fid == FID else None)
        v = grid.view(doc, grid.week_start(NOW))
        a = [s for s in v["slots"] if s["title"] == "Show A"]
        self.assertEqual([(s["day"], grid.hm(s["start"])) for s in a], [(d, "21:00") for d in range(5)])
        self.assertEqual(a[0]["detail"][:19], "Series 1, episode 5", "from the next episode not watched")
        self.assertTrue(any(s["title"] == "Show B" for s in v["slots"]))
        film = [s for s in v["slots"] if s["kind"] == "film"]
        self.assertEqual([(s["day"], grid.hm(s["start"])) for s in film], [(5, "20:00")])
        self.assertTrue(doc.get("suggested"))
        self.assertTrue(any("weekdays at 21:00" in n for n in notes))

    def test_only_the_channels_own_programmes_and_nothing_without_history(self):
        doc, _ = suggest.propose({SID2}, self.plays(), NOW, self.info, lambda fid: FILM)
        self.assertEqual({s["title"] for s in grid.view(doc, grid.week_start(NOW))["slots"]}, {"Show B"})
        doc, notes = suggest.propose(None, [], NOW, self.info, lambda fid: FILM)
        self.assertEqual(doc["slots"], [])
        self.assertIn("No watch history", notes[-1])


# The page's answers, through the plug-in's own server, with a stand-in Jellyfin. -------------------------------------
class FakeLibrary(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, body, status=200):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):  # noqa: N802
        self._send({"error": "no Playback Reporting"}, 404)

    def do_GET(self):  # noqa: N802
        u = urllib.parse.urlparse(self.path)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}

        def item(e, series=True):
            return {"Id": e["id"], "Type": "Episode" if series else "Movie", "Name": e.get("ep") or e["title"], "SeriesName": e["title"],
                    "SeriesId": e["group"] if series else None, "ParentIndexNumber": e.get("s"), "IndexNumber": e.get("e"),
                    "RunTimeTicks": int(e["dur"] * 1e7), "MediaStreams": [{"Type": "Audio", "Index": 1, "IsDefault": True}]}
        if u.path == "/Users":
            return self._send([{"Id": "u1", "Policy": {"IsAdministrator": True}}])
        if u.path == "/Users/u1/Items" and q.get("Filters") == "IsUnplayed":
            return self._send({"Items": [{"Id": eps(SID, 20)[3]["id"]}], "TotalRecordCount": 1})
        if u.path == "/Users/u1/Items":
            t = time.strftime("%Y-%m-%dT%H:%M:%S.0000000Z", time.gmtime(time.time() - 3 * 86400))
            return self._send({"Items": [{"Id": eps(SID, 20)[0]["id"], "Type": "Episode", "SeriesId": SID, "SeriesName": "Show A",
                                          "UserData": {"LastPlayedDate": t}}]})
        if u.path == "/Sessions":
            return self._send([])
        if u.path == "/Items" and q.get("SearchTerm"):
            types = q.get("IncludeItemTypes")
            found = [{"Id": SID, "Name": "Show A", "Type": "Series"}] if types == "Series" else [{"Id": FID, "Name": "A Film", "Type": "Movie",
                                                                                                 "ProductionYear": 1999}]
            return self._send({"Items": found})
        if u.path == "/Items" and q.get("ParentId") == SID:
            start = int(q.get("StartIndex") or 0)
            return self._send({"Items": [item(e) for e in eps(SID, 20)][start:start + 200], "TotalRecordCount": 20})
        if u.path == "/Items" and q.get("Ids") == FID:
            return self._send({"Items": [item({**FILM, "ep": None}, series=False)]})
        return self._send({"Items": [], "TotalRecordCount": 0})


class Page(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.jf = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeLibrary)
        threading.Thread(target=cls.jf.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.jf.shutdown()

    def setUp(self):
        from test_tv_station_pack import load_app
        self.tmp = tempfile.TemporaryDirectory()
        self.app = load_app(self.tmp.name, {}, {"url": f"http://127.0.0.1:{self.jf.server_address[1]}", "api_key": "k"})
        self.app.later_jellyfin = lambda: None
        s = self.app.state()
        ch = self.app.new_channel(s, "Comedy")
        s["channels"].append(ch)
        self.app.save(s)
        self.cid, self.token = ch["id"], s["token"]
        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), self.app.Handler)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}/t/{self.token}/grid"

    def tearDown(self):
        self.srv.shutdown()
        self.tmp.cleanup()

    def op(self, **body):
        req = urllib.request.Request(self.base + "/api/op", data=json.dumps({"cid": self.cid, **body}).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            return {"status": e.code, **json.loads(e.read() or b"{}")}

    def test_the_page_and_its_files_with_a_strict_policy(self):
        with urllib.request.urlopen(self.base, timeout=10) as r:
            page = r.read().decode()
            self.assertIn("default-src 'self'", r.headers["Content-Security-Policy"])
        self.assertIn('<html lang="en-GB">', page)
        for f in ("grid.js", "grid.css", "font.woff2"):
            with urllib.request.urlopen(f"{self.base}/{f}", timeout=10) as r:
                self.assertEqual(r.status, 200)
        with self.assertRaises(urllib.error.HTTPError):
            urllib.request.urlopen(self.base.replace(self.token, "wrong") + "/api/state", timeout=10)
        req = urllib.request.Request(self.base + "/api/op", data=b"op=remove", method="POST", headers={"Content-Type": "application/x-www-form-urlencoded"})
        with self.assertRaises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(req, timeout=10)
        self.assertEqual(e.exception.code, 415, "only JSON, which another site's form cannot send")

    def test_a_phone_or_tablet_is_told_to_use_a_computer(self):
        """The notice is chosen by the device (a phone's or tablet's signal and a touch screen with no hover), never by
        the width, so a desktop zoomed in keeps the page. The browser check is in the accessibility run."""
        with urllib.request.urlopen(self.base, timeout=10) as r:
            page = r.read().decode()
        self.assertIn("Create your own TV channel works in a desktop browser. Open Starboard on a computer to set up your channels.", page)
        self.assertIn('id="desktop-only" class="desktop-only" hidden', page)
        with urllib.request.urlopen(self.base + "/grid.js", timeout=10) as r:
            js = r.read().decode()
        self.assertIn("navigator.userAgentData.mobile", js)
        self.assertIn('"(pointer: coarse) and (hover: none)"', js)
        self.assertNotRegex(js + page, r"innerWidth|max-width: *\d+(rem|px)\) *\{", "no test of the width")
        with urllib.request.urlopen(self.base + "/grid.css", timeout=10) as r:
            self.assertNotIn("@media (max-width", r.read().decode(), "no phone layout")

    def test_add_search_start_point_undo_and_the_starboard_page(self):
        with urllib.request.urlopen(self.base + "/api/search?q=show", timeout=10) as r:
            found = json.loads(r.read())["items"]
        self.assertEqual(found[0], {"id": SID, "kind": "series", "name": "Show A"})
        got = self.op(op="add", kind="series", id=SID, day=0, start=1200, start_mode="unwatched")
        self.assertEqual(got["said"], "Added Show A at Monday 20:00")
        self.assertEqual(got["slots"][0]["detail"], "Series 1, episode 4: Part 4", "the next episode not watched")
        self.assertEqual(got["focus"], got["slots"][0]["id"], "focus goes to the slot added")
        got = self.op(op="stripe", slot=got["focus"], weekdays=[0, 1, 2], per_day=1, weekends=False)
        self.assertEqual(len(got["slots"]), 3)
        self.assertTrue(got["can_undo"])
        bad = self.op(op="add", kind="film", id=FID, day=1, start=1200)
        self.assertEqual(bad["status"], 400)
        self.assertIn("would run into Show A", bad["error"])
        got = self.op(op="undo")
        self.assertEqual(len(got["slots"]), 1)
        page = self.app.schedule_page()
        self.assertEqual(page["items"][0]["state_label"], "1 slot")
        a = self.app.sched_of(self.app.find(self.app.state(), self.cid)).airing(grid.at(grid.week_start(time.time()), 0, 1200) + 60)
        self.assertEqual(a["entry"]["title"], "Show A", "the channel follows the saved grid")

    def test_a_suggestion_is_a_draft_until_saved(self):
        got = self.op(op="suggest")
        self.assertTrue(got["draft"])
        self.assertTrue(got["slots"], got.get("said"))
        self.assertIsNone(self.app.grid_doc(self.cid), "nothing saved yet")
        got = self.op(op="move", slot=got["slots"][0]["id"], day=got["slots"][0]["day"], start=got["slots"][0]["start"] + 15)
        self.assertTrue(got["draft"], "changes go to the suggestion")
        got = self.op(op="discard_draft")
        self.assertFalse(got["draft"])
        self.assertEqual(got["slots"], [])
        self.op(op="suggest")
        got = self.op(op="save_draft")
        self.assertFalse(got["draft"])
        self.assertTrue(self.app.grid_doc(self.cid)["slots"])


if __name__ == "__main__":
    unittest.main()
