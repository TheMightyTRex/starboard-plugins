"""Create your own TV channel 0.5.5 (owner, 19 November 2026: "Yes, do it here", to make the refresh update each
programme's sound track): a line-up with the same programmes keeps its schedule, and its programmes' details are brought
up to date from Jellyfin."""
import copy
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT  # noqa: E402
from test_tv_station import NOW, channel, episodes  # noqa: E402
from test_tv_station_020 import App  # noqa: E402

TV = os.path.join(ROOT, "tv-station")
sys.path.insert(0, TV)
import schedule  # noqa: E402


class Details(unittest.TestCase):
    def test_details_change_and_timing_does_not(self):
        old = episodes("a", 4, 1500)
        for e in old:
            e["audio"] = 2  # read before 0.5.4: Jellyfin's Index
        spec = channel(old)
        before = [schedule.Channel(spec).airing(NOW + k * 1500)["entry"]["id"] for k in range(8)]
        fresh = copy.deepcopy(episodes("a", 4, 1500))
        for e in fresh:
            e.update(audio_n=1, title="Show a (renamed)", dur=999, group="other")  # dur and group must not move
        n = schedule.refresh_details(spec["eras"], fresh)
        self.assertEqual(n, 4)
        e = spec["eras"][0]["lineup"][0]
        self.assertEqual((e["audio_n"], e["title"]), (1, "Show a (renamed)"))
        self.assertNotIn("audio", e)
        self.assertEqual((e["dur"], e["group"]), (1500, "a"))
        self.assertEqual([schedule.Channel(spec).airing(NOW + k * 1500)["entry"]["id"] for k in range(8)], before)
        self.assertEqual(schedule.refresh_details(spec["eras"], fresh), 0, "nothing more to change the second time")

    def test_a_programme_no_longer_there_is_left_as_it_is(self):
        spec = channel(episodes("a", 2, 1500))
        self.assertEqual(schedule.refresh_details(spec["eras"], []), 0)


class TheRefresh(App):
    def test_same_programmes_new_details(self):
        lineup = episodes("aa", 3, 1500)
        for e in lineup:
            e["audio"] = 2
        cid = self.channel("Late ink", lineup)
        s = self.app.state()
        ch = self.app.find(s, cid)
        fresh = copy.deepcopy(episodes("aa", 3, 1500))
        for e in fresh:
            e["audio_n"] = 0
        ch["sources"] = [{"kind": "series", "id": "aa"}]
        ch["lineup_hash"] = schedule.lineup_hash(fresh) + f":{ch['order']}:{ch['run']}:{ch['start_on']}:{ch['break_seconds']}"
        eras_before = len(ch["eras"])
        self.app.save(s)
        with mock.patch.object(self.app.library, "lineup", lambda jf, sources: copy.deepcopy(fresh)), \
                mock.patch.object(self.app.library, "trailers", lambda jf, entries: []):
            self.app.refresh_channel(cid, now=1794600123.0)
        ch = self.app.find(self.app.state(), cid)
        self.assertEqual(len(ch["eras"]), eras_before, "no new era: the schedule did not move")
        self.assertTrue(all(e.get("audio_n") == 0 and "audio" not in e for e in ch["eras"][-1]["lineup"]))


if __name__ == "__main__":
    unittest.main()
