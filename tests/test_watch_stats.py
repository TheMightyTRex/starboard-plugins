"""Watch statistics (DASH-402): Playback Reporting's rows read with one query, series counted together, people and
titles added up, read-only tables Starboard accepts, the answer kept for 15 minutes, and plain words when Playback
Reporting is not installed."""
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import load, manifest, starboard_cleaners  # noqa: E402

NOW = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - 3600))
DAY_AGO = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - 86400 - 3600))
ROWS = [[NOW + ".1234567", "Sam", "Slow Horses - s01e01 - Failure's Contagious", "Episode", "Lounge TV", "Jellyfin Web", "3120"],
        [NOW, "Alex", "Dune: Part Two", "Movie", "Bedroom TV", "Android TV", "9960"],
        [DAY_AGO, "Sam", "Slow Horses - s01e02 - Last Stop", "Episode", "Lounge TV", "Jellyfin Web", "2940"],
        [DAY_AGO, "Alex", "Slow Horses - s01e02 - Last Stop", "Episode", "", "Jellyfin Web", "3000"],
        [DAY_AGO, "Test", "Dune: Part Two", "Movie", "Phone", "Jellyfin Web", "60"]]


class Fake:
    """Jellyfin with or without Playback Reporting, counting the calls."""

    def __init__(self, reporting=True):
        self.reporting, self.calls = reporting, []

    def get(self, path):
        self.calls.append(path)
        if path == "/Plugins":
            return [{"Name": "Playback Reporting", "Status": "Active"}] if self.reporting else [{"Name": "TMDb", "Status": "Active"}]
        if path == "/Users":
            return [{"Id": "u1", "Name": "Sam"}]
        if path.startswith("/Users/u1/Items"):
            stamp = time.strftime("%Y-%m-%dT%H:%M:%S.0000000Z", time.gmtime(time.time() - 7200))
            return {"Items": [{"Name": "Pilot", "SeriesName": "Slow Horses", "Type": "Episode", "UserData": {"LastPlayedDate": stamp}}]}
        return None

    def post(self, path, body):
        self.calls.append(path)
        assert path == "/user_usage_stats/submit_custom_query"
        assert "FROM PlaybackActivity" in body["CustomQueryString"] and body["ReplaceUserId"] is True
        return {"colums": ["DateCreated", "UserId", "ItemName", "ItemType", "DeviceName", "ClientName", "PlayDuration"], "results": ROWS}


def app_with(fake, **values):
    app = load("watch-stats", values)
    app.jellyfin, app.jellyfin_post = fake.get, fake.post
    return app


class Figures(unittest.TestCase):
    def test_series_count_together_and_people_add_up(self):
        app = app_with(Fake())
        rows = app.plays()["rows"]
        self.assertEqual(len(rows), 5)
        top = dict(app.tops(rows))
        self.assertEqual(top["Slow Horses"]["plays"], 3)
        self.assertEqual(top["Slow Horses"]["people"], {"Sam", "Alex"})
        people = dict(app.by_person(rows))
        self.assertEqual(people["Sam"]["seconds"], 3120 + 2940)
        self.assertEqual(people["Sam"]["titles"].most_common(1)[0][0], "Slow Horses")

    def test_people_can_be_left_out(self):
        app = app_with(Fake(), leave_out=["test"])
        self.assertNotIn("Test", {r["who"] for r in app.plays()["rows"]})

    def test_the_answer_is_kept_for_15_minutes(self):
        fake = Fake()
        app = app_with(fake)
        app.card_week()
        app.card_top()
        app.screen_people()
        self.assertEqual(fake.calls.count("/user_usage_stats/submit_custom_query"), 1)
        app.refresh()
        self.assertEqual(fake.calls.count("/user_usage_stats/submit_custom_query"), 2)

    def test_the_cards(self):
        app = app_with(Fake())
        week = app.card_week()
        self.assertEqual(week["value"], 5)
        self.assertEqual(week["note"], "5.3 hours by 3 people")
        self.assertEqual(app.card_top()["items"][0], {"title": "Slow Horses", "detail": "2 people, 3 plays"})
        self.assertTrue(app.card_people()["items"][0]["detail"].startswith("3.6 hours, 2 plays"))
        self.assertEqual(app.card_source()["state"], "ok")


class Tables(unittest.TestCase):
    def test_three_read_only_tables(self):
        app = app_with(Fake())
        plays, titles, people = app.screen_plays(), app.screen_titles(), app.screen_people()
        for s in (plays, titles, people):
            self.assertIs(s["readonly"], True)
            self.assertEqual(s["layout"], "folds")
            self.assertEqual(s["notices"], [])
            self.assertTrue(all(it["actions"] == [] for it in s["items"]))
        self.assertEqual([c["label"] for c in plays["columns"]], ["Time", "Person", "Title", "Device", "Minutes"])
        self.assertTrue({"Today", "Yesterday"} & {it["group"] for it in plays["items"]})
        self.assertEqual({it["group"] for it in titles["items"]}, {"Series", "Films"})
        with self.assertRaises(ValueError):
            app.act({"action": "toggle", "id": "p0"})

    def test_starboard_draws_them(self):
        got = starboard_cleaners()
        if not got:
            self.skipTest("Starboard's source is not on this computer")
        plugin_cards, plugin_custom = got
        app = app_with(Fake())
        for s in (app.screen_plays(), app.screen_titles(), app.screen_people()):
            out = plugin_custom.clean(s)
            self.assertEqual(out["layout"], "folds")
            if "readonly" not in out:
                self.skipTest("this Starboard is older than plug-in API 1.11")
            self.assertTrue(all(it["cells"] for it in out["items"]))
        plugin_cards.clean("stat", app.card_week())
        for path in ("card_top", "card_people"):
            plugin_cards.clean("list", getattr(app, path)())
        plugin_cards.clean("status", app.card_source())


class WithoutPlaybackReporting(unittest.TestCase):
    def test_it_says_so_and_how_to_add_it_and_shows_what_jellyfin_knows(self):
        fake = Fake(reporting=False)
        app = app_with(fake)
        self.assertNotIn("/user_usage_stats/submit_custom_query", fake.calls)
        source = app.card_source()
        self.assertEqual(source["state"], "warning")
        self.assertIn("Playback Reporting is not installed in Jellyfin", source["text"])
        screen = app.screen_titles()
        self.assertEqual(screen["notices"][0]["tone"], "warning")
        self.assertIn("Settings, Jellyfin", screen["notices"][0]["text"])
        self.assertEqual(screen["items"][0]["cells"]["title"], "Slow Horses")
        self.assertEqual(app.card_week()["note"], "Playback Reporting is not installed in Jellyfin")
        self.assertIn("last plays only", app.refresh()["said"])


class Manifest(unittest.TestCase):
    def test_it_rests_and_has_three_tables(self):
        m = manifest("watch-stats")
        self.assertEqual(m["containers"][0]["start"], "when_needed")
        self.assertEqual([s["choices"] for s in m["settings"] if s["type"] == "custom"], ["/screen/plays", "/screen/titles", "/screen/people"])
        self.assertEqual(m["permissions"], ["jellyfin:key", "network:lan"])
        got = starboard_cleaners()
        if got:
            from starboard import plugins
            if plugins._range_ok(m["starboard_api"]):
                m["containers"][0]["image"] = "ghcr.io/themightytrex/starboard-plugin-examples@sha256:" + "0" * 64
                self.assertEqual(plugins.check(m), [])


if __name__ == "__main__":
    unittest.main()
