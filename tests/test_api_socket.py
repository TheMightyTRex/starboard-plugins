"""The shared sbplugin reaches Starboard's API through STARBOARD_API_SOCKET when Starboard gives one (Starboard
DASH-482, issue 202): a plug-in on its own internal network, such as Disk forecast or Download summary, has no route
to Starboard's port. Without the socket it uses STARBOARD_API over HTTP, as before."""
import json
import os
import socketserver
import sys
import tempfile
import threading
import unittest
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Answers(BaseHTTPRequestHandler):
    seen = []

    def do_GET(self):  # noqa: N802
        Answers.seen.append((self.path, self.headers.get("Authorization")))
        ok = self.headers.get("Authorization") == "Bearer sb_read_abc123_made-up-key-for-tests"
        body = json.dumps({"path": self.path} if ok else {"title": "key_needed"}).encode()
        self.send_response(200 if ok else 401)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class UnixServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True

    def get_request(self):
        conn, _ = self.socket.accept()
        return conn, ("socket", 0)


class Socket(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sbp")
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        with open(os.path.join(self.tmp, "key"), "w") as f:
            f.write("sb_read_abc123_made-up-key-for-tests\n")
        Answers.seen = []
        sys.path.insert(0, os.path.join(ROOT, "_shared"))
        self.addCleanup(sys.path.remove, os.path.join(ROOT, "_shared"))
        sys.modules.pop("sbplugin", None)
        import sbplugin
        self.sb = sbplugin
        self.sb.RUN = self.tmp

    def serve_socket(self):
        path = os.path.join(self.tmp, "api.sock")
        srv = UnixServer(path, Answers)
        threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        return path

    def test_the_socket_is_used_when_starboard_gives_one(self):
        self.sb.API_SOCKET = self.serve_socket()
        self.sb.API = "http://starboard:8095/api/v1/"  # no such address on its own network
        self.assertEqual(self.sb.starboard("downloads?limit=5"), {"path": "/api/v1/downloads?limit=5"})
        self.assertEqual(Answers.seen[-1][1], "Bearer sb_read_abc123_made-up-key-for-tests")

    def test_a_refusal_raises_as_over_http(self):
        self.sb.API_SOCKET = self.serve_socket()
        with open(os.path.join(self.tmp, "key"), "w") as f:
            f.write("sb_read_abc123_another-key\n")
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.sb.starboard("me")
        self.assertEqual(e.exception.code, 401)

    def test_without_the_socket_it_calls_starboard_api_over_http(self):
        srv = ThreadingHTTPServer(("127.0.0.1", 0), Answers)
        threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        self.sb.API_SOCKET = os.path.join(self.tmp, "api.sock")  # named, but an older Starboard made none
        self.sb.API = f"http://127.0.0.1:{srv.server_address[1]}/api/v1/"
        self.assertEqual(self.sb.starboard("me"), {"path": "/api/v1/me"})


if __name__ == "__main__":
    unittest.main()
