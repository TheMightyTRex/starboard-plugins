"""The catalogue's "published" flag (14 November 2026): a plug-in is published when every container image it runs is
pinned by digest, or it runs no containers (Styles). Checks the rule itself and that catalogue.json follows it."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT, manifest  # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "tools"))
import make_examples  # noqa: E402

DIGEST = "@sha256:" + "0123456789abcdef" * 4


class ReplacesOrAdds(unittest.TestCase):
    """DASH-585 (plug-in API 1.23): every catalogue entry says in one plain line what it replaces or adds to."""

    def test_every_entry_has_one_line(self):
        with open(os.path.join(ROOT, "catalogue.json"), encoding="utf-8") as f:
            rows = json.load(f)["plugins"]
        for e in rows:
            line = e.get("replaces_or_adds", "")
            self.assertTrue(0 < len(line) <= 140, e["id"])
            self.assertNotRegex(line, r"[\r\n<>`]", e["id"])
            self.assertRegex(line, r"^(Adds to|Replaces|Stands alone)", e["id"])

    def test_a_plug_in_with_no_line_stops_the_build(self):
        self.assertTrue(set(make_examples.NOTES) >= {e["id"] for e in json.load(open(os.path.join(ROOT, "catalogue.json"), encoding="utf-8"))["plugins"]})


class Categories(unittest.TestCase):
    """DASH-626: every entry's kind is a known category, and a category nobody uses (AI assistants, for now) lists nothing."""

    def rows(self):
        with open(os.path.join(ROOT, "catalogue.json"), encoding="utf-8") as f:
            return json.load(f)["plugins"]

    def test_every_kind_is_a_known_category(self):
        for e in self.rows():
            self.assertIn(e["kind"], make_examples.CATEGORIES, e["id"])

    def test_the_list_has_no_repeats_and_is_sentence_case(self):
        cats = make_examples.CATEGORIES
        self.assertEqual(len(cats), len(set(cats)))
        for c in cats:
            for word in c.split()[1:]:
                self.assertEqual(word, word.lower(), c)

    def test_ai_assistants_is_a_category_with_no_plug_in_yet(self):
        self.assertIn("AI assistants", make_examples.CATEGORIES)
        self.assertEqual([e["id"] for e in self.rows() if e["kind"] == "AI assistants"], [])

    def test_an_unknown_category_stops_the_build(self):
        make_examples.KINDS["zz-test"] = "AI assistant"
        try:
            with self.assertRaises(SystemExit):
                make_examples.category("zz-test")
        finally:
            del make_examples.KINDS["zz-test"]
        self.assertEqual(make_examples.category("styles"), "Appearance")


class PublishedRule(unittest.TestCase):
    def test_no_containers_is_published(self):
        self.assertTrue(make_examples.published({"id": "styles"}))
        self.assertTrue(make_examples.published({"id": "styles", "containers": []}))

    def test_every_image_pinned_is_published(self):
        m = {"containers": [{"image": "ghcr.io/themightytrex/one" + DIGEST}, {"image": "docker.io/library/two" + DIGEST}]}
        self.assertTrue(make_examples.published(m))

    def test_one_tag_keeps_it_coming_soon(self):
        m = {"containers": [{"image": "ghcr.io/themightytrex/one" + DIGEST}, {"image": "docker.io/library/two:1.0.0"}]}
        self.assertFalse(make_examples.published(m))
        self.assertFalse(make_examples.published({"containers": [{"image": "ghcr.io/themightytrex/one:latest"}]}))

    def test_a_short_or_missing_digest_is_not_pinned(self):
        self.assertFalse(make_examples.published({"containers": [{"image": "ghcr.io/themightytrex/one@sha256:abc"}]}))
        self.assertFalse(make_examples.published({"containers": [{"name": "app"}]}))

    def test_catalogue_follows_the_rule(self):
        with open(os.path.join(ROOT, "catalogue.json"), encoding="utf-8") as f:
            rows = json.load(f)["plugins"]
        self.assertTrue(rows)
        for e in rows:
            self.assertEqual(e["published"], make_examples.published(manifest(e["id"])), e["id"])



class RecommendedRule(unittest.TestCase):
    """DASH-425 (owner, 14 November 2026): "its recommended in the catalogue", "only downloaded if required"."""

    def rows(self):
        with open(os.path.join(ROOT, "catalogue.json"), encoding="utf-8") as f:
            return {e["id"]: e for e in json.load(f)["plugins"]}

    def test_every_row_says_whether_it_is_recommended(self):
        rows = self.rows()
        self.assertTrue(all(isinstance(e.get("recommended"), bool) for e in rows.values()))
        self.assertEqual({k for k, e in rows.items() if e["recommended"]}, make_examples.RECOMMENDED)

    def test_direct_play_is_recommended_and_a_few_at_most(self):
        self.assertIn("direct-play", make_examples.RECOMMENDED)
        self.assertLessEqual(len(make_examples.RECOMMENDED), 4)
        self.assertTrue(make_examples.RECOMMENDED <= set(self.rows()))


if __name__ == "__main__":
    unittest.main()
