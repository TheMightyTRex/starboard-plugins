"""Create your own TV channel 0.5.4 (owner, 19 November 2026: "Late ink just shows a card with the words T-Rex TV - late
ink on it"). A programme with a subtitle file beside it: Jellyfin counts that file in its stream Index (often as 0), so
mapping the sound by Index asked FFmpeg for a subtitle and the programme never started. The sound is now the default
track's place among the file's own sound tracks.

The FFmpeg test runs only where ffmpeg is installed."""
import http.server
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT  # noqa: E402
from test_tv_station import NOW, FakeJellyfin, channel, episodes  # noqa: E402

TV = os.path.join(ROOT, "tv-station")
sys.path.insert(0, TV)
import dog  # noqa: E402
import library  # noqa: E402
import schedule  # noqa: E402
import stream  # noqa: E402

FFMPEG = bool(shutil.which("ffmpeg"))


def item(streams, iid="a" * 32):
    return {"Id": iid, "Type": "Episode", "SeriesId": "s" * 32, "SeriesName": "Archer", "Name": "Training Day", "RunTimeTicks": 1320 * 10**7,
            "MediaStreams": streams}


ARCHER = [  # as Jellyfin reported Archer S01E02 on the owner's server
    {"Index": 0, "Type": "Subtitle", "Codec": "subrip", "IsExternal": True},
    {"Index": 1, "Type": "Video", "Codec": "h264"},
    {"Index": 2, "Type": "Audio", "Codec": "aac", "IsDefault": True},
    {"Index": 3, "Type": "Subtitle", "Codec": "subrip"},
]


class WhichSound(unittest.TestCase):
    def test_an_external_subtitle_does_not_move_the_sound(self):
        e = library.entry(item(ARCHER))
        self.assertEqual(e["audio_n"], 0)
        self.assertNotIn("audio", e)
        self.assertEqual(stream.sound_map(e), "0:a:0")

    def test_the_default_of_several_sound_tracks(self):
        e = library.entry(item([{"Index": 0, "Type": "Video"}, {"Index": 1, "Type": "Audio", "Language": "jpn"},
                                {"Index": 2, "Type": "Audio", "Language": "eng", "IsDefault": True}, {"Index": 3, "Type": "Audio", "IsExternal": True}]))
        self.assertEqual(stream.sound_map(e), "0:a:1")

    def test_external_sound_only_is_no_sound_in_the_file(self):
        e = library.entry(item([{"Index": 0, "Type": "Video"}, {"Index": 1, "Type": "Audio", "IsExternal": True, "IsDefault": True}]))
        self.assertFalse(e["has_audio"])
        self.assertIsNone(e["audio_n"])

    def test_a_line_up_read_before_054_gets_the_first_sound_track(self):
        self.assertEqual(stream.sound_map({"audio": 2}), "0:a:0")
        self.assertEqual(stream.sound_map({"audio_n": 3}), "0:a:3")

    def test_the_command_maps_it(self):
        lineup = episodes("a", 2, 1500)
        for e in lineup:
            e["audio_n"] = 1
        a = schedule.Channel(channel(lineup)).airing(NOW)
        piece = {"kind": "programme", "start": a["start"], "end": a["content_end"], "airing": a}
        with tempfile.TemporaryDirectory() as d:
            ctx = {"W": 1280, "H": 720, "kbps": 3000, "opts": dog.resolve({}, None), "names": {"channel": "C", "station": "S"}, "logo": None,
                   "jf_url": "http://jf:8096", "jf_key": "k", "ts_offset": 0, "texts": dog.Texts(d), "clip_path": str}
            argv = stream.piece_command(piece, a["start"] + 5, ctx)
        maps = [argv[i + 1] for i, x in enumerate(argv) if x == "-map"]
        self.assertIn("0:a:1", maps)


@unittest.skipUnless(FFMPEG, "ffmpeg is not installed here")
class ItPlays(unittest.TestCase):
    """A file like Archer's: video, sound, then an embedded subtitle; Jellyfin also lists an external one first."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        srt = os.path.join(cls.tmp.name, "s.srt")
        with open(srt, "w") as f:
            f.write("1\n00:00:00,000 --> 00:00:05,000\nHello\n")
        mkv = os.path.join(cls.tmp.name, "a1.mkv")
        subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=320x180:r=25:d=20", "-f", "lavfi", "-i", "sine=f=440:d=20",
                        "-i", srt, "-map", "0", "-map", "1", "-map", "2", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-c:s", "srt",
                        "-y", mkv], check=True)
        os.replace(mkv, os.path.join(cls.tmp.name, "a1.ts"))  # the stand-in serves <id>.ts, whatever the container
        FakeJellyfin.folder = cls.tmp.name
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeJellyfin)
        threading.Thread(target=cls.server.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.tmp.cleanup()

    def test_the_programme_starts(self):
        e = library.entry(item(ARCHER, "a1"))
        e.update({"id": "a1", "dur": 20})
        a = schedule.Channel(channel([e])).airing(NOW)
        piece = {"kind": "programme", "start": a["start"], "end": a["content_end"], "airing": a}
        with tempfile.TemporaryDirectory() as d:
            ctx = {"W": 320, "H": 180, "kbps": 600, "opts": dog.resolve({}, None), "names": {"channel": "Late ink", "station": "T-Rex TV"},
                   "logo": None, "jf_url": self.url, "jf_key": "k", "ts_offset": 0, "texts": dog.Texts(d), "clip_path": str}
            argv = stream.piece_command(piece, a["start"] + 1, ctx)
            argv = [x for x in argv if x not in ("-re",)]
            r = subprocess.run(argv, capture_output=True, timeout=60, check=False)
        self.assertEqual(r.returncode, 0, r.stderr[-400:])
        self.assertGreater(len(r.stdout), 10000, "a stream came out")
        # Before 0.5.4 the map was 0:2, the embedded subtitle, and FFmpeg stopped with "Encoder not found".
        bad = [x if x != "0:a:0" else "0:2" for x in argv]
        r2 = subprocess.run(bad, capture_output=True, timeout=60, check=False)
        self.assertNotEqual(r2.returncode, 0)


if __name__ == "__main__":
    unittest.main()
