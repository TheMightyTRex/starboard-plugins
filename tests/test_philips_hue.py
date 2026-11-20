"""Philips Hue: pairing, the three groupings, brightness, colour words, scenes, schedules in words, the playback event
and the cards, against a made-up bridge over HTTPS (tests/hue_mock_bridge.py). Nothing real is touched."""
import datetime as dt
import json
import os
import shutil
import struct
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT, load, starboard_cleaners  # noqa: E402

HERE = os.path.join(ROOT, "philips-hue")
sys.path.insert(0, HERE)
import hue  # noqa: E402
import words  # noqa: E402
from hue_mock_bridge import MockBridge  # noqa: E402

HAS_OPENSSL = bool(shutil.which("openssl"))
TODAY = dt.date(2026, 11, 20)  # a Friday, as the mock bridge's own local time


def manifest():
    with open(os.path.join(HERE, "starboard-plugin.json"), encoding="utf-8") as f:
        return json.load(f)


class Words(unittest.TestCase):
    def targets(self):
        return [{"rtype": "room", "rid": "r1", "name": "Kitchen", "v1": "/groups/1", "kind": "colour",
                 "scenes": [{"rid": "s1", "name": "Relax", "v1": "S01"}]},
                {"rtype": "room", "rid": "r2", "name": "Kitchen spots", "v1": "/groups/2", "kind": "ambiance", "scenes": []},
                {"rtype": "light", "rid": "l1", "name": "Porch", "v1": "/lights/8", "kind": "white"},
                {"rtype": "bridge_home", "rid": "h", "name": "every light", "v1": "/groups/0", "kind": "colour"}]

    def round_trip(self, text, want=None):
        spec = words.parse(text, self.targets(), TODAY)
        self.assertEqual(words.describe(spec), want or text)
        self.assertEqual(words.describe(words.parse(words.describe(spec), self.targets(), TODAY)), want or text)
        return spec

    def test_written_and_read_in_the_same_words(self):
        s = self.round_trip("Every weekday at 07:00, Kitchen to 80%")
        self.assertEqual((s["days"], s["time"], s["do"]), ([0, 1, 2, 3, 4], "07:00", {"on": True, "bri": 80}))
        s = self.round_trip("Every Monday, Wednesday and Friday at sunset, Kitchen to Relax")
        self.assertEqual(s["do"]["scene"]["rid"], "s1")
        self.round_trip("Every day at 22:30, every light off")
        self.round_trip("Every weekend at 09:15, Kitchen spots to soft white at 40%")
        s = self.round_trip("Once on 24 December at 18:00, Porch on", "Once on Thursday 24 December at 18:00, Porch on")
        self.assertEqual(s["once"], "2026-12-24")

    def test_forgiving_input(self):
        s = words.parse("every sat and sun at 7pm, kitchen spots to 30 %", self.targets(), TODAY)
        self.assertEqual(words.describe(s), "Every weekend at 19:00, Kitchen spots to 30%")
        self.assertEqual(words.parse("tomorrow at 6.30, all lights off", self.targets() + [
            {"rtype": "bridge_home", "rid": "h", "name": "all lights", "v1": "/groups/0", "kind": "colour"}], TODAY)["once"], "2026-11-21")
        self.assertEqual(words.parse("Every Tuesdays at 0700, Porch off", self.targets(), TODAY)["days"], [1])

    def test_mistakes_say_what_to_change(self):
        cases = [("Kitchen to 80%", "Write when"), ("Every day at 25:00, Kitchen on", "hours and minutes"),
                 ("Every Funday at 07:00, Kitchen on", "Funday is not a day"), ("Every day at 07:00, Garage on", "Name a room"),
                 ("Every day at 07:00, Kitchen to 120%", "1% to 100%"), ("Once at sunset, Kitchen on", "Sunrise and sunset"),
                 ("Every day at 07:00, Porch to red", "cannot change colour"),
                 ("Every day at 07:00, Kitchen spots to red", "whites only"),
                 ("Every day at 07:00, Kitchen to Party", "no scene called Party")]
        for text, said in cases:
            with self.assertRaises(words.ScheduleError, msg=text) as e:
                words.parse(text, self.targets(), TODAY)
            self.assertIn(said, str(e.exception), text)

    def test_bridge_formats(self):
        self.assertEqual(words.bitmask(range(5)), 124)
        self.assertEqual(words.bitmask([5, 6]), 3)
        self.assertEqual(words.localtime({"days": [0, 1, 2, 3, 4], "time": "07:00"}), "W124/T07:00:00")
        self.assertEqual(words.localtime({"once": "2026-12-24", "time": "18:00"}), "2026-12-24T18:00:00")
        self.assertEqual(words.v1_body({"on": True, "bri": 80}), {"on": True, "bri": 203})
        self.assertEqual(words.v1_body({"on": True, "colour": "warm"}), {"on": True, "ct": 370})
        self.assertEqual(words.v1_body({"on": True, "colour": "daylight"}, (160, 450)), {"on": True, "ct": 160})
        self.assertEqual(words.v1_body({"on": True, "colour": "red"}), {"on": True, "xy": [0.675, 0.322]})
        self.assertEqual(words.v1_body({"scene": {"v1": "S01"}}), {"scene": "S01"})

    def test_next_run(self):
        now = dt.datetime(2026, 11, 20, 18, 5)  # Friday evening
        spec = {"days": [0, 1, 2, 3, 4], "time": "07:00"}
        self.assertEqual(words.when_words(words.next_run(spec, now), now), "Monday 23 November at 07:00")
        self.assertEqual(words.when_words(words.next_run({"days": list(range(7)), "time": "22:30"}, now), now), "today at 22:30")
        self.assertIsNone(words.next_run({"days": [0], "time": "sunset"}, now))
        self.assertIsNone(words.next_run({"once": "2026-11-19", "time": "07:00"}, now))

    def test_colour_in_words(self):
        self.assertEqual(words.colour_of({"color_temperature": {"mirek": 366, "mirek_valid": True}}), "warm")
        self.assertEqual(words.colour_of({"color_temperature": {"mirek": None, "mirek_valid": False}, "color": {"xy": {"x": 0.67, "y": 0.32}}}), "red")
        self.assertEqual(words.colour_of({"color": {"xy": {"x": 0.3127, "y": 0.329}}}), "daylight")
        self.assertEqual(words.light_words({"on": {"on": True}, "dimming": {"brightness": 79.6},
                                            "color_temperature": {"mirek": 370, "mirek_valid": True}}), "On at 80%, warm white")
        self.assertEqual(words.light_words({"on": {"on": False}}), "Off")
        self.assertEqual(words.light_words({"on": {"on": True}}, reachable=False), "Not reachable")
        self.assertEqual(len(words.colour_options("colour")), 12)  # Starboard draws up to 12 options in a row's choice
        self.assertEqual(len(words.brightness_options()), 12)  # Off, 1% and 10% to 100%
        self.assertEqual(words.nearest_brightness(57), "60")
        self.assertEqual(words.nearest_brightness(57, on=False), "0")


class Address(unittest.TestCase):
    def test_addresses(self):
        self.assertEqual(hue.clean_address(" https://192.168.1.20/ "), "192.168.1.20")
        self.assertEqual(hue.clean_address("hue-bridge.local:8443"), "hue-bridge.local:8443")
        for bad in ("", "192.168.1.20:99999", "rm -rf /", "a b"):
            with self.assertRaises(hue.BridgeError, msg=bad):
                hue.clean_address(bad)

    def test_mdns_answer(self):
        def label(name):
            return b"".join(bytes([len(p)]) + p.encode() for p in name.split(".")) + b"\0"
        ptr = label("Hue Bridge - 1A2B3C._hue._tcp.local")
        packet = struct.pack(">HHHHHH", 0, 0x8400, 0, 2, 0, 0)
        packet += label("_hue._tcp.local") + struct.pack(">HHIH", 12, 1, 120, len(ptr)) + ptr
        packet += label("hue-bridge.local") + struct.pack(">HHIH", 1, 1, 120, 4) + bytes([192, 168, 1, 20])
        self.assertEqual(hue.parse_answer(packet), [("Hue Bridge - 1A2B3C", "192.168.1.20")])
        self.assertEqual(hue.parse_answer(b"\x00\x01"), [])


@unittest.skipUnless(HAS_OPENSSL, "openssl makes the made-up bridge's certificate")
class WithBridge(unittest.TestCase):
    paired = True

    def setUp(self):
        self.mock = MockBridge(paired_key="made-up-key" if self.paired else "").start()
        self.app = load("philips-hue", {"only_dark": True})
        self.app.hue.discover = lambda seconds=1.5: []  # no multicast in a test
        self.app._found.update(at=0.0, list=[])
        if self.paired:
            seen = hue.Bridge(self.mock.address)
            seen.config()
            self.app.keep("bridge", {"address": self.mock.address, "key": "made-up-key", "fingerprint": seen.seen,
                                     "name": "Hue Bridge", "paired": "2026-11-20"})
        self.app.forget_cache()
        self.cleaners = starboard_cleaners()

    def tearDown(self):
        self.mock.stop()
        self.app._tmp.cleanup()

    def clean(self, screen):
        """Starboard's own check of a screen, when its source is here: nothing the plug-in sends may be dropped."""
        if self.cleaners:
            out = self.cleaners[1].clean(screen)
            self.assertEqual(len(out["items"]), len(screen["items"]))
            for a, b in zip(out["items"], screen["items"]):
                self.assertEqual(a["actions"], b.get("actions", []), b["id"])
                if b.get("choice"):
                    self.assertEqual(len(a["choice"]["options"]), len(b["choice"]["options"]), b["id"])
            self.assertEqual(len(out.get("menus") or []), len(screen.get("menus") or []))
            self.assertEqual(len(out.get("bulk") or []), len(screen.get("bulk") or []))
        ids = [i["id"] for i in screen["items"]]
        self.assertEqual(len(ids), len(set(ids)))
        return screen

    def light(self, name):
        return self.mock.state.lights[name]


class Pairing(WithBridge):
    paired = False

    def test_pairs_once_the_button_is_pressed(self):
        out = self.app.bridge_post({"action": "add", "value": self.mock.address})
        self.assertIn("Press the round link button", out["said"])
        self.assertEqual(out["notices"][0]["title"], "Press the link button on Hue Bridge")
        self.assertIn("progress", out["notices"][0])
        self.assertEqual(out["items"][0]["state_label"], "Waiting for the button")
        self.assertIsNone(self.app.paired())
        self.mock.state.pressed = True
        out = self.clean(self.app.bridge_screen())
        self.assertEqual(out["notices"][0]["tone"], "success")
        self.assertNotIn("progress", out["notices"][0])
        b = self.app.paired()
        self.assertTrue(b["key"].startswith("made-up-key-"))
        self.assertEqual(len(b["fingerprint"]), 64)
        self.assertEqual(out["items"][0]["state_label"], "Paired")
        self.assertNotIn("add", out)
        # Only the bridge was asked: the pairing request and its public config, nothing else
        self.assertIn(("POST", "/api", {"devicetype": "starboard#philips-hue", "generateclientkey": True}), self.mock.state.calls)
        out = self.app.bridge_post({"action": "dismiss", "id": "paired"})
        self.assertEqual(out["notices"], [])

    def test_waits_then_says_it_was_not_pressed(self):
        self.app.bridge_post({"action": "add", "value": self.mock.address})
        p = self.app.remember("pairing")
        self.app.keep("pairing", {**p, "started": p["started"] - 100})
        out = self.app.bridge_screen()
        self.assertEqual(out["notices"][0]["title"], "The link button was not pressed in time")
        self.assertEqual(out["items"][0]["actions"], ["toggle"])
        out = self.app.bridge_post({"action": "toggle", "id": f"bridge:{self.mock.address}"})
        self.assertIn("progress", out["notices"][0])

    def test_found_bridges_are_offered(self):
        self.app._found.update(at=1e18, list=[{"address": self.mock.address, "name": "Hue Bridge - 1A2B3C"}])
        out = self.clean(self.app.bridge_screen())
        self.assertEqual((out["items"][0]["group"], out["items"][0]["actions"]), ("Found on your network", ["toggle"]))

    def test_not_a_bridge_is_said_in_words(self):
        with self.assertRaises(hue.BridgeError) as e:
            self.app.bridge_post({"action": "add", "value": "127.0.0.1:9"})
        self.assertIn("did not answer", str(e.exception))

    def test_screens_before_pairing_say_so(self):
        for tab in ("rooms", "zones", "types"):
            self.assertEqual(self.app.lights_screen(tab)["notices"][0]["title"], "Pair a bridge first, on Bridge, then reload this page")
        self.assertEqual(self.app.schedules_screen()["notices"][0]["title"], "Pair a bridge first, on Bridge, then reload this page")
        self.assertEqual(self.app.rooms_card()["status"], "needs_setup")
        self.assertIn("No bridge is paired yet", self.app.lights_post("rooms", {"action": "test_all"})["said"])
        self.assertEqual(self.app.lights_card()["status"], "needs_setup")


class Certificate(WithBridge):
    def test_another_certificate_is_refused(self):
        self.app.keep("bridge", {**self.app.paired(), "fingerprint": "0" * 64})
        out = self.app.lights_screen("rooms")
        self.assertIn("different certificate", out["notices"][0]["title"])
        with self.assertRaises(hue.BridgeError):
            self.app.lights_post("rooms", {"action": "bulk", "id": "bulk:home", "value": "off"})


class Lights(WithBridge):
    def test_rooms_tab(self):
        out = self.clean(self.app.lights_screen("rooms"))
        self.assertEqual([m["title"] for m in out["menus"]], ["Bedroom", "Hall", "Kitchen", "Lounge"])
        kitchen = hue_id("room-Kitchen")
        rows = {i["title"]: i for i in out["items"] if i["menu"] == kitchen}
        self.assertEqual(rows["Ceiling"]["detail"], "On at 80%, warm white. Colour")
        self.assertEqual((rows["Ceiling"]["state_label"], rows["Ceiling"]["choice"]["value"]), ("On", "80"))
        self.assertEqual(rows["Ceiling colour"]["state_label"], "Warm white")  # the colour in words, never colour alone
        self.assertEqual(rows["Under cupboard colour"]["detail"], "Now red")
        self.assertEqual(len(rows["Spots colour"]["choice"]["options"]), 5)  # white ambiance: whites only
        self.assertEqual(rows["Every light in Kitchen"]["state_label"], "2 of 3 on")
        self.assertEqual(self.app.bridge_post({"action": "test_all"})["said"], "Hue Bridge answers: 8 lights, 4 rooms and 2 zones")
        hall = {i["title"]: i for i in out["items"] if i["menu"] == hue_id("room-Hall")}
        self.assertEqual((hall["Porch"]["state_label"], hall["Porch"]["actions"]), ("Not reachable", ["toggle"]))
        lounge = {i["title"]: i for i in out["items"] if i["menu"] == hue_id("room-Lounge")}
        self.assertNotIn("choice", lounge["Christmas tree"])  # a plug: on and off only
        self.assertNotIn("Christmas tree colour", lounge)
        self.assertEqual(out["bulk"][0], {"id": "bulk:home", "label": "Every light in the home", "kind": "", "on": 3, "total": 8,
                                          "active": True, "hint": "3 of 8 lights on. Deactivate it and every one goes off"})
        # Only lights can be switched on a row, so Starboard's "2 of 3 active" on the room counts lights
        self.assertTrue(all(i.get("actions", []) in ([], ["toggle"]) for i in out["items"]))
        self.assertTrue(all(i["id"].startswith("light:") for i in out["items"] if i.get("actions")))

    def test_zones_and_types(self):
        zones = self.clean(self.app.lights_screen("zones"))
        self.assertEqual([m["title"] for m in zones["menus"]], ["Downstairs", "Reading corner"])
        types = self.clean(self.app.lights_screen("types"))
        self.assertEqual([m["title"] for m in types["menus"]],
                         ["Bulbs", "Candle bulbs", "Spot lights", "Light strips", "Lamps", "Ceiling lights", "Smart plugs"])

    def test_switch_dim_and_colour(self):
        lid = hue_id("light-Table lamp")
        out = self.app.lights_post("rooms", {"action": "toggle", "id": f"light:{hue_id('room-Lounge')}:{lid}"})
        self.assertEqual(out["said"], "Table lamp is on")
        self.assertTrue(self.light("Table lamp")["on"]["on"])
        out = self.app.lights_post("rooms", {"action": "choose", "id": f"light:{hue_id('room-Lounge')}:{lid}", "value": "30"})
        self.assertEqual((out["said"], self.light("Table lamp")["dimming"]["brightness"]), ("Table lamp is at 30%", 30.0))
        cid = hue_id("light-Floor lamp")
        out = self.app.lights_post("zones", {"action": "choose", "id": f"colour:{hue_id('zone-Downstairs')}:{cid}", "value": "daylight"})
        self.assertEqual(out["said"], "Floor lamp is daylight")
        self.assertEqual(self.light("Floor lamp")["color_temperature"]["mirek"], 154)  # a million over 6500 kelvin
        out = self.app.lights_post("rooms", {"action": "choose", "id": f"light:{hue_id('room-Lounge')}:{lid}", "value": "0"})
        self.assertEqual((out["said"], self.light("Table lamp")["on"]["on"]), ("Table lamp is off", False))
        row = next(i for i in out["items"] if i["id"] == f"light:{hue_id('room-Lounge')}:{lid}")
        self.assertEqual(row["choice"]["value"], "0")  # an unlit light says Off, not the brightness it would come back at
        with self.assertRaises(hue.BridgeError):
            self.app.lights_post("rooms", {"action": "choose", "id": f"light:{hue_id('room-Lounge')}:{lid}", "value": "250"})
        with self.assertRaises(ValueError):
            self.app.lights_post("rooms", {"action": "choose", "id": f"colour:{hue_id('room-Lounge')}:{cid}", "value": "tartan"})

    def test_whole_room_and_home(self):
        kitchen = hue_id("room-Kitchen")
        out = self.app.lights_post("rooms", {"action": "bulk", "id": f"bulk:{kitchen}", "value": "off"})
        self.assertEqual(out["said"], "Every light in Kitchen is off")
        self.assertFalse(any(self.light(n)["on"]["on"] for n in ("Ceiling", "Spots", "Under cupboard")))
        out = self.app.lights_post("rooms", {"action": "choose", "id": f"gbri:{kitchen}", "value": "50"})
        self.assertEqual(out["said"], "Every light in Kitchen is at 50%")
        self.assertTrue(self.light("Under cupboard")["on"]["on"])
        self.app.lights_post("rooms", {"action": "choose", "id": f"gcol:{kitchen}", "value": "warm"})
        rows = {i["title"]: i for i in self.app.lights_screen("rooms")["items"] if i["menu"] == kitchen}
        self.assertEqual(rows["Every colour light in Kitchen"]["state_label"], "Warm white")
        out = self.app.lights_post("rooms", {"action": "bulk", "id": "bulk:home", "value": "off"})
        self.assertEqual(out["said"], "Every light is off")
        self.assertFalse(any(x["on"]["on"] for x in self.mock.state.lights.values()))

    def test_a_type_has_no_group_so_each_light_is_set(self):
        out = self.app.lights_post("types", {"action": "bulk", "id": "bulk:type:Lamps", "value": "on"})
        self.assertEqual(out["said"], "Lamps are on")
        self.assertTrue(self.light("Table lamp")["on"]["on"] and self.light("Floor lamp")["on"]["on"])
        self.app.lights_post("types", {"action": "choose", "id": "gcol:type:Lamps", "value": "blue"})
        self.assertEqual(self.light("Floor lamp")["color"]["xy"], {"x": 0.153, "y": 0.048})
        puts = [c for c in self.mock.state.calls if c[0] == "PUT" and c[1].endswith(hue_id("light-Table lamp"))]
        self.assertNotIn("color", puts[-1][2])  # a white light is left out of a colour change


class Scenes(WithBridge):
    def test_recall_and_turn_off(self):
        out = self.clean(self.app.scenes_screen())
        self.assertEqual([m["title"] for m in out["menus"]], ["Bedroom", "Kitchen", "Lounge", "Downstairs"])
        self.assertEqual([m["group"] for m in out["menus"]], ["Rooms", "Rooms", "Rooms", "Zones"])
        film = hue_id("scene-Lounge-Film night")
        out = self.app.scenes_post({"action": "toggle", "id": f"scene:{film}"})
        self.assertEqual(out["said"], "Film night is on in Lounge")
        row = next(i for i in out["items"] if i["id"] == f"scene:{film}")
        self.assertEqual(row["state_label"], "In use")
        out = self.app.scenes_post({"action": "toggle", "id": f"scene:{film}"})
        self.assertEqual(out["said"], "Lounge is off")
        self.assertFalse(self.light("Floor lamp")["on"]["on"])


class Schedules(WithBridge):
    def test_add_change_turn_off_and_remove(self):
        empty = self.clean(self.app.schedules_screen())
        self.assertIn("No schedules yet", empty["intro"])
        out = self.app.schedules_post({"action": "add", "value": "every weekday at 7:00, kitchen to 80%"})
        self.assertEqual(out["said"], "Added: Every weekday at 07:00, Kitchen to 80%")
        sched = next(iter(self.mock.state.schedules.values()))
        self.assertEqual(sched["localtime"], "W124/T07:00:00")
        self.assertEqual(sched["command"], {"address": "/api/made-up-key/groups/1/action", "method": "PUT", "body": {"on": True, "bri": 203}})
        self.assertLessEqual(len(sched["name"]), 32)
        row = self.clean(out)["items"][0]
        self.assertEqual((row["title"], row["detail"], row["state_label"]),
                         ("Every weekday at 07:00, Kitchen to 80%", "Next Monday 23 November at 07:00", "On"))
        self.assertEqual(row["attach"]["value"], row["title"])  # changed in the same words it is shown in
        out = self.app.schedules_post({"action": "attach", "id": row["id"], "value": "Every weekday at 07:30, Kitchen to 80%"})
        self.assertEqual(out["said"], "Changed: Every weekday at 07:30, Kitchen to 80%")
        self.assertEqual([s["localtime"] for s in self.mock.state.schedules.values()], ["W124/T07:30:00"])
        out = self.app.schedules_post({"action": "toggle", "id": row["id"]})
        self.assertEqual((out["items"][0]["state_label"], out["said"]), ("Off", "Deactivated: Every weekday at 07:30, Kitchen to 80%"))
        self.assertEqual(next(iter(self.mock.state.schedules.values()))["status"], "disabled")
        out = self.app.schedules_post({"action": "remove", "id": row["id"]})
        self.assertEqual((self.mock.state.schedules, out["items"]), ({}, []))

    def test_a_refused_change_keeps_the_old_one(self):
        out = self.app.schedules_post({"action": "add", "value": "Every day at 22:30, every light off"})
        rid = out["items"][0]["id"]
        with self.assertRaises(ValueError) as e:
            self.app.schedules_post({"action": "attach", "id": rid, "value": "Every day at 22:30, Garage off"})
        self.assertIn("Name a room", str(e.exception))
        self.assertEqual(len(self.mock.state.schedules), 1)
        self.assertEqual(self.app.schedules_screen()["items"][0]["title"], "Every day at 22:30, every light off")

    def test_sunset_is_a_rule_on_the_daylight_sensor(self):
        self.app.schedules_post({"action": "add", "value": "Every Monday and Friday at sunset, Lounge to Film night"})
        rule = next(iter(self.mock.state.rules.values()))
        self.assertEqual(rule["conditions"][0], {"address": "/sensors/1/state/daylight", "operator": "eq", "value": "false"})
        self.assertEqual(rule["conditions"][2], {"address": "/config/localtime", "operator": "in", "value": "W68/T00:00:00/T23:59:59"})
        self.assertEqual(rule["actions"], [{"address": "/groups/2/action", "method": "PUT", "body": {"scene": "S04abc"}}])
        row = self.app.schedules_screen()["items"][0]
        self.assertIn("when the bridge works it out", row["detail"])

    def test_one_off_goes_once_run(self):
        self.app.schedules_post({"action": "add", "value": "Tomorrow at 06:30, Porch on"})
        sched = next(iter(self.mock.state.schedules.values()))
        self.assertEqual((sched["localtime"], sched["autodelete"]), ("2026-11-21T06:30:00", True))
        self.assertEqual(sched["command"]["address"], "/api/made-up-key/lights/8/state")
        self.mock.state.schedules.clear()  # the bridge removes it once it has run
        self.assertEqual(self.app.schedules_screen()["items"], [])
        self.assertEqual(self.app.remember("schedules"), [])

    def test_schedules_from_other_apps_are_shown_not_changed(self):
        self.mock.state.schedules["9"] = {"name": "Wake up", "status": "enabled", "localtime": "W127/T06:00:00"}
        row = self.app.schedules_screen()["items"][0]
        self.assertEqual((row["group"], row["actions"]), ("Made in another app", []))


class Playback(WithBridge):
    def test_scene_runs_when_something_plays_after_dark(self):
        film = hue_id("scene-Lounge-Film night")
        out = self.clean(self.app.play_post({"action": "toggle", "id": f"play:{film}"}))
        self.assertEqual(out["said"], "Film night runs when something starts playing")
        event = {"event": "playback.started", "at": "2026-11-20T18:10:00+00:00",
                 "data": {"title": "Dune", "series": None, "type": "Movie", "user": "Sam", "client": "Jellyfin Web"}}
        self.mock.state.daylight = True
        self.assertEqual(self.app.events(event)["said"], "Still daylight")
        self.mock.state.daylight = False
        self.assertEqual(self.app.events(event)["said"], "Ran Film night")
        self.assertIn(("PUT", f"/clip/v2/resource/scene/{film}", {"recall": {"action": "active"}}), self.mock.state.calls)
        self.assertIn("for Dune", self.app.play_screen()["intro"])
        self.app._set(only_apps=["Android TV"])
        self.assertEqual(self.app.events(event)["said"], "Another app")
        self.assertEqual(self.app.events({"event": "item.added", "data": {}}), {"ok": True})
        out = self.app.play_post({"action": "toggle", "id": f"play:{film}"})
        self.assertEqual(out["said"], "No scene runs when something plays")


class Cards(WithBridge):
    def test_cards_and_buttons(self):
        rooms = self.app.rooms_card()
        lights = self.app.lights_card()
        self.assertEqual(rooms["items"][2], {"title": "Kitchen", "detail": "On at 80%, 2 of 3 lights"})
        self.assertEqual(rooms["items"][1], {"title": "Hall", "detail": "Not reachable"})
        self.assertEqual((rooms["status"], rooms["status_label"]), ("ok", "2 rooms on"))
        self.assertEqual(lights["text"], "Lights on in Kitchen and Lounge. Not reachable: Porch")
        if self.cleaners:
            self.cleaners[0].clean("list", rooms)
            self.cleaners[0].clean("status", lights)
        self.assertEqual(self.app.every_light(False)(), {"said": "Every light is off"})
        self.assertEqual(self.app.rooms_card()["status_label"], "All off")
        self.assertEqual(self.app.lights_card()["text"], "Every light is off. Not reachable: Porch")

    def test_a_bridge_that_does_not_answer(self):
        self.mock.stop()
        self.mock = MockBridge().start()  # stop() in tearDown needs one running
        self.app.keep("bridge", {**self.app.paired(), "address": "127.0.0.1:9"})
        self.app.forget_cache()
        self.assertEqual(self.app.rooms_card()["status"], "problem")
        self.assertIn("did not answer", self.app.lights_screen("rooms")["notices"][0]["title"])


class Manifest(unittest.TestCase):
    def test_every_path_is_answered(self):
        m = manifest()
        sys.modules.pop("app_philips_hue", None)
        app = load("philips-hue", {})
        try:
            routes = {(k if isinstance(k, tuple) else ("GET", k)) for k in app.ROUTES}
            for s in m["settings"]:
                if s["type"] == "custom":
                    self.assertIn(("GET", s["choices"]), routes, s["key"])
                    self.assertIn(("POST", s["choices"]), routes, s["key"])
            for c in m["cards"]:
                self.assertIn(("GET", c["path"]), routes, c["id"])
            for a in m["actions"]:
                self.assertIn(("POST", a["path"]), routes, a["id"])
            self.assertIn(("POST", "/events"), routes)
        finally:
            app._tmp.cleanup()

    def test_lightweight_and_local(self):
        m = manifest()
        main = m["containers"][0]
        self.assertEqual((main["start"], main["network"]), ("when_needed", "lan"))
        self.assertLessEqual(m["resources"]["main"]["memory"], 64)
        self.assertNotIn("network:port", m["permissions"])  # Starboard draws every screen: no page of its own
        for name in ("app.py", "hue.py", "words.py"):
            with open(os.path.join(HERE, name), encoding="utf-8") as f:
                src = f.read()
            for cloud in ("meethue.com", "discovery.meethue", "api.meethue"):
                self.assertNotIn(cloud, src, name)  # nothing goes to the Hue cloud

    def test_starboard_accepts_it(self):
        if not os.path.isdir(os.path.join(os.environ.get("STARBOARD_SRC", os.path.expanduser("~/src/starboard")), "starboard")):
            self.skipTest("Starboard's source is not here")
        from starboard import plugins
        self.assertEqual(plugins.check(manifest(), dev=True), [])


def hue_id(name):
    from hue_mock_bridge import rid
    return rid(name)


if __name__ == "__main__":
    unittest.main()
