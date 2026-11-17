"""tools/publish_images.py: pins a built image only when it was built from the files there now (17 November 2026)."""
import glob
import os
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import publish_images as pi  # noqa: E402

D1 = "sha256:" + "a" * 64
D2 = "sha256:" + "b" * 64


class Targets(unittest.TestCase):
    def test_every_image_workflow_is_a_target_with_its_paths(self):
        names = {t["repo"] for t in pi.targets()}
        built = set()
        for wf in glob.glob(os.path.join(ROOT, ".github", "workflows", "*.yml")):
            m = re.search(r"ghcr\.io/themightytrex/(starboard-plugin-[a-z0-9-]+):\$\{\{", open(wf).read())
            if m:
                built.add(m.group(1))
        self.assertEqual(names, built)
        for t in pi.targets():
            self.assertTrue(t["paths"], t["repo"])
            self.assertFalse(any(p.startswith(".github/") for p in t["paths"]))

    def test_every_image_is_labelled_with_the_commit_it_was_built_from(self):
        for wf in glob.glob(os.path.join(ROOT, ".github", "workflows", "*.yml")):
            text = open(wf).read()
            if "docker/build-push-action" in text:
                self.assertIn("org.opencontainers.image.revision=${{ github.sha }}", text, wf)

    def test_the_publish_workflow_follows_every_image_workflow(self):
        publish = open(os.path.join(ROOT, ".github", "workflows", "publish.yml")).read()
        for wf in glob.glob(os.path.join(ROOT, ".github", "workflows", "*.yml")):
            text = open(wf).read()
            if "docker/build-push-action" in text:
                name = re.search(r"^name: (.+)$", text, re.M).group(1).strip()
                self.assertIn(f'"{name}"', publish, f"add {name!r} to workflow_run in publish.yml")


class Pinning(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.manifest = os.path.join(self.dir, "starboard-plugin.json")
        open(self.manifest, "w").write('{"x": {"image": "ghcr.io/themightytrex/starboard-plugin-demo:1.0.0"}}')
        self.t = {"name": "Demo", "repo": "starboard-plugin-demo", "tag": "1.0.0", "paths": ["demo/app.py"],
                  "pin": ("manifest", self.manifest)}

    def test_a_tag_is_replaced_by_the_digest_and_a_digest_by_a_newer_one(self):
        pi.pin(self.t, D1)
        self.assertIn(f"starboard-plugin-demo@{D1}\"", open(self.manifest).read())
        self.assertEqual(pi.pinned(self.t), D1)
        pi.pin(self.t, D2)
        self.assertEqual(pi.pinned(self.t), D2)
        self.assertNotIn(D1, open(self.manifest).read())

    def run_main(self, digest, revision, same):
        with mock.patch.object(pi, "targets", return_value=[self.t]), \
             mock.patch.object(pi, "registry", return_value=(digest, revision)), \
             mock.patch.object(pi, "same_files", return_value=same):
            pi.main([])
        return pi.pinned(self.t)

    def test_pinned_only_when_built_from_the_same_files(self):
        self.assertEqual(self.run_main(D1, "abc1234", False), "")
        self.assertEqual(self.run_main(D1, None, True), "")
        self.assertEqual(self.run_main(None, None, True), "")
        self.assertEqual(self.run_main(D1, "abc1234", True), D1)

    def test_same_files_compares_with_git(self):
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        self.assertTrue(pi.same_files(head, ["tools/examples_src.py"]) in (True, False))
        self.assertFalse(pi.same_files("0" * 40, ["tools/examples_src.py"]))
        self.assertFalse(pi.same_files(None, ["tools/examples_src.py"]))
        self.assertFalse(pi.same_files(head, []))


if __name__ == "__main__":
    unittest.main()
