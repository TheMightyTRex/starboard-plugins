"""Create your own TV channel 0.5.1 (owner, 19 November 2026): a channel's promos are made again when its broadcast
pack changes. Late ink's promos had been made with the station's pack minutes before its own pack was uploaded, and
were kept for two days."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT  # noqa: E402
from test_tv_station_020 import NOW, App  # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "tv-station"))
import promo  # noqa: E402

TREX = {"name": "T-Rex TV", "folder": "/data/packs/station", "checked": 1795110000}
LATE = {"name": "Late ink", "folder": "/data/packs/ch-a51bd5a8", "checked": 1795121410}


class Designs(unittest.TestCase):
    def test_a_design_is_the_pack_and_when_it_was_checked(self):
        self.assertEqual(promo.design_of(TREX), "station:1795110000")
        self.assertEqual(promo.design_of(LATE), "ch-a51bd5a8:1795121410")
        self.assertNotEqual(promo.design_of(TREX), promo.design_of({**TREX, "checked": 1795110001}), "the same pack uploaded again")
        self.assertEqual(promo.design_of(promo.plain_pack("0x2e7d32")), "plain:0x2e7d32")
        self.assertIsNone(promo.design_of(None))

    def test_a_promo_from_before_has_no_design_and_is_kept(self):
        self.assertTrue(promo.current({"cid": "a"}, {"a": "station:1"}))
        self.assertTrue(promo.current({"cid": "a", "design": "station:1"}, {"a": "station:1"}))
        self.assertFalse(promo.current({"cid": "a", "design": "station:1"}, {"a": "ch-a:2"}))

    def test_a_promo_with_the_old_pack_is_removed_and_made_again(self):
        class Sched:
            def airings(self, start, stop, limit=400):
                return [{"start": NOW + 3 * 3600, "entry": {"id": "e1", "group": "g1"}}]
        chans = [{"id": "late", "sched": Sched(), "can": True, "design": promo.design_of(LATE)}]
        kept = [{"id": "p1", "cid": "late", "group": "g1", "airs": NOW + 3 * 3600, "made": NOW - 600, "design": promo.design_of(TREX)}]
        remove, make = promo.plan(chans, kept, 1, 2, NOW)
        self.assertEqual([p["id"] for p in remove], ["p1"])
        self.assertEqual([m["cid"] for m in make], ["late"])
        kept[0]["design"] = promo.design_of(LATE)
        remove, make = promo.plan(chans, kept, 1, 2, NOW)
        self.assertEqual((remove, make), ([], []), "made with the pack it has now: kept")


class NotShown(App):
    def test_a_promo_with_the_old_pack_is_not_shown(self):
        cid = self.channel("Late ink")
        s = self.app.state()
        s["promos"] = [{"id": "p1", "cid": cid, "title": "Old", "airs": NOW + 9000, "made": NOW - 600, "dur": 15, "design": promo.design_of(TREX)},
                       {"id": "p2", "cid": cid, "title": "New", "airs": NOW + 9000, "made": NOW - 60, "dur": 15, "design": promo.design_of(LATE)},
                       {"id": "p3", "cid": cid, "title": "Before 0.5.1", "airs": NOW + 9000, "made": NOW - 60, "dur": 15}]
        self.app.save(s)
        self.app.promo_design = lambda s, ch: LATE
        ch = self.app.find(self.app.state(), cid)
        shown = [c["title"] for c in self.app.promo_clips(self.app.state(), ch, {})]
        self.assertEqual(shown, ["Coming-up trailer: New", "Coming-up trailer: Before 0.5.1"])


if __name__ == "__main__":
    unittest.main()
