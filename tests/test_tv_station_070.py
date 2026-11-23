"""Create your own TV channel 0.7.0, audio description on promos (DASH-509, owner, 21 November 2026: "Can you add a task
to add audio description to promos"). A promo is clips, music and words on the picture, so a blind viewer heard only
music. With the setting activated (it is not unless changed), a voice made on the server says the words.

The FFmpeg test runs only where ffmpeg is installed; the voice in it is a tone, so it needs no speech program."""
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import wave
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT, manifest  # noqa: E402
from test_tv_station import FakeJellyfin, channel, episodes  # noqa: E402
from test_tv_station_020 import NOW, App  # noqa: E402

TV = os.path.join(ROOT, "tv-station")
sys.path.insert(0, TV)
import dog  # noqa: E402
import library  # noqa: E402
import promo  # noqa: E402
import schedule  # noqa: E402
import speak  # noqa: E402
import tv_words as words  # noqa: E402

FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def at(y, mo, d, h, mi):
    return time.mktime((y, mo, d, h, mi, 0, 0, 0, -1))


SUNDAY_21 = at(2026, 11, 22, 21, 0)
AIRING = {"start": SUNDAY_21, "entry": {"id": "c" * 32, "title": "The Lighthouse Keepers", "dur": 3000, "s": 2, "e": 3, "ep": "Fog",
                                        "plot": "A storm cuts the island off. Nobody is coming for a week, and the lamp is failing."}}


def tone(path, seconds, hz=1000):
    """A WAV file of a steady tone, standing in for the voice."""
    import math
    import struct
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(b"".join(struct.pack("<h", int(20000 * math.sin(2 * math.pi * hz * i / 22050))) for i in range(int(22050 * seconds))))
    return path


class TheSetting(unittest.TestCase):
    def test_not_active_unless_changed_and_says_where_the_voice_is_made(self):
        m = manifest("tv-station")
        s = next(x for x in m["settings"] if x["key"] == "promo_audio_description")
        self.assertEqual((s["type"], s["default"], s["group"], s["label"]), ("switch", False, "Promos", "Audio description on promos"))
        self.assertIn("on your server", s["hint"])
        self.assertIn("nothing is sent anywhere", s["hint"])
        self.assertIn("0.7.0", [c["version"] for c in m["changes"]])

    def test_the_image_has_the_speech_program_and_the_module(self):
        with open(os.path.join(TV, "Dockerfile"), encoding="utf-8") as f:
            text = f.read()
        self.assertRegex(text, r"apk add --no-cache [^\n]*\bespeak-ng\b")
        self.assertRegex(text, r"COPY [^\n]*\bspeak\.py\b")
        self.assertNotIn("speak.py", "")


class TheVoice(unittest.TestCase):
    def test_a_voice_for_every_language(self):
        self.assertEqual(set(speak.VOICES), set(words.TABLES))
        self.assertEqual(speak.voice_of("xx"), "en-gb")
        self.assertEqual(speak.voice_of("DE"), "de")

    def test_the_words_go_in_on_standard_input_never_as_options(self):
        argv = speak.command("fr", "/tmp/out.wav")
        self.assertEqual(argv, ["espeak-ng", "-v", "fr-fr", "-s", "160", "--stdin", "-w", "/tmp/out.wav"])
        seen = {}

        def fake(argv, **kw):
            seen.update(argv=argv, **kw)
            tone(argv[-1], 1.5)
            return subprocess.CompletedProcess(argv, 0)
        with tempfile.TemporaryDirectory() as d, mock.patch.object(speak, "available", return_value=True), \
                mock.patch.object(speak.subprocess, "run", side_effect=fake):
            got = speak.make("--version -v xx\nComing  soon\x07.", "en", os.path.join(d, "v.wav"))
        self.assertAlmostEqual(got, 1.5, places=1)
        self.assertEqual(seen["input"], "--version -v xx Coming soon .".encode())
        self.assertNotIn("--version", seen["argv"])
        self.assertEqual(seen["timeout"], speak.LIMIT)

    def test_no_speech_program_or_a_failure_makes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(speak, "available", return_value=False):
                self.assertEqual(speak.make("Coming soon", "en", os.path.join(d, "v.wav")), 0.0)
                self.assertIsNone(speak.fitting(["Coming soon"], "en", d, 10))
            with mock.patch.object(speak, "available", return_value=True), \
                    mock.patch.object(speak.subprocess, "run", side_effect=subprocess.TimeoutExpired("espeak-ng", 20)):
                self.assertEqual(speak.make("Coming soon", "en", os.path.join(d, "v.wav")), 0.0)
            self.assertEqual(speak.make("", "en", os.path.join(d, "v.wav")), 0.0)
            self.assertEqual(speak.seconds_of(os.path.join(d, "missing.wav")), 0.0)

    def test_the_longest_words_that_fit_are_used(self):
        lengths = {"long": 14.0, "middle": 6.0, "short": 3.0}
        with tempfile.TemporaryDirectory() as d, mock.patch.object(speak, "make", side_effect=lambda w, lang, out: lengths[w]):
            self.assertEqual(speak.fitting(["long", "middle", "short"], "en", d, 12.9)["words"], "middle")
            self.assertEqual(speak.fitting(["long", "middle", "short"], "en", d, 20)["words"], "long")
            self.assertEqual(speak.fitting(["long", "middle", "short"], "en", d, 4)["dur"], 3.0)
            self.assertIsNone(speak.fitting(["long", "middle", "short"], "en", d, 2))

    @unittest.skipUnless(speak.available(), "espeak-ng is not installed here")
    def test_a_real_voice_in_every_language(self):
        with tempfile.TemporaryDirectory() as d:
            for lang in words.TABLES:
                said = promo.spoken(AIRING, "Harbour One", lang)[-1]
                self.assertGreater(speak.make(said, lang, os.path.join(d, f"{lang}.wav")), 1.0, lang)


class TheTimeSaid(unittest.TestCase):
    def test_a_time_is_said_as_a_time_in_every_language(self):
        half = at(2026, 11, 22, 21, 30)
        want = {"en": ("Sunday at 21 o'clock", "Sunday at 21 30"), "fr": ("Dimanche à 21 heures", "Dimanche à 21 heures 30"),
                "de": ("Sonntag um 21 Uhr", "Sonntag um 21 Uhr 30"), "es": ("Domingo a las 21 horas", "Domingo a las 21 horas 30"),
                "it": ("Domenica alle 21", "Domenica alle 21 e 30"), "pt": ("Domingo às 21 horas", "Domingo às 21 horas e 30"),
                "nl": ("Zondag om 21 uur", "Zondag om 21 uur 30"), "sv": ("Söndag klockan 21", "Söndag klockan 21 och 30"),
                "da": ("Søndag klokken 21", "Søndag klokken 21 30"), "nb": ("Søndag klokken 21", "Søndag klokken 21 30")}
        self.assertEqual(set(want), set(words.TABLES))
        for lang, (hour, minutes) in want.items():
            self.assertEqual((words.day_time_spoken(SUNDAY_21, lang), words.day_time_spoken(half, lang)), (hour, minutes), lang)
            self.assertNotIn(":", words.day_time_spoken(half, lang))
        self.assertEqual(words.time_spoken(at(2026, 11, 22, 9, 5), "en"), "9 oh 5")
        self.assertEqual(words.day_time(SUNDAY_21, "en"), "Sunday at 21:00", "the words on the picture are as they were")


class WhatIsSaid(unittest.TestCase):
    def test_the_words_on_screen_in_order_then_the_first_sentence(self):
        said = promo.spoken(AIRING, "Harbour One")
        self.assertEqual(said[0], "Coming soon. The Lighthouse Keepers. Series 2, episode 3: Fog. Sunday at 21 o'clock. Harbour One. "
                                  "A storm cuts the island off.")
        self.assertEqual(said[1], "Coming soon. The Lighthouse Keepers. Series 2, episode 3: Fog. Sunday at 21 o'clock. Harbour One.")
        self.assertEqual(said[2], "The Lighthouse Keepers. Sunday at 21 o'clock. Harbour One.")

    def test_in_the_stations_language(self):
        self.assertEqual(promo.spoken(AIRING, "Hafen Eins", "de")[1],
                         "Demnächst. The Lighthouse Keepers. Staffel 2, Folge 3: Fog. Sonntag um 21 Uhr. Hafen Eins.")

    def test_a_film_with_no_description(self):
        film = {"start": SUNDAY_21, "entry": {"id": "f" * 32, "title": "Sintel", "dur": 900}}
        self.assertEqual(promo.spoken(film, "Films"), ["Coming soon. Sintel. Sunday at 21 o'clock. Films.", "Sintel. Sunday at 21 o'clock. Films."])

    def test_a_long_first_sentence_is_left_out(self):
        self.assertEqual(promo.first_sentence("word " * 60 + "end. More."), "")
        self.assertEqual(promo.first_sentence("Short one."), "Short one.")
        self.assertEqual(promo.first_sentence("No full stop"), "")
        self.assertEqual(promo.first_sentence(None), "")

    def test_how_much_speech_fits(self):
        self.assertAlmostEqual(promo.voice_room(15), 12.9)
        self.assertAlmostEqual(promo.voice_room(10), 7.9)
        self.assertEqual(promo.voice_room(1), 0.0)


class TheCommand(unittest.TestCase):
    def cmd(self, **how):
        with tempfile.TemporaryDirectory() as d:
            argv, seconds = promo.command(promo.plain_pack("0x1f5f99"), AIRING, "Harbour One", {"file": "/m/bed.m4a", "gain": 0}, 640, 360,
                                          "http://jf", "k", dog.Texts(d), "/out/p.mp4", seed=1, **how)
        return argv, argv[argv.index("-filter_complex") + 1]

    def test_without_a_voice_it_is_as_it_was(self):
        plain, graph = self.cmd()
        again, _ = self.cmd(voice=None)
        strip = lambda argv: [re.sub(r"/tmp/[^:,]*", "T", a) for a in argv]  # noqa: E731  the text files' folder differs
        self.assertEqual(strip(plain), strip(again))
        self.assertNotIn("[voice]", graph)
        self.assertNotIn("[a0]", graph)

    def test_a_voice_is_one_more_input_mixed_into_the_one_track(self):
        plain, _ = self.cmd()
        argv, graph = self.cmd(voice={"file": "/tmp/v/voice0.wav", "dur": 5.0})
        self.assertEqual(argv.count("-i"), plain.count("-i") + 1)
        n = argv.count("-i") - 1
        self.assertEqual(argv[len(argv) - 1 - argv[::-1].index("-i") + 1], "/tmp/v/voice0.wav")
        self.assertIn(f"[{n}:a]", graph)
        self.assertIn("adelay=600|600,apad[voice]", graph)
        self.assertIn("[under][voice]amix=inputs=2:duration=first", graph)
        # everything else falls to about a third from when the voice starts until it ends
        self.assertIn(f"[a0]volume=eval=frame:volume='{promo.duck(0.3, 0.6, 5.6)}'[under]", graph)
        self.assertEqual(argv.count("-map"), 2, "still one picture and one sound track")
        self.assertEqual(argv[argv.index("-ac") + 1], "2")

    def test_with_the_station_logo_the_voice_comes_after_it(self):
        argv, graph = self.cmd(voice={"file": "/tmp/v/voice0.wav", "dur": 5.0}, station_logo="/p/logo.png")
        ins = [argv[i + 1] for i, a in enumerate(argv) if a == "-i"]
        self.assertEqual(ins[-2:], ["/p/logo.png", "/tmp/v/voice0.wav"])
        self.assertIn(f"[{len(ins) - 1}:a]", graph)
        self.assertIn(f"[{len(ins) - 2}:v]format=rgba", graph)

    def test_a_voice_too_long_for_the_promo_is_left_out(self):
        _, graph = self.cmd(voice={"file": "/tmp/v/voice0.wav", "dur": 13.5}, seconds=15)
        self.assertNotIn("[voice]", graph)
        _, graph = self.cmd(voice={"file": "", "dur": 3})
        self.assertNotIn("[voice]", graph)

    def test_with_a_voice_the_clips_play_the_described_track(self):
        described = {**AIRING, "entry": {**AIRING["entry"], "audio_n": 0, "audio_langs": ["eng", "eng"], "audio_ad": [1]}}
        with tempfile.TemporaryDirectory() as d:
            how = dict(seed=1)
            pk = promo.plain_pack("0x1f5f99")
            plain = promo.command(pk, described, "Harbour One", None, 640, 360, "http://jf", "k", dog.Texts(d), "/o.mp4", **how)[0]
            voiced = promo.command(pk, described, "Harbour One", None, 640, 360, "http://jf", "k", dog.Texts(d), "/o.mp4",
                                   voice={"file": "/v.wav", "dur": 4}, **how)[0]
        self.assertIn("[1:a]", plain[plain.index("-filter_complex") + 1])
        self.assertIn("[1:a:1]", voiced[voiced.index("-filter_complex") + 1])


class DescribedTracks(unittest.TestCase):
    def item(self, *tracks):
        streams = [{"Type": "Video", "Index": 0}] + [{"Type": "Audio", "Index": i + 1, "Language": lang, "DisplayTitle": title, "IsDefault": i == 0}
                                                    for i, (lang, title) in enumerate(tracks)]
        return {"Id": "a" * 32, "Name": "Film", "Type": "Movie", "RunTimeTicks": 6e10, "MediaStreams": streams}

    def test_a_described_track_is_known_by_its_name(self):
        e = library.entry(self.item(("eng", "English - AAC - Stereo - Default"), ("eng", "English (Audio Description) - AAC - Stereo")))
        self.assertEqual(e["audio_ad"], [1])
        self.assertEqual(library.sound_for(e, "en"), 0, "a channel plays the programme's own track, as before")
        self.assertEqual(library.sound_for(e, "en", described=True), 1)

    def test_a_commentary_never_counts_and_most_files_keep_nothing(self):
        e = library.entry(self.item(("eng", "English"), ("eng", "AD commentary"), ("eng", "Director's commentary")))
        self.assertNotIn("audio_ad", e)
        self.assertEqual(library.sound_for(e, "en", described=True), 0)
        self.assertNotIn("audio_ad", library.entry(self.item(("eng", "English"))))

    def test_the_described_track_in_the_stations_language_first(self):
        e = library.entry(self.item(("eng", "English"), ("eng", "English AD"), ("ger", "Deutsch"), ("ger", "Deutsch (Audio Description)")))
        self.assertEqual(e["audio_ad"], [1, 3])
        self.assertEqual(library.sound_for(e, "de", described=True), 3)
        self.assertEqual(library.sound_for(e, "fr", described=True), 1, "none in French: any described track")
        self.assertEqual(library.sound_for(e, "de"), 2)

    def test_the_rule_matches_the_audio_description_plug_ins(self):
        with open(os.path.join(ROOT, "audio-description-tracks", "rules.json"), encoding="utf-8") as f:
            rule = json.load(f)["described_track"]
        self.assertEqual(library.TRACK_AD.pattern, rule["pattern"])
        self.assertEqual(library.COMMENTARY.pattern, rule["ruled_out_pattern"])
        for name in rule["examples"]["described"]:
            self.assertEqual(library.described_tracks([{"DisplayTitle": name}]), [0], name)
        for name in rule["examples"]["not_described"]:
            self.assertEqual(library.described_tracks([{"DisplayTitle": name}]), [], name)


class TheApp(App):
    def settings(self, **more):
        with open(os.path.join(os.environ["PLUGIN_RUN"], "settings.json"), "w") as f:
            json.dump({"station_name": "Home TV", **more}, f)

    def test_activating_it_makes_promos_again_and_an_update_alone_does_not(self):
        cid = self.channel("Comedy", episodes("a", 4, 1500))
        self.app.promo_design = lambda s, ch: {"name": "Plain", "promo": {"colour": "0x1f5f99"}}
        ch = self.app.find(self.app.state(), cid)
        self.assertFalse(self.app.promo_described())
        self.assertEqual(self.app.promo_design_key(self.app.state(), ch), "plain:0x1f5f99", "as before 0.7.0: every promo is kept")
        self.settings(promo_audio_description=True)
        self.assertTrue(self.app.promo_described())
        self.assertEqual(self.app.promo_design_key(self.app.state(), ch), "plain:0x1f5f99|ad")
        self.settings(promo_audio_description=True, language="de")
        self.assertEqual(self.app.promo_design_key(self.app.state(), ch), "plain:0x1f5f99|de|ad")
        old = {"id": "p1", "cid": cid, "design": "plain:0x1f5f99"}
        self.assertFalse(promo.current(old, {cid: "plain:0x1f5f99|ad"}))
        self.assertTrue(promo.current(old, {cid: "plain:0x1f5f99"}))

    def job(self):
        """One run of the promos job with FFmpeg and the speech program stood in for. Returns (commands, words asked)."""
        made, asked = [], []

        def run(argv, limit=600):
            made.append(argv)
            with open(argv[-1], "wb") as f:
                f.write(b"mp4")
            return True, ""

        def fitting(candidates, lang, folder, room):
            asked.append((candidates, lang, room))
            return {"file": tone(os.path.join(folder, "voice0.wav"), 2.0), "dur": 2.0, "words": candidates[-1]}
        with mock.patch.object(self.app.promo, "run", side_effect=run), mock.patch.object(self.app.speak, "fitting", side_effect=fitting), \
                mock.patch.object(self.app, "someone_watching", return_value=False):
            said = self.app.promos_job(now=NOW)
        return made, asked, said

    def test_the_job_speaks_only_when_activated(self):
        cid = self.channel("Comedy", episodes("a", 4, 1500))
        self.app.promo_design = lambda s, ch: self.app.promo.plain_pack("0x1f5f99")
        made, asked, said = self.job()
        self.assertTrue(made, said)
        self.assertEqual(asked, [], "not activated: the speech program is never asked")
        self.assertNotIn("[voice]", " ".join(made[0]))
        self.assertFalse([p for p in self.app.state()["promos"] if p["design"].endswith("|ad")])
        self.settings(promo_audio_description=True, promo_seconds="20")
        made, asked, said = self.job()
        self.assertTrue(made, said)
        self.assertEqual(len(asked), len(made))
        candidates, lang, room = asked[0]
        self.assertEqual(lang, "en")
        self.assertAlmostEqual(room, promo.voice_room(20))
        self.assertTrue(candidates[-1].endswith("Comedy."), candidates)
        self.assertIn("[voice]", " ".join(made[0]))
        kept = [p for p in self.app.state()["promos"] if p["cid"] == cid]
        self.assertTrue(kept and all(p["design"].endswith("|ad") for p in kept), "the promos made before were replaced")


@unittest.skipUnless(FFMPEG, "ffmpeg is not installed here")
class MakingOne(unittest.TestCase):
    """A real 12 second promo with a tone for the voice, music that is silence and no programme sound, so whatever is
    heard is the voice: it is there while it should speak, and gone after."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        FakeJellyfin.folder = cls.tmp.name
        subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=320x180:r=25:d=60", "-f", "lavfi", "-i", "sine=f=440:d=60",
                        "-c:v", "libx264", "-preset", "ultrafast", "-g", "25", "-c:a", "aac", "-shortest", "-y",
                        os.path.join(cls.tmp.name, "a1.ts")], check=True)
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeJellyfin)
        threading.Thread(target=cls.server.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.tmp.cleanup()

    def level(self, path, start, length):
        got = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-ss", str(start), "-t", str(length), "-i", path, "-af", "volumedetect",
                              "-vn", "-f", "null", "-"], capture_output=True, text=True, check=True).stderr
        return float(re.search(r"mean_volume: (-?[0-9.]+|-inf) dB", got).group(1).replace("-inf", "-200"))

    def test_the_voice_is_heard_in_the_one_sound_track(self):
        lineup = [{"id": "a1", "dur": 60, "title": "Pattern Show", "group": "a", "kind": "Episode"}]
        a = schedule.Channel(channel(lineup, start_on=0)).airing(NOW + 86400)
        out = os.path.join(self.tmp.name, "voiced.mp4")
        voice = {"file": tone(os.path.join(self.tmp.name, "voice.wav"), 4.0), "dur": 4.0}
        with tempfile.TemporaryDirectory() as d:
            argv, seconds = promo.command(promo.plain_pack("0x1f5f99"), a, "Comedy", None, 320, 180, self.url, "k", dog.Texts(d), out,
                                          seed=1, seconds=12, clip_sound=False, voice=voice)
            ok, why = promo.run(argv, limit=120)
        self.assertTrue(ok, why)
        probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", out], capture_output=True, text=True,
                                          check=True).stdout)
        sound = [s for s in probe["streams"] if s["codec_type"] == "audio"]
        self.assertEqual(len(sound), 1, "one sound track, as a channel's stream carries one")
        self.assertEqual((sound[0]["channels"], sound[0]["sample_rate"]), (2, "48000"))
        self.assertAlmostEqual(float(probe["streams"][0].get("duration") or seconds), 12, delta=0.6)
        self.assertGreater(self.level(out, 1.0, 3.0), -30, "the voice, from 0.6 to 4.6 seconds")
        self.assertLess(self.level(out, 6.0, 4.0), -60, "nothing after it: the music here is silence")


if __name__ == "__main__":
    unittest.main()
