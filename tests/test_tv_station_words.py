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
from test_tv_station_020 import App  # noqa: E402

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
            if it["group"] not in out:
                out.append(it["group"])
        return out

    def test_the_groups_follow_the_task(self):
        page = self.app.clips_page()
        self.assertEqual(page["title"], "What plays between programmes")
        self.assertEqual(self.groups(page), ["Start here", "Short title clips", "Clips", "Music", "Waiting screen", "More: your own short videos",
                                             "More: public messages", "More: background loops"])
        self.assertNotIn("Add", self.groups(page))

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


if __name__ == "__main__":
    unittest.main()
