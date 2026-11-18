#!/usr/bin/env python3
"""Unit tests for the Remote access plug-in's helper (remote-access/app.py): keys and tokens, Cloudflare routes, and
what the card and screen say. No network, no real key or token. Run: python3 tools/test_remote_access.py"""
import base64
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
RUN = tempfile.mkdtemp(prefix="ra-test-")
os.environ.update({"PLUGIN_RUN": RUN, "PLUGIN_DATA": os.path.join(RUN, "data")})
sys.dont_write_bytecode = True  # keep remote-access/ clean for its zip
sys.path.insert(0, os.path.join(ROOT, "remote-access"))
import app  # noqa: E402


def use(**settings):
    with open(os.path.join(RUN, "settings.json"), "w") as f:
        json.dump(settings, f)


def fake_token():
    return base64.b64encode(json.dumps({"a": "0" * 32, "t": "1" * 36, "s": "c2VjcmV0"}).encode()).decode()


class Keys(unittest.TestCase):
    def test_tailscale_key(self):
        self.assertEqual(app.check_tailscale_key(""), "missing")
        self.assertIn("start with tskey-auth-", app.check_tailscale_key("hello"))
        self.assertEqual(app.check_tailscale_key("tskey-auth-kAbc123CNTRL-abcdefghij"), "")

    def test_cloudflare_token(self):
        self.assertEqual(app.check_cloudflare_token("  "), "missing")
        self.assertIn("not a Cloudflare Tunnel token", app.check_cloudflare_token("abc"))
        self.assertEqual(app.check_cloudflare_token(fake_token()), "")
        # the whole command, pasted from Cloudflare's dashboard, still works
        self.assertEqual(app.check_cloudflare_token("cloudflared tunnel run --token " + fake_token()), "")
        self.assertEqual(app.clean_token("sudo cloudflared service install " + fake_token()), fake_token())

    def test_messages(self):
        self.assertTrue(app.explain_cloudflare('ERR Register tunnel error error="Failed to get tunnel"')[1])
        self.assertTrue(app.explain_tailscale("backend error: invalid key: unable to validate API key")[1])
        self.assertFalse(app.explain_tailscale("dial tcp: lookup controlplane.tailscale.com: no such host")[1])

    def test_wanted_changes_with_the_key_but_never_holds_it(self):
        use(method="tailscale", tailscale_key="tskey-auth-one1234567")
        a = app.wanted()
        use(method="tailscale", tailscale_key="tskey-auth-two1234567")
        self.assertNotEqual(a, app.wanted())
        self.assertNotIn("tskey-auth-two1234567", json.dumps(app.wanted()))


class Routes(unittest.TestCase):
    def setUp(self):
        use(method="cloudflare")

    def rule(self, host, service, access=False):
        r = {"hostname": host, "service": service}
        if access:
            r["originRequest"] = {"access": {"required": True, "teamName": "home", "audTag": ["x"]}}
        return r

    def test_only_the_three_forwarders(self):
        routes = app.judge_routes([self.rule("tv.example.org", "http://localhost:8096"),
                                   self.rule("qb.example.org", "http://192.168.1.5:8080"), {"service": "http_status:404"}])
        self.assertEqual(routes[0]["problem"], "")
        self.assertIn("not Starboard, Jellyfin or Audiobookshelf", routes[1]["problem"])
        self.assertEqual(len(routes), 2)

    def test_starboard_needs_access(self):
        self.assertIn("without Cloudflare Access", app.judge_routes([self.rule("sb.example.org", "http://localhost:8095")])[0]["problem"])
        self.assertEqual(app.judge_routes([self.rule("sb.example.org", "http://127.0.0.1:8095", access=True)])[0]["problem"], "")

    def test_an_app_not_shared(self):
        use(method="cloudflare", share_jellyfin=False)
        self.assertIn("not shared", app.judge_routes([self.rule("tv.example.org", "http://localhost:8096")])[0]["problem"])


class Screen(unittest.TestCase):
    def test_connected_tailscale(self):
        use(method="tailscale")
        app.targets.update({"starboard": ("starboard", 8095), "jellyfin": ("host.docker.internal", 8096)})
        app.state.update({"method": "tailscale", "phase": "connected", "text": "Connected", "ips": ["100.101.102.103"], "dns": "starboard.tail1.ts.net"})
        self.assertEqual(app.card(), {"state": "ok", "text": "Away from home: http://100.101.102.103:8095 (Tailscale)",
                                      "status": "ok", "status_label": "Connected"})
        items = {i["id"]: i for i in app.screen()["items"]}
        self.assertEqual(items["jellyfin"]["address"], "http://100.101.102.103:8096")
        self.assertEqual(items["audiobookshelf"]["state"], "off")
        self.assertEqual(items["download-apps"]["group"], "Never shared")
        self.assertIn("If it does not open at the name starboard.tail1.ts.net", items["starboard"]["detail"])  # Starboard not asked
        self.assertIn("STARBOARD_ALLOWED_HOSTS", items["starboard"]["detail"])
        real = app._starboard_name_ok
        try:
            app._starboard_name_ok = lambda host: True
            self.assertIn("The name starboard.tail1.ts.net works too.", {i["id"]: i for i in app.screen()["items"]}["starboard"]["detail"])
            app._starboard_name_ok = lambda host: False
            refused = {i["id"]: i for i in app.screen()["items"]}["starboard"]["detail"]
            self.assertIn("To use the name starboard.tail1.ts.net: in Starboard's folder on the server", refused)
            self.assertIn("then run ./update.sh.", refused)
        finally:
            app._starboard_name_ok = real

    def test_unreachable_starboard_and_unread_apps_say_what_to_do(self):
        use(method="tailscale")
        app.targets.clear()
        app.targets.update({"starboard": ("127.0.0.1", 9)})
        app.state["apps_read"] = False
        ok, words = app._reach("starboard")
        self.assertFalse(ok)
        self.assertIn("Remote access cannot reach Starboard on the server", words)
        self.assertIn("Update Starboard in Settings, Updates", words)
        ok, words = app._reach("jellyfin")
        self.assertIn("Not checked: Remote access could not read Starboard's apps", words)
        app.state["apps_read"] = True
        ok, words = app._reach("jellyfin")
        self.assertIn("is not in Starboard's apps, so it is not shared. Add it in Settings, Apps.", words)

    def test_missing_key_is_a_problem(self):
        app.state.update({"method": "tailscale", "phase": "needs-key", "text": "Paste a Tailscale auth key", "fatal": True})
        self.assertEqual(app.card()["state"], "problem")

    def test_never_forwards_download_apps(self):
        self.assertEqual(sorted(app.PORTS), ["audiobookshelf", "jellyfin", "starboard"])


if __name__ == "__main__":
    unittest.main()
