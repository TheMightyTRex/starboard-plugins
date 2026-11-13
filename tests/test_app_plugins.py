"""App plug-ins (DASH-411): Jellystat, Navidrome, Kavita, Calibre-Web, Wizarr, Maintainerr, Uptime Kuma, Seerr and
Tdarr, each a whole app kept out of the main install. These check each one asks for the least it needs and passes
Starboard's own manifest check (plug-in API 1.13), and that its catalogue entry says what it costs at rest."""
import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT, STARBOARD_SRC, manifest  # noqa: E402

APPS = ("jellystat", "navidrome", "kavita", "calibre-web", "wizarr", "maintainerr", "uptime-kuma", "seerr", "tdarr")
# Each app's own folders: read only, except Tdarr, which converts films and series in place.
WRITES_MEDIA = {"tdarr": {"media/movies", "media/tv", "media/tdarr-cache"}}  # tdarr-cache: its working copies (1.0.2)
JELLYFIN_KEY = {"jellystat"}  # the only one Starboard hands Jellyfin's key to; the others are given it in their own page
OWN_IMAGE = re.compile(r"^ghcr\.io/themightytrex/")


def checker():
    if not os.path.isdir(os.path.join(STARBOARD_SRC, "starboard")):
        return None
    sys.path.insert(0, STARBOARD_SRC)
    from starboard import plugins
    return plugins if plugins._range_ok(">=1.13") else None


class AppPlugins(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "catalogue.json"), encoding="utf-8") as f:
            self.catalogue = {e["id"]: e for e in json.load(f)["plugins"]}

    def test_each_passes_starboards_check(self):
        plugins = checker()
        if not plugins:
            self.skipTest("Starboard's source with plug-in API 1.13 is not here (STARBOARD_SRC)")
        for pid in APPS:
            # dev: only Jellystat's own helper, named by its next tag until GitHub builds it
            self.assertEqual(plugins.check(manifest(pid), dev=pid == "jellystat"), [], pid)

    def test_third_party_images_pinned_by_digest(self):
        for pid in APPS:
            for c in manifest(pid)["containers"]:
                if not OWN_IMAGE.match(c["image"]):
                    self.assertRegex(c["image"], r"@sha256:[0-9a-f]{64}$", f"{pid} {c['name']}")

    def test_least_permissions(self):
        for pid in APPS:
            m = manifest(pid)
            perms = set(m["permissions"])
            self.assertEqual(perms - {"network:lan", "network:port", "jellyfin:key"}, set(), pid)
            self.assertEqual("jellyfin:key" in perms, pid in JELLYFIN_KEY, pid)
            vols = {v for c in m["containers"] for v in c.get("volumes") or []}
            self.assertNotIn("media:ro", vols, f"{pid} sees only its own media folders")
            writes = {v for v in vols if v.startswith("media/") and not v.endswith(":ro")}
            self.assertEqual(writes, WRITES_MEDIA.get(pid, set()), pid)
            for c in m["containers"]:
                self.assertNotEqual((c.get("user") or "10001:10001").split(":")[0], "0", pid)

    def test_one_web_page_each_and_the_database_stays_private(self):
        for pid in APPS:
            m = manifest(pid)
            pages = [c for c in m["containers"] if c.get("publish")]
            self.assertEqual(len(pages), 1, pid)
            self.assertEqual(pages[0]["network"], "lan", pid)
        db = next(c for c in manifest("jellystat")["containers"] if c["name"] == "db")
        self.assertEqual(db.get("network", "default"), "default")
        self.assertIn("{secret:db_password}", db["env"]["POSTGRES_PASSWORD"])

    def test_catalogue_entry_in_apps_you_can_add_with_rest_figures(self):
        for pid in APPS:
            e = self.catalogue.get(pid)
            self.assertIsNotNone(e, pid)
            self.assertEqual(e["kind"], "Apps you can add", pid)
            self.assertGreater(e["rest"]["memory_mb"], 0, pid)
            self.assertGreaterEqual(e["rest"]["cpu_percent"], 0, pid)
            self.assertEqual(sorted(e["permissions"]), sorted(manifest(pid)["permissions"]), pid)
            self.assertEqual(e["version"], manifest(pid)["version"], pid)

    def test_readme_says_who_it_is_for_and_what_removing_does(self):
        for pid in APPS:
            with open(os.path.join(ROOT, pid, "README.md"), encoding="utf-8") as f:
                text = f.read()
            for words in ("Who it is for", "At rest", "Removing it", "What it may do"):
                self.assertIn(words, text, pid)
            self.assertNotRegex(text, r"\b(can't|don't|won't|isn't|doesn't|it's)\b", pid)
            self.assertNotIn("—", text, pid)

    def test_seerr_says_reelix_has_requests(self):
        self.assertIn("Reelix already has requests", manifest("seerr")["description"])

    def test_tdarr_adopts_by_copying(self):
        a = manifest("tdarr")["adopt"]
        self.assertEqual((a["app"], a["into"], a["stop"]), ("tdarr", "server", True))
        self.assertEqual(set(a["copy"]), {"/app/server", "/app/configs", "/app/logs"})  # never the 51 GB cache


if __name__ == "__main__":
    unittest.main()
