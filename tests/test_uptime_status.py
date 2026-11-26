"""Uptime and status (outside-services 2.0.0): every kind of check with the network replaced, the one-line form, the
90-day history, certificates, maintenance windows, alerts through Starboard, the Checks and Groups pages, heartbeats,
the status page and the cards, checked with Starboard's own card cleaner where its source is here."""
import base64
import html.parser
import json
import os
import socket
import ssl
import struct
import sys
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT, load, starboard_cleaners  # noqa: E402

PID = "outside-services"
HERE = os.path.join(ROOT, PID)
sys.path.insert(0, HERE)
for _m in ("checks", "history", "windows", "page"):
    sys.modules.pop(_m, None)
import checks as ck  # noqa: E402
import windows as win  # noqa: E402
from history import HOURS, History  # noqa: E402

sys.path.remove(HERE)
# A self-signed certificate made for these tests: O=Example Home, CN=nas.example.org, for nas.example.org,
# files.example.org and 192.0.2.5, running out on 20 December 2026 at 15:37:19 UTC.
CERT = base64.b64decode(
    "MIIB7zCCAZSgAwIBAgIUKoKSjz+tdcCB0gbQh2NxFZM9L4swCgYIKoZIzj0EAwIwMTEVMBMGA1UECgwMRXhhbXBsZSBIb21lMRgwFgYDVQQDDA9uYXMu"
    "ZXhhbXBsZS5vcmcwHhcNMjYxMTIwMTUzNzE5WhcNMjYxMjIwMTUzNzE5WjAxMRUwEwYDVQQKDAxFeGFtcGxlIEhvbWUxGDAWBgNVBAMMD25hcy5leGFt"
    "cGxlLm9yZzBZMBMGByqGSM49AgEGCCqGSM49AwEHA0IABBcJPv1I9GLUwECNjag8jhgyxhmMjWgNPcbE8v7cR5FrKeBa0hizHjH5OLTNAEtS7BabV491"
    "kBLq4qm0yKmS6KCjgYkwgYYwHQYDVR0OBBYEFD8Sp4GG+Xn1rOduwoXR4inb6vcqMB8GA1UdIwQYMBaAFD8Sp4GG+Xn1rOduwoXR4inb6vcqMA8GA1Ud"
    "EwEB/wQFMAMBAf8wMwYDVR0RBCwwKoIPbmFzLmV4YW1wbGUub3JnghFmaWxlcy5leGFtcGxlLm9yZ4cEwAACBTAKBggqhkjOPQQDAgNJADBGAiEAzx6E"
    "n6bl2LdYSbopmOsHcJhdW3hnYv5zXmIRGcH4Mr8CIQDS/YY02iSWARPSGiGEW+qbc04RFr1EkPLLWxV99UB5FQ==")
CERT_END = 1797781039  # 20 December 2026 15:37:19 UTC


class Answer:
    """What urlopen gives back: a status and a body."""

    def __init__(self, status=200, body=b""):
        self.status, self.body = status, body

    def read(self, n=-1):
        return self.body if n < 0 else self.body[:n]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def http_error(code):
    return urllib.error.HTTPError("http://x", code, "error", {}, None)


class Line(unittest.TestCase):
    def test_each_kind_reads_from_one_line(self):
        c = ck.parse("Router: ping 192.168.1.1 in Home #network every 1m")
        self.assertEqual((c["name"], c["kind"], c["target"], c["group"], c["tags"], c["every"]),
                         ("Router", "ping", "192.168.1.1", "Home", ["network"], 60))
        c = ck.parse('Shop: keyword https://example.org/shop "In stock" in "Web sites"')
        self.assertEqual((c["kind"], c["words"], c["group"]), ("keyword", "In stock", "Web sites"))
        self.assertTrue(ck.parse("Errors: keyword https://example.org without Error")["absent"])
        c = ck.parse("NAS: tcp 192.168.1.5:445 tls")
        self.assertEqual((c["kind"], c["target"], c["tls"]), ("tcp", "192.168.1.5:445", True))
        c = ck.parse("Mail: dns example.org MX is mail.example.org at 192.0.2.53")
        self.assertEqual((c["record"], c["expect"], c["server"]), ("MX", "mail.example.org", "192.0.2.53"))
        c = ck.parse("Backup: push grace 25h")
        self.assertEqual((c["kind"], c["grace"]), ("push", 25 * 3600))
        self.assertGreaterEqual(len(c["token"]), 24)

    def test_the_kind_is_worked_out_when_left_out(self):
        self.assertEqual(ck.parse("https://example.org")["kind"], "http")
        self.assertEqual(ck.parse("nas.home:22")["kind"], "tcp")
        self.assertEqual(ck.parse("192.168.1.1")["kind"], "ping")
        self.assertEqual(ck.parse("https://example.org")["name"], "example.org")
        self.assertEqual(ck.parse("Home: http http://192.0.2.1:8080/x")["name"], "Home")

    def test_mistakes_say_what_to_change(self):
        for bad, words in [("", "Write the check"), ("Router: ping", "after ping"), ("tcp nas.home", "computer and port"),
                           ("tcp nas:70000", "between 1 and 65535"), ("keyword https://example.org", "words to find"),
                           ("http ftp://x", "web address"), ("ping x every 5s", "20 seconds"), ("dns example.org SRV type SRV", "DNS checks know"),
                           ("push https://x", "needs no address"), ('keyword https://x "open', "quote mark"),
                           ("ping x every soon", "not a time")]:
            with self.assertRaises(ck.LineError, msg=bad) as e:
                ck.parse(bad)
            self.assertIn(words, str(e.exception), bad)

    def test_a_check_is_written_back_as_the_same_line(self):
        for text in ["Router: ping 192.168.1.1 in Home #network every 1m", 'Shop: keyword https://example.org "In stock" every 5m',
                     "NAS: tcp 192.168.1.5:445 tls in \"Home office\" every 2m", "Mail: dns example.org MX is mail.example.org every 5m",
                     "Backup: push grace 25h in Jobs", "Site: cert example.org:8443 in Web every 1d"]:
            c = ck.parse(text)
            again = ck.parse(ck.line(c))
            for k in ("name", "kind", "target", "group", "tags", "every", "words", "record", "expect", "tls", "grace"):
                self.assertEqual(c.get(k), again.get(k), (text, k))


class Http(unittest.TestCase):
    def run_with(self, c, answer=None, error=None):
        def urlopen(req, timeout, context):
            self.assertEqual(context.verify_mode, ssl.CERT_NONE)  # a home device's own certificate still counts as up
            if error:
                raise error
            return answer
        with mock.patch.object(ck.urllib.request, "urlopen", urlopen):
            return ck.run(c)

    def test_an_answer_under_500_is_up(self):
        c = ck.parse("Site: http https://example.org")
        self.assertTrue(self.run_with(c, Answer(200))["up"])
        self.assertTrue(self.run_with(c, error=http_error(404))["up"])
        out = self.run_with(c, error=http_error(503))
        self.assertEqual((out["up"], out["said"]), (False, "It answered with error 503"))
        out = self.run_with(c, error=urllib.error.URLError(ConnectionRefusedError()))
        self.assertEqual((out["up"], out["said"]), (False, "The connection was refused"))
        out = self.run_with(c, error=urllib.error.URLError(TimeoutError()))
        self.assertEqual(out["said"], "No answer in 8 seconds")

    def test_keyword_needs_the_words_and_an_answer_under_400(self):
        c = ck.parse('Shop: keyword https://example.org "in stock"')
        self.assertTrue(self.run_with(c, Answer(200, b"<p>In Stock now</p>"))["up"])
        out = self.run_with(c, Answer(200, b"<p>Sold out</p>"))
        self.assertEqual((out["up"], out["said"]), (False, '"in stock" is not on the page'))
        self.assertFalse(self.run_with(c, error=http_error(404))["up"])
        c = ck.parse("Errors: keyword https://example.org without Error")
        self.assertTrue(self.run_with(c, Answer(200, b"All fine"))["up"])
        self.assertFalse(self.run_with(c, Answer(200, b"Error 42"))["up"])


class Tcp(unittest.TestCase):
    def test_a_port_that_takes_a_connection_is_up(self):
        c = ck.parse("NAS: tcp 192.168.1.5:445")
        conn = mock.MagicMock()
        with mock.patch.object(ck.socket, "create_connection", return_value=conn) as cc:
            out = ck.run(c)
        cc.assert_called_once_with(("192.168.1.5", 445), timeout=ck.TIMEOUT)
        self.assertTrue(out["up"])
        self.assertIsNotNone(out["ms"])
        with mock.patch.object(ck.socket, "create_connection", side_effect=ConnectionRefusedError()):
            self.assertEqual(ck.run(c), {"up": False, "said": "The connection was refused"})
        with mock.patch.object(ck.socket, "create_connection", side_effect=socket.gaierror()):
            self.assertEqual(ck.run(c)["said"], "The name was not found")


class FakeIcmp:
    """A ping socket that answers each echo with a reply carrying the same sequence number."""

    def __init__(self, family, kind, proto, answer=True):
        self.sent, self.answer = None, answer

    def settimeout(self, t):
        pass

    def sendto(self, packet, address):
        self.sent = packet

    def recvfrom(self, n):
        if not self.answer:
            raise TimeoutError
        reply = bytearray(self.sent)
        reply[0] = 0
        return bytes(reply), ("192.0.2.1", 0)

    def close(self):
        pass


class Ping(unittest.TestCase):
    def setUp(self):
        self.addr = mock.patch.object(ck, "_address", return_value=(socket.AF_INET, "192.0.2.1"))
        self.addr.start()

    def tearDown(self):
        self.addr.stop()

    def test_an_echo_reply_is_up(self):
        made = []

        def sock(*a):
            made.append(FakeIcmp(*a))
            return made[-1]
        with mock.patch.object(ck.socket, "socket", sock):
            out = ck.run(ck.parse("Router: ping 192.0.2.1"))
        self.assertEqual((out["up"], out["said"]), (True, "It answers ping"))
        self.assertEqual(made[0].sent[0], 8)  # an echo request
        self.assertEqual(ck._checksum(made[0].sent), 0)  # with a correct checksum

    def test_no_reply_is_down(self):
        with mock.patch.object(ck.socket, "socket", lambda *a: FakeIcmp(*a, answer=False)):
            out = ck.run(ck.parse("Router: ping 192.0.2.1"))
        self.assertEqual(out, {"up": False, "said": "No answer to ping in 8 seconds"})

    def test_without_ping_it_knocks_on_ports_and_a_refusal_is_an_answer(self):
        tried = []

        def connect(address, timeout):
            tried.append(address[1])
            if address[1] == 443:
                raise TimeoutError
            raise ConnectionRefusedError
        with mock.patch.object(ck.socket, "socket", side_effect=PermissionError(1, "Operation not permitted")), \
                mock.patch.object(ck.socket, "create_connection", connect):
            out = ck.run(ck.parse("Router: ping 192.0.2.1"))
        self.assertEqual(tried, [443, 80])
        self.assertTrue(out["up"])
        self.assertIn("port 80", out["said"])
        with mock.patch.object(ck.socket, "socket", side_effect=PermissionError(1, "no")), \
                mock.patch.object(ck.socket, "create_connection", side_effect=TimeoutError):
            self.assertFalse(ck.run(ck.parse("Router: ping 192.0.2.1"))["up"])


def dns_answer(qid, rtype, values, rcode=0, name="example.org"):
    """A DNS answer as a server would send it, with the name compressed to the question."""
    q = b"".join(bytes([len(p)]) + p.encode() for p in name.split(".")) + b"\0" + struct.pack("!HH", rtype, 1)
    out = struct.pack("!HHHHHH", qid, 0x8180 | rcode, 1, len(values), 0, 0) + q
    for v in values:
        if rtype == 1:
            data = socket.inet_aton(v)
        elif rtype == 15:
            data = struct.pack("!H", 10) + b"".join(bytes([len(p)]) + p.encode() for p in v.split(".")) + b"\0"
        elif rtype == 16:
            data = bytes([len(v)]) + v.encode()
        out += b"\xc0\x0c" + struct.pack("!HHIH", rtype, 1, 300, len(data)) + data
    return out


class FakeUdp:
    def __init__(self, answer):
        self.answer, self.sent, self.address = answer, None, None

    def settimeout(self, t):
        pass

    def connect(self, address):
        self.address = address

    def send(self, data):
        self.sent = data

    def recv(self, n):
        return self.answer(struct.unpack("!H", self.sent[:2])[0])

    def close(self):
        pass


class Dns(unittest.TestCase):
    def ask(self, line, answer):
        made = []
        with mock.patch.object(ck.socket, "socket", lambda *a: made.append(FakeUdp(answer)) or made[-1]):
            out = ck.run(ck.parse(line))
        return out, made[0]

    def test_a_record_and_the_server_it_asks(self):
        out, s = self.ask("Home: dns example.org A at 192.0.2.53", lambda q: dns_answer(q, 1, ["192.0.2.10"]))
        self.assertEqual((out["up"], out["said"]), (True, "A 192.0.2.10"))
        self.assertEqual(s.address, ("192.0.2.53", 53))
        self.assertIn(b"\x07example\x03org\x00", s.sent)

    def test_mx_txt_and_an_expected_value(self):
        out, _ = self.ask("Mail: dns example.org MX is mail.example.org", lambda q: dns_answer(q, 15, ["mail.example.org"]))
        self.assertTrue(out["up"])
        out, _ = self.ask("Mail: dns example.org MX is other.example.org", lambda q: dns_answer(q, 15, ["mail.example.org"]))
        self.assertEqual((out["up"], out["said"]), (False, "MX is mail.example.org, not other.example.org"))
        out, _ = self.ask("Txt: dns example.org TXT", lambda q: dns_answer(q, 16, ["v=spf1 -all"]))
        self.assertEqual(out["said"], "TXT v=spf1 -all")

    def test_a_missing_name_or_record_is_down(self):
        out, _ = self.ask("Gone: dns example.org", lambda q: dns_answer(q, 1, [], rcode=3))
        self.assertEqual((out["up"], out["said"]), (False, "The name does not exist"))
        out, _ = self.ask("Empty: dns example.org AAAA", lambda q: dns_answer(q, 28, []))
        self.assertEqual(out["said"], "No AAAA record")

    def test_the_server_comes_from_resolv_conf(self):
        with mock.patch.dict(os.environ, {"RESOLV_CONF": os.devnull}):
            self.assertEqual(ck.nameserver(), "127.0.0.11")


class Push(unittest.TestCase):
    def test_up_within_the_grace_time_then_down(self):
        c = ck.parse("Backup: push grace 1h")
        self.assertIsNone(ck.check_push(c, None)["up"])
        self.assertTrue(ck.check_push(c, {"at": 1000}, now=1000 + 3500)["up"])
        out = ck.check_push(c, {"at": 1000}, now=1000 + 7200)
        self.assertEqual((out["up"], out["said"]), (False, "No call for 2 hours"))
        self.assertFalse(ck.check_push(c, {"at": 1000, "down": True, "said": "disk full"}, now=1001)["up"])


class Certificates(unittest.TestCase):
    def test_the_date_and_the_names_it_was_issued_for(self):
        cert = ck.read_cert(CERT)
        self.assertEqual(cert["not_after"], CERT_END)
        self.assertEqual(cert["subject"], "nas.example.org")
        self.assertEqual(cert["names"], ["nas.example.org", "files.example.org", "192.0.2.5"])
        self.assertEqual(cert["issuer"], "Example Home")

    def test_which_checks_have_one(self):
        self.assertEqual(ck.cert_target(ck.parse("https://example.org:8443/x")), ("example.org", 8443))
        self.assertIsNone(ck.cert_target(ck.parse("http://example.org")))
        self.assertEqual(ck.cert_target(ck.parse("tcp mail.example.org:993 tls")), ("mail.example.org", 993))
        self.assertIsNone(ck.cert_target(ck.parse("tcp mail.example.org:993")))

    def test_a_certificate_check_reads_the_certificate_and_sends_no_request(self):
        c = ck.parse("Site: cert example.org #web")
        self.assertEqual((c["kind"], c["target"], c["every"]), ("cert", "example.org:443", ck.CERT_CHECK_EVERY))
        self.assertEqual(ck.parse("cert https://example.org:8443/x")["target"], "example.org:8443")
        self.assertEqual(ck.parse("cert [2001:db8::1]:443")["target"], "[2001:db8::1]:443")
        self.assertEqual(ck.parse("cert example.org every 1d")["every"], 86400)
        self.assertEqual(ck.cert_target(c), ("example.org", 443))
        with self.assertRaises(ck.LineError):
            ck.parse("cert")
        with self.assertRaises(ck.LineError):
            ck.parse("cert example.org extra")
        good = {**ck.read_cert(CERT), "trusted": True, "why": "", "checked": 0}
        with mock.patch.object(ck, "fetch_cert", return_value=good), mock.patch.object(ck.time, "time", return_value=CERT_END - 5 * 86400):
            out = ck.run(c)
        self.assertTrue(out["up"])
        self.assertEqual(out["said"], "5 days left")
        with mock.patch.object(ck, "fetch_cert", return_value=good), mock.patch.object(ck.time, "time", return_value=CERT_END + 86400):
            out = ck.run(c)
        self.assertFalse(out["up"])
        self.assertEqual(out["said"], "The certificate has run out")
        bad = {**good, "trusted": False, "why": "self-signed certificate"}
        with mock.patch.object(ck, "fetch_cert", return_value=bad), mock.patch.object(ck.time, "time", return_value=CERT_END - 5 * 86400):
            self.assertIn("not trusted: self-signed", ck.run(c)["said"])
        with mock.patch.object(ck, "fetch_cert", side_effect=OSError("refused")):
            self.assertFalse(ck.run(c)["up"])

    def test_an_untrusted_certificate_is_still_read(self):
        class Tls:
            def __init__(self, verified):
                self.verified = verified

            def __enter__(self):
                if self.verified:
                    raise ssl.SSLCertVerificationError(1, "x")
                return self

            def __exit__(self, *a):
                return False

            def getpeercert(self, binary_form):
                return CERT
        ctx = mock.MagicMock()
        ctx.wrap_socket.side_effect = lambda s, server_hostname: Tls(True)
        plain = mock.MagicMock()
        plain.wrap_socket.side_effect = lambda s, server_hostname: Tls(False)
        with mock.patch.object(ck.ssl, "create_default_context", return_value=ctx), \
                mock.patch.object(ck, "_unverified", return_value=plain), \
                mock.patch.object(ck.socket, "create_connection", return_value=mock.MagicMock()):
            out = ck.fetch_cert("nas.example.org", 443)
        self.assertFalse(out["trusted"])
        self.assertEqual(out["names"][0], "nas.example.org")


class Kept(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.h = History(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_hours_roll_up_and_ninety_days_are_43_kb(self):
        now = 1_800_000_000
        for i in range(24):
            t = now - i * 3600
            self.h.add("a", i % 4 != 0, 10 + i % 3, t)
        self.h.save()
        self.assertEqual(os.path.getsize(os.path.join(self.tmp.name, "a.bin")), HOURS * 5 * 4)
        again = History(self.tmp.name)
        self.assertEqual(again.hours("a", 24, now), self.h.hours("a", 24, now))
        self.assertEqual(again.uptime("a", 24, now), 75.0)
        pts = again.hourly_ms("a", 24, now)
        self.assertEqual(len(pts), 24)
        self.assertTrue(all(p is None or 10 <= p <= 12 for p in pts))
        days = again.daily("a", 90, now)
        self.assertEqual(sum(d["checks"] for d in days), 24)
        self.assertLessEqual(len(days), 3)

    def test_a_slot_ninety_days_on_is_reused_not_added_to(self):
        now = 1_800_000_000
        self.h.add("a", False, None, now)
        self.h.add("a", True, 5, now + HOURS * 3600)
        self.assertEqual(self.h.uptime("a", 24, now + HOURS * 3600), 100.0)
        self.assertIsNone(self.h.uptime("a", 1, now + 2 * HOURS * 3600))

    def test_written_only_when_the_hour_changes(self):
        now = 1_800_000_000 - 1_800_000_000 % 3600 + 60
        self.h.hour = int(now // 3600)
        self.h.add("a", True, 3, now)
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "a.bin")))
        self.h.add("a", True, 3, now + 3600)
        self.assertTrue(os.path.exists(os.path.join(self.tmp.name, "a.bin")))

    def test_forget_removes_it(self):
        self.h.add("a", True, 3)
        self.h.save()
        self.h.forget("a")
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "a.bin")))


class Windows(unittest.TestCase):
    def setUp(self):
        os.environ["TZ"] = "Europe/London"
        time.tzset()

    def at(self, text):
        return time.mktime(time.strptime(text, "%Y-%m-%d %H:%M"))

    def test_weekly_windows_and_one_over_midnight(self):
        ws = win.parse("Sunday 02:00 to 04:00; every day 23:30 to 00:30")
        self.assertTrue(win.active(ws, self.at("2026-11-22 03:00")))  # a Sunday
        self.assertFalse(win.active(ws, self.at("2026-11-23 03:00")))
        self.assertTrue(win.active(ws, self.at("2026-11-23 00:15")))
        self.assertTrue(win.active(ws, self.at("2026-11-23 23:45")))
        self.assertEqual(win.words(ws[0]), "Sundays 02:00 to 04:00")
        self.assertEqual(win.words(win.parse("weekdays 01:00 to 02:00")[0]), "Weekdays 01:00 to 02:00")
        self.assertEqual(win.parse("Saturday and Sunday 01:00 to 02:00")[0]["days"], [5, 6])

    def test_once_and_now(self):
        now = self.at("2026-11-20 15:00")
        ws = win.parse("2026-11-21 02:00 to 06:00; now for 2 hours", now)
        self.assertTrue(win.active(ws, now + 60))
        self.assertFalse(win.active(ws, now + 3 * 3600))
        self.assertTrue(win.active(ws, self.at("2026-11-21 05:59")))
        self.assertEqual(win.words(ws[0]), "21 November 02:00 to 06:00")
        self.assertEqual(len(win.live(ws, self.at("2026-11-22 00:00"))), 0)

    def test_written_back_the_same(self):
        now = self.at("2026-11-20 15:00")
        text = "Sunday 02:00 to 04:00; every day 03:00 to 03:30; 2026-11-21 02:00 to 06:00"
        self.assertEqual(win.parse(win.line(win.parse(text, now)), now), win.parse(text, now))

    def test_mistakes(self):
        for bad in ("Sunday 25:00 to 26:00", "soon", "now for 2 weeks", "2026-02-31 01:00 to 02:00"):
            with self.assertRaises(win.WindowError, msg=bad):
                win.parse(bad)
        self.assertEqual(win.parse(""), [])


class App(unittest.TestCase):
    def setUp(self):
        self.app = load(PID, {"addresses": ["Router http://192.0.2.1"], "minutes": 5, "alerts": True, "down_after": 2})
        self.app.PAGE_DIR = os.path.join(self.app._data, "page")
        self.sent = []

        def send(key, state, title, message, level="problem"):
            self.sent.append((key, state, title))
            return True
        self.app.send_alert = send

    def tearDown(self):
        self.app._tmp.cleanup()

    def add(self, line):
        return self.app.checks_action({"action": "add", "value": line})

    def test_outside_services_addresses_keep_working(self):
        rows = self.app.all_checks()
        self.assertEqual([(c["name"], c["kind"], c["target"], c["group"]) for c in rows],
                         [("Router", "http", "http://192.0.2.1", "Outside services")])
        page_ = self.app.checks_page()
        self.assertEqual(page_["items"][0]["actions"], ["test"])
        with self.assertRaises(self.app.Refused):
            self.app.checks_action({"action": "remove", "id": "addr0"})

    def test_add_change_pause_and_remove(self):
        out = self.add("NAS: tcp 192.168.1.5:445 in Home")
        self.assertIn("Added NAS", out["said"])
        cid = next(i["id"] for i in out["items"] if i["title"] == "NAS")
        item = next(i for i in out["items"] if i["id"] == cid)
        self.assertEqual((item["group"], item["attach"]["value"]), ("Home", "NAS: tcp 192.168.1.5:445 in Home every 5m"))
        out = self.app.checks_action({"action": "attach", "id": cid, "value": "NAS: tcp 192.168.1.5:22 in Home"})
        self.assertEqual(self.app.find(cid)["target"], "192.168.1.5:22")
        out = self.app.checks_action({"action": "toggle", "id": cid})
        self.assertFalse(self.app.find(cid)["on"])
        self.assertEqual(next(i for i in out["items"] if i["id"] == cid)["state_label"], "Paused")
        self.app.checks_action({"action": "remove", "id": cid})
        self.assertIsNone(self.app.find(cid))
        with self.assertRaises(ck.LineError):
            self.add("NAS: tcp nowhere")

    def test_a_heartbeat_keeps_its_address_when_changed(self):
        self.add("Backup: push grace 25h")
        c = next(c for c in self.app.stored() if c["kind"] == "push")
        self.app.checks_action({"action": "attach", "id": c["id"], "value": "Backup: push grace 2h in Jobs"})
        self.assertEqual(self.app.find(c["id"])["token"], c["token"])
        self.assertFalse(self.app.push("wrong", {}))
        self.assertTrue(self.app.push(c["token"], {}))
        self.assertEqual(self.app.state_of(self.app.find(c["id"])), "up")
        self.assertTrue(self.app.push(c["token"], {"status": ["down"], "msg": ["disk full"]}))
        self.assertEqual(self.app.state_of(self.app.find(c["id"])), "down")
        self.assertIn("disk full", self.app.said_of(self.app.find(c["id"])))

    def run_round(self, result, now):
        with mock.patch.object(self.app.ck, "run", return_value=result):
            self.app.NEXT.clear()
            self.app.round_once(now)

    def test_alerts_after_failures_in_a_row_once_and_cleared_once(self):
        now = time.time()
        self.run_round({"up": False, "said": "The connection was refused"}, now)
        self.assertEqual(self.sent, [])  # one failure: trying again
        self.run_round({"up": False, "said": "The connection was refused"}, now + 60)
        self.run_round({"up": False, "said": "The connection was refused"}, now + 120)
        self.assertEqual(self.sent, [("check-addr0", "raised", "Router is down")])
        self.run_round({"up": True, "ms": 4}, now + 180)
        self.assertEqual(self.sent[-1], ("check-addr0", "cleared", "Router is up again"))
        self.assertEqual(len(self.sent), 2)

    def test_maintenance_pauses_alerts_and_sends_when_it_ends(self):
        now = time.time()
        kept = {"Outside services": {"windows": win.parse("now for 10 minutes", now)}}
        self.app.keep_groups(kept)
        for i in range(3):
            self.run_round({"up": False, "said": "No answer"}, now + i * 60)
        self.assertEqual(self.sent, [])
        self.assertIn("Maintenance", self.app.summary()["text"])
        self.assertEqual(self.app.page_rows(now)[0]["state"], "maintenance")
        self.run_round({"up": False, "said": "No answer"}, now + 11 * 60)
        self.assertEqual(self.sent, [("check-addr0", "raised", "Router is down")])

    def test_a_group_with_alerts_paused_sends_nothing(self):
        self.app.groups_action({"action": "toggle", "id": "Outside services"})
        self.assertIs(self.app.groups_kept()["Outside services"]["alerts"], False)
        now = time.time()
        for i in range(3):
            self.run_round({"up": False, "said": "No answer"}, now + i * 60)
        self.assertEqual(self.sent, [])
        out = self.app.groups_action({"action": "attach", "id": "Outside services", "value": "Sunday 02:00 to 04:00"})
        self.assertIn("Sundays 02:00 to 04:00", out["items"][0]["detail"])
        with self.assertRaises(win.WindowError):
            self.app.groups_action({"action": "attach", "id": "Outside services", "value": "whenever"})

    def test_a_certificate_running_out_is_a_warning(self):
        now = CERT_END - 5 * 86400
        self.app.CERTS["addr0"] = {**ck.read_cert(CERT), "trusted": True, "checked": now}
        self.app.reconcile(now)
        self.assertEqual(self.sent, [("cert-addr0", "raised", "Router's certificate runs out in 5 days")])
        self.assertIn("5 days left, for nas.example.org", self.app.cert_words("addr0", now))

    def test_a_certificate_check_keeps_its_certificate_for_the_alert(self):
        c = ck.parse("Site: cert example.org")
        c["id"] = "cert0"
        good = {**ck.read_cert(CERT), "trusted": True, "why": "", "checked": time.time()}
        with mock.patch.object(ck, "fetch_cert", return_value=good), mock.patch.object(self.app.ck, "fetch_cert", return_value=good):
            self.app.run_one(c, time.time())
        self.assertIn("cert0", self.app.CERTS)
        self.assertNotIn("cert", self.app.LIVE["cert0"])

    def test_starboard_without_the_alerts_api_is_said_once_an_hour(self):
        app = load(PID, {"addresses": ["Router http://192.0.2.1"]})
        calls = []
        app._post_starboard = lambda path, body: calls.append(path) or 404
        self.assertFalse(app.send_alert("k", "raised", "t", "m"))
        self.assertFalse(app.send_alert("k", "raised", "t", "m"))
        self.assertEqual(calls, ["plugin/alerts"])
        app.LIVE["addr0"] = {"up": True, "ms": 3, "at": time.time()}
        self.assertIn("does not take alerts", app.summary()["text"])
        app._tmp.cleanup()

    def test_cards_pass_starboards_own_cleaner(self):
        now = time.time()
        self.add("NAS: tcp 192.168.1.5:445 in Home")
        self.run_round({"up": True, "ms": 12.4}, now)
        self.app.CERTS["addr0"] = {**ck.read_cert(CERT), "trusted": False, "why": "self-signed certificate", "checked": now}
        cards = {"status": self.app.summary(), "list": self.app.checks_card(), "groups": self.app.groups_card(),
                 "sparkline": self.app.trend_card(), "certs": self.app.certs_card()}
        self.assertEqual(cards["status"]["text"], "All 2 checks are up")
        self.assertEqual(len(cards["sparkline"]["series"][0]["points"]), 24)
        self.assertEqual(cards["sparkline"]["series"][0]["points"][-1], 12)
        self.assertIn("Not trusted", cards["certs"]["items"][0]["detail"])
        sb = starboard_cleaners()
        if not sb:
            self.skipTest("Starboard's source is not here")
        from starboard import plugins
        if "sparkline" not in plugins.CARD_TYPES:
            self.skipTest("This Starboard has no sparkline card yet (plug-in API 1.17)")
        for kind, answer in cards.items():
            card_type = "list" if kind in ("groups", "certs") else kind
            sb[0].clean(card_type, json.loads(json.dumps(answer)), strict=True)
        self.assertIn("Now 12 ms", sb[0].clean("sparkline", cards["sparkline"])["series"][0]["summary"])

    def test_custom_pages_pass_starboards_own_cleaner(self):
        self.add("Backup: push grace 25h in Jobs")
        sb = starboard_cleaners()
        if not sb:
            self.skipTest("Starboard's source is not here")
        for answer in (self.app.checks_page(), self.app.groups_page()):
            cleaned = sb[1].clean(json.loads(json.dumps(answer)))
            self.assertEqual(len(cleaned["items"]), len(answer["items"]))


class Parser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.text = [], []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

    def handle_data(self, data):
        self.text.append(data)


class StatusPage(unittest.TestCase):
    def test_names_never_addresses_with_table_headers(self):
        app = load(PID, {"addresses": ["Router http://192.0.2.1"], "status_title": "Our house"})
        app.PAGE_DIR = os.path.join(app._data, "page")
        app.checks_action({"action": "add", "value": "Backup: push grace 25h in Jobs"})
        token = app.stored()[0]["token"]
        app.LIVE["addr0"] = {"up": True, "ms": 4, "at": time.time(), "fails": 0}
        app.write_page()
        text = open(os.path.join(app.PAGE_DIR, "index.html"), encoding="utf-8").read()
        self.assertNotIn("192.0.2.1", text)
        self.assertNotIn(token, text)
        p = Parser()
        p.feed(text)
        self.assertEqual(p.tags[0][1].get("lang"), "en-GB")
        self.assertIn(("h1", {}), p.tags)
        self.assertTrue(any(t == "th" and a.get("scope") == "row" for t, a in p.tags))
        self.assertTrue(any(t == "a" and a.get("class") == "skip-link" for t, a in p.tags))
        words = " ".join(p.text)
        self.assertIn("Our house", words)
        self.assertIn("Status: Up", words.replace("  ", " "))
        for banned in ("—", "click", "please"):
            self.assertNotIn(banned, text.lower())
        app._tmp.cleanup()


class Server(unittest.TestCase):
    """The one port: Starboard's calls with its key, the status page, its files and heartbeats."""

    def setUp(self):
        from http.server import ThreadingHTTPServer
        self.app = load(PID, {"addresses": ["Router http://192.0.2.1"]})
        self.app.PAGE_DIR = os.path.join(self.app._data, "page")
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), self.app.Handler)
        threading.Thread(target=self.srv.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.srv.server_address[1]}"

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.app._tmp.cleanup()

    def get(self, path, headers=None, data=None):
        req = urllib.request.Request(self.base + path, headers=headers or {}, data=data, method="POST" if data else "GET")
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, r.headers, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.headers, e.read()

    def test_the_lists_need_starboards_key(self):
        self.assertEqual(self.get("/manage/checks")[0], 401)
        self.assertEqual(self.get("/manage/checks", {"X-Api-Key": "wrong"})[0], 401)
        status, _, body = self.get("/manage/checks", {"X-Api-Key": "sbk_test"})
        self.assertEqual((status, json.loads(body)["title"]), (200, "Checks"))
        status, _, body = self.get("/manage/checks", {"X-Api-Key": "sbk_test", "Content-Type": "application/json"},
                                   json.dumps({"action": "add", "value": "nonsense: tcp x"}).encode())
        self.assertEqual(status, 400)
        self.assertIn("computer and port", json.loads(body)["error"])

    def test_the_page_its_files_and_a_heartbeat(self):
        status, headers, body = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertIn(b"<h1>Home services</h1>", body)
        for path in ("/ds.css", "/status.css", "/theme.js", "/fonts/atkinson-hyperlegible-next.woff2"):
            self.assertEqual(self.get(path)[0], 200, path)
        self.assertEqual(self.get("/push/nothing")[0], 404)
        self.app.checks_action({"action": "add", "value": "Backup: push"})
        token = self.app.stored()[0]["token"]
        self.assertEqual(self.get(f"/push/{token}?status=up")[0], 200)
        self.assertEqual(self.get("/health")[0], 200)
        self.assertEqual(json.loads(self.get("/run", data=b"{}")[2])["said"], "Checking everything now")
        self.app._set(status_page=False)
        self.assertEqual(self.get("/")[0], 404)


class Manifest(unittest.TestCase):
    def test_outside_services_settings_move_with_starboards_own_code(self):
        """The update from the published Outside services 1.1.4 (its manifest at the commit kept in
        tools/previous-versions.json), rehearsed with Starboard's own migration code: every setting keeps its value."""
        import subprocess
        prev = json.load(open(os.path.join(ROOT, "tools", "previous-versions.json"), encoding="utf-8"))["more"][PID][0]
        got = subprocess.run(["git", "-C", ROOT, "show", f"{prev['commit']}:{PID}/starboard-plugin.json"], capture_output=True)
        if got.returncode or not starboard_cleaners():
            self.skipTest("The published manifest or Starboard's source is not here")
        from starboard import plugin_update
        old = json.loads(got.stdout)
        new = json.load(open(os.path.join(HERE, "starboard-plugin.json"), encoding="utf-8"))
        self.assertEqual(old["version"], "1.1.4")
        moved, said = plugin_update.migrate(old, new, {"addresses": ["Router http://192.0.2.1"], "minutes": 7})
        self.assertEqual((moved, said), ({"addresses": ["Router http://192.0.2.1"], "minutes": 7}, []))
        self.assertEqual([i[0] for i in plugin_update.rehearse(old, new)], ["info"])  # only: new permissions, chosen by hand

    def test_it_keeps_its_id_and_settings_and_needs_api_117(self):
        m = json.load(open(os.path.join(HERE, "starboard-plugin.json"), encoding="utf-8"))
        self.assertEqual((m["id"], m["version"], m["starboard_api"]), ("outside-services", "2.1.1", ">=1.17 <2.0"))
        keys = {s["key"]: s for s in m["settings"]}
        self.assertEqual(keys["addresses"]["type"], "list")  # Outside services' settings, unchanged
        self.assertEqual((keys["minutes"]["type"], keys["minutes"]["default"]), ("number", 5))
        self.assertEqual(sorted(m["permissions"]), ["alerts:send", "network:lan", "network:port"])
        self.assertEqual({c["id"] for c in m["cards"]} >= {"summary", "list"}, True)  # dashboards keep their cards
        self.assertEqual(m["resources"]["main"]["memory"], 48)


if __name__ == "__main__":
    unittest.main()
