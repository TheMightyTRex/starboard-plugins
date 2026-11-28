"""Create your own TV channel 0.14.0: plain words and one-time explainers (DASH-641, owner 28 November 2026)."""
import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT  # noqa: E402

TV = os.path.join(ROOT, "tv-station")
sys.path.insert(0, TV)
import explain  # noqa: E402
from test_tv_station_020 import App, episodes  # noqa: E402

# The trade words the glossary replaces. They may stay in an explainer ("TV people call it an ident") and in ids and file names.
TRADE = re.compile(r"\b(idents?|promos?|straps?|bumpers?|PSAs?|broadcast packs?|holding slides?|break grids?|backing plate|conversions?)\b", re.I)


def words_in(node, key=""):
    """Every text a person reads in the manifest: labels, hints, choices, actions and cards."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k in ("changes", "image", "path", "key", "id", "version", "homepage", "support_url", "example", "update", "group"):
                continue
            yield from words_in(v, k)
    elif isinstance(node, list):
        for v in node:
            yield from words_in(v, key)
    elif isinstance(node, str) and key in ("label", "hint", "description", "confirm", "title", "small", "medium", "half", "wide", "full"):
        yield node


class TheManifestWords(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(TV, "starboard-plugin.json"), encoding="utf-8") as f:
            self.m = json.load(f)

    def test_no_trade_word_in_a_label_or_hint(self):
        for t in words_in(self.m):
            self.assertIsNone(TRADE.search(t), t)

    def test_the_house_rules_hold(self):
        for t in words_in(self.m):
            self.assertNotIn("—", t, t)
            self.assertIsNone(re.search(r"\b\w+n't\b|\b(it|that|there|let|you|we|they)'(s|ll|re|ve)\b", t), t)
            self.assertIsNone(re.search(r"\b(see|look|click|tap)\b", t, re.I), t)

    def test_groups_keep_their_keys(self):
        keys = [s["key"] for s in self.m["settings"]]
        for k in ("station_name", "picture", "promos", "promo_keep", "dog_kind", "dog_corner", "dog_strap_start", "channels", "clips", "pack"):
            self.assertIn(k, keys)


class TheExplainers(App):
    def test_a_new_person_meets_each_explainer_on_the_page_that_uses_the_word(self):
        got = self.app.clips_page()["notices"]
        self.assertEqual([n["id"] for n in got], ["explain:short-title-clip", "explain:waiting-screen"])
        for n in got:
            self.assertTrue(n["dismiss"])
            self.assertEqual(n["tone"], "info")

    def test_dismissing_one_hides_it_everywhere_for_good(self):
        self.app.clips_post({"action": "dismiss", "id": "explain:short-title-clip"})
        self.assertEqual(self.app.state()["explained"], ["short-title-clip"])
        self.assertNotIn("explain:short-title-clip", [n["id"] for n in self.app.clips_page()["notices"]])
        self.assertNotIn("explain:short-title-clip", [n["id"] for n in self.app.channels_page().get("notices", [])])
        self.app.clips_post({"action": "dismiss", "id": "explain:short-title-clip"})
        self.assertEqual(self.app.state()["explained"], ["short-title-clip"], "twice is the same as once")

    def test_the_next_explainer_takes_its_place(self):
        self.app.clips_post({"action": "dismiss", "id": "explain:short-title-clip"})
        self.assertEqual([n["id"] for n in self.app.clips_page()["notices"]], ["explain:waiting-screen", "explain:coming-up-trailer"])

    def test_the_branding_page_explains_branding(self):
        self.assertEqual(self.app.pack_page()["notices"][0]["id"], "explain:branding")
        self.app.pack_post({"action": "dismiss", "id": "explain:branding"})
        self.assertNotIn("explain:branding", [n["id"] for n in self.app.pack_page().get("notices", [])])

    def test_an_unknown_id_changes_nothing(self):
        s = {}
        self.assertTrue(explain.dismiss(s, "explain:nothing-like-it"))
        self.assertNotIn("explained", s)
        self.assertFalse(explain.dismiss(s, "error"))

    def test_the_words_follow_the_house_rules(self):
        for title, text in explain.TERMS.values():
            for t in (title, text):
                self.assertNotIn("—", t)
                self.assertIsNone(re.search(r"\w'(s|t|ll|re|ve)\b", t.replace("station's", "")), t)
            self.assertLessEqual(len(text), 400)
            self.assertLessEqual(max(len(x.split()) for x in re.split(r"[.?]", text)), 25, text)


class TheClipsPage(App):
    """What plays between programmes (DASH-642): the order of the groups, no Add group, and the empty state."""

    def groups(self, page):
        out = []
        for it in page["items"]:
            if "menu" not in it and it["group"] not in out:
                out.append(it["group"])
        return out

    def test_the_groups_follow_the_task(self):
        page = self.app.clips_page()
        self.assertEqual(page["title"], "What plays between programmes")
        self.assertEqual(self.groups(page), ["Start here", "Break style", "Short title clips", "Clips", "Music", "Waiting screen", "More: your own short videos",
                                             "More: public messages", "More: background loops"])
        self.assertNotIn("Add", self.groups(page))

    def test_the_break_layouts_and_files_are_sub_menus_of_this_page(self):
        page = self.app.clips_page()
        self.assertEqual([m["id"] for m in page["menus"]], ["layouts", "files"])
        self.assertTrue(all(it["id"].split("~")[0] in ("layouts", "files") for it in page["items"] if "menu" in it))

    def test_every_add_row_keeps_its_id_and_sits_in_its_own_group(self):
        by_id = {it["id"]: it["group"] for it in self.app.clips_page()["items"]}
        self.assertEqual({k: by_id[k] for k in ("add:idents", "add:clips", "add:music", "add:extras", "add:psa", "add:back", "holding")},
                         {"add:idents": "Short title clips", "add:clips": "Clips", "add:music": "Music", "add:extras": "More: your own short videos",
                          "add:psa": "More: public messages", "add:back": "More: background loops", "holding": "Waiting screen"})

    def test_an_empty_page_offers_the_example_files_and_a_full_one_does_not(self):
        first = self.app.clips_page()["items"][0]
        self.assertEqual((first["id"], first["title"], first["actions"]), ("use-example", "Use the example files", ["toggle"]))
        s = self.app.state()
        s["shared"]["clips"].append({"id": "c1", "title": "Opening", "dur": 5})
        self.app.save(s)
        self.assertNotIn("use-example", [it["id"] for it in self.app.clips_page()["items"]])

    def test_the_hints_say_one_thing_and_do_not_warn(self):
        for it in self.app.clips_page()["items"]:
            for t in (it.get("detail", ""), (it.get("attach") or {}).get("hint", "")):
                self.assertNotIn("names are not used", t)
            self.assertLessEqual(len((it.get("detail") or "").split(". ")), 2, it["id"])


class TheSixTabs(App):
    """Fewer tabs (DASH-643): four pages of the plug-in's own, two groups of settings, and nothing lost."""

    def setUp(self):
        super().setUp()
        with open(os.path.join(TV, "starboard-plugin.json"), encoding="utf-8") as f:
            self.m = json.load(f)

    def test_the_tabs(self):
        tabs = []
        for s in self.m["settings"]:
            t = s["label"] if s["type"] == "custom" else s["group"]
            if t not in tabs:
                tabs.append(t)
        self.assertEqual(sorted(tabs), sorted(["Station", "Logo, title bars and trailers", "Channels", "What plays between programmes",
                                               "What plays when", "Branding", "Choose a style for my channel"]))

    def test_no_setting_key_was_lost(self):
        keys = {s["key"] for s in self.m["settings"]}
        old = {"channels", "schedule", "clips", "pack", "station_name", "language", "first_number", "address", "guide_days", "picture",
               "most_at_once", "stop_after", "copy_plain", "leave_out_3d", "promos", "promo_keep", "promo_replace_days", "promo_seconds",
               "promo_clips", "promo_sound", "promo_music_level", "promo_station_logo", "promo_audio_description", "promo_other",
               "dog_kind", "dog_corner", "dog_size", "dog_margin", "dog_opacity", "dog_when", "dog_fade_in", "dog_clock", "dog_label",
               "dog_plate", "dog_strap_start", "dog_strap_end", "dog_strap_seconds", "dog_cards"}
        self.assertEqual(old - keys, set())

    def test_the_guide_is_inside_what_plays_when(self):
        self.channel(lineup=episodes("a", 3, 1500))
        page = self.app.schedule_page()
        self.assertEqual(page["title"], "What plays when")
        self.assertIn("guide", [m["id"] for m in page["menus"]])
        self.assertTrue(any(it.get("menu") == "guide" for it in page["items"]))

    def test_an_animation_choice_still_saves_through_branding(self):
        page = self.app.pack_page()
        row = next(it for it in page["items"] if it["id"].startswith("anim~station:") and it.get("choice"))
        value = row["choice"]["options"][-1][0]
        got = self.app.pack_post({"action": "choose", "id": row["id"], "value": value})
        again = next(it for it in got["items"] if it["id"] == row["id"])
        self.assertEqual(again["choice"]["value"], value)
        self.assertEqual(got["title"], "Branding")


class TheStationTab(unittest.TestCase):
    """Station and streaming (DASH-647): the choices most people make come first, and every key and default stays."""

    def setUp(self):
        with open(os.path.join(TV, "starboard-plugin.json"), encoding="utf-8") as f:
            self.rows = [x for x in json.load(f)["settings"] if x.get("group") == "Station"]

    def test_the_first_five_are_the_ones_most_people_make(self):
        self.assertEqual([x["key"] for x in self.rows][:5], ["station_name", "language", "picture", "most_at_once", "stop_after"])
        self.assertEqual([x["label"] for x in self.rows][2:5], ["Picture quality", "Channels playing at once", "Stop a channel when nobody is watching"])

    def test_the_rest_say_they_can_stay_as_they_are(self):
        for x in self.rows[5:]:
            if x["key"] != "address":
                self.assertIn("You can leave this as it is.", x["hint"], x["key"])

    def test_defaults_and_choice_values_are_as_before(self):
        by = {x["key"]: x for x in self.rows}
        self.assertEqual((by["picture"]["default"], [c["value"] for c in by["picture"]["choices"]]), ("720", ["720", "1080"]))
        self.assertEqual((by["most_at_once"]["default"], by["stop_after"]["default"], by["first_number"]["default"]), (2, 30, 1))

    def test_no_hint_has_a_sentence_over_25_words(self):
        for x in self.rows:
            for sentence in re.split(r"(?<=[.])\s", x.get("hint", "")):
                self.assertLessEqual(len(sentence.split()), 25, x["key"])


class TheBrandingPage(App):
    """Branding (DASH-648): Plain, Example TV or My own branding; the pack format is unchanged."""

    def mine(self, have=True):
        fake = {"name": "Mine", "folder": self.tmp.name, "made": "", "dog": ""}
        self.app.load_pack = lambda name: fake if (have and name == "station") else None
        self.app.pack.summary = lambda p: "a logo and 2 short title clips"
        return fake

    def row(self, page, rid):
        return next(i for i in page["items"] if i["id"] == rid)

    def test_the_first_row_is_the_choice_and_starts_on_plain(self):
        page = self.app.pack_page()
        first = page["items"][0]
        self.assertEqual((first["id"], first["group"]), ("branding", "Branding"))
        self.assertEqual(first["choice"]["options"], [["none", "Plain"], ["example", "Example TV"], ["own", "My own branding"]])
        self.assertEqual(first["choice"]["value"], "none")
        self.assertIn("Plain", first["detail"])

    def test_own_branding_needs_an_upload_first(self):
        self.mine(have=False)
        with self.assertRaises(ValueError):
            self.app.pack_post({"action": "choose", "id": "branding", "value": "own"})

    def test_plain_and_own_switch_without_losing_the_upload(self):
        self.mine()
        s = self.app.state()
        s["station_pack"] = "station"
        self.app.save(s)
        page = self.app.pack_post({"action": "choose", "id": "branding", "value": "none"})
        self.assertEqual(self.app.state()["station_pack"], "")
        self.assertEqual(self.row(page, "branding")["choice"]["value"], "none")
        page = self.app.pack_post({"action": "choose", "id": "branding", "value": "own"})
        self.assertEqual(self.app.state()["station_pack"], "station")
        self.assertEqual(self.row(page, "branding")["choice"]["value"], "own")

    def test_a_bad_choice_is_refused(self):
        with self.assertRaises(ValueError):
            self.app.pack_post({"action": "choose", "id": "branding", "value": "loud"})

    def test_the_corner_logo_row_says_where_it_is(self):
        self.channel("Comedy")
        page = self.app.pack_page()
        row = self.row(page, "corner-logo")
        self.assertEqual(row["title"], "The logo in the corner: top right, medium")
        self.assertIn("/preview/", row["link"]["url"])

    def test_the_groups_are_in_the_order_of_the_task(self):
        page = self.app.pack_page()
        groups = []
        for it in page["items"]:
            if "menu" not in it and it["group"] not in groups:
                groups.append(it["group"])
        self.assertEqual(groups[:3], ["Branding", "My own branding", "The logo in the corner"])


if __name__ == "__main__":
    unittest.main()
