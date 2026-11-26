"""UPS and power (DASH-517): NUT read over its real text protocol from a made-up server, PeaNUT's answer as recorded samples
(flat and nested), the mains-loss and low-battery alerts raised once and cleared, the password never kept, and the manifest
Starboard checks. No real UPS, NUT or PeaNUT was available: the samples follow NUT's protocol and PeaNUT's README."""
import json
import os
import socket
import sys
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import load, manifest, starboard_cleaners  # noqa: E402

NOW = 1_795_000_000
ONLINE = {"ups.status": "OL CHRG", "battery.charge": "100", "battery.runtime": "2520", "ups.load": "23", "input.voltage": "230.4",
          "output.voltage": "230.0", "ups.realpower": "61", "device.mfr": "APC", "device.model": 'Back-UPS "ES" 700'}
ON_BATTERY = {**ONLINE, "ups.status": "OB DISCHRG", "battery.charge": "87", "battery.runtime": "1860"}


class FakeNut:
    """upsd's text protocol: LIST UPS, LIST VAR <ups>, LOGOUT, and an ERR for anything else."""

    def __init__(self, variables, names=("ups",), slow=False, flood=False):
        self.variables, self.names, self.slow, self.flood, self.seen = variables, names, slow, flood, []
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(5)
        self.port = self.sock.getsockname()[1]
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        while True:
            try:
                c, _ = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=self.talk, args=(c,), daemon=True).start()

    def talk(self, c):
        f = c.makefile("rwb")
        try:
            for raw in f:
                cmd = raw.decode().strip()
                self.seen.append(cmd)
                if self.slow:
                    time.sleep(30)
                if cmd == "LIST UPS":
                    out = ["BEGIN LIST UPS"] + [f'UPS {n} "A made-up UPS"' for n in self.names] + ["END LIST UPS"]
                elif cmd.startswith("LIST VAR "):
                    n = cmd[9:]
                    if n not in self.names:
                        out = ["ERR UNKNOWN-UPS"]
                    elif self.flood:
                        out = [f"BEGIN LIST VAR {n}"] + [f'VAR {n} x{i} "1"' for i in range(100000)]
                    else:
                        out = [f"BEGIN LIST VAR {n}"] + [f'VAR {n} {k} "{v.replace(chr(34), chr(92) + chr(34))}"' for k, v in self.variables.items()] + [f"END LIST VAR {n}"]
                elif cmd == "LOGOUT":
                    out = ["OK Goodbye"]
                else:
                    out = ["ERR UNKNOWN-COMMAND"]
                f.write(("\n".join(out) + "\n").encode())
                f.flush()
        except OSError:
            pass
        finally:
            c.close()

    def stop(self):
        self.sock.close()


def app(**values):
    a = load("ups-power", {"tool": "nut", "host": "127.0.0.1", "alerts": True, **values})
    a.sent = []
    a.send_alert = lambda key, state, title, message, level="problem": a.sent.append((key, state, title, level)) or True
    a.STATE["failures"] = 0
    return a


class Nut(unittest.TestCase):
    def test_the_protocol_is_read_and_a_quoted_value_unescaped(self):
        n = FakeNut(ONLINE)
        try:
            a = app(host=f"127.0.0.1:{n.port}")
            name, v = a.read_ups()
            self.assertEqual((name, v["battery.charge"], v["device.model"]), ("ups", "100", 'Back-UPS "ES" 700'))
            self.assertEqual(n.seen, ["LIST UPS", "LIST VAR ups", "LOGOUT"])
        finally:
            n.stop()

    def test_a_named_ups_is_asked_for_and_a_missing_one_is_said(self):
        n = FakeNut(ONLINE, names=("rack", "desk"))
        try:
            a = app(host=f"127.0.0.1:{n.port}", ups="desk")
            self.assertEqual(a.read_ups()[0], "desk")
            a._set(ups="nope")
            with self.assertRaises(ValueError) as e:
                a.read_ups()
            self.assertIn("no UPS called nope", str(e.exception))
        finally:
            n.stop()

    def test_too_much_and_too_slow_are_stopped(self):
        a = app()
        n = FakeNut(ONLINE, flood=True)
        try:
            with self.assertRaises(ValueError):
                a.read_nut("127.0.0.1", n.port)
        finally:
            n.stop()
        n = FakeNut(ONLINE, slow=True)
        try:
            began = time.monotonic()
            with self.assertRaises(OSError):
                a.read_nut("127.0.0.1", n.port, timeout=1)
            self.assertLess(time.monotonic() - began, 5)
        finally:
            n.stop()

    def test_host_and_port(self):
        a = app()
        self.assertEqual(a.host_port("192.0.2.5"), ("192.0.2.5", 3493))
        self.assertEqual(a.host_port("nas.home:3500"), ("nas.home", 3500))
        self.assertEqual(a.host_port("[::1]:3494"), ("::1", 3494))
        self.assertEqual(a.host_port("[::1]"), ("::1", 3493))


class PeaNut(unittest.TestCase):
    def serve(self, body, status=200):
        seen = []

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                seen.append((self.path, self.headers.get("Authorization")))
                raw = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
        s = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=s.serve_forever, daemon=True).start()
        self.addCleanup(s.shutdown)
        self.addCleanup(s.server_close)
        return f"http://127.0.0.1:{s.server_address[1]}", seen

    def test_flat_and_nested_answers_are_both_read(self):
        a = app(tool="peanut")
        for body in (ONLINE, {"rack": ONLINE}, {"battery": {"charge": 100, "runtime": 2520}, "ups": {"status": "OL CHRG", "load": 23}}, [ONLINE]):
            url, seen = self.serve(body)
            name, v = a.read_peanut(url)
            self.assertEqual(seen[0][0], "/api/v1/devices?meta=true")
            u = a.summarise(name, v)
            self.assertEqual((u["charge"], u["flags"]), (100.0, ["OL", "CHRG"]))

    def test_a_named_ups_and_basic_sign_in(self):
        a = app(tool="peanut")
        url, seen = self.serve(ONLINE)
        a.read_peanut(url, "rack one", "sam", "s3cret-pass")
        self.assertEqual(seen[0][0], "/api/v1/devices/rack%20one")
        self.assertTrue(seen[0][1].startswith("Basic "))

    def test_a_refusal_is_said_in_words(self):
        a = app(tool="peanut", peanut_address="http://127.0.0.1:1", password="s3cret-pass")
        url, _ = self.serve({"error": "no"}, status=401)
        a._set(peanut_address=url)
        out = a.check()
        self.assertIn("refused the user name or password", out["said"])
        self.assertNotIn("s3cret-pass", json.dumps(a.card()))


class Words(unittest.TestCase):
    def test_what_each_status_means(self):
        a = app()
        u = a.summarise("ups", ONLINE)
        self.assertEqual((u["on_battery"], u["low"], u["load"], u["runtime"], u["watts"]), (False, False, 23.0, 2520.0, 61.0))
        self.assertEqual(u["model"], 'APC Back-UPS "ES" 700')
        b = a.summarise("ups", {**ON_BATTERY, "ups.status": "OB LB RB"})
        self.assertEqual((b["on_battery"], b["low"], b["replace"]), (True, True, True))
        self.assertFalse(a.summarise("ups", {})["known"])
        self.assertEqual(a.minutes_words(2520), "42 minutes")
        self.assertEqual(a.minutes_words(30), "under a minute")
        self.assertEqual(a.minutes_words(7200), "2 hours")
        self.assertEqual(a.minutes_words(5400 + 600), "1 h 40 min")


class Alerts(unittest.TestCase):
    def test_mains_loss_is_raised_once_and_cleared(self):
        a = app()
        n = FakeNut(ON_BATTERY)
        try:
            a._set(host=f"127.0.0.1:{n.port}")
            a.check(NOW)
            a.check(NOW + 60)
            self.assertEqual([(k, s) for k, s, t, l in a.sent], [("mains", "raised")])
            self.assertIn("Mains power lost", a.sent[0][2])
            n.variables = ONLINE
            a.check(NOW + 120)
            self.assertEqual([(k, s) for k, s, t, l in a.sent], [("mains", "raised"), ("mains", "cleared")])
            self.assertEqual(a.remember("raised"), {})
            self.assertEqual([e["what"] for e in a.remember("state")["events"]], ["Mains power came back"])
        finally:
            n.stop()

    def test_low_battery_by_percent_or_by_minutes_or_by_the_ups(self):
        a = app(low_percent=30, low_minutes=5)
        self.assertEqual(sorted(a.problems(a.summarise("u", {**ON_BATTERY, "battery.charge": "25"}))), ["low", "mains"])
        self.assertEqual(sorted(a.problems(a.summarise("u", {**ON_BATTERY, "battery.runtime": "200"}))), ["low", "mains"])
        self.assertEqual(sorted(a.problems(a.summarise("u", {**ON_BATTERY, "ups.status": "OB LB"}))), ["low", "mains"])
        self.assertEqual(sorted(a.problems(a.summarise("u", ON_BATTERY))), ["mains"])
        self.assertEqual(a.problems(a.summarise("u", {**ONLINE, "battery.charge": "10"})), {})  # low on mains is not an emergency
        self.assertEqual(sorted(a.problems(a.summarise("u", {**ONLINE, "ups.status": "OL RB"}))), ["replace"])

    def test_alerts_can_be_switched_off(self):
        a = app(alerts=False)
        a.alert(a.problems(a.summarise("u", ON_BATTERY)), NOW)
        self.assertEqual(a.sent, [])

    def test_an_unreachable_ups_is_said_after_three_misses_not_one(self):
        a = app(host="127.0.0.1:1")
        a.check(NOW)
        a.check(NOW + 60)
        self.assertEqual(a.sent, [])
        a.check(NOW + 120)
        self.assertEqual([(k, s, l) for k, s, t, l in a.sent], [("unreachable", "raised", "warning")])
        self.assertIn("nothing is listening", a.card()["text"])

    def test_a_starboard_without_alerts_is_said_once_an_hour(self):
        a = load("ups-power", {"host": "x"})
        calls = []
        a._post_starboard = lambda path, body: calls.append(path) or 404
        self.assertFalse(a.send_alert("k", "raised", "t", "m"))
        self.assertFalse(a.send_alert("k", "raised", "t", "m"))
        self.assertEqual(len(calls), 1)


class Cards(unittest.TestCase):
    def test_a_check_is_kept_and_the_cards_read_it(self):
        a = app()
        n = FakeNut(ONLINE)
        try:
            a._set(host=f"127.0.0.1:{n.port}")
            self.assertIn("ups: on mains power, battery 100%", a.check()["said"])
            c = a.card()
            self.assertEqual((c["status"], c["status_label"]), ("ok", "On mains power"))
            self.assertIn("about 42 minutes left", c["text"])
            self.assertIn("load 23%", c["text"])
            d = {i["title"]: i["detail"] for i in a.details()["items"]}
            self.assertEqual((d["Battery"], d["Load"], d["Time left on battery"], d["Power in"]), ("100%", "23%", "42 minutes", "230 V"))
            self.assertEqual(a.history()["series"][0]["title"], "Load")
        finally:
            n.stop()

    def test_on_battery_is_a_problem_in_words(self):
        a = app()
        a.keep("state", {"ups": a.summarise("ups", ON_BATTERY), "checked": time.time(), "history": [], "events": []})
        c = a.card()
        self.assertEqual((c["status"], c["status_label"]), ("problem", "On battery"))
        self.assertIn("87%", c["text"])

    def test_history_is_one_point_every_five_minutes_and_kept_short(self):
        a = app()
        n = FakeNut(ONLINE)
        try:
            a._set(host=f"127.0.0.1:{n.port}")
            for i in range(600):
                a.check(NOW + i * 60)
            h = a.remember("state")["history"]
            self.assertEqual(len(h), a.HISTORY)
            self.assertEqual(h[1]["at"] - h[0]["at"], 300)
        finally:
            n.stop()

    def test_before_setup_the_card_says_what_to_do(self):
        self.assertEqual(load("ups-power", {})._needs()["status"], "needs_setup")
        self.assertEqual(load("ups-power", {"tool": "peanut", "host": "x"})._needs()["status"], "needs_setup")

    def test_an_old_reading_is_not_shown_as_fine(self):
        a = app()
        a.keep("state", {"ups": a.summarise("ups", ONLINE), "checked": time.time() - 3 * 3600, "history": [], "events": []})
        self.assertEqual(a.card()["status"], "warning")

    def test_the_password_is_never_kept_or_shown(self):
        a = app(tool="peanut", peanut_address="http://x", user="sam", password="s3cret-pass")

        def boom():
            raise ValueError("bad s3cret-pass for sam")
        a.read_ups = boom
        a.check(NOW)
        for name in os.listdir(a._data):
            self.assertNotIn("s3cret-pass", open(os.path.join(a._data, name)).read())
        self.assertEqual(a.clean("x s3cret-pass y"), "x *** y")


class StarboardChecks(unittest.TestCase):
    """Starboard refuses a card answer in the wrong shape (a sparkline with no series, for one), so every card is checked in
    every state it can be in: not set up, waiting, failing, on mains power and on battery."""

    def test_every_card_in_every_state_passes_starboards_check(self):
        got = starboard_cleaners()
        if not got:
            self.skipTest("Starboard's source is not on this computer")
        cards, _ = got
        states = [load("ups-power", {}), app(host="127.0.0.1:1")]
        waiting = app()
        states.append(waiting)
        failing = app(host="127.0.0.1:1")
        failing.check(NOW)
        states.append(failing)
        for variables in (ONLINE, ON_BATTERY, {"ups.status": "OL"}, {}):
            a = app()
            a.keep("state", {"ups": a.summarise("ups", variables), "checked": time.time(), "history": [{"at": 1, "load": None, "charge": None, "runtime": None, "ob": False}], "events": []})
            states.append(a)
        for a in states:
            for fn, kind in ((a.card, "status"), (a.details, "list"), (a.history, "sparkline")):
                self.assertTrue(cards.clean(kind, dict(fn())), f"{fn.__name__} {kind}")


class Manifest(unittest.TestCase):
    def test_it_asks_once_a_minute_and_is_light(self):
        m = manifest("ups-power")
        self.assertEqual(m["version"], "0.1.1")
        self.assertEqual(m["containers"][0].get("start", "always"), "always")
        self.assertLessEqual(m["resources"]["main"]["memory"], 48)
        self.assertIn("alerts:send", m["permissions"])
        self.assertIn("network:lan", m["permissions"])
        self.assertEqual([s["key"] for s in m["settings"] if s["type"] == "secret"], ["password"])
        self.assertEqual({c["type"] for c in m["cards"]}, {"status", "list", "sparkline"})

    def test_starboard_accepts_the_cards(self):
        got = starboard_cleaners()
        if not got:
            self.skipTest("Starboard's source is not on this computer")
        cards, _ = got
        for c in manifest("ups-power")["cards"]:
            self.assertTrue(cards.clean(c["type"], c["example"]), c["id"])


if __name__ == "__main__":
    unittest.main()
