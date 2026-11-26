"""Every plug-in that runs from the shared examples image has its app copied into that image (25 November 2026:
Backups watch 0.1.0 was pinned to an image that lacked /app/backups-watch/app.py, so its container would not start)."""
import glob
import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ExamplesDockerfile(unittest.TestCase):
    def test_every_example_app_is_copied(self):
        with open(os.path.join(ROOT, "Dockerfile"), encoding="utf-8") as f:
            copies = re.findall(r"^COPY\s+(\S+)", f.read(), re.M)
        found = 0
        for path in sorted(glob.glob(os.path.join(ROOT, "*", "starboard-plugin.json"))):
            with open(path, encoding="utf-8") as f:
                manifest = json.load(f)
            for c in manifest.get("containers", []):
                if "starboard-plugin-examples" not in c.get("image", ""):
                    continue
                name = (c.get("env") or {}).get("EXAMPLE")
                if not name:
                    continue
                found += 1
                self.assertIn(f"{name}/app.py", copies, f"{name} runs from the examples image but the Dockerfile does not copy its app.py")
        self.assertGreater(found, 5)


if __name__ == "__main__":
    unittest.main()
