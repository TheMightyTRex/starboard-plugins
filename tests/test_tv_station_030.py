"""Create your own TV channel 0.3.0 (owner, 19 November 2026): things drawn over the picture animate on and off, with
choices for the station, each channel and the broadcast pack and a preview of each; and each channel remembers what it
has played to someone watching, for From the next episode not watched, without changing Jellyfin.

The FFmpeg tests run only where ffmpeg is installed."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT  # noqa: E402
from test_tv_station_020 import NOW, SID, App, episodes  # noqa: E402

TV = os.path.join(ROOT, "tv-station")
sys.path.insert(0, TV)
import animate  # noqa: E402
import dog  # noqa: E402
import pack  # noqa: E402
import played  # noqa: E402
import stream  # noqa: E402

FFMPEG = bool(shutil.which("ffmpeg"))
NAMES = {"channel": "Comedy", "station": "Home TV"}


def anim(item_moves, speed="normal", **more):
    """Resolved options with these animations: {item: (in, out)}."""
    cfg = {f"dog_{k}": v for k, v in more.items()}
    for item, (a, b) in item_moves.items():
        cfg[f"dog_{animate.key(item, 'in')}"], cfg[f"dog_{animate.key(item, 'out')}"] = a, b
        cfg[f"dog_{animate.key(item, 'speed')}"] = speed
    return dog.resolve(cfg)


def evaluate(expr, t, **v):
    """Works out an FFmpeg expression of the kinds animate.py writes, at time t, in Python."""
    py = expr.replace("^", "**")
    env = {"clip": lambda x, lo, hi: max(lo, min(hi, x)), "pow": pow, "max": max, "trunc": int, "t": t,
           "between": lambda x, a, b: float(a <= x <= b), "lt": lambda a, b: float(a < b), **v}
    return eval(py, {"__builtins__": {}}, env)  # noqa: S307 - the test's own expressions


class Expressions(unittest.TestCase):
    """Each animation's filters, and its timing inside the thing's own time."""

    def test_each_animation_has_its_own_expression(self):
        for move in animate.MOVES:
            f = animate.fit({"in": move, "out": move, "d": 0.6}, 2.0, 10.0)
            if move == "none":
                self.assertIsNone(f, "None: no layer at all")
                continue
            filters = ",".join(animate.layer_filters(f, 200, 60))
            x, y = animate.position(f, "100", "50")
            if move == "fade":
                self.assertIn("fade=t=in:st=2:d=0.6:alpha=1", filters)
                self.assertIn("fade=t=out:st=9.4:d=0.6:alpha=1", filters)
                self.assertEqual((x, y), ("(100)", "(50)"))
            elif move in ("left", "right"):
                self.assertEqual(filters, "")
                self.assertIn("clip((t-2)/0.6,0,1)", x)
                self.assertIn("clip((t-9.4)/0.6,0,1)", x)
                self.assertEqual(y, "(50)")
            elif move == "bottom":
                self.assertIn("H-(50)", y)
                self.assertEqual(x, "(100)")
            elif move == "wipe":
                self.assertIn("pad=3*iw:ih:iw:0:color=black@0", filters)
                self.assertIn("crop=iw/3:ih:x='iw/3*(clip((t-2)/0.6,0,1)+clip((t-9.4)/0.6,0,1))'", filters)
                self.assertIn("-w+w*(", x)
            elif move == "grow":
                self.assertIn("eval=frame", filters)
                self.assertIn("pad=200:60:", filters)

    def test_slides_rest_in_place_and_leave_the_picture(self):
        W, H, w, h = 1280, 720, 200, 60
        for move in ("left", "right", "bottom"):
            f = animate.fit({"in": move, "out": move, "d": 0.6}, 0.0, 8.0)
            x, y = animate.position(f, "W-w-64", "36")
            rest = (evaluate(x, 4.0, W=W, H=H, w=w, h=h), evaluate(y, 4.0, W=W, H=H, w=w, h=h))
            self.assertAlmostEqual(rest[0], W - w - 64)
            self.assertAlmostEqual(rest[1], 36)
            for t in (0.0, 8.0):  # at the start and at the end it is wholly off the picture
                px, py = evaluate(x, t, W=W, H=H, w=w, h=h), evaluate(y, t, W=W, H=H, w=w, h=h)
                self.assertTrue(px + w <= 1e-6 or px >= W - 1e-6 or py >= H - 1e-6, (move, t, px, py))

    def test_wipe_keeps_its_words_still(self):
        f = animate.fit({"in": "wipe", "out": "wipe", "d": 1.0}, 0.0, 6.0)
        x, _ = animate.position(f, "40", "0")
        cx = "iw/3*(" + animate._wipe(f) + ")"
        for t in (0.0, 0.25, 0.5, 1.0, 3.0, 5.5, 6.0):
            window_x = evaluate(x, t, W=1280, H=720, w=200, h=60)
            crop_x = evaluate(cx, t, iw=600)
            self.assertAlmostEqual(window_x + (200 - crop_x), 40, msg=t)  # where the layer's own left edge lands

    def test_timing_never_runs_past_the_end(self):
        for t0, t1 in ((0.0, 8.0), (3.0, 3.5), (0.0, 0.7), (-2.0, 5.0), (1720.0, 1749.0)):
            for move in ("fade", "left", "wipe", "grow"):
                f = animate.fit({"in": move, "out": move, "d": 1.0}, t0, t1)
                if not f:
                    continue
                self.assertLessEqual(f["t1"], t1)
                self.assertGreaterEqual(f["t0"] + f["din"], t0)
                self.assertLessEqual(f["din"] + f["dout"], t1 - t0 + 1e-9, "both fit inside the thing")
                self.assertIn(animate._n(t1), animate.enable(f))
                self.assertEqual(evaluate(animate.enable(f), t1 + 0.04), 0.0, "not a frame past its end")
                if move == "fade":
                    st = float(re.search(r"t=out:st=([\d.]+):d=([\d.]+)", ",".join(animate.layer_filters(f, 10, 10))).group(1))
                    self.assertAlmostEqual(st + f["dout"], t1)

    def test_a_join_part_way_through_skips_the_way_on(self):
        f = animate.fit({"in": "left", "out": "fade", "d": 0.6}, -3.0, 5.0)
        self.assertEqual((f["in"], f["out"]), ("none", "fade"))
        self.assertIsNone(animate.fit({"in": "left", "out": "none", "d": 0.6}, -3.0, 5.0))
        self.assertIsNone(animate.fit({"in": "fade", "out": "fade", "d": 0.6}, -9.0, -1.0), "over before the piece")

    def test_none_is_as_before(self):
        o = dog.resolve({"dog_kind": "channel_name", "dog_clock": True, "dog_label": "new_repeat"})
        layers = []
        with tempfile.TemporaryDirectory() as d:
            prog = {"duration": 1800, "label": "New", "start_words": "Show A", "next_words": "Up next at 21:00: B"}
            a = dog.overlay_chain(o, 1280, 720, "programme", dog.Texts(d), NAMES, rel=0, programme=prog, layers=layers)
            b = dog.overlay_chain(o, 1280, 720, "programme", dog.Texts(d + "/b"), NAMES, rel=0, programme=prog)
        self.assertEqual(layers, [])
        self.assertEqual(len(a[0]), len(b[0]))
        self.assertIn("enable='between(t,1770.00,1799.00)'", a[0][-1])

    def test_straps_label_and_logo_become_layers_with_their_windows(self):
        o = anim({"straps": ("left", "fade"), "label": ("fade", "fade"), "logo": ("grow", "grow"), "clock": ("fade", "fade")},
                 kind="channel_name", clock=True, label="new_repeat", when="programmes")
        layers = []
        with tempfile.TemporaryDirectory() as d:
            prog = {"duration": 1800, "label": "New", "start_words": "Show A", "next_words": "Up next at 21:00: B"}
            chain, _ = dog.overlay_chain(o, 1280, 720, "programme", dog.Texts(d), NAMES, rel=0, programme=prog, layers=layers)
        self.assertEqual(chain, [], "everything is on a layer")
        windows = [(ly["f"]["t0"], ly["f"]["t1"]) for ly in layers]
        self.assertEqual(windows, [(0, 1800), (0, 1800), (0, 120), (0, 8), (1770, 1799)], "logo, clock, label, the two straps")

    def test_the_logo_animates_only_when_it_comes_and_goes(self):
        prog = {"duration": 1800, "label": "", "start_words": "", "next_words": ""}
        with tempfile.TemporaryDirectory() as d:
            logo = os.path.join(d, "l.png")
            with open(logo, "wb") as f:  # a PNG header is all the size needs
                f.write(b"\x89PNG\r\n\x1a\n" + b"\0\0\0\rIHDR" + (512).to_bytes(4, "big") + (256).to_bytes(4, "big"))
            for when, fade_in, want in (("always", 0, None), ("programmes", 0, ("fade", "fade")), ("always", 30, ("fade", "none"))):
                layers = []
                o = anim({"logo": ("fade", "fade")}, when=when, fade_in=fade_in, strap_start=False, strap_end=False)
                _, lf = dog.overlay_chain(o, 1280, 720, "programme", dog.Texts(d), NAMES, logo=logo, rel=0, programme=prog, layers=layers)
                got = next((ly["f"] for ly in layers if ly.get("logo")), None)
                self.assertEqual((got["in"], got["out"]) if got else None, want, when)
                if want:
                    self.assertIn("scale=82:41", lf, "the logo's own size, so Grow can scale it")
                    if fade_in:
                        self.assertIn("fade=t=in:st=30", lf)


class Settings(unittest.TestCase):
    """A broadcast pack chooses only what the settings leave to it."""

    def test_channel_then_station_then_pack(self):
        p = {"animation": {"cards": {"in": "wipe", "out": "fade", "speed": "slow"}}}
        o = dog.resolve({"dog_anim_cards_in": "pack"}, None, p)
        self.assertEqual((o["anim_cards_in"], o["anim_cards_out"], o["anim_cards_speed"]), ("wipe", "fade", "slow"))
        o = dog.resolve({"dog_anim_cards_in": "left"}, None, p)
        self.assertEqual(o["anim_cards_in"], "left", "a station choice comes before the pack")
        o = dog.resolve({"dog_anim_cards_in": "left"}, {"dog": {"anim_cards_in": "grow"}}, p)
        self.assertEqual(o["anim_cards_in"], "grow", "a channel's own comes first")
        o = dog.resolve({}, None, None)
        self.assertEqual((o["anim_logo_in"], o["anim_logo_speed"]), ("none", "normal"))
        self.assertEqual(dog.still(dog.resolve({"dog_anim_cards_in": "left"}))["anim_cards_in"], "none")

    def test_pack_json_animation_is_checked(self):
        doc = pack.template_pack_json("T")
        self.assertEqual(pack.validate(doc), [])
        doc["animation"] = {"cards": {"in": "spin"}}
        self.assertTrue(any("should be one of" in p for p in pack.validate(doc)))
        doc["animation"] = {"sparkles": {"in": "fade"}}
        self.assertTrue(any("not something a pack may set" in p for p in pack.validate(doc)))
        with open(os.path.join(TV, "pack.schema.json"), encoding="utf-8") as f:
            schema = json.load(f)
        self.assertEqual(set(schema["properties"]["animation"]["properties"]), set(animate.ITEMS))
        self.assertEqual(schema["$defs"]["animation"]["properties"]["in"]["enum"], list(animate.MOVES))
        self.assertIn("animation", pack.README)


class Pages(App):
    def test_the_animation_page_and_a_channels_card(self):
        page = self.app.animation_page()
        ids = [it["id"] for it in page["items"]]
        self.assertEqual(len(ids), len(animate.ITEMS) * 3)
        first = page["items"][0]
        self.assertEqual(first["choice"]["value"], "pack")
        self.assertIn("/animation/station/cards.mp4", first["link"]["url"])
        got = self.app.animation_post({"action": "choose", "id": "station:anim-cards-in", "value": "left"})
        self.assertIn("Slide in from the left", got["said"])
        self.assertEqual(self.app.state()["anim"]["anim_cards_in"], "left")
        cid = self.channel(lineup=episodes("a", 3, 1500))
        page = self.app.channels_page(now=NOW)
        row = next(it for it in page["items"] if it["id"] == f"{cid}:anim-cards-in")
        self.assertEqual(row["choice"]["options"][0], ["", "Station default (Slide in from the left)"])
        got = self.app.channels_post({"action": "choose", "id": f"{cid}:anim-cards-in", "value": "wipe"}, now=NOW)
        self.assertIn("Wipe on from the left", got["said"])
        ch = self.app.find(self.app.state(), cid)
        self.assertEqual(ch["dog"]["anim_cards_in"], "wipe")
        self.assertEqual(self.app.opts_for(self.app.state(), ch, {})["anim_cards_in"], "wipe")
        self.app.channels_post({"action": "choose", "id": f"{cid}:anim-cards-in", "value": ""}, now=NOW)
        self.assertEqual(self.app.opts_for(self.app.state(), self.app.find(self.app.state(), cid), {})["anim_cards_in"], "left")
        with self.assertRaises(ValueError):
            self.app.channels_post({"action": "choose", "id": f"{cid}:anim-cards-in", "value": "spin"}, now=NOW)

    @unittest.skipUnless(FFMPEG, "ffmpeg is not installed here")
    def test_a_preview_is_a_few_seconds_of_mp4(self):
        cid = self.channel(lineup=episodes("a", 3, 1500))
        self.app.channels_post({"action": "choose", "id": f"{cid}:anim-cards-in", "value": "left"}, now=NOW)
        for item in ("cards", "logo", "straps", "holding"):
            data = self.app.anim_preview(cid if item != "holding" else "station", item)
            self.assertEqual(data[4:8], b"ftyp", item)
        with self.assertRaises(LookupError):
            self.app.anim_preview(cid, "sparkles")


@unittest.skipUnless(FFMPEG, "ffmpeg is not installed here")
class Drawn(unittest.TestCase):
    """The stream itself: an animated strap is on screen only inside its time, and None draws as before."""

    def frames(self, opts, secs, kind="programme", W=320, H=180):
        with tempfile.TemporaryDirectory() as d:
            e = {"id": "x", "title": "Show A", "has_audio": False}
            now = 1000.0
            piece = {"kind": kind, "start": now, "end": now + secs, "airing": {"entry": e, "start": now, "end": now + secs, "content_end": now + secs}}
            out = os.path.join(d, "o.mp4")
            ctx = {"W": W, "H": H, "kbps": 500, "opts": opts, "names": NAMES, "texts": dog.Texts(d), "ts_offset": 0.0, "to_file": out,
                   "stand_in": ["-f", "lavfi", "-t", str(secs + 1), "-i", f"color=c=black:s={W}x{H}:r=25"],
                   "next_words": "Up next at 21:00: Show B", "start_words": "Show A"}
            r = subprocess.run(stream.piece_command(piece, now, ctx), capture_output=True, timeout=60, check=False)
            self.assertEqual(r.returncode, 0, r.stderr[-500:])
            raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", out, "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1"],
                                 capture_output=True, check=True).stdout
        n = W * H
        return [raw[i:i + n] for i in range(0, len(raw), n)]

    def lit(self, frame):
        return sum(1 for b in frame if b > 60)

    def test_the_up_next_strap_is_inside_its_time(self):
        # A programme of 8 seconds with Up next for its last 5: on at 3 seconds, off by 7, with every animation.
        for move in ("fade", "left", "right", "bottom", "wipe", "grow"):
            o = {**anim({"straps": (move, move)}, kind="none", strap_start=False), "strap_seconds": 5}
            fr = self.frames(o, 8.0)
            self.assertEqual(self.lit(fr[int(2.9 * 25)]), 0, f"{move}: not before its start")
            self.assertGreater(self.lit(fr[5 * 25]), 50, f"{move}: on screen in the middle")
            self.assertEqual(self.lit(fr[int(7.04 * 25) + 1]), 0, f"{move}: off by its end, never past it")

    def test_none_draws_as_before(self):
        o = {**dog.resolve({"dog_kind": "none", "dog_strap_start": False}), "strap_seconds": 5}
        fr = self.frames(o, 8.0)
        self.assertEqual(self.lit(fr[int(2.9 * 25)]), 0)
        self.assertGreater(self.lit(fr[int(3.2 * 25)]), 50, "on at once, as before")


class Record(unittest.TestCase):
    """What a channel played to someone watching."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.rec = played.Record(os.path.join(self.tmp.name, "played"))
        self.e = {"id": "e1", "title": "Show A", "kind": "Episode", "group": SID, "s": 1, "e": 1, "ep": "Part 1"}

    def tearDown(self):
        self.tmp.cleanup()

    def test_seen_at_seventy_per_cent(self):
        self.assertEqual(played.SEEN_SHARE, 0.7)
        row = self.rec.note("c1", self.e, NOW, 1000, 690)
        self.assertFalse(row["seen"])
        row = self.rec.note("c1", self.e, NOW, 1000, 10)  # joined again: the same airing adds up
        self.assertTrue(row["seen"])
        self.assertEqual(self.rec.count("c1"), 1)
        self.assertEqual(self.rec.seen_ids("c1"), {"e1"})
        row = self.rec.note("c1", self.e, NOW, 1000, 5000)
        self.assertEqual(row["seconds"], 1000, "never more than the programme")
        self.rec.note("c1", self.e, NOW + 86400, 1000, 100)
        self.assertEqual(self.rec.count("c1"), 2, "another airing is another entry")
        self.assertEqual(self.rec.latest("c1")[0]["at"], int(NOW + 86400), "newest first")

    def test_capped_and_written_in_batches(self):
        most, every = played.MOST, played.WRITE_EVERY
        played.MOST, played.WRITE_EVERY = 10, 3600
        try:
            for i in range(25):
                self.rec.note("c1", {**self.e, "id": f"e{i}"}, NOW + i * 2000, 1000, 800)
            self.assertEqual(self.rec.count("c1"), 10)
            self.assertEqual(self.rec.latest("c1", 1)[0]["id"], "e24")
            with open(self.rec.path("c1"), encoding="utf-8") as f:
                self.assertEqual(len(json.load(f)), 1, "written once, then not again within the hour")
            self.rec.flush("c1", force=True)
            with open(self.rec.path("c1"), encoding="utf-8") as f:
                self.assertEqual(len(json.load(f)), 10)
            fresh = played.Record(self.rec.folder)
            self.assertEqual(fresh.seen_ids("c1"), {f"e{i}" for i in range(15, 25)}, "read back")
            fresh.forget("c1")
            self.assertFalse(os.path.exists(self.rec.path("c1")))
        finally:
            played.MOST, played.WRITE_EVERY = most, every

    def test_streamed_seconds(self):
        piece = {"start": NOW, "end": NOW + 600}
        self.assertEqual(played.streamed(piece, NOW, True, 598.0), 600.0, "played to its end: the first burst counts")
        self.assertEqual(played.streamed(piece, NOW + 300, False, 120.0), 120.0)


class NextNotWatched(App):
    def eps(self):
        return episodes("a", 6, 1500)

    def answer_unplayed(self, ids):
        self.answers["/Users/u1/Items"] = {"Items": [{"Id": i} for i in ids]}
        self.answers["/Users"] = [{"Id": "u1", "Policy": {"IsAdministrator": True}}]

    def test_played_or_seen_counts_as_watched(self):
        eps = self.eps()
        self.answer_unplayed(["a2", "a3", "a4", "a5", "a6"])
        self.assertEqual(self.app.unwatched_index(SID, eps), 1, "Jellyfin: a1 played")
        self.assertEqual(self.app.unwatched_index(SID, eps, {"a2", "a3"}), 3, "and the channel saw a2 and a3")
        self.answers.clear()
        self.assertEqual(self.app.unwatched_index(SID, eps, {"a1"}), 1, "with no Jellyfin answer, the record alone")

    def test_the_channel_setting_and_nothing_sent_to_jellyfin(self):
        cid = self.channel(lineup=self.eps())
        a = {"entry": self.eps()[0], "start": NOW, "content_end": NOW + 1500}
        self.asked.clear()
        self.app.note_played(cid, {"kind": "programme", "airing": a, "start": NOW, "end": NOW + 1500}, 1400)
        self.app.note_played(cid, None, 0)
        self.assertEqual(self.asked, [], "nothing is sent to Jellyfin")
        self.assertEqual(self.app.seen_on(cid), {"a1"})
        page = self.app.channels_page(now=NOW + 1600)
        rows = {it["id"]: it for it in page["items"] if it["group"] == "Played on this channel"}
        self.assertEqual(rows[f"{cid}:played0"]["state_label"], "Watched")
        self.assertIn("23 of 25 minutes", rows[f"{cid}:played0"]["detail"])
        self.assertEqual(rows[f"{cid}:count_played"]["choice"]["value"], "on", "Yes unless changed")
        self.app.channels_post({"action": "choose", "id": f"{cid}:count_played", "value": "off"}, now=NOW)
        self.assertEqual(self.app.seen_on(cid), set(), "No: only Jellyfin's marks count")
        self.app.channels_post({"action": "choose", "id": f"{cid}:count_played", "value": "on"}, now=NOW)
        got = self.app.channels_post({"action": "remove", "id": f"{cid}:forget-played"}, now=NOW)
        self.assertIn("forgotten", got["said"])
        self.assertEqual(self.app.seen_on(cid), set())
        self.assertTrue(all(m in ("GET", None) for m, _, _ in self.asked), "only reads from Jellyfin")


if __name__ == "__main__":
    unittest.main()
