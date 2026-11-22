"""Create your own TV channel 0.6.0 (owner, 21 November 2026: "the create your own tv channel needs to have a language
choice in the settings and it defaults to english"; asked what it should change: the words on screen, the sound track,
and titles and descriptions)."""
import json
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT, manifest  # noqa: E402
from test_tv_station import NOW, channel, episodes  # noqa: E402
from test_tv_station_020 import App  # noqa: E402

TV = os.path.join(ROOT, "tv-station")
sys.path.insert(0, TV)
import dog  # noqa: E402
import guide  # noqa: E402
import library  # noqa: E402
import promo  # noqa: E402
import schedule  # noqa: E402
import stream  # noqa: E402
import titles  # noqa: E402
import tv_words as words  # noqa: E402


def at(y, mo, d, h, mi):
    return time.mktime((y, mo, d, h, mi, 0, 0, 0, -1))


NOW_LOCAL = at(2026, 11, 18, 20, 2)  # a Wednesday evening, local time


class TheSetting(unittest.TestCase):
    def test_english_unless_changed_with_each_language_offered(self):
        m = manifest("tv-station")
        s = next(x for x in m["settings"] if x["key"] == "language")
        self.assertEqual((s["type"], s["default"], s["label"]), ("choice", "en", "Language"))
        self.assertEqual([c["value"] for c in s["choices"]], list(words.TABLES))
        for c in s["choices"]:
            self.assertIn(c["value"], words.SOUND_CODES)

    def test_an_unknown_or_empty_language_is_english(self):
        for v in (None, "", "xx", "EN"):
            self.assertEqual(words.code(v), "en")
        self.assertEqual(words.code("DE"), "de")

    def test_every_letter_is_in_the_bundled_font(self):
        # atkinson-hyperlegible-next.woff2 has Latin-1 and a few more (fc-query: a0-ff, 152-153 and some punctuation);
        # drawtext has no fallback, so a letter outside it would draw a gap
        extra = {0x152, 0x153}
        for lang, t in words.TABLES.items():
            text = "".join(v if isinstance(v, str) else "".join(v) for v in t.values())
            self.assertEqual([c for c in text if ord(c) > 0xFF and ord(c) not in extra], [], lang)

    def test_every_language_has_every_word(self):
        keys = set(words.TABLES["en"])
        for lang, t in words.TABLES.items():
            self.assertLessEqual(keys, set(t), lang)
            self.assertEqual((len(t["days"]), len(t["months"])), (7, 12), lang)


class EnglishIsAsItWas(unittest.TestCase):
    def test_when_and_day_time(self):
        self.assertEqual(dog.when_words(at(2026, 11, 18, 18, 30), NOW_LOCAL), "Today at 18:30")
        self.assertEqual(dog.when_words(at(2026, 11, 19, 6, 0), NOW_LOCAL), "Tomorrow at 06:00")
        self.assertEqual(dog.when_words(at(2026, 11, 22, 21, 0), NOW_LOCAL), "Sunday 22 November at 21:00")
        self.assertEqual(dog.day_time_words(at(2026, 11, 22, 21, 0)), "Sunday at 21:00")

    def test_episode_up_next_heading_and_coming_soon(self):
        e = {"s": 2, "e": 4, "ep": "The Lift"}
        self.assertEqual(guide.episode_words(e), "Series 2, episode 4: The Lift")
        self.assertEqual(words.up_next(at(2026, 11, 18, 21, 0), "Show b"), "Up next at 21:00: Show b")
        self.assertEqual(words.heading("next", "Comedy"), "Coming up next")
        self.assertEqual(words.heading("later", "Comedy"), "Later on Comedy")
        a = {"entry": {"title": "Show", "s": 1, "e": 2}, "start": at(2026, 11, 22, 21, 0)}
        self.assertEqual(promo.words(a, "Comedy")["Heading"], "Coming soon")
        self.assertEqual(dog.countdown_text(10).split("%")[0], "Next programme in ")


class German(unittest.TestCase):
    def test_when_words(self):
        self.assertEqual(dog.when_words(at(2026, 11, 18, 18, 30), NOW_LOCAL, "de"), "Heute um 18:30")
        self.assertEqual(dog.when_words(at(2026, 11, 19, 6, 0), NOW_LOCAL, "de"), "Morgen um 06:00")
        self.assertEqual(dog.when_words(at(2026, 11, 22, 21, 0), NOW_LOCAL, "de"), "Sonntag, 22. November um 21:00")
        self.assertEqual(dog.day_time_words(at(2026, 11, 22, 21, 0), "de"), "Sonntag um 21:00")

    def test_never_the_servers_locale(self):
        # French, Spanish and Norwegian names come from the tables, capitalised at the start of a line, whatever the
        # locale is
        self.assertEqual(dog.when_words(at(2026, 11, 22, 21, 0), NOW_LOCAL, "fr"), "Dimanche 22 novembre à 21:00")
        self.assertEqual(dog.when_words(at(2026, 11, 22, 21, 0), NOW_LOCAL, "es"), "Domingo 22 de noviembre a las 21:00")
        self.assertEqual(dog.day_time_words(at(2026, 11, 22, 21, 0), "nb"), "Søndag kl. 21:00")

    def test_episode_words_and_the_guide(self):
        e = {"s": 2, "e": 4, "ep": "The Lift"}
        self.assertEqual(guide.episode_words(e, "de"), "Staffel 2, Folge 4: The Lift")
        self.assertEqual(guide.episode_words(e, "fr"), "Saison 2, épisode 4 : The Lift")
        ch = {**channel(episodes("a", 3, 1500)), "on": True}
        xml = guide.xmltv([ch], "http://x/t/k", "Home TV", start=NOW, days=1, lang="de")
        self.assertIn("<sub-title>Staffel 1, Folge 1: Part 1</sub-title>", xml)
        self.assertIn("<sub-title>Series 1, episode 1: Part 1</sub-title>", guide.xmltv([ch], "http://x/t/k", "Home TV", start=NOW, days=1))

    def test_up_next_heading_and_coming_soon(self):
        self.assertEqual(words.up_next(at(2026, 11, 18, 21, 0), "Show b", "de"), "Als Nächstes um 21:00: Show b")
        self.assertEqual(words.heading("next", "Comedy", "de"), "Als Nächstes")
        self.assertEqual(words.heading("later", "Comedy", "de"), "Später auf Comedy")
        a = {"entry": {"title": "Show", "s": 1, "e": 2}, "start": at(2026, 11, 22, 21, 0)}
        got = promo.words(a, "Comedy", "de")
        self.assertEqual((got["Heading"], got["Episode"], got["Day and time"]), ("Demnächst", "Staffel 1, Folge 2", "Sonntag um 21:00"))

    def test_the_card_strap_and_label_drawn(self):
        a = schedule.Channel(channel(episodes("a", 3, 1500, premiere="2026-11-10"))).airing(NOW)
        opts = dog.resolve({"dog_label": "new_repeat"}, None)
        with tempfile.TemporaryDirectory() as d:
            ctx = {"W": 1280, "H": 720, "kbps": 3000, "opts": opts, "names": {"channel": "Comedy", "station": "S"}, "logo": None,
                   "jf_url": "http://jf:8096", "jf_key": "k", "ts_offset": 0.0, "texts": dog.Texts(d), "lang": "de"}
            card = {"kind": "card", "card": "later", "start": NOW, "end": NOW + 10, "airing": a}
            stream.piece_command(card, NOW, ctx)
            prog = {"kind": "programme", "start": a["start"], "end": a["content_end"], "airing": a}
            stream.piece_command(prog, a["start"] + 1, ctx)
            drawn = [open(os.path.join(d, f), encoding="utf-8").read() for f in os.listdir(d)]
        self.assertIn("Später auf Comedy", drawn)
        self.assertIn("Staffel 1, Folge 1: Part 1", drawn)
        self.assertIn("Show a: Staffel 1, Folge 1: Part 1", drawn)  # the start strap
        self.assertIn("Neu", drawn)

    def test_the_holding_slide(self):
        with tempfile.TemporaryDirectory() as d:
            t = dog.Texts(d)
            dog.holding_chain(1280, 720, t, "back_soon", lang="de")
            dog.holding_chain(1280, 720, t, "countdown", "", 60, lang="de")
            drawn = [open(os.path.join(d, f), encoding="utf-8").read() for f in os.listdir(d)]
        self.assertIn("Gleich geht es weiter", drawn)
        self.assertTrue(any(x.startswith("Nächste Sendung in %{eif:") for x in drawn))


def item(streams):
    return {"Id": "a" * 32, "Type": "Movie", "Name": "Film", "RunTimeTicks": 5400 * 10**7, "MediaStreams": streams}


class TheSoundTrack(unittest.TestCase):
    def test_the_track_in_the_language_comes_first(self):
        e = library.entry(item([{"Index": 0, "Type": "Video"}, {"Index": 1, "Type": "Audio", "Language": "eng", "IsDefault": True},
                                {"Index": 2, "Type": "Audio", "Language": "fre"}, {"Index": 3, "Type": "Audio", "Language": "ger"}]))
        self.assertEqual(e["audio_langs"], ["eng", "fre", "ger"])
        self.assertEqual(stream.sound_map(e, "fr"), "0:a:1")
        self.assertEqual(stream.sound_map(e, "de"), "0:a:2")
        self.assertEqual(stream.sound_map(e, "en"), "0:a:0")

    def test_bibliographic_and_terminology_codes(self):
        e = library.entry(item([{"Index": 0, "Type": "Audio", "Language": "eng", "IsDefault": True},
                                {"Index": 1, "Type": "Audio", "Language": "deu"}, {"Index": 2, "Type": "Audio", "Language": "nld"},
                                {"Index": 3, "Type": "Audio", "Language": "nob"}]))
        self.assertEqual([library.sound_for(e, x) for x in ("de", "nl", "nb")], [1, 2, 3])

    def test_none_in_the_language_is_the_default_track(self):
        e = library.entry(item([{"Index": 0, "Type": "Audio", "Language": "jpn"}, {"Index": 1, "Type": "Audio", "Language": "eng", "IsDefault": True}]))
        self.assertEqual(stream.sound_map(e, "es"), "0:a:1")
        self.assertEqual(stream.sound_map(e, "en"), "0:a:1")

    def test_external_tracks_before_do_not_move_it(self):
        e = library.entry(item([{"Index": 0, "Type": "Audio", "Language": "spa", "IsExternal": True},
                                {"Index": 1, "Type": "Subtitle", "IsExternal": True}, {"Index": 2, "Type": "Video"},
                                {"Index": 3, "Type": "Audio", "Language": "eng", "IsDefault": True}, {"Index": 4, "Type": "Audio", "Language": "spa"}]))
        self.assertEqual(stream.sound_map(e, "es"), "0:a:1")  # the file's second own track, never the external file

    def test_one_track_keeps_no_languages(self):
        e = library.entry(item([{"Index": 0, "Type": "Audio", "Language": "eng"}]))
        self.assertNotIn("audio_langs", e)
        self.assertEqual(stream.sound_map(e, "fr"), "0:a:0")

    def test_a_refresh_brings_the_languages_and_drops_them_when_gone(self):
        spec = channel(episodes("a", 1, 1500))
        fresh = [{**spec["eras"][0]["lineup"][0], "audio_n": 0, "audio_langs": ["eng", "fre"]}]
        schedule.refresh_details(spec["eras"], fresh)
        self.assertEqual(spec["eras"][0]["lineup"][0]["audio_langs"], ["eng", "fre"])
        fresh[0].pop("audio_langs")
        self.assertEqual(schedule.refresh_details(spec["eras"], fresh), 1)
        self.assertNotIn("audio_langs", spec["eras"][0]["lineup"][0])


class FakeJf:
    """Jellyfin's item list and remote search, as the owner's Jellyfin answered for Kong: Skull Island (21 November 2026)."""

    def __init__(self, fail=False):
        self.asked, self.fail = [], fail

    def __call__(self, path, method=None, data=None):
        self.asked.append((method or "GET", path, data))
        if self.fail:
            raise OSError("Jellyfin is not answering")
        if path.startswith("/Items?Ids="):
            return {"Items": [{"Id": "m1", "Name": "Kong: Skull Island", "ProductionYear": 2017, "ProviderIds": {"Tmdb": "293167", "Imdb": "tt3731562"}}]}
        if path in ("/Items/RemoteSearch/Movie", "/Items/RemoteSearch/Series"):
            return [{"Name": "Kong. La isla Calavera", "Overview": "En los años 70, un variopinto grupo de exploradores...",
                     "ProviderIds": {"Tmdb": "293167"}, "SearchProviderName": "TheMovieDb"}]
        return []


class Titles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "titles.json")
        self.film = {"id": "m1", "kind": "Movie", "title": "Kong: Skull Island", "plot": "English plot."}

    def tearDown(self):
        self.tmp.cleanup()

    def test_english_asks_nothing(self):
        jf = FakeJf()
        t = titles.Titles(self.path, jf)
        self.assertIs(t.localise(self.film, "en"), self.film)
        self.assertEqual(t.want([self.film], "en"), 0)
        self.assertEqual(jf.asked, [])

    def test_asked_once_kept_and_used(self):
        jf = FakeJf()
        t = titles.Titles(self.path, jf)
        self.assertEqual(t.localise(self.film, "es")["title"], "Kong: Skull Island", "drawing never waits: Jellyfin's own first")
        self.assertEqual(t.work(), 1)
        got = t.localise(self.film, "es")
        self.assertEqual((got["title"], got["plot"][:11]), ("Kong. La isla Calavera", "En los años"))
        body = jf.asked[-1][2]
        self.assertEqual((body["SearchInfo"]["MetadataLanguage"], body["SearchInfo"]["ProviderIds"]["Tmdb"]), ("es", "293167"))
        again = titles.Titles(self.path, jf)  # from the file, after a restart
        self.assertEqual(again.localise(self.film, "es")["title"], "Kong. La isla Calavera")
        self.assertEqual(again.want([self.film], "es"), 0)

    def test_an_episode_takes_its_series_name_and_keeps_its_plot(self):
        t = titles.Titles(self.path, FakeJf())
        ep = {"id": "e1", "kind": "Episode", "group": "m1", "title": "Series", "plot": "The episode's own plot.", "ep": "Pilot"}
        t.want([ep], "es")
        t.work()
        got = t.localise(ep, "es")
        self.assertEqual((got["title"], got["plot"], got["ep"]), ("Kong. La isla Calavera", "The episode's own plot.", "Pilot"))

    def test_a_failure_keeps_jellyfins_text(self):
        t = titles.Titles(self.path, FakeJf(fail=True))
        t.want([self.film], "de")
        t.work()
        self.assertEqual(t.localise(self.film, "de"), self.film)
        self.assertEqual(t.want([self.film], "de"), 0, "not asked again until RETRY_DAYS have passed")

    def test_an_answer_for_another_item_is_not_taken(self):
        jf = FakeJf()
        orig = jf.__call__

        def other(path, method=None, data=None):
            got = orig(path, method, data)
            if path.startswith("/Items/RemoteSearch"):
                got[0]["ProviderIds"] = {"Tmdb": "1"}
            return got
        t = titles.Titles(self.path, other)
        t.want([self.film], "es")
        t.work()
        self.assertEqual(t.localise(self.film, "es"), self.film)

    def test_the_hourly_limit(self):
        clock = [NOW]
        t = titles.Titles(self.path, FakeJf(), per_hour=2, clock=lambda: clock[0])
        films = [{**self.film, "id": f"m{i}"} for i in range(5)]
        self.assertEqual(t.want(films, "es"), 5)
        self.assertEqual(t.work(), 2)
        self.assertEqual(t.work(), 0)
        clock[0] += 3601
        self.assertEqual(t.work(), 2)


    def test_a_promo_being_made_goes_first(self):
        t = titles.Titles(self.path, FakeJf(), per_hour=1)
        films = [{**self.film, "id": f"m{i}"} for i in range(3)]
        t.want(films, "es")
        t.want([films[2]], "es", first=True)
        self.assertEqual(t.work(), 1)
        self.assertIsNotNone(t.kept(films[2], "es"))
        self.assertIsNone(t.kept(films[0], "es"))


class TheApp(App):
    def test_the_up_next_strap_and_the_promo_design(self):
        cid = self.channel("Comedy", episodes("a", 4, 1500))
        run = os.environ["PLUGIN_RUN"]
        asked = []
        self.app.ask_titles = lambda entries, lang: asked.append((len(entries), lang))  # no thread in a test
        piece, ctx, cleanup = self.app.plan_for(cid)(NOW, NOW)
        cleanup()
        self.assertTrue(ctx["next_words"].startswith("Up next at "), ctx["next_words"])
        self.assertEqual(ctx["lang"], "en")
        self.assertNotIn("localise", ctx)
        with open(os.path.join(run, "settings.json"), "w") as f:
            json.dump({"station_name": "Home TV", "language": "de"}, f)
        self.answers = {"/Items?Ids=": {"Items": []}}
        piece, ctx, cleanup = self.app.plan_for(cid)(NOW, NOW)
        cleanup()
        self.assertTrue(ctx["next_words"].startswith("Als Nächstes um "), ctx["next_words"])
        self.assertTrue(ctx["next_words"].endswith(": Show a"))
        self.assertEqual(ctx["lang"], "de")
        self.assertEqual(self.app.language(), "de")
        self.assertEqual(asked[-1][1], "de", "the programmes coming up are asked for in German")
        # A change of language makes promos again: their design names the language, except English (kept as before)
        self.app.promo_design = lambda s, ch: {"name": "Plain", "promo": {"colour": "0x1f5f99"}}
        ch = self.app.find(self.app.state(), cid)
        self.assertEqual(self.app.promo_design_key(self.app.state(), ch), "plain:0x1f5f99|de")
        self.assertEqual(self.app.promo_design_key(self.app.state(), ch, {"language": "en"}), "plain:0x1f5f99")


if __name__ == "__main__":
    unittest.main()
