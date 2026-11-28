"""Create your own TV channel 0.5.5 (owner, 19 November 2026: "Yes, do it here", to make the refresh update each
programme's sound track): a line-up with the same programmes keeps its schedule, and its programmes' details are brought
up to date from Jellyfin."""
import copy
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT  # noqa: E402
from test_tv_station import NOW, channel, episodes  # noqa: E402
from test_tv_station_020 import App  # noqa: E402

TV = os.path.join(ROOT, "tv-station")
sys.path.insert(0, TV)
import schedule  # noqa: E402


class Details(unittest.TestCase):
    def test_details_change_and_timing_does_not(self):
        old = episodes("a", 4, 1500)
        for e in old:
            e["audio"] = 2  # read before 0.5.4: Jellyfin's Index
        spec = channel(old)
        before = [schedule.Channel(spec).airing(NOW + k * 1500)["entry"]["id"] for k in range(8)]
        fresh = copy.deepcopy(episodes("a", 4, 1500))
        for e in fresh:
            e.update(audio_n=1, title="Show a (renamed)", dur=999, group="other")  # dur and group must not move
        n = schedule.refresh_details(spec["eras"], fresh)
        self.assertEqual(n, 4)
        e = spec["eras"][0]["lineup"][0]
        self.assertEqual((e["audio_n"], e["title"]), (1, "Show a (renamed)"))
        self.assertNotIn("audio", e)
        self.assertEqual((e["dur"], e["group"]), (1500, "a"))
        self.assertEqual([schedule.Channel(spec).airing(NOW + k * 1500)["entry"]["id"] for k in range(8)], before)
        self.assertEqual(schedule.refresh_details(spec["eras"], fresh), 0, "nothing more to change the second time")

    def test_a_programme_no_longer_there_is_left_as_it_is(self):
        spec = channel(episodes("a", 2, 1500))
        self.assertEqual(schedule.refresh_details(spec["eras"], []), 0)


class TheRefresh(App):
    def test_same_programmes_new_details(self):
        lineup = episodes("aa", 3, 1500)
        for e in lineup:
            e["audio"] = 2
        cid = self.channel("Late ink", lineup)
        s = self.app.state()
        ch = self.app.find(s, cid)
        fresh = copy.deepcopy(episodes("aa", 3, 1500))
        for e in fresh:
            e["audio_n"] = 0
        ch["sources"] = [{"kind": "series", "id": "aa"}]
        ch["lineup_hash"] = schedule.lineup_hash(fresh) + f":{ch['order']}:{ch['run']}:{ch['start_on']}:{ch['break_seconds']}"
        eras_before = len(ch["eras"])
        self.app.save(s)
        with mock.patch.object(self.app.library, "lineup", lambda jf, sources: copy.deepcopy(fresh)), \
                mock.patch.object(self.app.library, "trailers", lambda jf, entries: []):
            self.app.refresh_channel(cid, now=1794600123.0)
        ch = self.app.find(self.app.state(), cid)
        self.assertEqual(len(ch["eras"]), eras_before, "no new era: the schedule did not move")
        self.assertTrue(all(e.get("audio_n") == 0 and "audio" not in e for e in ch["eras"][-1]["lineup"]))


# Leave out 3D films (owner, 19 November 2026: "I dont want any 3d films as it plays as 2 images") ----------------------
import http.server  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402
import threading  # noqa: E402

import library  # noqa: E402
import three_d  # noqa: E402
from test_tv_station import FakeJellyfin  # noqa: E402


def film(fid, title="A Film", **more):
    return {"id": fid, "dur": 6000, "title": title, "group": fid, "kind": "Movie", **more}


class WhatSaysThreeD(unittest.TestCase):
    def test_jellyfin_and_the_file_name(self):
        self.assertIn("HalfSideBySide", three_d.said({"Video3DFormat": "HalfSideBySide"}))
        for name in ("Avatar (2009) 3D HSBS.mkv", "Film.2012.1080p.H-SBS.mkv", "Film.HOU.mkv", "Film (2010) [3D].mkv"):
            self.assertEqual(three_d.said({"Path": "/media/movies/x/" + name}), "its file name says 3D", name)
        for name in ("Cloudy with a Chance of Meatballs (2009) Bluray-1080p Proper.mkv", "3Days.to.Kill.2014.mkv", "Sbs.News.mkv"):
            self.assertEqual(three_d.said({"Path": "/media/movies/x/" + name}), "", name)
        self.assertEqual(three_d.said({"Path": "/media/3D films/Film (2010).mkv"}), "", "only the file's own name counts")
        self.assertEqual(three_d.said({"Name": "Saw 3D", "Path": "/media/movies/Saw 3D (2010)/Saw 3D (2010) Bluray-1080p.mkv"}), "",
                         "3D in the film's own title (the owner's Saw 3D is 2D)")
        self.assertEqual(three_d.said({"Name": "Saw 3D: The Final Chapter", "Path": "/m/Saw 3D (2010) 1080p HSBS.mkv"}), "its file name says 3D")

    def test_the_line_up_reads_it(self):
        e = library.entry({"Id": "f" * 32, "Type": "Movie", "Name": "Up", "RunTimeTicks": 5400 * 10**7, "Video3DFormat": "FullSideBySide",
                           "MediaStreams": []})
        self.assertTrue(e["three_d"])

    def test_the_picture_check(self):
        flat = bytes([128]) * (three_d.W * three_d.H)
        self.assertEqual(three_d.verdict([three_d.halves(flat)] * 2), "", "a flat frame tells nothing")
        row = bytes(range(0, 256, 4))  # 64 dots: the same picture in each half
        sbs = (row + row) * three_d.H
        self.assertEqual(three_d.verdict([three_d.halves(sbs)] * 2), "side by side")
        both = three_d.halves(sbs)
        self.assertEqual(three_d.verdict([both, (40.0, 40.0, 200)]), "", "both frames must agree")


class LeftOut(App):
    def test_left_out_of_the_line_up_unless_deactivated(self):
        import json
        app = self.app
        entries = [film("a" * 32, "Two pictures", three_d="its file name says 3D"), film("b" * 32, "Cloudy"), film("c" * 32, "Normal")]
        app.found_3d().put("b" * 32, "side by side")
        app.found_3d().put("c" * 32, "")
        keep, n = app.without_3d(entries, {})
        self.assertEqual(([e["title"] for e in keep], n), (["Normal"], 2))
        keep, n = app.without_3d(entries, {"leave_out_3d": False})
        self.assertEqual((len(keep), n), (3, 0))
        self.assertTrue(json.load(open(os.path.join(os.environ["PLUGIN_DATA"], "three_d.json")))["b" * 32]["3d"])

    def test_the_quiet_hours_job(self):
        app = self.app
        cid = self.channel("Late ink", [film("a" * 32, "Cloudy"), film("b" * 32, "Normal"), film("c" * 32, "Said 3D", three_d="x")])
        app.someone_watching = lambda: False
        app.jf_conf = lambda: {"url": "http://jf", "api_key": "k"}
        refreshed = []
        looked = []

        def look(url, key, e):
            looked.append(e["title"])
            return "side by side" if e["title"] == "Cloudy" else ""
        with mock.patch.object(three_d, "look", look), mock.patch.object(app, "refresh_soon", refreshed.append):
            said = app.three_d_job()["said"]
            again = app.three_d_job()["said"]
        self.assertEqual(sorted(looked), ["Cloudy", "Normal"], "each film once; one its name says is 3D needs no check")
        self.assertIn("Checked 2 films for 3D: 1 3D (Cloudy), left out", said)
        self.assertEqual(refreshed, [cid], "its channel is read again")
        self.assertIn("Every film on the channels has been checked", again)

    def test_it_waits_while_anyone_watches_and_when_deactivated(self):
        app = self.app
        self.channel("Late ink", [film("a" * 32)])
        app.someone_watching = lambda: True
        self.assertIn("Someone is watching", app.three_d_job()["said"])
        with mock.patch.object(app, "settings", lambda: {"leave_out_3d": False}):
            self.assertIn("turned off", app.three_d_job()["said"])


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is not installed here")
class RealFrames(unittest.TestCase):
    """A made-up half side by side clip (the same picture twice, squeezed) and a normal one, through a stand-in Jellyfin."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        src = "testsrc2=s=640x360:r=25:d=40"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", src, "-filter_complex",
                        "[0:v]scale=320:360,split[a][b];[a][b]hstack", "-c:v", "libx264", "-preset", "ultrafast", "-y",
                        os.path.join(cls.tmp.name, "sbs.ts")], check=True)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", src, "-c:v", "libx264", "-preset", "ultrafast", "-y",
                        os.path.join(cls.tmp.name, "flat.ts")], check=True)
        FakeJellyfin.folder = cls.tmp.name
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeJellyfin)
        threading.Thread(target=cls.server.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.tmp.cleanup()

    def test_side_by_side_and_normal(self):
        three_d.begin()
        self.assertEqual(three_d.look(self.url, "k", {"id": "sbs", "dur": 40}), "side by side")
        self.assertEqual(three_d.look(self.url, "k", {"id": "flat", "dur": 40}), "")
        self.assertIsNone(three_d.look(self.url, "k", {"id": "missing", "dur": 40}), "a film that cannot be read is checked again later")


if __name__ == "__main__":
    unittest.main()
