"""Create your own TV channel (tv-station): broadcast packs (the checker, pack.json against its schema, the zip
rules), the random ident choice, the logo with music as a sting, transitions at each cut, promos (what is made and
replaced, and the real FFmpeg command), promos shown on the other channels, the placement guides and the template,
and the example pack made in code."""
import http.server
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT  # noqa: E402
from test_tv_station import NOW, FakeJellyfin, channel, episodes  # noqa: E402

TV = os.path.join(ROOT, "tv-station")
sys.path.insert(0, TV)
import dog  # noqa: E402
import example_pack  # noqa: E402
import pack  # noqa: E402
import promo  # noqa: E402
import schedule  # noqa: E402
import stream  # noqa: E402

HAS_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def load_app(tmp, values=None, jellyfin=None):
    run, data = os.path.join(tmp, "run"), os.path.join(tmp, "data")
    os.makedirs(run, exist_ok=True)
    os.makedirs(data, exist_ok=True)
    json.dump(values or {}, open(os.path.join(run, "settings.json"), "w"))
    json.dump(jellyfin or {"url": "http://jellyfin.invalid:8096", "api_key": "k"}, open(os.path.join(run, "jellyfin.json"), "w"))
    open(os.path.join(run, "key"), "w").write("sbk_test")
    os.environ["PLUGIN_RUN"], os.environ["PLUGIN_DATA"] = run, data
    for m in ("sbplugin", "app"):
        sys.modules.pop(m, None)
    import app
    return app


_SMALL = {}


def small_pack():
    """The example pack made small, once for every test here that needs it (it takes about half a minute)."""
    if "folder" not in _SMALL:
        _SMALL["tmp"] = tempfile.TemporaryDirectory()
        _SMALL["folder"] = example_pack.make(os.path.join(_SMALL["tmp"].name, "Example-TV"), small=True)
        _SMALL["got"] = pack.check(_SMALL["folder"])
    return _SMALL["folder"], _SMALL["got"]


def zip_of(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            if isinstance(data, zipfile.ZipInfo):
                z.writestr(data, b"x")
            else:
                z.writestr(name, data)
    return buf.getvalue()


class Schema(unittest.TestCase):
    def test_the_template_and_the_owners_shape_pass(self):
        self.assertEqual(pack.validate(pack.template_pack_json()), [])
        # The shape of the first pack made for a channel (18 November 2026), its brand left out.
        first = {"pack": 1, "name": "A channel", "made": "18 November 2026", "size": [1920, 1080], "fps": 25,
                 "logo": {"dog": "logo/dog.png", "with_music": "logo/logo-with-music.mp4"}, "idents": ["ident01.mp4", "ident02.mp4"],
                 "coming_next": {"background": "coming-next/background.mp4", "clip": [980, 210, 1780, 660],
                                 "fields": {"Title": [140, 330, 940, 470], "Day and time": [140, 590, 940, 650]}},
                 "promo": {"background": "promo/background.mp4", "clip": [980, 210, 1780, 660], "music": ["promo/music/music01.m4a"],
                           "fields": {"Title": [140, 330, 940, 470], "Channel name": [140, 680, 940, 740]}},
                 "transitions": ["sting01.webm", "wipe01.webm"]}
        self.assertEqual(pack.validate(first), [])

    def test_mistakes_are_named(self):
        bad = pack.template_pack_json()
        bad["pack"] = 2
        bad["idents"] = ["my ident.mp4"]
        bad["coming_next"]["fields"]["Weather"] = [0, 0, 100, 100]
        bad["promo"]["clip"] = [900, 200, 800, 300]
        bad["promo"]["fields"]["Title"] = {"box": [140, 330, 940, 470], "align": "middle"}
        bad["colour"] = "#fff"
        said = " | ".join(pack.validate(bad))
        for words in ("pack should be 1", "not a name a pack may use: my ident.mp4", "Weather is not a field", "promo, clip: the box",
                      "colour is not something", "should be [left, top, right, bottom]"):
            self.assertIn(words, said)

    def test_the_schema_is_json_schema(self):
        s = json.load(open(os.path.join(TV, "pack.schema.json")))
        self.assertTrue(s["$schema"].startswith("https://json-schema.org/"))
        self.assertEqual(s["required"], ["pack", "name"])


class ZipRules(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def unpack(self, data):
        path = os.path.join(self.tmp.name, "p.zip")
        open(path, "wb").write(data)
        dest = os.path.join(self.tmp.name, "out")
        shutil.rmtree(dest, ignore_errors=True)
        pack.unpack(path, dest)
        return dest

    def refused(self, data, words):
        with self.assertRaises(pack.PackError) as e:
            self.unpack(data)
        self.assertIn(words, str(e.exception))
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "out")), "nothing is unpacked from a zip that is refused")

    def test_paths_outside_the_folder_links_and_strange_names_are_refused(self):
        self.refused(zip_of({"pack.json": "{}", "../evil.mp4": b"x"}), "outside the pack")
        self.refused(zip_of({"pack.json": "{}", "/etc/passwd": b"x"}), "from the top of a disk")
        self.refused(zip_of({"pack.json": "{}", "idents\\ident01.mp4": b"x"}), "backslash")
        self.refused(zip_of({"pack.json": "{}", "idents/my ident.mp4": b"x"}), "not a name a pack uses")
        self.refused(zip_of({"pack.json": "{}", "run.sh": b"x"}), "not a name a pack uses")
        link = zipfile.ZipInfo("idents/ident01.mp4")
        link.external_attr = (0o120777 << 16)
        self.refused(zip_of({"pack.json": "{}", "idents/ident01.mp4": link}), "a link")
        self.refused(zip_of({"logo/dog.png": b"x"}), "pack.json is missing")
        self.refused(b"not a zip at all", "not a zip")

    def test_a_zip_bomb_and_too_much_are_refused(self):
        self.refused(zip_of({"pack.json": "{}", "idents/ident01.mp4": b"\0" * (2 * 1024 * 1024)}), "packed far smaller")
        old = pack.MAX_TOTAL
        pack.MAX_TOTAL = 1000
        try:
            self.refused(zip_of({"pack.json": "{}", "idents/ident01.mp4": os.urandom(800), "idents/ident02.mp4": os.urandom(800)}),
                         "unpacked, more than")
        finally:
            pack.MAX_TOTAL = old
        many = {"pack.json": "{}", **{f"idents/ident{i:03d}.mp4": b"x" for i in range(pack.MAX_FILES + 1)}}
        self.refused(zip_of(many), "more than the 150")

    def test_one_folder_inside_the_zip_and_junk_are_fine(self):
        dest = self.unpack(zip_of({"My-pack/pack.json": "{}", "My-pack/idents/ident01.mp4": b"x", "__MACOSX/My-pack/._pack.json": b"x",
                                   "My-pack/README.txt": "read me", "My-pack/coming-next/placement.png": b"x"}))
        self.assertEqual(sorted(pack.files_in(dest)), ["idents/ident01.mp4", "pack.json"])
        self.assertFalse(os.path.exists(os.path.join(dest, "README.txt")), "files for people are not unpacked")


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg is not installed here")
class ExamplePack(unittest.TestCase):
    """The example pack, made small, and the checker on it and on broken copies of it."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.folder, cls.got = small_pack()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def copy(self):
        d = tempfile.mkdtemp(dir=self.tmp.name)
        shutil.rmtree(d)
        shutil.copytree(self.folder, d)
        return d

    def test_the_example_pack_passes_and_holds_everything(self):
        self.assertEqual(self.got["problems"], [])
        p = self.got["pack"]
        self.assertEqual(p["name"], "Example TV")
        self.assertEqual(p["dog"], "logo/dog.png")
        self.assertEqual([i["path"] for i in p["idents"]], ["idents/ident01.mp4", "idents/ident02.mp4", "idents/ident03.mp4"])
        self.assertTrue(p["sting"]["has_audio"])
        self.assertEqual(len(p["music"]), 2)
        self.assertEqual([t["codec"] for t in p["transitions"]], ["vp9", "vp9", "vp9"])
        self.assertEqual(set(p["coming_next"]["fields"]), {"Heading", "Title", "Episode", "Day and time", "Synopsis"})
        self.assertIn("Day and time", p["promo"]["fields"])
        for item in p["idents"] + p["music"] + [p["sting"]]:
            self.assertLessEqual(abs(item["gain"]), 1.0, f"{item['path']} is made at -23 LUFS")
        self.assertTrue(any("scaled to the picture" in n for n in self.got["notes"]), "another size is scaled, and said so")
        self.assertIn("3 idents", pack.summary(p))

    def test_its_pack_json_passes_the_schema(self):
        self.assertEqual(pack.validate(json.load(open(os.path.join(self.folder, "pack.json")))), [])

    def test_zip_round_trip_and_install(self):
        z = os.path.join(self.tmp.name, "example.zip")
        open(z, "wb").write(pack.zip_folder(self.folder, "Example-TV"))
        dest = os.path.join(self.tmp.name, "installed")
        got = pack.install_zip(z, dest, self.tmp.name)
        self.assertTrue(got["ok"])
        loaded = pack.load(dest)
        self.assertEqual(loaded["folder"], dest)
        self.assertEqual(len(loaded["idents"]), 3)

    def test_a_logo_with_no_transparency_is_refused(self):
        d = self.copy()
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=red:s=300x100", "-frames:v", "1",
                        os.path.join(d, "logo", "dog.png")], check=True)
        self.assertIn("logo/dog.png: has no transparent parts. Save it with a transparent background", pack.check(d)["problems"])

    def test_a_transition_without_alpha_and_a_long_ident_are_refused(self):
        d = self.copy()
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=blue:s=480x270:d=1", "-c:v", "libvpx-vp9",
                        os.path.join(d, "transitions", "wipe01.webm")], check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=blue:s=480x270:r=5:d=70", "-c:v", "libx264",
                        "-preset", "ultrafast", os.path.join(d, "idents", "ident04.mp4")], check=True)
        said = pack.check(d)["problems"]
        self.assertIn("transitions/wipe01.webm: has no transparency. Save it as WebM VP9 with alpha, or ProRes 4444 with alpha", said)
        self.assertIn("idents/ident04.mp4: 70.0 seconds. It should be 2 to 60 seconds", said)

    def test_a_sting_needs_its_music_and_pack_json_names_must_exist(self):
        d = self.copy()
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(self.folder, "logo", "logo-with-music.mp4"), "-an", "-c:v", "copy",
                        os.path.join(d, "logo", "logo-with-music.mp4")], check=True)
        os.remove(os.path.join(d, "idents", "ident03.mp4"))
        said = pack.check(d)["problems"]
        self.assertIn("logo/logo-with-music.mp4: has no sound. The logo's music is baked into this file", said)
        self.assertIn("pack.json names idents/ident03.mp4, which is not in the pack", said)

    def test_placement_guides_mark_the_clip_and_fields(self):
        lay = self.got["pack"]["coming_next"]
        png = pack.placement_png("coming_next", lay, dog.FONT)
        self.assertTrue(png.startswith(b"\x89PNG"))
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", "pipe:0", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"], input=png,
                             capture_output=True, check=True).stdout
        self.assertEqual(len(raw), 1920 * 1080 * 3)

        def px(x, y):
            i = (y * 1920 + x) * 3
            return tuple(raw[i:i + 3])
        x0, y0, x1, y1 = lay["clip"]
        r, g, b = px(x0 + 2, (y0 + y1) // 2)
        self.assertTrue(r > 230 and 190 < g < 230 and b < 110, f"the clip area's edge is yellow: {(r, g, b)}")
        t = lay["fields"]["Title"]["box"]
        r, g, b = px(t[0] + 2, (t[1] + t[3]) // 2)
        self.assertTrue(r < 140 and g > 220 and 140 < b < 200, f"a field's edge is green: {(r, g, b)}")
        r, g, b = px(pack.TITLE_SAFE[0] + 1, 540)
        self.assertTrue(min(r, g, b) > 230, "the title safe area is marked in white")
        self.assertTrue(os.path.isfile(os.path.join(self.folder, "promo", "placement.png")), "the pack carries its own guides")

    def test_a_card_drawn_from_the_pack(self):
        p = pack.load(self.folder) or {**self.got["pack"], "folder": self.folder}
        lay = p["coming_next"]
        a = schedule.Channel(channel(episodes("a", 2, 1500))).airing(NOW)
        piece = {"kind": "card", "card": "next", "start": NOW, "end": NOW + 10, "airing": a}
        with tempfile.TemporaryDirectory() as d:
            ctx = {"W": 640, "H": 360, "kbps": 800, "opts": dog.resolve({"dog_kind": "none"}, None), "names": {"channel": "Comedy", "station": "S"},
                   "logo": None, "jf_url": "", "jf_key": "", "ts_offset": 0, "texts": dog.Texts(d), "clip_path": str, "still": True,
                   "layout": {**lay, "file": os.path.join(self.folder, lay["background"])}}
            argv = stream.piece_command(piece, NOW, ctx)
            words = [open(os.path.join(d, f)).read() for f in sorted(os.listdir(d))]
            r = subprocess.run(argv, capture_output=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr[-300:])
        self.assertTrue(r.stdout.startswith(b"\x89PNG"))
        self.assertIn("Coming up next", words)
        self.assertIn("Show a", words)
        self.assertTrue(any(w.startswith(("Today at", "Tomorrow at")) for w in words), words)


class Breaks(unittest.TestCase):
    def setUp(self):
        self.ch = channel(episodes("a", 3, 1500), start_on=30)  # 25 minutes in a 30 minute slot: a 5 minute break
        self.sched = schedule.Channel(self.ch)
        self.idents = [{"id": f"i{k}", "dur": 5, "title": f"ident0{k}", "src": f"pack:station/idents/ident0{k}.mp4"} for k in (1, 2, 3)]

    def picks(self, clips, n=120, options=None):
        out = []
        t = NOW
        for _ in range(n):
            a, pieces = schedule.pieces_at(self.sched, t, clips, {"seed": 7, "cards": True, **(options or {})})
            out.append(next(p["clip"]["id"] for p in pieces if p.get("role") == "ident"))
            t = a["end"] + 1
        return out

    def test_a_packs_idents_play_in_a_random_order(self):
        got = self.picks({"idents": self.idents, "fillers": [], "random_idents": True})
        self.assertEqual(set(got), {"i1", "i2", "i3"}, "every ident is played")
        in_turn = self.picks({"idents": self.idents, "fillers": []})
        self.assertNotEqual(got, in_turn, "not in turn")
        self.assertTrue(all(c > 20 for c in (got.count(k) for k in ("i1", "i2", "i3"))), "each about a third of the time")
        self.assertEqual(got, self.picks({"idents": self.idents, "fillers": [], "random_idents": True}), "the same break each time it is asked")

    def test_the_logo_with_music_opens_the_break(self):
        sting = {"id": "pk-sting", "dur": 5, "title": "The logo with music", "src": "pack:station/logo/logo-with-music.mp4"}
        a, pieces = schedule.pieces_at(self.sched, NOW, {"idents": self.idents, "fillers": [], "sting": sting}, {"seed": 7})
        roles = [p.get("role") or p["kind"] for p in pieces]
        self.assertEqual(roles[:3], ["programme", "sting", "ident"])
        self.assertAlmostEqual(pieces[-1]["end"], a["end"])

    def test_a_promo_is_shown_only_before_its_programme(self):
        a = self.sched.airing(NOW)
        soon = {"id": "p1", "dur": 15, "title": "Promo: soon", "src": "promo:aaaa", "airs": a["end"] + 3600, "role": "promo"}
        gone = {"id": "p2", "dur": 15, "title": "Promo: gone", "src": "promo:bbbb", "airs": a["start"] - 60, "role": "promo"}
        got = set()
        t = NOW
        for _ in range(20):
            _, pieces = schedule.pieces_at(self.sched, t, {"idents": [], "fillers": [soon, gone]}, {"seed": 7})
            got |= {p["clip"]["id"] for p in pieces if p["kind"] == "clip"}
            t = self.sched.airing(t)["end"] + 1
            if t > soon["airs"]:
                break
        self.assertIn("p1", got)
        self.assertNotIn("p2", got)


class Transitions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = load_app(self.tmp.name)
        self.p = {"folder": "/data/packs/station", "transitions": [{"path": "transitions/wipe01.webm", "dur": 1.0, "codec": "vp9"},
                                                                   {"path": "transitions/sting01.mov", "dur": 2.0, "codec": "prores"}]}

    def tearDown(self):
        self.tmp.cleanup()

    def test_each_cut_has_both_halves_of_one_transition(self):
        sched = schedule.Channel(channel(episodes("a", 3, 1500), start_on=30))
        a, pieces = schedule.pieces_at(sched, NOW, {"idents": [], "fillers": []}, {"seed": 7, "cards": True})
        out = self.app.with_transitions(pieces, self.p, 7)
        tails = [x for x in out if "tail_from" in x]
        self.assertEqual(len(tails), 2, "the programme's end and the break's end each have a tail")
        prog_tail, last_tail = tails
        self.assertEqual(prog_tail["kind"], "programme")
        cut = a["content_end"]
        self.assertEqual(prog_tail["trans_out_at"], cut)
        first_break = next(x for x in out if x["kind"] != "programme")
        self.assertEqual(first_break["trans_in_at"], cut)
        self.assertEqual(self.app.pick_transition(self.p, 7, cut), self.app.pick_transition(self.p, 7, cut), "the same transition both sides")
        half = self.app.pick_transition(self.p, 7, cut)["dur"] / 2
        self.assertAlmostEqual(prog_tail["tail_from"], cut - half)
        self.assertEqual(prog_tail["start"], a["start"], "the tail still seeks from the programme's start")
        self.assertEqual(last_tail["trans_out_at"], a["end"])
        head = out[0]
        self.assertAlmostEqual(head["end"], cut - half)
        self.assertEqual(head["trans_in_at"], a["start"])
        # Every moment of the slot is in exactly one piece, as the stream finds them.
        for k in range(0, int(a["end"] - a["start"]), 7):
            t = a["start"] + k + 0.5
            found = [x for x in out if x["start"] <= t < x["end"] and t >= x.get("tail_from", x["start"])]
            self.assertTrue(found, t)

    def test_the_command_overlays_the_transition_with_its_transparency(self):
        a = schedule.Channel(channel(episodes("a", 2, 1500))).airing(NOW)
        piece = {"kind": "programme", "start": a["start"], "end": a["content_end"], "airing": a, "tail_from": a["content_end"] - 0.5}
        tr = {"file": "/data/packs/station/transitions/wipe01.webm", "dur": 1.0, "codec": "vp9"}
        with tempfile.TemporaryDirectory() as d:
            ctx = {"W": 1280, "H": 720, "kbps": 3000, "opts": dog.resolve({}, None), "names": {"channel": "C", "station": "S"}, "logo": None,
                   "jf_url": "http://jf", "jf_key": "k", "ts_offset": 1, "texts": dog.Texts(d), "clip_path": str, "copy_ok": True,
                   "trans_out": tr}
            argv = stream.piece_command(piece, a["content_end"] - 0.5, ctx)
        i = argv.index(tr["file"])
        self.assertEqual(argv[i - 3:i], ["-c:v", "libvpx-vp9", "-i"], "VP9 is decoded with libvpx, which keeps its alpha")
        self.assertIn("-re", argv[i - 7:i], "paced like the piece, so no frames wait")
        graph = argv[argv.index("-filter_complex") + 1]
        self.assertIn("trim=duration=0.500", graph)
        self.assertIn("overlay=eof_action=pass", graph)
        self.assertNotIn("copy", argv, "a programme with a transition is never copied")


class Promos(unittest.TestCase):
    def chans(self, lineups, can=True):
        out = []
        for k, lu in enumerate(lineups):
            ch = channel(lu, start_on=30, id=f"c{k}")
            out.append({"id": f"c{k}", "sched": schedule.Channel(ch), "can": can})
        return out

    def test_each_channel_keeps_its_number_of_different_programmes(self):
        lineup = episodes("a", 4, 1500) + episodes("b", 4, 1500) + episodes("c", 4, 1500) + episodes("d", 4, 1500)
        remove, make = promo.plan(self.chans([lineup, episodes("z", 6, 1500)]), [], 3, 2, NOW)
        self.assertEqual(remove, [])
        mine = [m for m in make if m["cid"] == "c0"]
        self.assertEqual(len(mine), 3)
        self.assertEqual(len({promo.group_of(m["airing"]["entry"]) for m in mine}), 3, "a different programme in each")
        self.assertTrue(all(m["airing"]["start"] >= NOW + promo.LEAD for m in make), "never for a programme about to start")
        self.assertEqual(len([m for m in make if m["cid"] == "c1"]), 1, "a channel of one series has one promo")

    def test_old_ones_are_replaced_and_never_pile_up(self):
        chans = self.chans([episodes("a", 4, 1500) + episodes("b", 4, 1500) + episodes("c", 4, 1500) + episodes("d", 4, 1500)])
        day = 86400
        existing = [{"id": "old", "cid": "c0", "group": "a", "airs": NOW + 3 * day, "made": NOW - 3 * day},
                    {"id": "aired", "cid": "c0", "group": "b", "airs": NOW - 60, "made": NOW - 3600},
                    {"id": "new1", "cid": "c0", "group": "c", "airs": NOW + day, "made": NOW - 3600},
                    {"id": "new2", "cid": "c0", "group": "d", "airs": NOW + day, "made": NOW - 7200},
                    {"id": "extra", "cid": "c0", "group": "a", "airs": NOW + day, "made": NOW - 9000},
                    {"id": "gone", "cid": "c9", "group": "x", "airs": NOW + day, "made": NOW}]
        remove, make = promo.plan(chans, existing, 2, 2, NOW)
        self.assertEqual({p["id"] for p in remove}, {"old", "aired", "extra", "gone"})
        self.assertEqual(make, [], "two kept, two wanted: nothing more is made")
        remove, make = promo.plan(chans, existing, 4, 2, NOW)
        self.assertEqual({p["id"] for p in remove}, {"old", "aired", "gone"})
        self.assertEqual(len(make), 1)
        self.assertEqual(promo.group_of(make[0]["airing"]["entry"]), "b", "not a programme it has a promo for already")
        kept = [p for p in existing if p not in remove]
        self.assertLessEqual(len(kept) + len(make), 4)

    def test_no_pack_with_a_promo_means_none(self):
        remove, make = promo.plan(self.chans([episodes("a", 4, 1500)], can=False),
                                  [{"id": "x", "cid": "c0", "group": "a", "airs": NOW + 86400, "made": NOW}], 3, 2, NOW)
        self.assertEqual([p["id"] for p in remove], ["x"])
        self.assertEqual(make, [])

    def test_the_day_and_time_stay_true_all_week(self):
        a = schedule.Channel(channel(episodes("a", 2, 1500))).airing(NOW + 3 * 86400)
        words = promo.words(a, "Comedy")
        self.assertRegex(words["Day and time"], r"^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday) at \d\d:\d\d$")
        self.assertEqual(words["Heading"], "Coming soon")
        self.assertEqual(words["Channel name"], "Comedy")


class CrossChannel(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def setup(self, values=None):
        app = load_app(tempfile.mkdtemp(dir=self.tmp.name), values)
        s = app.state()
        for name in ("Comedy", "Drama", "Films"):
            s["channels"].append(app.new_channel(s, name))
        a, b, c = s["channels"]
        c["on"] = False
        s["promos"] = [{"id": "aaaa000001", "cid": a["id"], "group": "x", "title": "X", "airs": NOW + 86400, "made": NOW, "dur": 15},
                       {"id": "bbbb000002", "cid": b["id"], "group": "y", "title": "Y", "airs": NOW + 86400, "made": NOW, "dur": 15},
                       {"id": "cccc000003", "cid": c["id"], "group": "z", "title": "Z", "airs": NOW + 86400, "made": NOW, "dur": 15}]
        app.save(s)
        return app, app.state()

    def test_other_channels_promos_are_shown_unless_deactivated(self):
        app, s = self.setup()
        a = s["channels"][0]
        got = {c["title"] for c in app.clips_for(s, a)["fillers"]}
        self.assertEqual(got, {"Promo: X", "Promo: Y"}, "its own and the other channel's, not a channel off air")
        app, s = self.setup({"promo_other": False})
        self.assertEqual({c["title"] for c in app.clips_for(s, s["channels"][0])["fillers"]}, {"Promo: X"})

    def test_a_promo_is_a_file_in_the_plug_ins_folder(self):
        app, s = self.setup()
        data = app.sbplugin.DATA
        self.assertEqual(app.clip_path("promo:aaaa000001"), os.path.join(data, "promos", "aaaa000001.mp4"))
        self.assertEqual(app.clip_path("promo:../../x"), os.path.join(data, "promos", ".mp4"))
        with self.assertRaises(ValueError):
            app.clip_path("pack:station/../../run/key")


class PacksInTheApp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = load_app(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_pages_keep_to_starboards_limits_and_offer_the_downloads(self):
        app = self.app
        app.sbplugin.keep("learned", {"address": "http://192.168.1.20:8790"})
        app.channels_post({"action": "add", "value": "Comedy"}, now=NOW)
        page = app.pack_page()
        ids = [it["id"] for it in page["items"]]
        for want in ("station", "example", "dl-template", "dl-coming-next", "dl-promo", "dl-logo", "promo-none"):
            self.assertIn(want, ids)
        token = app.state()["token"]
        dl = {it["id"]: it for it in page["items"]}
        self.assertEqual(dl["dl-template"]["link"]["url"], f"http://192.168.1.20:8790/t/{token}/download/template.zip")
        self.assertEqual(dl["station"]["attach"]["accept"], ".zip")
        for it in page["items"]:
            self.assertLessEqual(len(it["title"]), 120)
            self.assertLessEqual(len(it.get("detail", "")), 200)
        rows = {it["id"].split(":")[1]: it for it in app.channels_page(now=NOW)["items"] if ":" in it["id"]}
        self.assertEqual([o[0] for o in rows["pack"]["choice"]["options"]], ["", "own", "none"])
        cid = app.state()["channels"][0]["id"]
        app.channels_post({"action": "choose", "id": f"{cid}:pack", "value": "none"}, now=NOW)
        self.assertEqual(app.find(app.state(), cid)["pack"], "none")
        self.assertIsNone(app.channel_pack(app.state(), app.find(app.state(), cid)))

    @unittest.skipUnless(HAS_FFMPEG, "ffmpeg is not installed here")
    def test_the_template_zip(self):
        data, kind, name = self.app.download("template.zip", {})
        self.assertEqual(kind, "application/zip")
        z = zipfile.ZipFile(io.BytesIO(data))
        names = set(z.namelist())
        for want in ("broadcast-pack/pack.json", "broadcast-pack/pack.schema.json", "broadcast-pack/README.txt",
                     "broadcast-pack/coming-next/placement.png", "broadcast-pack/promo/placement.png", "broadcast-pack/logo/placement.png",
                     "broadcast-pack/idents/what-goes-here.txt", "broadcast-pack/promo/music/what-goes-here.txt"):
            self.assertIn(want, names)
        self.assertEqual(pack.validate(json.loads(z.read("broadcast-pack/pack.json"))), [])
        readme = z.read("broadcast-pack/README.txt").decode()
        for words in ("1920 by 1080", "-23 LUFS", "identNN" if "identNN" in readme else "ident01.mp4", "WebM VP9", "ProRes 4444", "title safe"):
            self.assertIn(words, readme)
        # The template, unchanged, is checked as a pack: what is missing is named, nothing in it is refused for its name.
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "t.zip")
            open(p, "wb").write(data)
            pack.unpack(p, os.path.join(d, "out"))
            said = pack.check(os.path.join(d, "out"))["problems"]
        self.assertIn("logo/dog.png is missing: every pack has the on-screen logo", said)


@unittest.skipUnless(HAS_FFMPEG, "ffmpeg is not installed here")
class MakingAPromo(unittest.TestCase):
    """A real promo, from the small example pack and a stand-in Jellyfin's clip."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        FakeJellyfin.folder = cls.tmp.name
        subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=25:d=60", "-f", "lavfi", "-i", "sine=f=330:d=60",
                        "-c:v", "libx264", "-preset", "ultrafast", "-g", "25", "-c:a", "aac", "-shortest", "-y",
                        os.path.join(cls.tmp.name, "a1.ts")], check=True)
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeJellyfin)
        threading.Thread(target=cls.server.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}"
        cls.folder, got = small_pack()
        cls.pack = {**got["pack"], "folder": cls.folder}

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.tmp.cleanup()

    def test_a_promo_with_clips_music_and_its_day_and_time(self):
        lineup = [{"id": "a1", "dur": 60, "title": "Pattern Show", "group": "a", "kind": "Episode", "s": 1, "e": 2, "ep": "The Middle"}]
        a = schedule.Channel(channel(lineup, start_on=0)).airing(NOW + 86400)
        out = os.path.join(self.tmp.name, "promo.mp4")
        with tempfile.TemporaryDirectory() as d:
            texts = dog.Texts(d)
            argv, seconds = promo.command(self.pack, a, "Comedy", promo.pick_music(self.pack, 1), 480, 270, self.url, "k", texts, out)
            words = [open(os.path.join(d, f)).read() for f in sorted(os.listdir(d))]
            self.assertEqual(argv[argv.index("-threads") + 1], "1", "one thread")
            began = time.monotonic()
            ok, why = promo.run(argv, limit=120)
            took = time.monotonic() - began
        self.assertTrue(ok, why)
        self.assertIn(dog.day_time_words(a["start"]), words)
        self.assertIn("Pattern Show", words)
        self.assertIn("Comedy", words)
        info = pack.probe(out)
        self.assertTrue(info["audio"], "with its music bed")
        self.assertAlmostEqual(info["duration"], seconds, delta=0.6)
        self.assertEqual((info["video"]["width"], info["video"]["height"]), (480, 270))
        self.assertLess(took, 90)

    def test_a_promo_gives_way_when_someone_starts_watching(self):
        lineup = [{"id": "a1", "dur": 60, "title": "Pattern Show", "group": "a", "kind": "Episode"}]
        a = schedule.Channel(channel(lineup, start_on=0)).airing(NOW + 86400)
        with tempfile.TemporaryDirectory() as d:
            argv, _ = promo.command(self.pack, a, "Comedy", None, 1920, 1080, self.url, "k", dog.Texts(d), os.path.join(d, "p.mp4"))
            threading.Timer(0.5, promo.stop).start()
            ok, why = promo.run(argv, limit=120)
        self.assertFalse(ok)
        self.assertIn("someone began watching", why)


if __name__ == "__main__":
    unittest.main()
