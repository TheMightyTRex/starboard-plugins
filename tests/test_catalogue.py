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


if __name__ == "__main__":
    unittest.main()
