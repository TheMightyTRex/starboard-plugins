"""Library clean-up (DASH-406): the rules and what is always kept, what moves for a film or a series, the move into the
holding folder keeping its folders, Put back, what Reelix and Jellyfin are told, Preview, the daily job (deactivated
by default), the screens and card, and that nothing in it can delete. A made-up Jellyfin and Reelix answer in memory,
and the media folder is a temporary folder of small made-up files."""
import ast
import json
import os
import re
import sys
import tempfile
import unittest
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT, load, manifest, starboard_cleaners  # noqa: E402

DAY = 86400
NOW = 1794700000.0  # 15 November 2026


def iso(t):
    import datetime as dt
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.0000000Z")


class FakeJellyfin:
    """Two people, a Films and a Series library at Jellyfin's own paths (/data/media/...)."""

    def __init__(self):
        self.users = [{"Id": "u1", "Name": "Alex", "Policy": {}}, {"Id": "u2", "Name": "Sam", "Policy": {}},
                      {"Id": "u3", "Name": "Old account", "Policy": {"IsDisabled": True}}]
        self.libs = [{"Name": "Films", "ItemId": "lf", "CollectionType": "movies", "Locations": ["/data/media/movies"]},
                     {"Name": "Series", "ItemId": "ls", "CollectionType": "tvshows", "Locations": ["/data/media/tv"]},
                     {"Name": "Music", "ItemId": "lm", "CollectionType": "music", "Locations": ["/data/media/music"]}]
        self.items = {}  # id -> (library id, type, base fields)
        self.userdata = {}  # (user, id) -> UserData
        self.resume = {}  # user -> [items]
        self.boxsets = {}  # box id -> [ids]
        self.episodes_last = {}  # series id -> last played time (for anyone)
        self.told = []

    def add(self, iid, lib, kind, name, path, added, data=None, **more):
        self.items[iid] = (lib, kind, {"Id": iid, "Name": name, "ProductionYear": more.pop("year", 2001), "Path": path,
                                        "DateCreated": iso(added), "Tags": more.pop("tags", []), "ProviderIds": more.pop("ids", {}), **more})
        for u, d in (data or {}).items():
            self.userdata[(u, iid)] = d

    def __call__(self, path, data=None, method=None):
        url = urllib.parse.urlparse(path)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}
        if url.path == "/Library/VirtualFolders":
            return self.libs
        if url.path == "/Users":
            return self.users
        if url.path == "/Library/Media/Updated":
            self.told.append((data["Updates"][0]["UpdateType"], data["Updates"][0]["Path"]))
            return None
        if url.path == "/UserItems/Resume":
            return self._page(self.resume.get(q["userId"], []), q)
        if url.path == "/Items":
            if q.get("IncludeItemTypes") == "BoxSet":
                return self._page([{"Id": b} for b in self.boxsets], q)
            if q.get("ParentId") in self.boxsets:
                return self._page([{"Id": i} for i in self.boxsets[q["ParentId"]]], q)
            if q.get("IncludeItemTypes") == "Episode":
                t = self.episodes_last.get(q["ParentId"])
                return {"Items": [{"Id": "e", "UserData": {"LastPlayedDate": iso(t)}}] if t else [], "TotalRecordCount": 1 if t else 0}
            rows = [{**base, "UserData": self.userdata.get((q["userId"], iid), {})}
                    for iid, (lib, kind, base) in self.items.items() if lib == q["ParentId"] and kind == q["IncludeItemTypes"]]
            return self._page(rows, q)
        raise AssertionError(f"Jellyfin was asked {path}")

    @staticmethod
    def _page(rows, q):
        start, limit = int(q.get("StartIndex", 0)), int(q.get("Limit", 1000))
        return {"Items": rows[start:start + limit], "TotalRecordCount": len(rows)}


class FakeReelix:
    def __init__(self):
        self.movies = [{"id": 7, "tmdb_id": 111, "monitored": True}, {"id": 8, "tmdb_id": 222, "monitored": False}]
        self.series = [{"id": 30, "tvdb_id": 9000, "monitored": True}]
        self.episodes = {30: [{"id": 301, "season_number": 1, "monitored": True}, {"id": 302, "season_number": 1, "monitored": False},
                              {"id": 303, "season_number": 2, "monitored": True}]}
        self.calls = []

    def __call__(self, path, data=None, method=None):
        url = urllib.parse.urlparse(path)
        self.calls.append((method or "GET", url.path, data))
        if url.path == "/movies":
            return {"items": self.movies, "total": len(self.movies)}
        if url.path == "/series":
            return {"items": self.series, "total": len(self.series)}
        m = re.match(r"^/series/(\d+)/episodes$", url.path)
        if m:
            return self.episodes[int(m.group(1))]
        return {}


def touch(path, size=10):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"x" * size)
    return path


class Base(unittest.TestCase):
    def setUp(self):
        self.app = load("library-cleanup", {})
        self.media = tempfile.TemporaryDirectory()
        self.app.MEDIA = self.media.name
        self.app.now = lambda: NOW
        self.jf, self.rx = FakeJellyfin(), FakeReelix()
        self.app.jf, self.app.rx = self.jf, self.rx
        with open(os.path.join(self.app._run, "reelix.json"), "w") as f:
            json.dump({"url": "http://reelix.invalid/api/v1", "api_key": "rx"}, f)
        self.app.sbplugin._work["hold"] = 0.0
        os.makedirs(self.m("music"))

    def tearDown(self):
        t = self.app._job.get("thread")
        if t:
            t.join(10)
        self.media.cleanup()
        self.app._tmp.cleanup()

    def m(self, *parts):
        return os.path.join(self.media.name, *parts)

    def film(self, iid, folder, data=None, added=NOW - 400 * DAY, **more):
        touch(self.m("movies", folder, f"{folder}.mkv"), 1000)
        touch(self.m("movies", folder, f"{folder}.en.srt"), 10)
        self.jf.add(iid, "lf", "Movie", folder.split(" (")[0], f"/data/media/movies/{folder}/{folder}.mkv", added, data, **more)

    def show(self, iid, folder, data=None, added=NOW - 400 * DAY, status="Ended", **more):
        touch(self.m("tv", folder, "Season 01", "Episode 1.mkv"), 2000)
        self.jf.add(iid, "ls", "Series", folder.split(" (")[0], f"/data/media/tv/{folder}", added, data, Status=status, **more)

    @staticmethod
    def seen(days_ago, **more):
        return {"Played": True, "LastPlayedDate": iso(NOW - days_ago * DAY), **more}


class Rules(Base):
    def test_watched_by_everyone_and_long_ago(self):
        self.film("a", "Old Film (2001)", {"u1": self.seen(200), "u2": self.seen(120)})
        self.film("b", "Recent (2002)", {"u1": self.seen(200), "u2": self.seen(10)})  # Sam watched it 10 days ago
        self.film("c", "Half (2003)", {"u1": self.seen(200)}, added=NOW - 100 * DAY)  # Sam has not watched it
        p = self.app.plan()
        self.assertEqual([(i["title"], i["rule"]) for i in p["items"]], [("Old Film", "watched")])
        self.assertIn("last 120 days ago", p["items"][0]["why"])
        self.assertEqual(p["people"], 2)  # the disabled account does not count

    def test_people_to_leave_out(self):
        self.film("c", "Half (2003)", {"u1": self.seen(200)}, added=NOW - 100 * DAY)
        self.assertEqual(self.app.plan()["items"], [])
        self.app._set(ignore_people=["sam"])
        self.assertEqual([i["title"] for i in self.app.plan()["items"]], ["Half"])

    def test_not_watched_for_a_long_time(self):
        self.film("a", "Forgotten (1999)", {"u1": {"Played": False}}, added=NOW - 500 * DAY)
        self.film("b", "New (2026)", {}, added=NOW - 20 * DAY)  # added recently: never caught
        self.film("c", "Last year (2000)", {"u1": {"Played": True, "LastPlayedDate": iso(NOW - 300 * DAY)}}, added=NOW - 900 * DAY)
        p = self.app.plan()
        self.assertEqual([(i["title"], i["rule"]) for i in p["items"]], [("Forgotten", "unwatched")])
        self.app._set(unwatched_months=6)
        self.assertEqual(sorted(i["title"] for i in self.app.plan()["items"]), ["Forgotten", "Last year"])

    def test_a_series_that_ended_and_is_all_watched(self):
        self.show("s1", "Harbour Lights (2019)", {"u1": {"Played": True}, "u2": {"Played": True}}, ids={"Tvdb": "9000"})
        self.show("s2", "Still Going (2020)", {"u1": {"Played": True}, "u2": {"Played": True}}, status="Continuing")
        self.show("s3", "Just Finished (2018)", {"u1": {"Played": True}, "u2": {"Played": True}})
        self.jf.episodes_last = {"s1": NOW - 200 * DAY, "s3": NOW - 3 * DAY}
        p = self.app.plan()
        self.assertEqual([(i["title"], i["rule"]) for i in p["items"]], [("Harbour Lights", "ended")])
        self.assertEqual(p["items"][0]["paths"], ["tv/Harbour Lights (2019)"])

    def test_each_rule_can_be_deactivated(self):
        self.film("a", "Old Film (2001)", {"u1": self.seen(200), "u2": self.seen(120)})
        self.film("b", "Forgotten (1999)", {}, added=NOW - 500 * DAY)
        self.show("s1", "Harbour Lights (2019)", {"u1": {"Played": True}, "u2": {"Played": True}})
        self.app._set(watched=False, unwatched=False, ended=False)
        self.assertEqual(self.app.plan()["items"], [])

    def test_always_kept(self):
        self.film("fav", "Loved (2001)", {"u1": self.seen(200, IsFavorite=True), "u2": self.seen(200)})
        self.film("part", "Half Way (2001)", {"u1": self.seen(200), "u2": self.seen(200)})
        self.film("box", "In A Set (2001)", {"u1": self.seen(200), "u2": self.seen(200)})
        self.film("tag", "Tagged (2001)", {"u1": self.seen(200), "u2": self.seen(200)}, tags=["Keep"])
        self.film("go", "Goes (2001)", {"u1": self.seen(200), "u2": self.seen(200)})
        self.jf.resume = {"u2": [{"Id": "part"}]}
        self.jf.boxsets = {"bx": ["box"]}
        p = self.app.plan()
        self.assertEqual([i["title"] for i in p["items"]], ["Goes"])
        self.assertEqual(p["kept"], 4)
        self.app._set(keep_favourites=False, keep_in_progress=False, keep_collections=False, keep_tag="")
        self.assertEqual(len(self.app.plan()["items"]), 5)

    def test_part_way_through_a_series(self):
        self.show("s1", "Halfway Show (2019)", {"u1": {"Played": False, "PlayedPercentage": 40}}, added=NOW - 900 * DAY)
        self.jf.resume = {}
        self.assertEqual(self.app.plan()["items"], [])

    def test_libraries_can_be_left_alone(self):
        self.film("a", "Old Film (2001)", {"u1": self.seen(200), "u2": self.seen(120)})
        out = self.app.libraries_post({"action": "toggle", "id": "lf"})
        self.assertEqual(out["said"], "The rules leave this library alone")
        self.assertEqual([i["id"] for i in out["items"]], ["lf", "ls"])  # films and series only, not music
        self.assertEqual(self.app.plan()["items"], [])
        self.app.libraries_post({"action": "toggle", "id": "lf"})
        self.assertEqual(len(self.app.plan()["items"]), 1)


class WhatMoves(Base):
    def test_a_film_in_its_own_folder_moves_with_its_folder(self):
        self.film("a", "Old Film (2001)", {"u1": self.seen(200), "u2": self.seen(120)})
        item = self.app.plan()["items"][0]
        self.assertEqual(item["paths"], ["movies/Old Film (2001)"])
        self.assertEqual(item["size"], 1010)

    def test_films_sharing_a_folder_move_one_by_one(self):
        touch(self.m("movies", "loose", "One.mkv"), 100)
        touch(self.m("movies", "loose", "One.en.srt"), 5)
        touch(self.m("movies", "loose", "One-two.mkv"), 100)
        touch(self.m("movies", "loose", "Two.mkv"), 100)
        self.jf.add("one", "lf", "Movie", "One", "/data/media/movies/loose/One.mkv", NOW - 400 * DAY, {"u1": self.seen(200), "u2": self.seen(200)})
        self.jf.add("two", "lf", "Movie", "Two", "/data/media/movies/loose/Two.mkv", NOW - 400 * DAY, {})
        item = next(i for i in self.app.plan()["items"] if i["title"] == "One")
        self.assertEqual(item["paths"], ["movies/loose/One.en.srt", "movies/loose/One.mkv"])  # not One-two.mkv

    def test_a_film_at_the_top_of_the_library_moves_with_its_files(self):
        touch(self.m("movies", "Top.mkv"), 100)
        touch(self.m("movies", "Top.nfo"), 5)
        self.jf.add("top", "lf", "Movie", "Top", "/data/media/movies/Top.mkv", NOW - 400 * DAY, {"u1": self.seen(200), "u2": self.seen(200)})
        self.assertEqual(self.app.plan()["items"][0]["paths"], ["movies/Top.mkv", "movies/Top.nfo"])

    def test_something_not_in_the_media_folder_is_left_and_said(self):
        self.jf.add("x", "lf", "Movie", "Elsewhere", "/data/media/movies/Gone/Gone.mkv", NOW - 400 * DAY, {"u1": self.seen(200), "u2": self.seen(200)})
        os.makedirs(self.m("movies"), exist_ok=True)
        p = self.app.plan()
        self.assertEqual(p["items"], [])
        self.assertIn("Elsewhere", p["problems"][0])

    def test_never_the_library_folder_itself(self):
        os.makedirs(self.m("tv"), exist_ok=True)
        self.jf.add("bad", "ls", "Series", "Bad", "/data/media/tv", NOW - 900 * DAY, {}, Status="Ended")
        self.assertEqual(self.app.plan()["items"], [])

    def test_paths_are_found_by_their_tail(self):
        os.makedirs(self.m("movies", "A"))
        self.assertEqual(self.app.local_for("/data/media/movies/A"), self.m("movies", "A"))
        self.assertEqual(self.app.local_for("/movies/A"), self.m("movies", "A"))
        self.assertIsNone(self.app.local_for("/nowhere/at/all"))


class MoveAndPutBack(Base):
    def setUp(self):
        super().setUp()
        self.film("a", "Old Film (2001)", {"u1": self.seen(200), "u2": self.seen(120)}, ids={"Tmdb": "111"})
        self.show("s1", "Harbour Lights (2019)", {"u1": {"Played": True}, "u2": {"Played": True}}, ids={"Tvdb": "9000"})
        self.jf.episodes_last = {"s1": NOW - 200 * DAY}

    def run_job(self):
        self.app._set(active=True)
        return self.app.job_move()

    def test_deactivated_by_default_and_nothing_moves(self):
        self.assertFalse(self.app.active())
        out = self.app.job_move()
        self.assertIn("deactivated", out["said"])
        self.assertTrue(os.path.isdir(self.m("movies", "Old Film (2001)")))
        self.assertEqual(self.rx.calls, [])
        self.assertEqual(self.jf.told, [])

    def test_the_job_moves_keeping_the_folders(self):
        out = self.run_job()
        self.assertEqual(out["said"], "Moved 2 items to the holding folder, freeing 3.0 KB")
        hold = self.m(".holding", "library-cleanup")
        self.assertFalse(os.path.exists(self.m("movies", "Old Film (2001)")))
        self.assertTrue(os.path.isfile(os.path.join(hold, "movies", "Old Film (2001)", "Old Film (2001).mkv")))
        self.assertTrue(os.path.isfile(os.path.join(hold, "tv", "Harbour Lights (2019)", "Season 01", "Episode 1.mkv")))
        self.assertEqual(len(self.app._held()), 2)

    def test_reelix_stops_following_and_jellyfin_is_told(self):
        self.run_job()
        self.assertIn(("PUT", "/movies/7", {"monitored": False}), self.rx.calls)
        self.assertIn(("POST", "/movies/7/rescan", {}), self.rx.calls)
        self.assertIn(("PUT", "/series/30", {"monitored": False}), self.rx.calls)
        self.assertIn(("PUT", "/episodes/monitor", {"episode_ids": [301, 303], "monitored": False}), self.rx.calls)
        self.assertEqual(sorted(self.jf.told), [("Deleted", "/data/media/movies/Old Film (2001)/Old Film (2001).mkv"),
                                                ("Deleted", "/data/media/tv/Harbour Lights (2019)")])

    def test_put_back_reverses_everything(self):
        self.run_job()
        self.rx.calls.clear()
        film = next(r for r in self.app._held() if r["kind"] == "films")
        show = next(r for r in self.app._held() if r["kind"] == "series")
        out = self.app.held_post({"action": "restore", "id": film["id"]})
        self.assertTrue(out["said"].startswith("Put back Old Film (2001) in movies"))
        self.assertIn("Reelix follows it again", out["said"])
        self.assertTrue(os.path.isfile(self.m("movies", "Old Film (2001)", "Old Film (2001).en.srt")))
        self.assertIn(("PUT", "/movies/7", {"monitored": True}), self.rx.calls)
        self.app.held_post({"action": "restore", "id": show["id"]})
        self.assertIn(("PUT", "/series/30", {"monitored": True}), self.rx.calls)
        self.assertIn(("PUT", "/episodes/monitor", {"episode_ids": [301, 303], "monitored": True}), self.rx.calls)  # only those it followed
        self.assertEqual(self.jf.told[-2:], [("Created", "/data/media/movies/Old Film (2001)/Old Film (2001).mkv"),
                                             ("Created", "/data/media/tv/Harbour Lights (2019)")])
        self.assertEqual(self.app._held(), [])

    def test_a_film_reelix_did_not_follow_stays_unfollowed(self):
        self.jf.items.clear()
        self.film("b", "Never Followed (2002)", {"u1": self.seen(200), "u2": self.seen(200)}, ids={"Tmdb": "222"})
        self.run_job()
        self.rx.calls.clear()
        self.app.held_post({"action": "restore", "id": self.app._held()[0]["id"]})
        self.assertNotIn(("PUT", "/movies/8", {"monitored": True}), self.rx.calls)
        self.assertIn(("POST", "/movies/8/rescan", {}), self.rx.calls)

    def test_put_back_refuses_when_something_is_there(self):
        self.run_job()
        film = next(r for r in self.app._held() if r["kind"] == "films")
        touch(self.m("movies", "Old Film (2001)", "new.mkv"))
        out = self.app.held_post({"action": "restore", "id": film["id"]})
        self.assertEqual(out["said"], "Something is at movies/Old Film (2001) now, so it stays in the holding folder")
        self.assertEqual(len(self.app._held()), 2)

    def test_a_row_moved_away_by_hand_has_no_put_back(self):
        self.run_job()
        film = next(r for r in self.app._held() if r["kind"] == "films")
        os.rename(self.m(film["entries"][0]["to"]), self.m("elsewhere"))
        row = next(i for i in self.app.held_screen()["items"] if i["id"] == film["id"])
        self.assertEqual((row["state_label"], row["actions"]), ("Not found", []))

    def test_without_reelix_it_still_moves(self):
        os.remove(os.path.join(self.app._run, "reelix.json"))
        self.app.rx = lambda *a, **k: None
        out = self.run_job()
        self.assertTrue(out["said"].startswith("Moved 2 items"))
        self.assertTrue(all(r["reelix"] is None for r in self.app._held()))

    def test_a_move_that_would_copy_is_refused(self):
        import errno
        real = os.rename

        def cross(a, b):
            raise OSError(errno.EXDEV, "Invalid cross-device link")
        self.app.os.rename = cross
        try:
            out = self.run_job()
        finally:
            self.app.os.rename = real
        self.assertIn("2 could not move", out["said"])
        self.assertTrue(os.path.isdir(self.m("movies", "Old Film (2001)")))
        rec = self.app._state()["runs"][-1]
        self.assertIn("another disk", rec["failures"][0]["why"])

    def test_a_name_already_in_holding_is_not_overwritten(self):
        touch(self.m(".holding", "library-cleanup", "movies", "Old Film (2001)", "other.mkv"))
        out = self.run_job()
        self.assertIn("1 could not move", out["said"])
        self.assertTrue(os.path.isfile(self.m(".holding", "library-cleanup", "movies", "Old Film (2001)", "other.mkv")))
        self.assertTrue(os.path.isdir(self.m("movies", "Old Film (2001)")))

    def test_the_holding_folder_is_never_looked_at_again(self):
        self.run_job()
        self.jf.items.clear()  # Jellyfin has forgotten them; the holding folder is outside every library
        self.assertEqual(self.app.plan()["items"], [])


class PreviewAndScreens(Base):
    def setUp(self):
        super().setUp()
        self.film("a", "Old Film (2001)", {"u1": self.seen(200), "u2": self.seen(120)})

    def test_preview_is_worked_out_in_the_background_and_moves_nothing(self):
        first = self.app.preview_screen()
        self.assertEqual(first["items"], [])
        self.assertEqual(first["notices"][0]["title"], "Working out Preview")
        self.app._job["thread"].join(10)
        out = self.app.preview_screen()
        self.assertEqual([i["title"] for i in out["items"]], ["Old Film (2001)"])
        self.assertTrue(out["intro"].startswith("1 item would move to the holding folder, freeing 1.0 KB."))
        self.assertIn("Nothing moves until you activate Move items each day", out["intro"])
        self.assertTrue(os.path.isdir(self.m("movies", "Old Film (2001)")))

    def test_a_changed_setting_works_it_out_again(self):
        self.app.keep("preview", self.app.plan())
        self.assertTrue(self.app._preview_fresh(self.app.remember("preview")))
        self.app._set(watched_days=365)
        self.assertFalse(self.app._preview_fresh(self.app.remember("preview")))

    def test_screens_and_card_pass_starboards_checks(self):
        cleaners = starboard_cleaners()
        self.app.keep("preview", self.app.plan())
        self.app._set(active=True)
        self.app.job_move()
        if cleaners:
            cards, custom = cleaners
            for screen in (self.app.preview_screen(), self.app.held_screen(), self.app.libraries_screen()):
                out = custom.clean(screen)
                self.assertTrue(out["items"] or screen["title"] == "Preview")
            held = custom.clean(self.app.held_screen())
            if "restore" in custom.ACTIONS:  # Starboard with plug-in API 1.15
                self.assertEqual(held["items"][0]["actions"], ["restore"])
            cards.clean("stat", self.app.card())
        c = self.app.card()
        self.assertEqual((c["status"], c["status_label"], c["value"]), ("scheduled", "Next in quiet hours", 1010))

    def test_card_when_deactivated(self):
        c = self.app.card()
        self.assertEqual((c["status"], c["status_label"]), ("inactive", "Deactivated"))
        self.assertEqual(c["note"], "Deactivated. Open Preview to see what would move")


class Safety(unittest.TestCase):
    def test_nothing_in_it_can_delete(self):
        """No call that removes a file or folder, anywhere in its own code (its data files are replaced whole by
        sbplugin.keep, never removed)."""
        with open(os.path.join(ROOT, "library-cleanup", "app.py"), encoding="utf-8") as f:
            text = f.read()
        tree = ast.parse(text)
        names = {n.attr if isinstance(n, ast.Attribute) else n.id for n in ast.walk(tree) if isinstance(n, (ast.Attribute, ast.Name))}
        for bad in ("remove", "unlink", "rmdir", "removedirs", "rmtree", "truncate", "DELETE"):
            self.assertNotIn(bad, names)
        self.assertNotIn('"DELETE"', text)

    def test_manifest(self):
        m = manifest("library-cleanup")
        self.assertEqual(m["starboard_api"], ">=1.15 <2.0")
        self.assertEqual(m["permissions"], ["jellyfin:key", "reelix:key", "library:holding", "network:lan"])
        self.assertEqual(m["containers"][0]["volumes"], ["data", "media:holding"])
        self.assertEqual(m["containers"][0]["user"], "media")
        active = next(s for s in m["settings"] if s["key"] == "active")
        self.assertIs(active["default"], False)
        job = m["jobs"][0]
        self.assertEqual((job["every_hours"], job["quiet_hours"]), (24, True))



@unittest.skipUnless(os.path.isdir(os.path.join(os.environ.get("STARBOARD_SRC", os.path.expanduser("~/src/starboard")), "starboard")),
                     "Starboard's source is not here")
class StarboardAccepts(unittest.TestCase):
    """Starboard's own checks: the manifest, the plug-in tester with accessibility, and the install warning."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, os.environ.get("STARBOARD_SRC", os.path.expanduser("~/src/starboard")))
        from starboard import plugin_cards, plugin_tester, plugins
        cls.cards, cls.tester, cls.plugins = plugin_cards, plugin_tester, plugins
        if not plugins._range_ok(manifest("library-cleanup")["starboard_api"], plugins.API_VERSION):
            raise unittest.SkipTest(f"Starboard here has plug-in API {plugins.API_VERSION}; this needs 1.15")

    def test_manifest_and_tester(self):
        from helpers import as_published
        m = manifest("library-cleanup")
        self.assertEqual(self.plugins.check(m, dev=True), [])
        self.assertEqual(as_published(self.plugins.check(m), m), [])
        report = self.tester.report(m, dev=True)
        self.assertTrue(report["accessibility"]["passed"], report)
        self.assertEqual(report["errors"], 0, report)
        w = self.plugins.install_warning(m)
        self.assertEqual(w["risk"], "high")
        self.assertTrue(any("holding folder there (media/.holding)" in c for c in w["change"]))
        for c in m["cards"]:
            self.cards.clean(c["type"], c["example"])


if __name__ == "__main__":
    unittest.main()
