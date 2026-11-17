"""Plug-in API 1.14 across the collection (15 November 2026): every plug-in has a logo Starboard accepts with words
for it, names an API range that has 1.14, says what is new in its own version, and every card example uses the
band's status values; the catalogue carries each logo and keeps the last version for an older Starboard; and the
shared helper's band and update steps work."""
import base64
import json
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT, STARBOARD_SRC, manifest  # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "tools"))
import make_logos  # noqa: E402

IDS = sorted(d for d in os.listdir(ROOT) if os.path.isfile(os.path.join(ROOT, d, "starboard-plugin.json")))
STATUSES = {"ok", "done", "ready", "protected", "working", "converting", "scanning", "updating", "running", "waiting", "idle",
            "scheduled", "paused", "inactive", "warning", "needs_setup", "problem", "failed", "stopped"}
PREVIOUS = json.load(open(os.path.join(ROOT, "tools", "previous-versions.json")))


def starboard():
    if not os.path.isfile(os.path.join(STARBOARD_SRC, "starboard", "plugin_logo.py")):
        return None
    sys.path.insert(0, STARBOARD_SRC)
    from starboard import plugin_logo, plugins
    return plugin_logo, plugins


class Collection(unittest.TestCase):
    def test_every_plugin_has_a_logo_starboard_accepts(self):
        sb = starboard()
        for pid in IDS:
            m = manifest(pid)
            self.assertEqual(m.get("logo"), make_logos.entry(pid), pid)
            data = open(os.path.join(ROOT, pid, "logo.svg"), "rb").read()
            self.assertEqual(data, make_logos.svg(pid).encode(), pid)
            self.assertLess(len(data), 16 * 1024, pid)
            self.assertGreaterEqual(make_logos.contrast(make_logos.LOGOS[pid][0]), 4.5, pid)
            # ALT-TEXT.md section 6: a logo is described by its name. Starboard uses the alt only where the logo stands
            # on its own, and hides the logo beside the name (design system audit, 17 November 2026).
            self.assertEqual(m["logo"]["alt"], f"{m['name']} logo", pid)
            if sb:
                sb[0].clean_svg(data)
                self.assertEqual(sb[0].check_entry(m["logo"]), [], pid)

    def test_no_brand_marks_in_the_symbols(self):
        """The symbol's own words (for the help) name no other project's logo: each symbol is a neutral one."""
        for pid in IDS:
            alt = make_logos.LOGOS[pid][1].lower()
            for brand in ("jellyfin", "home assistant", "seerr", "calibre", "kavita", "navidrome", "tdarr", "kuma", "wizarr", "jellystat"):
                self.assertNotIn(brand, alt, pid)

    def test_every_plugin_needs_api_114_and_says_what_is_new(self):
        sb = starboard()
        newer = {"library-cleanup": ">=1.15 <2.0",  # DASH-406: needs library:holding, new in plug-in API 1.15
                 "tv-station": ">=1.15 <2.0"}  # DASH-477: a title for each card size, new in plug-in API 1.15
        for pid in IDS:
            m = manifest(pid)
            self.assertEqual(m["starboard_api"], newer.get(pid, ">=1.14 <2.0"), pid)
            self.assertEqual(m["changes"][0]["version"], m["version"], pid)
            if sb and pid not in newer:
                self.assertTrue(sb[1]._range_ok(m["starboard_api"], "1.14.0"), pid)
                self.assertFalse(sb[1]._range_ok(m["starboard_api"], "1.13.0"), pid)

    def test_every_published_plugin_has_a_new_version(self):
        for pid, old in PREVIOUS["plugins"].items():
            self.assertNotEqual(manifest(pid)["version"], old["version"], pid)

    def test_card_examples_use_the_band(self):
        for pid in IDS:
            for c in manifest(pid).get("cards") or []:
                ex = c.get("example")
                if ex is None:
                    continue
                self.assertIn(ex.get("status"), STATUSES, f"{pid} {c['id']}")
                self.assertLessEqual(len(ex.get("status_label", "")), 24, f"{pid} {c['id']}")
                self.assertIsInstance(ex.get("updated"), int, f"{pid} {c['id']}")

    def test_update_steps_point_at_the_shared_paths(self):
        for pid in IDS:
            u = manifest(pid).get("update")
            if u:
                self.assertEqual((u["before"]["path"], u["after"]["path"]), ("/update/before", "/update/after"), pid)
                self.assertTrue(manifest(pid).get("health"), pid)

    def test_catalogue_carries_logos_and_older_versions(self):
        rows = {e["id"]: e for e in json.load(open(os.path.join(ROOT, "catalogue.json")))["plugins"]}
        self.assertEqual(set(rows), set(IDS))
        for pid, e in rows.items():
            self.assertEqual(e["logo_alt"], make_logos.alt(pid))
            self.assertLessEqual(len(e["logo"]), 24 * 1024)
            self.assertEqual(base64.b64decode(e["logo"].split(",", 1)[1]), open(os.path.join(ROOT, pid, "logo.svg"), "rb").read())
            old = PREVIOUS["plugins"].get(pid)
            if old:
                newest, kept = e["versions"]
                self.assertEqual(newest["version"], manifest(pid)["version"])
                self.assertEqual((kept["version"], kept["manifest_sha256"]), (old["version"], old["sha256"]))
                self.assertIn(PREVIOUS["commit"], kept["manifest"])
            else:
                self.assertNotIn("versions", e)
        self.assertFalse(rows["picture-shrinker"]["recommended"])

    def test_every_manifest_passes_starboards_check(self):
        sb = starboard()
        if not sb:
            self.skipTest("Starboard's source is not here")
        for pid in IDS:
            self.assertEqual(sb[1].check(manifest(pid), dev=True), [], pid)


class SharedHelper(unittest.TestCase):
    """The shared sbplugin: the band and the update steps. Imported on its own (the examples serve when loaded)."""

    def setUp(self):
        sys.path.insert(0, os.path.join(ROOT, "_shared"))
        sys.modules.pop("sbplugin", None)
        import sbplugin
        self.sb = sbplugin
        self.sb._work.update(running=[], hold=0.0)

    def tearDown(self):
        sys.path.remove(os.path.join(ROOT, "_shared"))

    def test_band(self):
        out = self.sb.band({"value": 1}, "scheduled", time.time() + 999, "Next test at 04:00 and more words", 5)
        self.assertEqual(out["status"], "scheduled")
        self.assertEqual(len(out["status_label"]), 24)
        self.assertLessEqual(out["updated"], time.time())
        self.assertEqual(out["refresh_seconds"], 10)
        self.assertEqual(self.sb.STATUSES, STATUSES)
        with self.assertRaises(ValueError):
            self.sb.band({}, "sleeping")

    def test_before_waits_and_holds_then_after_lets_go(self):
        self.sb.WAIT_SECONDS = 0.2
        with self.sb.working("test"):
            busy = self.sb.before_update({})
        self.assertFalse(busy["ok"])
        self.assertFalse(self.sb.holding())
        ready = self.sb.before_update({})
        self.assertTrue(ready["ok"])
        self.assertTrue(self.sb.holding())
        self.assertTrue(self.sb.after_update({"outcome": "rolled_back"})["ok"])
        self.assertFalse(self.sb.holding())

    def test_every_copy_is_the_shared_one(self):
        shared = open(os.path.join(ROOT, "_shared", "sbplugin.py"), "rb").read()
        for pid in IDS:
            path = os.path.join(ROOT, pid, "sbplugin.py")
            # Picture shrinker 1.2.0 sends Jellyfin's key its own way and keeps the copy from before DASH-458 until
            # its next version takes this one.
            if os.path.isfile(path) and pid not in ("remote-access", "picture-shrinker"):
                self.assertEqual(open(path, "rb").read(), shared, pid)


if __name__ == "__main__":
    unittest.main()
