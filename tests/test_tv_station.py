"""TV station (DASH-477): the schedule, the guide (XMLTV) and the channel list (M3U), the on-screen logo (DOG) options,
the pages Starboard draws, and a real FFmpeg run that tunes in part way through a programme and draws the DOG.

The FFmpeg tests run only where ffmpeg is installed; they use short made-up clips from a stand-in Jellyfin."""
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
import urllib.request
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT, STARBOARD_SRC, manifest  # noqa: E402

TV = os.path.join(ROOT, "tv-station")
sys.path.insert(0, TV)
import dog  # noqa: E402
import guide  # noqa: E402
import schedule  # noqa: E402
import stream  # noqa: E402

NOW = 1794600123.0  # Tuesday 18 November 2026, 20:02:03 UTC


def episodes(series, n, dur, premiere="2020-01-01"):
    return [{"id": f"{series}{i}", "dur": dur, "title": f"Show {series}", "group": series, "s": 1, "e": i, "ep": f"Part {i}",
             "plot": f"Episode {i}.", "kind": "Episode", "premiere": premiere, "art": f"{series}{i}", "backdrop": series} for i in range(1, n + 1)]


def channel(lineup, now=NOW, **more):
    ch = {"id": "abcd1234", "name": "Comedy", "number": 1, "order": "in_order", "run": 1, "start_on": 30, "break_seconds": 0,
          "seed": 7, "eras": [], **more}
    ch["eras"] = schedule.new_era(ch, lineup, now)
    return ch


class Schedule(unittest.TestCase):
    def test_same_answer_for_the_same_time(self):
        ch = channel(episodes("a", 5, 1500) + episodes("b", 3, 2700), order="shuffle", run=2)
        for t in (NOW, NOW + 7777, NOW + 86400 * 3 + 5):
            one, two = schedule.Channel(ch).airing(t), schedule.Channel(json.loads(json.dumps(ch))).airing(t)
            self.assertEqual(one["entry"]["id"], two["entry"]["id"])
            self.assertEqual(one["start"], two["start"])

    def test_tuning_in_part_way_through_finds_the_offset(self):
        c = schedule.Channel(channel(episodes("a", 3, 1500)))
        a = c.airing(NOW + 600)
        self.assertLessEqual(a["start"], NOW + 600)
        self.assertLess(NOW + 600, a["end"])
        self.assertEqual(a["entry"]["id"], c.airing(a["start"])["entry"]["id"])
        self.assertAlmostEqual(NOW + 600 - a["start"], (NOW + 600) % 1800, places=3)

    def test_programmes_start_on_the_boundary_and_breaks_fill_the_gap(self):
        for grid in (15, 30, 60):
            c = schedule.Channel(channel(episodes("a", 4, 1300), start_on=grid))
            for a in c.airings(NOW, NOW + 86400):
                self.assertEqual(a["start"] % (grid * 60), 0)
                self.assertEqual(a["end"] % (grid * 60), 0)
                self.assertLessEqual(a["content_end"], a["end"])

    def test_back_to_back_runs_one_after_another(self):
        c = schedule.Channel(channel(episodes("a", 3, 1234.5), start_on=0, break_seconds=60))
        got = c.airings(NOW, NOW + 20000)
        for x, y in zip(got, got[1:]):
            self.assertEqual(x["end"], y["start"])
            self.assertAlmostEqual(x["end"] - x["content_end"], 60)

    def test_episodes_in_a_row_take_turns_by_series(self):
        order = schedule.cycle_order(episodes("a", 4, 60) + episodes("b", 4, 60), "in_order", 2, 1, 0)
        self.assertEqual(order, [0, 1, 4, 5, 2, 3, 6, 7])

    def test_shuffle_keeps_every_programme_once_and_its_runs_together(self):
        lineup = episodes("a", 6, 60) + episodes("b", 6, 60)
        o1 = schedule.cycle_order(lineup, "shuffle", 3, 9, 0)
        self.assertEqual(sorted(o1), list(range(12)))
        self.assertNotEqual(o1, schedule.cycle_order(lineup, "shuffle", 3, 9, 1))
        for k in range(0, 12, 3):
            self.assertEqual(o1[k + 1], o1[k] + 1)

    def test_new_episodes_join_at_the_next_boundary_without_a_jump(self):
        ch = channel(episodes("a", 3, 1500))
        later = NOW + 2000
        on = schedule.Channel(ch).airing(later)
        nxt = schedule.Channel(ch).airing(on["end"])
        ch["eras"] = schedule.new_era(ch, episodes("a", 4, 1500), later)
        c = schedule.Channel(ch)
        self.assertEqual(c.airing(later)["entry"]["id"], on["entry"]["id"])
        self.assertEqual(c.airing(later)["end"], on["end"])
        self.assertEqual(c.airing(on["end"])["entry"]["id"], nxt["entry"]["id"])
        self.assertEqual(len(ch["eras"]), 2)
        self.assertIn("a4", {a["entry"]["id"] for a in c.airings(NOW, NOW + 86400)})

    def test_breaks_fill_the_gap_exactly(self):
        c = schedule.Channel(channel(episodes("a", 3, 1300)))
        clips = {"idents": [{"id": "i", "dur": 6, "title": "Ident"}], "fillers": [{"id": "t", "dur": 125, "title": "Trailer"},
                                                                                  {"id": "u", "dur": 40, "title": "Clip"}]}
        for t in (NOW, NOW + 1800, NOW + 3600 * 5):
            a, pieces = schedule.pieces_at(c, t, clips, {"seed": 1})
            self.assertEqual(pieces[0]["kind"], "programme")
            for x, y in zip(pieces, pieces[1:]):
                self.assertAlmostEqual(x["end"], y["start"])
            self.assertAlmostEqual(pieces[-1]["end"], a["end"])
            self.assertEqual(pieces[-1]["role"], "ident", "0.4.0: the ident plays immediately before the next programme")
            self.assertEqual(pieces[-2]["card"], "next")
            self.assertEqual(schedule.pieces_at(c, t, clips, {"seed": 1})[1], pieces)

    def test_a_break_with_no_clips_is_cards(self):
        c = schedule.Channel(channel(episodes("a", 2, 1000)))
        _, pieces = schedule.pieces_at(c, NOW, {}, {"seed": 1})
        self.assertTrue(all(p["kind"] == "card" for p in pieces[1:]))
        self.assertTrue(all(p["end"] - p["start"] <= 40 for p in pieces[1:]))
        _, plain = schedule.pieces_at(c, NOW, {}, {"seed": 1, "cards": False})
        self.assertEqual([p["kind"] for p in plain[1:]], ["slate"])


class Guide(unittest.TestCase):
    def setUp(self):
        self.ch = channel(episodes("a", 3, 1500, premiere="2026-11-10") + episodes("b", 2, 2700))
        self.off = {**channel(episodes("c", 1, 600)), "id": "ffff0000", "number": 2, "on": False}

    def test_m3u_lists_channels_on_air_in_order_with_numbers(self):
        two = {**self.ch, "id": "beef0001", "number": 3, "name": "Drama & films"}
        text = guide.m3u([self.ch, self.off, two], "http://192.0.2.5:8790/t/tok", "Home TV")
        lines = text.splitlines()
        self.assertEqual(lines[0], "#EXTM3U")
        self.assertEqual(len(lines), 5)
        self.assertIn('tvg-chno="1"', lines[1])
        self.assertEqual(lines[2], "http://192.0.2.5:8790/t/tok/stream/abcd1234.ts")
        self.assertIn('tvg-name="Drama &amp; films"', lines[3])
        self.assertNotIn("ffff0000", text)

    def test_xmltv_has_seven_days_with_titles_episodes_and_new(self):
        root = ET.fromstring(guide.xmltv([self.ch, self.off], "http://h/t/tok", "Home TV", start=NOW))
        self.assertEqual([c.get("id") for c in root.iter("channel")], ["tv-station-abcd1234"])
        progs = list(root.iter("programme"))
        stamps = [time.mktime(time.strptime(p.get("start")[:14], "%Y%m%d%H%M%S")) for p in progs]
        self.assertGreaterEqual(max(stamps) - min(stamps), 6.9 * 86400)
        for p, q in zip(progs, progs[1:]):
            self.assertEqual(p.get("stop"), q.get("start"))
        first = progs[0]
        self.assertEqual(first.find("title").text, "Show a")
        self.assertEqual(first.find("sub-title").text, "Series 1, episode 1: Part 1")
        self.assertIsNotNone(first.find("new"))
        self.assertEqual(first.find("icon").get("src"), "http://h/t/tok/art/a1.jpg")
        self.assertEqual(first.find("episode-num").text, "0.0.")
        b = next(p for p in progs if p.find("title").text == "Show b")
        self.assertIsNotNone(b.find("previously-shown"))

    def test_same_guide_for_the_same_time(self):
        self.assertEqual(guide.xmltv([self.ch], "h", "S", start=NOW), guide.xmltv([self.ch], "h", "S", start=NOW + 60))


class Dog(unittest.TestCase):
    def test_channel_overrides_station_and_defaults(self):
        st = {"dog_corner": "bottom_left", "dog_opacity": 60, "dog_clock": True}
        o = dog.resolve(st, {"dog": {"corner": "top_left", "opacity": ""}})
        self.assertEqual(o["corner"], "top_left")
        self.assertEqual(o["opacity"], 60)
        self.assertTrue(o["clock"])
        self.assertEqual(o["size"], "medium")
        self.assertTrue(o["plate"])

    def test_bad_values_fall_back(self):
        o = dog.resolve({"dog_corner": "middle", "dog_opacity": 5, "dog_size": "huge"}, None)
        self.assertEqual((o["corner"], o["opacity"], o["size"]), ("top_right", 30, "medium"))

    def test_copy_only_when_nothing_is_drawn(self):
        o = dog.resolve({}, None)
        self.assertFalse(dog.needs_encoding(o))
        plain = dog.resolve({"dog_kind": "none", "dog_strap_start": False, "dog_strap_end": False}, None)
        self.assertTrue(dog.needs_encoding(plain))

    def test_when_it_shows(self):
        o = dog.resolve({"dog_when": "programmes_cards"}, None)
        self.assertEqual([dog.shows_on(o, k) for k in ("programme", "clip", "card")], [True, False, True])
        o = dog.resolve({"dog_when": "programmes"}, None)
        self.assertEqual([dog.shows_on(o, k) for k in ("programme", "clip", "card")], [True, False, False])

    def test_text_dog_has_an_outline_and_a_plate(self):
        with tempfile.TemporaryDirectory() as d:
            o = dog.resolve({"dog_kind": "channel_name", "dog_label": "new_repeat", "dog_fade_in": 60}, None)
            chain, logo = dog.overlay_chain(o, 1280, 720, "programme", dog.Texts(d), {"channel": "Comedy", "station": "Home TV"},
                                            rel=20, programme={"duration": 1500, "label": "New", "start_words": "Show", "next_words": "Up next"})
            self.assertIsNone(logo)
            joined = ",".join(chain)
            self.assertIn("borderw=", joined)
            self.assertIn("box=1", joined)
            self.assertIn("enable='gte(t,40.00)'", joined)  # fades in 60 seconds into the programme: 40 after a join at 20
            self.assertIn("enable='lt(t,100.00)'", joined)  # the label, for the first 2 minutes
            self.assertIn("between(t,1450.00,1479.00)", joined)  # Up next in the last 30 seconds

    def test_logo_dog_with_plate_and_opacity(self):
        with tempfile.TemporaryDirectory() as d:
            o = dog.resolve({"dog_opacity": 70}, None)
            _, logo = dog.overlay_chain(o, 1280, 720, "programme", dog.Texts(d), {"channel": "C", "station": "S"}, logo="/x.png")
            self.assertIn("pad=", logo)
            self.assertIn("aa=0.70", logo)
            self.assertEqual(dog.logo_position(o, 1280, 720), ("W-w-64", "36"))  # 5% of the width from the side, 5% of the height from the top

    def test_when_words(self):
        noon = time.mktime((2026, 11, 18, 12, 0, 0, 0, 0, -1))
        self.assertEqual(dog.when_words(noon + 3600, noon), "Today at 13:00")
        self.assertEqual(dog.when_words(noon + 86400, noon), "Tomorrow at 12:00")
        self.assertEqual(dog.when_words(noon + 3 * 86400, noon), "Saturday 21 November at 12:00")


class Commands(unittest.TestCase):
    def ctx(self, d, **more):
        return {"W": 1280, "H": 720, "kbps": 3000, "opts": dog.resolve({}, None), "names": {"channel": "C", "station": "S"},
                "logo": None, "jf_url": "http://jf:8096", "jf_key": "k", "ts_offset": 12.5, "texts": dog.Texts(d),
                "clip_path": lambda s: "/data/clips/" + s[5:], **more}

    def test_programme_joined_part_way_seeks_and_paces(self):
        a = schedule.Channel(channel(episodes("a", 2, 1500))).airing(NOW)
        piece = {"kind": "programme", "start": a["start"], "end": a["content_end"], "airing": a}
        with tempfile.TemporaryDirectory() as d:
            argv = stream.piece_command(piece, a["start"] + 300, self.ctx(d))
        self.assertEqual(argv[argv.index("-ss") + 1], "300.000")
        self.assertIn("-re", argv)
        self.assertIn("http://jf:8096/Videos/a1/stream?static=true", argv)
        self.assertEqual(argv[argv.index("-t") + 1], "1200.000")
        self.assertEqual(argv[argv.index("-output_ts_offset") + 1], "12.500")
        self.assertEqual(argv[-1], "pipe:1")

    def test_copy_when_nothing_is_drawn(self):
        a = schedule.Channel(channel(episodes("a", 2, 1500))).airing(NOW)
        piece = {"kind": "programme", "start": a["start"], "end": a["content_end"], "airing": a}
        plain = dog.resolve({"dog_kind": "none", "dog_strap_start": False, "dog_strap_end": False}, None)
        with tempfile.TemporaryDirectory() as d:
            argv = stream.piece_command(piece, a["start"] + 5, self.ctx(d, opts=plain, copy_ok=True))
        self.assertEqual(argv[argv.index("-c:v") + 1], "copy")
        self.assertNotIn("-filter_complex", argv)


# The real FFmpeg test: a stand-in Jellyfin serves short made-up clips, with the Range answers FFmpeg seeks with. ------
class FakeJellyfin(http.server.BaseHTTPRequestHandler):
    folder = ""

    def log_message(self, *a):
        pass

    def do_HEAD(self):  # noqa: N802
        self.send_response(404)
        self.end_headers()

    def do_GET(self):  # noqa: N802
        m = re.match(r"^/Videos/(\w+)/stream", self.path)
        path = os.path.join(self.folder, f"{m.group(1)}.ts") if m else ""
        if not os.path.isfile(path):
            self.send_response(404)
            self.end_headers()
            return
        data = open(path, "rb").read()
        start, end = 0, len(data) - 1
        r = re.match(r"bytes=(\d+)-(\d*)", self.headers.get("Range") or "")
        if r:
            start = int(r.group(1))
            end = int(r.group(2)) if r.group(2) else end
        self.send_response(206 if r else 200)
        self.send_header("Content-Type", "video/mp2t")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if r:
            self.send_header("Content-Range", f"bytes {start}-{end}/{len(data)}")
        self.end_headers()
        try:
            self.wfile.write(data[start:end + 1])
        except (BrokenPipeError, ConnectionResetError):
            pass


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is not installed here")
class RealFFmpeg(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        FakeJellyfin.folder = cls.tmp.name
        # A 30-second clip whose picture changes every frame (a moving test pattern), and a short ident.
        for name, secs in (("ep1", 30), ("ep2", 30)):
            subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", f"testsrc2=s=640x360:r=25:d={secs}", "-f", "lavfi",
                            "-i", f"sine=f=440:d={secs}", "-c:v", "libx264", "-preset", "ultrafast", "-g", "25", "-c:a", "aac",
                            "-shortest", "-y", os.path.join(cls.tmp.name, f"{name}.ts")], check=True)
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeJellyfin)
        threading.Thread(target=cls.server.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.tmp.cleanup()

    def frame(self, argv_input, at=None):
        cmd = ["ffmpeg", "-loglevel", "error"] + (["-ss", str(at)] if at is not None else []) + argv_input + [
            "-frames:v", "1", "-vf", "scale=320:180,format=gray", "-f", "rawvideo", "pipe:1"]
        return subprocess.run(cmd, capture_output=True, check=True).stdout

    def test_tunes_in_part_way_and_draws_the_dog(self):
        lineup = [{"id": "ep1", "dur": 30, "title": "Test pattern", "group": "x", "kind": "Movie", "has_audio": True, "audio": None}]
        ch = channel(lineup, start_on=0)
        a = schedule.Channel(ch).airing(NOW)
        piece = {"kind": "programme", "start": a["start"], "end": a["content_end"], "airing": a}
        out = os.path.join(self.tmp.name, "out.ts")
        with tempfile.TemporaryDirectory() as d:
            opts = dog.resolve({"dog_kind": "channel_name", "dog_corner": "top_right", "dog_size": "large", "dog_label": "live",
                                "dog_strap_start": False, "dog_strap_end": False}, None)
            ctx = {"W": 640, "H": 360, "kbps": 800, "opts": opts, "names": {"channel": "COMEDY", "station": "S"}, "logo": None,
                   "jf_url": self.url, "jf_key": "k", "ts_offset": 0, "texts": dog.Texts(d), "clip_path": str}
            argv = stream.piece_command(piece, a["start"] + 20, ctx)
            argv = [x for x in argv if x not in ("-re",)]
            i = argv.index("-readrate_initial_burst")
            del argv[i:i + 2]
            with open(out, "wb") as f:
                subprocess.run(argv, stdout=f, check=True, timeout=120)
        with open(out, "rb") as f:
            head = f.read(188 * 4)
        self.assertTrue(all(head[k] == 0x47 for k in range(0, len(head), 188)), "MPEG-TS packets")
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", out],
                                   capture_output=True, check=True).stdout)
        self.assertAlmostEqual(dur, 10, delta=1.0)  # 20 of 30 seconds already shown: the last 10 play
        src20 = self.frame(["-i", os.path.join(self.tmp.name, "ep1.ts")], at=20)
        src0 = self.frame(["-i", os.path.join(self.tmp.name, "ep1.ts")], at=0)
        got = self.frame(["-i", out])

        def diff(x, y, rows=range(60, 180)):  # the lower two thirds, away from the DOG
            return sum(abs(x[r * 320 + c] - y[r * 320 + c]) for r in rows for c in range(0, 320, 4)) / (len(rows) * 80)
        self.assertLess(diff(got, src20), diff(got, src0), "the first frame is from 20 seconds in")
        corner = range(0, 50)

        def cdiff(x, y):
            return sum(abs(x[r * 320 + c] - y[r * 320 + c]) for r in corner for c in range(200, 320)) / (50 * 120)
        self.assertGreater(cdiff(got, src20), 8, "the DOG is drawn in the top right corner")

    def test_a_card_frame_and_the_shared_stream(self):
        """A Coming up next card draws; then the plug-in's server streams a channel to two viewers with one FFmpeg."""
        os.environ["TV_TEST"] = "1"
        run, data = os.path.join(self.tmp.name, "run"), os.path.join(self.tmp.name, "data")
        os.makedirs(run, exist_ok=True)
        os.makedirs(data, exist_ok=True)
        json.dump({"picture": "720", "most_at_once": 1, "stop_after": 5}, open(os.path.join(run, "settings.json"), "w"))
        json.dump({"url": self.url, "api_key": "k"}, open(os.path.join(run, "jellyfin.json"), "w"))
        open(os.path.join(run, "key"), "w").write("sbk_test")
        os.environ["PLUGIN_RUN"], os.environ["PLUGIN_DATA"] = run, data
        for m in ("sbplugin", "app"):
            sys.modules.pop(m, None)
        import app
        # 19 November 2026 (owner: "is this not populated automatically?"): with the setting empty, the address
        # Starboard gives it on the home network is the one Jellyfin uses.
        os.environ["STARBOARD_HOME_ADDRESS"] = "http://192.0.2.9:8790/"
        self.assertEqual(app.address(), "http://192.0.2.9:8790")
        os.environ.pop("STARBOARD_HOME_ADDRESS")
        lineup = [{"id": f"ep{i}", "dur": 30, "title": f"Pattern {i}", "group": f"g{i}", "kind": "Movie", "plot": "A test.",
                   "backdrop": "none", "has_audio": True, "audio": None} for i in (1, 2)]
        s = app.state()
        ch = app.new_channel(s, "Comedy")
        ch["start_on"] = 0
        ch["break_seconds"] = 12
        ch["eras"] = schedule.new_era(ch, lineup, time.time() - 5)
        s["channels"].append(ch)
        app.save(s)
        png = app.preview(ch["id"], "card")
        self.assertTrue(png.startswith(b"\x89PNG"))
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
        threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_address[1]}/t/{s['token']}"
        try:
            m3u = urllib.request.urlopen(base + "/channels.m3u").read().decode()
            self.assertIn(f"/stream/{ch['id']}.ts", m3u)
            self.assertEqual(app._streams.playing(), {}, "nothing streams until a channel is chosen")
            got = {}

            def watch(k):
                with urllib.request.urlopen(base + f"/stream/{ch['id']}.ts", timeout=30) as r:
                    got[k] = r.read(188 * 2000)
            viewers = [threading.Thread(target=watch, args=(k,)) for k in (1, 2)]
            for v in viewers:
                v.start()
            time.sleep(2)
            self.assertEqual(len(app._streams.hubs), 1, "two viewers share one stream")
            for v in viewers:
                v.join(60)
            self.assertTrue(all(len(b) == 188 * 2000 and b[0] == 0x47 for b in got.values()))
            deadline = time.time() + 30
            while app._streams.hubs and time.time() < deadline:
                time.sleep(1)
            self.assertEqual(app._streams.hubs, {}, "it stops after the last viewer leaves")
        finally:
            srv.shutdown()
            app._streams.stop_all()


class Pages(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        run, data = os.path.join(self.tmp.name, "run"), os.path.join(self.tmp.name, "data")
        os.makedirs(run)
        os.makedirs(data)
        json.dump({"station_name": "Home TV"}, open(os.path.join(run, "settings.json"), "w"))
        open(os.path.join(run, "key"), "w").write("sbk_test")
        os.environ["PLUGIN_RUN"], os.environ["PLUGIN_DATA"] = run, data
        for m in ("sbplugin", "app"):
            sys.modules.pop(m, None)
        import app
        self.app = app

    def tearDown(self):
        self.tmp.cleanup()

    def test_add_a_channel_and_change_it(self):
        page = self.app.channels_post({"action": "add", "value": "Comedy"}, now=NOW)
        self.assertIn("Added Comedy", page["said"])
        cid = page["menus"][0]["id"]
        self.assertTrue(page["menus"][0]["title"].startswith("1  Comedy"))
        page = self.app.channels_post({"action": "attach", "id": f"{cid}:name", "value": "Laughs"}, now=NOW)
        self.assertEqual(self.app.find(self.app.state(), cid)["name"], "Laughs")
        self.app.channels_post({"action": "choose", "id": f"{cid}:dog-corner", "value": "bottom_left"}, now=NOW)
        self.assertEqual(self.app.find(self.app.state(), cid)["dog"]["corner"], "bottom_left")
        self.app.channels_post({"action": "choose", "id": f"{cid}:dog-corner", "value": ""}, now=NOW)
        self.assertNotIn("corner", self.app.find(self.app.state(), cid)["dog"])
        with self.assertRaises(ValueError):
            self.app.channels_post({"action": "attach", "id": f"{cid}:number", "value": "0"}, now=NOW)

    def test_pages_keep_to_starboards_limits(self):
        self.app.channels_post({"action": "add", "value": "Comedy"}, now=NOW)
        s = self.app.state()
        s["channels"][0]["eras"] = schedule.new_era(s["channels"][0], episodes("a", 4, 1500), NOW)
        self.app.save(s)
        for page in (self.app.channels_page(now=NOW), self.app.guide_page(now=NOW), self.app.clips_page()):
            self.assertEqual(page["type"], "list")
            self.assertLessEqual(len(json.dumps(page)), 2 * 1024 * 1024)
            for it in page["items"]:
                self.assertLessEqual(len(it["title"]), 120)
                self.assertLessEqual(len(it.get("detail", "")), 200)
                if "choice" in it:
                    self.assertLessEqual(len(it["choice"]["options"]), 12)
                    self.assertTrue(all(len(o[1]) <= 40 for o in it["choice"]["options"]), it["choice"])
        g = self.app.guide_page(now=NOW)
        self.assertTrue(g["readonly"])
        self.assertEqual(g["columns"][0]["key"], "time")
        card = self.app.card(now=NOW)
        self.assertEqual(card["items"][0]["number"], "1")
        self.assertIn("next", card["items"][0])


class Manifest(unittest.TestCase):
    def test_passes_starboards_check_and_asks_for_little(self):
        m = manifest("tv-station")
        self.assertLessEqual(len(m["description"]), 200)
        for c in m.get("changes") or []:
            for kind in ("added", "changed", "fixed"):
                for line in c.get(kind) or []:
                    self.assertLessEqual(len(line), 300)
        self.assertEqual(set(m["permissions"]), {"jellyfin:key", "network:lan", "network:port"})
        self.assertEqual([v for c in m["containers"] for v in c.get("volumes") or []], ["data"])
        if os.path.isdir(os.path.join(STARBOARD_SRC, "starboard")):
            sys.path.insert(0, STARBOARD_SRC)
            from starboard import plugins
            problems = [p for p in plugins.check(m) if "digest" not in p]
            self.assertEqual(problems, [])

    def test_words(self):
        banned = re.compile(r"\b(click|enable|disable|activate|deactivate|toggle|above|below|please|just|simply|easy|advanced|see|look)\b", re.I)
        texts = json.dumps(manifest("tv-station"))
        for name in ("README.md",):
            texts += open(os.path.join(TV, name), encoding="utf-8").read()
        self.assertEqual(banned.findall(texts), [])
        self.assertNotIn("—", texts)


if __name__ == "__main__":
    unittest.main()
