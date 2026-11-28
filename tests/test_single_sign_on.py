"""Single sign-on 0.1.0 (DASH-589, stage 1): the switch and the Tailscale name. The name is checked in words, the first valid
one is kept because passkeys are tied to it, a later change is said and needs a choice, and nothing is asked of any network."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import load, manifest, starboard_cleaners  # noqa: E402

NAME = "starboard.tail1234.ts.net"


def app(**values):
    return load("single-sign-on", values)


class Name(unittest.TestCase):
    def test_a_tailscale_name_is_accepted_in_any_of_the_ways_it_is_written(self):
        a = app()
        for raw in (NAME, "https://" + NAME, "https://" + NAME + "/", "  Starboard.Tail1234.TS.net. ", "http://" + NAME):
            self.assertEqual(a.check_name(raw), (NAME, ""), raw)
        self.assertEqual(a.check_name("media-server.example-fox.ts.net")[0], "media-server.example-fox.ts.net")

    def test_what_is_not_a_name_is_said_in_words(self):
        a = app()
        for raw, words in (("", "Enter the Tailscale name"), ("100.101.102.103", "an address, not a name"), ("fd7a:115c:a1e0::1", "an address, not a name"),
                           (NAME + ":8443", "no port"), (NAME + "/settings", "no port, path"), ("starboard", ".ts.net"),
                           ("starboard.example.com", ".ts.net"), ("tail1234.ts.net", "not a full Tailscale name"), ("a b.tail1234.ts.net", "no port, path or spaces"),
                           ("-bad.tail1234.ts.net", "not a full Tailscale name"), ("user@" + NAME, "no port, path")):
            name, problem = a.check_name(raw)
            self.assertEqual(name, "", raw)
            self.assertIn(words, problem, raw)


class States(unittest.TestCase):
    def test_off_is_the_default_and_says_nothing_runs(self):
        c = app().card()
        self.assertEqual((c["status"], c["status_label"]), ("inactive", "Off"))
        self.assertIn("Nothing runs", c["text"])

    def test_on_without_a_name_needs_one(self):
        c = app(enabled=True).card()
        self.assertEqual((c["status"], c["status_label"]), ("needs_setup", "Needs a name"))

    def test_on_with_a_bad_name_says_what_is_wrong(self):
        c = app(enabled=True, tailscale_name="100.1.2.3").card()
        self.assertEqual(c["status"], "needs_setup")
        self.assertIn("an address, not a name", c["text"])

    def test_a_good_name_is_waiting_for_the_provider_and_says_passkeys_are_tied_to_it(self):
        a = app(enabled=True, tailscale_name="https://" + NAME)
        c = a.card()
        self.assertEqual((c["status"], c["status_label"]), ("waiting", "Waiting for provider"))
        self.assertIn("https://" + NAME, c["text"])
        self.assertIn("Passkeys will be tied to this address", c["text"])
        self.assertEqual(json.load(open(os.path.join(a._data, "address.json")))["name"], NAME)

    def test_the_first_valid_name_is_kept_and_a_later_one_is_said_not_used(self):
        a = app(enabled=True, tailscale_name=NAME)
        a.card()
        a._set(tailscale_name="other.tail1234.ts.net")
        c = a.card()
        self.assertEqual((c["status"], c["status_label"]), ("warning", "Name changed"))
        self.assertIn(NAME, c["text"])
        self.assertIn("other.tail1234.ts.net", c["text"])
        self.assertIn("Passkeys made at one address do not work at another", c["text"])
        self.assertEqual(json.load(open(os.path.join(a._data, "address.json")))["name"], NAME)  # not overwritten

    def test_switching_off_does_not_forget_the_name(self):
        a = app(enabled=True, tailscale_name=NAME)
        a.card()
        a._set(enabled=False)
        self.assertEqual(a.card()["status"], "inactive")
        self.assertEqual(a.kept()["name"], NAME)
        a._set(enabled=True, tailscale_name="")
        self.assertEqual(a.state()["kept"], NAME)

    def test_use_the_new_address_changes_what_is_kept_only_when_it_differs(self):
        a = app(enabled=True, tailscale_name=NAME)
        a.card()
        self.assertIn("nothing to change", a.use_new_address()["said"])
        a._set(tailscale_name="other.tail1234.ts.net")
        self.assertIn("Passkeys made at " + NAME + " do not work", a.use_new_address()["said"])
        self.assertEqual(a.card()["status"], "waiting")
        self.assertEqual(a.kept()["name"], "other.tail1234.ts.net")

    def test_a_bad_name_never_replaces_the_kept_one(self):
        a = app(enabled=True, tailscale_name=NAME)
        a.card()
        a._set(tailscale_name="nonsense")
        a.card()
        self.assertEqual(a.kept()["name"], NAME)

    def test_off_and_unset_write_nothing(self):
        a = app()
        a.card(), a.check()
        self.assertEqual(os.listdir(a._data), [])
        b = app(enabled=True)
        b.card()
        self.assertEqual(os.listdir(b._data), [])

    def test_check_says_where_it_stands(self):
        self.assertIn("is off", app().check()["said"])
        self.assertIn("will be the provider's address", app(enabled=True, tailscale_name=NAME).check()["said"])

    def test_it_makes_no_network_call(self):
        import socket
        a = app(enabled=True, tailscale_name=NAME)
        real = socket.socket.connect

        def refuse(*args, **kw):
            raise AssertionError("it tried to connect")
        socket.socket.connect = refuse
        try:
            a.card(), a.check(), a.use_new_address()
        finally:
            socket.socket.connect = real


class Manifest(unittest.TestCase):
    def test_it_is_off_light_and_runs_only_when_asked(self):
        m = manifest("single-sign-on")
        self.assertEqual(m["version"], "0.1.0")
        self.assertEqual(m["permissions"], [])
        self.assertEqual(m["containers"][0]["start"], "when_needed")
        self.assertNotIn("jobs", m)
        self.assertNotIn("events", m)
        self.assertLessEqual(m["resources"]["main"]["memory"], 48)
        self.assertEqual((m["switch"], m["starboard_api"]), ("enabled", ">=1.21 <2.0"))  # Starboard asks before it turns off what needs it
        switch = next(s for s in m["settings"] if s["key"] == "enabled")
        self.assertEqual((switch["type"], switch["default"]), ("switch", False))

    def test_the_setting_says_passkeys_are_tied_to_the_address_for_ever(self):
        m = manifest("single-sign-on")
        name = next(s for s in m["settings"] if s["key"] == "tailscale_name")
        self.assertIn("Passkeys are tied to this address for ever", name["hint"])
        self.assertIn("Set it once", name["hint"])
        action = next(a for a in m["actions"] if a["id"] == "use-new-address")
        self.assertIn("Passkeys made at the old name will not work", action["confirm"])

    def test_starboard_accepts_the_cards_and_every_card_state(self):
        got = starboard_cleaners()
        if not got:
            self.skipTest("Starboard's source is not on this computer")
        cards, _ = got
        for c in manifest("single-sign-on")["cards"]:
            self.assertTrue(cards.clean(c["type"], c["example"]), c["id"])
        for values in ({}, {"enabled": True}, {"enabled": True, "tailscale_name": "10.0.0.1"}, {"enabled": True, "tailscale_name": NAME}):
            self.assertTrue(cards.clean("status", app(**values).card()), values)
        a = app(enabled=True, tailscale_name=NAME)
        a.card()
        a._set(tailscale_name="other.tail1234.ts.net")
        self.assertTrue(cards.clean("status", a.card()))


if __name__ == "__main__":
    unittest.main()
