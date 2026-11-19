"""Catalogue summaries end at a whole sentence or word (Starboard issue #169: one ended "a described track an")."""
import json
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))
import make_examples  # noqa: E402


class Summaries(unittest.TestCase):
    def test_cut_at_a_sentence_or_a_word(self):
        self.assertEqual(make_examples.whole("One two three. Four five six seven.", 20), "One two three.")
        self.assertEqual(make_examples.whole("alpha beta gamma delta epsilon", 18), "alpha beta gamma…")
        self.assertEqual(make_examples.whole("short", 10), "short")
        self.assertLessEqual(len(make_examples.whole("word " * 400, 600)), 600)

    def test_no_summary_in_the_catalogue_stops_mid_word(self):
        for p in json.load(open(os.path.join(ROOT, "catalogue.json")))["plugins"]:
            for v in p.get("versions") or []:
                text = (v.get("changelog") or "").rstrip()
                if text:
                    self.assertTrue(text.endswith((".", "…", "!", "?", ")")), (p["id"], v["version"], text[-40:]))
