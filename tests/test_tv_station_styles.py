"""Create your own TV channel 0.12.0: break styles (DASH-644) and a channel's own style in words (DASH-645)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT  # noqa: E402

TV = os.path.join(ROOT, "tv-station")
sys.path.insert(0, TV)
import styles  # noqa: E402
from test_tv_station_020 import NOW, App, episodes  # noqa: E402

OLD = {"id": "a", "name": "Old", "break_seconds": 0, "idents": "both", "ident_order": "in_order", "trailers": False, "clips": "both"}


class ThePresets(unittest.TestCase):
    def test_three_presets_in_plain_words(self):
        self.assertEqual([p["name"] for p in styles.PRESETS.values()], ["Quiet", "Classic TV", "Busy"])
        for sid in styles.PRESETS:
            w = styles.words(sid)
            self.assertLessEqual(len(w), 200)
            self.assertNotIn("—", w)
            self.assertLessEqual(max(len(x.split()) for x in w.split(". ")), 25, w)

    def test_every_preset_value_is_one_the_rows_already_offer(self):
        import app  # the rows' own tables, read from the app
        for p in styles.PRESETS.values():
            v = p["values"]
            self.assertIn(str(v["break_seconds"]), app.BREAKS)
            self.assertIn(str(v["per_break"]), app.PER_BREAK)
            self.assertIn(v["ident_order"], ("in_order", "random"))
            for k in ("idents", "clips", "extras"):
                self.assertIn(v[k], ("none", "own", "shared", "both"))

    def test_a_preset_sets_only_the_break_keys(self):
        ch = dict(OLD, own={"idents": [{"id": "x"}]}, colour="0x1f5f99")
        styles.apply(ch, "busy")
        self.assertEqual((ch["break_seconds"], ch["per_break"], ch["trailers"]), (300, 6, True))
        self.assertEqual((ch["colour"], ch["own"]), ("0x1f5f99", {"idents": [{"id": "x"}]}))

    def test_matching_finds_a_preset_a_channel_already_has(self):
        ch = dict(OLD)
        self.assertEqual(styles.matching(ch), "")
        styles.apply(ch, "classic")
        self.assertEqual(styles.matching(ch), "classic")


class TheMigration(unittest.TestCase):
    """A channel saved before 0.12.0 has no style: nothing about it changes."""

    def test_a_channel_that_never_changed_a_break_setting_uses_the_station_style(self):
        self.assertEqual(styles.style_of(dict(OLD)), "")

    def test_a_channel_that_changed_one_has_its_own_settings(self):
        self.assertEqual(styles.style_of(dict(OLD, break_seconds=180)), styles.CUSTOM)
        self.assertEqual(styles.style_of(dict(OLD, per_break=4)), styles.CUSTOM)
        self.assertEqual(styles.style_of(dict(OLD, trailers=True)), styles.CUSTOM)

    def test_reading_a_style_never_writes_anything(self):
        ch = dict(OLD, break_seconds=60)
        before = dict(ch)
        styles.style_of(ch)
        self.assertEqual(ch, before)

    def test_a_bad_saved_style_falls_back_to_the_station(self):
        self.assertEqual(styles.style_of(dict(OLD, style="nonsense")), "")


class TheStationStyle(App):
    def style_row(self, page, cid):
        return next(i for i in page["items"] if i["id"] == f"{cid}:style")

    def test_choosing_the_station_style_changes_only_channels_that_use_it(self):
        a = self.channel("Comedy")
        b = self.channel("Drama")
        s = self.app.state()
        mine = self.app.find(s, b)
        mine["break_seconds"] = 180
        mine["style"] = styles.CUSTOM
        self.app.save(s)
        got = self.app.clips_post({"action": "choose", "id": "station-style", "value": "quiet"})
        self.assertIn("1 channel changed", got["said"])
        self.assertIn("1 with their own style", got["said"])
        s = self.app.state()
        self.assertEqual((self.app.find(s, a)["break_seconds"], self.app.find(s, a)["style"]), (60, ""))
        self.assertEqual((self.app.find(s, b)["break_seconds"], self.app.find(s, b)["style"]), (180, styles.CUSTOM))

    def test_a_new_channel_takes_the_station_style(self):
        self.app.clips_post({"action": "choose", "id": "station-style", "value": "busy"})
        cid = self.channel("News")
        ch = self.app.find(self.app.state(), cid)
        self.assertEqual((ch["break_seconds"], ch["per_break"], ch["style"]), (300, 6, ""))

    def test_the_page_says_the_style_in_words(self):
        cid = self.channel("Comedy")
        self.app.clips_post({"action": "choose", "id": "station-style", "value": "classic"})
        row = self.style_row(self.app.channels_page(now=NOW), cid)
        self.assertIn("Uses the station style: Classic TV", row["detail"])
        self.assertEqual(row["choice"]["value"], "")
        self.assertEqual(row["choice"]["options"][0], ["", "Use the station style: Classic TV"])

    def test_with_no_station_style_a_channel_plays_as_it_did(self):
        cid = self.channel("Comedy")
        ch = self.app.find(self.app.state(), cid)
        self.assertEqual((ch["break_seconds"], ch["idents"], ch["trailers"]), (0, "both", False))
        self.assertIn("plays as it always has", self.style_row(self.app.channels_page(now=NOW), cid)["detail"])


class TheChannelsOwnStyle(App):
    def test_a_channels_own_style_is_its_own_and_the_station_style_leaves_it(self):
        cid = self.channel("Comedy")
        self.app.channels_post({"action": "choose", "id": f"{cid}:style", "value": "busy"}, now=NOW)
        self.app.clips_post({"action": "choose", "id": "station-style", "value": "quiet"})
        ch = self.app.find(self.app.state(), cid)
        self.assertEqual((ch["style"], ch["break_seconds"]), ("busy", 300))

    def test_use_the_station_style_brings_it_back_and_own_settings_are_kept(self):
        self.app.clips_post({"action": "choose", "id": "station-style", "value": "quiet"})
        cid = self.channel("Comedy")
        self.app.channels_post({"action": "choose", "id": f"{cid}:break_seconds", "value": "180"}, now=NOW)
        ch = self.app.find(self.app.state(), cid)
        self.assertEqual(ch["style"], styles.CUSTOM)
        got = self.app.channels_post({"action": "choose", "id": f"{cid}:style", "value": ""}, now=NOW)
        self.assertIn("Its own settings are kept", got["said"])
        ch = self.app.find(self.app.state(), cid)
        self.assertEqual((ch["style"], ch["break_seconds"]), ("", 60))
        self.app.channels_post({"action": "choose", "id": f"{cid}:style", "value": "custom"}, now=NOW)
        ch = self.app.find(self.app.state(), cid)
        self.assertEqual((ch["style"], ch["break_seconds"]), ("custom", 180), "the channel's own value came back")

    def test_changing_an_old_row_by_hand_gives_its_own_settings(self):
        self.app.clips_post({"action": "choose", "id": "station-style", "value": "quiet"})
        cid = self.channel("Comedy")
        got = self.app.channels_post({"action": "choose", "id": f"{cid}:per_break", "value": "4"}, now=NOW)
        self.assertIn("own settings", got["said"])
        self.assertEqual(self.app.find(self.app.state(), cid)["style"], styles.CUSTOM)

    def test_the_old_rows_are_in_a_sub_menu_and_the_style_is_not(self):
        cid = self.channel("Comedy", lineup=episodes("a", 2, 1500))
        page = self.app.channels_page(now=NOW)
        sub = next(m for m in page["menus"] if m["id"] == f"{cid}~more")
        self.assertEqual((sub["parent"], sub["title"]), (cid, "More"))
        menu = {i["id"].split(":", 1)[1]: i.get("menu") for i in page["items"] if i["id"].startswith(cid + ":")}
        self.assertEqual(menu["style"], cid)
        for k in ("start_on", "break_seconds", "per_break", "idents", "clips", "extras", "ident_order", "trailers"):
            self.assertEqual(menu[k], f"{cid}~more", k)

    def test_a_partial_answer_covers_the_sub_menu_too(self):
        cid = self.channel("Comedy")
        self.can("partial", "cards", "picker")
        got = self.app.channels_post({"action": "choose", "id": f"{cid}:style", "value": "quiet"}, now=NOW)
        self.assertEqual(got["partial"]["menus"], [cid, f"{cid}~more"])

    def test_a_bad_style_is_refused(self):
        cid = self.channel("Comedy")
        with self.assertRaises(ValueError):
            self.app.channels_post({"action": "choose", "id": f"{cid}:style", "value": "loud"}, now=NOW)


class TheFourCards(App):
    """A channel page of four cards and More (DASH-646): about 20 rows show, and nothing is lost."""

    def test_the_rows_that_show_without_opening_more(self):
        cid = self.channel("Comedy", lineup=episodes("a", 4, 1500))
        page = self.app.channels_page(now=NOW)
        shown = [i for i in page["items"] if i["menu"] == cid]
        everything = [i for i in page["items"]]
        self.assertLessEqual(len(shown), 20, [i["id"] for i in shown])
        self.assertGreater(len(everything), len(shown))
        self.assertEqual(len({i["id"] for i in everything}), len(everything), "no row twice")

    def test_every_row_a_channel_had_is_still_there(self):
        cid = self.channel("Comedy")
        ids = {i["id"].split(":", 1)[1] for i in self.app.channels_page(now=NOW)["items"] if i["id"].startswith(cid + ":")}
        for k in ("on", "name", "number", "colour", "order", "run", "initial", "style", "start_on", "break_seconds", "mid_break_seconds",
                  "place_how", "idents", "clips", "extras", "psa", "add-ident", "add-clip", "pack", "holding_mode", "holding_words",
                  "count_played"):
            self.assertIn(k, ids)

    def test_the_plan_helper_is_with_what_plays_when(self):
        cid = self.channel("Comedy")
        row = next(i for i in self.app.channels_page(now=NOW)["items"] if i["id"] == f"{cid}:initial")
        self.assertEqual((row["group"], row["menu"]), ("What plays when", cid))


if __name__ == "__main__":
    unittest.main()
