"""Notifications (DASH-401): plain words for every event, each channel's request, secrets never kept or shown, the
weekly message once on its day, per-person request messages and the manifest Starboard checks."""
import datetime as dt
import json
import os
import re
import sys
import time
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import load, manifest, starboard_cleaners  # noqa: E402

SECRET = "123456:AAHsecretTOKENvalue"
EVENTS = {"request.available": {"title": "Dune", "year": "2021", "kind": "Film", "by": "Sam"},
          "download.failed": {"title": "Dune.2021.1080p", "app": "qBittorrent", "reason": "Not enough space."},
          "app.down": {"app": "Jellyfin", "type": "jellyfin"}, "app.up": {"app": "Jellyfin", "type": "jellyfin"},
          "disk.nearly_full": {"disk": "Media", "percent": 93, "free": 152_000_000_000},
          "disk.changed": {"action": "add", "state": "done", "disk": "pool3", "erased": ["pool3"], "result": ""},
          "update.available": {"app": "Starboard", "current": "0.17.0", "latest": "0.18.0"}}


class Words(unittest.TestCase):
    def setUp(self):
        self.app = load("notifications")

    def test_every_event_has_a_title_and_a_sentence_in_plain_text(self):
        for event, data in EVENTS.items():
            title, body, tone = self.app.words(event, data)
            self.assertTrue(title and body.endswith("."), event)
            self.assertIn(tone, ("info", "success", "warning", "failure"))
            self.assertTrue(all(ord(ch) < 0x2000 for ch in title + body), f"{event}: no symbols or emoji carry meaning")
            self.assertNotIn("—", title + body)  # no em dashes
        self.assertEqual(self.app.words("request.available", EVENTS["request.available"])[1],
                         "Dune (2021), which Sam asked for, is ready to watch in Jellyfin.")
        self.assertIn("152.0 GB free", self.app.words("disk.nearly_full", EVENTS["disk.nearly_full"])[1])

    def test_a_disk_change_names_what_was_erased_and_what_to_do(self):
        # 1.2.0 (Starboard issue #187): every pool change is said, a warning when a disk was erased.
        title, body, tone = self.app.words("disk.changed", EVENTS["disk.changed"])
        self.assertEqual(title, "pool3 was added to the pool")
        self.assertIn("Erased: pool3.", body)
        self.assertIn("If you did not start this", body)
        self.assertEqual(tone, "warning")
        title, _, tone = self.app.words("disk.changed", {"action": "balance", "state": "done", "erased": []})
        self.assertEqual((title, tone), ("The pool was balanced", "info"))
        title, _, tone = self.app.words("disk.changed", {"action": "remove", "state": "failed", "disk": "pool1", "erased": []})
        self.assertEqual((title, tone), ("pool1 was taken out of the pool (it stopped with a problem)", "warning"))

    def test_a_link_has_words_before_it(self):
        self.app._set(starboard_address="http://192.0.2.10:8095")
        self.assertTrue(self.app.with_link("Body.").endswith("\n\nOpen Starboard: http://192.0.2.10:8095"))


class Channels(unittest.TestCase):
    def setUp(self):
        self.app = load("notifications", {
            "starboard_address": "http://192.0.2.10:8095", "telegram_token": SECRET, "telegram_chat": ["42"],
            "discord_webhook": "https://discord.example/api/webhooks/1/abc", "signal_api": "http://192.0.2.20:8080",
            "signal_number": "+447700900123", "signal_to": ["+447700900456"], "pushover_user": "u-key", "pushover_token": "p-token",
            "ntfy_url": "https://ntfy.example", "ntfy_topic": "harbour-alerts", "ntfy_token": "tk_ntfy", "webhooks": "http://apprise.local:8000/notify/abc"})
        self.calls = []
        self.app.fetch = lambda url, headers=None, data=None, method=None, timeout=15, raw=False, limit=0: self.calls.append((url, headers, data)) or {}

    def test_each_channel_sends_what_its_service_reads(self):
        for c in ("telegram", "discord", "signal", "pushover", "ntfy", "webhook"):
            self.app.SENDERS[c]("Ready to watch: Dune (2021)", "Dune is ready.", "success")
        by = {re.sub(r"https?://([^/]+).*", r"\1", u): (u, h, d) for u, h, d in self.calls}
        self.assertEqual(by["api.telegram.org"][2]["chat_id"], "42")
        self.assertTrue(by["api.telegram.org"][2]["text"].startswith("Ready to watch: Dune (2021)\n\nDune is ready."))
        self.assertEqual(by["discord.example"][2]["allowed_mentions"], {"parse": []})  # nobody is pinged
        self.assertEqual(by["192.0.2.20:8080"][0], "http://192.0.2.20:8080/v2/send")
        self.assertEqual(by["192.0.2.20:8080"][2]["recipients"], ["+447700900456"])
        self.assertEqual(by["api.pushover.net"][2]["url_title"], "Open Starboard")
        self.assertEqual(by["ntfy.example"][2]["topic"], "harbour-alerts")
        self.assertEqual(by["ntfy.example"][2]["actions"][0]["label"], "Open Starboard")
        self.assertEqual(by["ntfy.example"][1], {"Authorization": "Bearer tk_ntfy"})
        self.assertEqual(by["apprise.local:8000"][2]["type"], "success")
        self.assertEqual(set(by["apprise.local:8000"][2]), {"title", "body", "type", "link"})

    def test_email_uses_starttls_and_signs_in(self):
        self.app._set(smtp_host="smtp.example.com", smtp_port=587, smtp_user="me", smtp_password="pw-secret",
                      email_from="starboard@example.com", email_to=["sam@example.com"])
        sent = {}

        class SMTP:
            def __init__(self, host, port, timeout=None):
                sent["to"] = (host, port)

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def starttls(self, context=None):
                sent["tls"] = True

            def login(self, user, password):
                sent["login"] = user

            def send_message(self, msg):
                sent["msg"] = msg
        with mock.patch.object(self.app.smtplib, "SMTP", SMTP):
            self.app.send_email("Ready to watch: Dune (2021)", "Dune is ready.", "success")
        self.assertEqual(sent["to"], ("smtp.example.com", 587))
        self.assertTrue(sent["tls"])
        self.assertEqual(sent["msg"]["Subject"], "Ready to watch: Dune (2021)")
        self.assertIn("Open Starboard: http://192.0.2.10:8095", sent["msg"].get_content())

    def test_missing_details_are_named(self):
        self.app._set(discord_webhook="")
        with self.assertRaises(ValueError) as e:
            self.app.send_discord("t", "b", "info")
        self.assertIn("discord webhook", str(e.exception))


class Secrets(unittest.TestCase):
    def test_a_failure_never_keeps_or_shows_a_secret(self):
        app = load("notifications", {"telegram_active": True, "telegram_token": SECRET, "telegram_chat": ["42"]})

        def boom(url, **k):
            raise urllib.error.URLError(f"could not open {url}")
        app.fetch = boom
        with mock.patch("builtins.print") as said:
            out = app.on_event({"event": "app.down", "data": EVENTS["app.down"]}, wait=True)
        self.assertEqual(out["sent"], [])
        kept = open(os.path.join(app._data, "log.json")).read()
        shown = json.dumps(app.card()) + json.dumps(app.recent()) + json.dumps(out)
        for text in (kept, shown, str(said.call_args_list)):
            self.assertNotIn(SECRET, text)
            self.assertNotIn("AAHsecret", text)
        self.assertEqual(app.card()["state"], "problem")
        self.assertIn("Telegram", app.card()["text"])

    def test_clean_takes_out_every_secret_setting(self):
        app = load("notifications", {"smtp_password": "hunter22", "webhooks": "https://a.example/x?k=abcd https://b.example/y"})
        self.assertEqual(app.clean("hunter22 at https://a.example/x?k=abcd"), "[hidden] at [hidden]")

    def test_an_http_refusal_is_said_in_words(self):
        app = load("notifications")
        self.assertEqual(app._why(urllib.error.HTTPError("https://x", 401, "Unauthorized", {}, None)), "it refused the sign-in or token")


class Events(unittest.TestCase):
    def setUp(self):
        self.app = load("notifications", {"webhook_active": True, "webhooks": "http://hook.local/x", "email_active": False})
        self.calls = []
        self.app.fetch = lambda url, **k: self.calls.append((url, k.get("data"))) or {}

    def test_an_event_goes_to_the_active_channels_only(self):
        out = self.app.on_event({"event": "download.failed", "data": EVENTS["download.failed"]}, wait=True)
        self.assertEqual(out["sent"], ["Webhooks"])
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.app.card()["state"], "ok")

    def test_a_deactivated_kind_is_not_sent(self):
        self.app._set(send_disk=False)
        self.app.on_event({"event": "disk.nearly_full", "data": EVENTS["disk.nearly_full"]}, wait=True)
        self.assertEqual(self.calls, [])

    def test_the_person_who_asked_hears_too(self):
        self.app._set(people=["Sam, telegram 777", "Alex, alex@example.com"], telegram_token=SECRET)
        out = self.app.on_event({"event": "request.available", "data": EVENTS["request.available"]}, wait=True)
        self.assertIn("Telegram to Sam", out["sent"])
        self.assertTrue(any("api.telegram.org" in u and d["chat_id"] == "777" for u, d in self.calls))

    def test_starboard_is_answered_at_once_and_a_retry_is_sent_once(self):
        body = {"event": "app.down", "at": "2026-11-13T09:30:00+00:00", "data": EVENTS["app.down"]}
        started = time.monotonic()
        self.assertEqual(self.app.on_event(body)["said"], "Sending")
        self.assertLess(time.monotonic() - started, 0.5)
        self.assertEqual(self.app.on_event(body)["said"], "Already had this one")
        for _ in range(50):
            if self.calls:
                break
            time.sleep(0.02)
        time.sleep(0.1)
        self.assertEqual(len(self.calls), 1)

    def test_item_added_is_kept_for_the_weekly_message_only(self):
        self.app.on_event({"event": "item.added", "data": {"title": "Dune", "type": "Movie", "year": 2021}}, wait=True)
        self.assertEqual(self.calls, [])
        self.assertEqual(len(json.load(open(os.path.join(self.app._data, "week.json")))), 1)


class Weekly(unittest.TestCase):
    def setUp(self):
        self.app = load("notifications", {"webhook_active": True, "webhooks": "http://hook.local/x"})
        self.calls = []
        self.app.fetch = lambda url, **k: self.calls.append(k.get("data")) or {}
        self.app.starboard = lambda path: {"items": []}
        for d in ({"title": "Dune", "type": "Movie", "year": 2021}, {"title": "Pilot", "series": "Slow Horses", "type": "Episode"},
                  {"title": "Two", "series": "Slow Horses", "type": "Episode"}):
            self.app.on_event({"event": "item.added", "data": d}, wait=True)

    def test_off_until_switched_on(self):
        self.assertIn("deactivated", self.app.weekly()["said"])
        self.assertEqual(self.calls, [])
        self.assertFalse(next(s for s in manifest("notifications")["settings"] if s["key"] == "send_weekly")["default"])

    def test_sent_once_by_email_with_titles_and_years_only(self):
        self.app._set(send_weekly=True, email_active=True, smtp_host="smtp.example.com", email_from="a@example.com", email_to=["b@example.com"],
                      webhook_active=True)
        mails = []
        self.app.send_email = lambda title, body, tone, to=None: mails.append((title, body))
        self.app.SENDERS["email"] = self.app.send_email
        self.assertIn("sent by Email", self.app.weekly()["said"])
        self.assertIn("Already sent", self.app.weekly()["said"])  # a retry sends nothing more
        self.assertEqual(len(mails), 1)
        self.assertEqual(self.calls, [])  # email only: the webhook was not used
        title, body = mails[0]
        self.assertEqual(title, "New on your server this week")
        self.assertIn("Films (1):\n- Dune (2021)", body)
        self.assertIn("Episodes (2):\n- Slow Horses: Pilot, Two", body)

    def test_every_active_way_when_chosen(self):
        self.app._set(send_weekly=True, weekly_by="all")
        self.assertIn("sent by Webhooks", self.app.weekly()["said"])

    def test_email_only_says_so_when_email_is_off(self):
        self.app._set(send_weekly=True)
        self.assertIn("email is not activated", self.app.weekly()["said"])
        self.assertEqual(self.calls, [])

    def test_films_episodes_albums_and_books(self):
        text = self.app.weekly_words([
            {"title": "Dune", "type": "Movie", "year": 2021}, {"title": "Dune", "type": "Movie", "year": 2021},
            {"title": "Pilot", "series": "Slow Horses", "type": "Episode", "year": 2022},
            {"title": "Blue", "type": "MusicAlbum", "year": 1971}, {"title": "Emma", "type": "Book", "year": 1815},
            {"title": "Dracula", "type": "AudioBook"}, {"title": "A series", "type": "Series"}])
        self.assertEqual(text, "Films (1):\n- Dune (2021)\n\nAlbums (1):\n- Blue (1971)\n\nBooks (2):\n- Dracula\n- Emma (1815)\n\n"
                               "Episodes (1):\n- Slow Horses: Pilot")

    def test_a_long_week_stays_short(self):
        items = [{"title": f"Film {i:03d}", "type": "Movie", "year": 2000} for i in range(55)]
        text = self.app.weekly_words(items)
        self.assertIn("Films (55):", text)
        self.assertIn("- and 15 more", text)
        self.assertEqual(text.count("\n- Film"), 40)

    def test_nothing_new_sends_nothing(self):
        self.app.keep("week", [])
        self.app._set(send_weekly=True, weekly_by="all")
        self.assertIn("Nothing new", self.app.weekly()["said"])
        self.assertEqual(self.calls, [])

    def test_send_now_always_sends(self):
        self.app._set(weekly_by="all")
        self.assertIn("sent by Webhooks", self.app.weekly(force=True)["said"])

    def test_starboard_runs_it_at_the_chosen_day_and_hour(self):
        m = manifest("notifications")
        job = m["jobs"][0]
        self.assertEqual((job["id"], job["schedule"]), ("weekly", "weekly_when"))
        spec = next(s for s in m["settings"] if s["key"] == "weekly_when")
        self.assertEqual((spec["type"], spec["default"]["every"], spec["default"]["time"]), ("schedule", "week", "09:00"))
        self.assertNotIn("weekly_day", {s["key"] for s in m["settings"]})


class Manifest(unittest.TestCase):
    def test_it_rests_and_is_woken_by_starboard(self):
        m = manifest("notifications")
        self.assertEqual(m["containers"][0]["start"], "when_needed")
        self.assertTrue(set(m["events"]) >= {"request.available", "download.failed", "app.down", "app.up", "disk.nearly_full", "update.available"})
        self.assertEqual([j["id"] for j in m["jobs"]], ["weekly"])
        secrets = {s["key"] for s in m["settings"] if s["type"] == "secret"}
        self.assertEqual(secrets, {"smtp_password", "telegram_token", "discord_webhook", "pushover_user", "pushover_token", "ntfy_token", "webhooks"})
        load_app = load("notifications")
        self.assertEqual(set(load_app.SECRETS), secrets)
        self.assertEqual({a["path"] for a in m["actions"]} - {"/weekly-now"}, {f"/test/{c}" for c in load_app.CHANNELS})

    def test_starboard_accepts_the_manifest_and_the_cards(self):
        got = starboard_cleaners()
        if not got:
            self.skipTest("Starboard's source is not on this computer")
        from starboard import plugins
        if not plugins._range_ok(manifest("notifications")["starboard_api"]):
            self.skipTest("this Starboard is older than plug-in API 1.11")
        m = manifest("notifications")
        m["containers"][0]["image"] = "ghcr.io/themightytrex/starboard-plugin-examples@sha256:" + "0" * 64
        self.assertEqual(plugins.check(m), [])
        app = load("notifications")
        plugin_cards = got[0]
        plugin_cards.clean("status", app.card())
        plugin_cards.clean("list", app.recent())


if __name__ == "__main__":
    unittest.main()
