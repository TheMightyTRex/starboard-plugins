"""The app plug-ins' helpers that run in the official Python image from the manifest's files (17 November 2026):
Themearr and Checkrr. Each helper runs against a stand-in for its app on this computer, and its answers pass
Starboard's own card and page checks when Starboard's source is here (STARBOARD_SRC)."""
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT, manifest, starboard_cleaners  # noqa: E402


class Stand(ThreadingHTTPServer):
    """A stand-in app: answers GET from `answers`, records every call in `calls`."""

    def __init__(self, answers, on_post=None):
        self.answers, self.on_post, self.calls = answers, on_post or {}, []
        super().__init__(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.serve_forever, daemon=True).start()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server_address[1]}"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _answer(self, body):
        raw = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        self.server.calls.append(("GET", self.path, None, self.headers.get("Authorization")))
        if self.path not in self.server.answers:
            self.send_response(404)
            self.end_headers()
            return
        self._answer(self.server.answers[self.path])

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"null") if n else None
        self.server.calls.append(("POST", self.path, body, self.headers.get("Authorization")))
        result = self.server.on_post.get(self.path)
        self._answer(result(body) if callable(result) else (result if result is not None else {}))


def load(pid, env):
    """The plug-in's helper.py as a module, with its own /run/starboard and folder in a temporary place."""
    tmp = tempfile.TemporaryDirectory()
    run = os.path.join(tmp.name, "run")
    os.makedirs(run)
    with open(os.path.join(run, "key"), "w") as f:
        f.write("sbk_test")
    with open(os.path.join(run, "settings.json"), "w") as f:
        json.dump({}, f)
    os.environ.update({"STARBOARD_RUN": run, "HELPER_DATA": tmp.name, **env})
    name = f"helper_{pid}"
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, pid, "helper.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod._tmp, mod._run = tmp, run
    return mod


def write(mod, name, value):
    with open(os.path.join(mod._run, name), "w") as f:
        json.dump(value, f)


class InTheManifest(unittest.TestCase):
    def test_manifests_carry_the_helpers_as_they_are(self):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_app_helpers.py"), "--check"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_each_helper_is_versioned_small_and_standard_library_only(self):
        for pid in ("themearr", "checkrr"):
            m = manifest(pid)
            main = m["containers"][0]
            self.assertEqual(main["name"], "main")  # Starboard calls the first container
            self.assertTrue(main["image"].startswith("docker.io/library/python@sha256:"), pid)
            self.assertEqual(main["command"], ["python3", f"/helper/app-{m['version']}.py"])
            self.assertEqual(main.get("network", "default"), "default", f"{pid}: the helper reaches only Starboard and its app")
            for name, text in main["files"].items():
                self.assertLessEqual(len(text), 16384, name)
            with open(os.path.join(ROOT, pid, "helper.py"), encoding="utf-8") as f:
                src = f.read()
            imported = set(re.findall(r"^(?:import|from) ([a-z_.]+)", src, re.M))
            self.assertTrue(all(sys.modules.get(n.split(".")[0]) or n.split(".")[0] in sys.stdlib_module_names for n in imported), imported)

    def test_checkrr_only_reports(self):
        m = manifest("checkrr")
        app = m["containers"][1]
        text = app["files"]["checkrr.yaml"]
        self.assertNotRegex(text, r"(?m)^arr:", "no Radarr, Sonarr or Lidarr, so it never asks one to delete a file")
        for word in ("removevideo", "removeaudio", "removelang", "apikey"):
            self.assertNotIn(word, text)
        self.assertEqual(sorted(v for v in app["volumes"] if v.startswith("media")), ["media/movies:ro", "media/tv:ro"])
        self.assertNotIn("reelix:key", m["permissions"])
        self.assertIn("never deletes", m["description"])

    def test_themearr_writes_only_the_films_folder_as_the_media_owner(self):
        m = manifest("themearr")
        app = m["containers"][1]
        self.assertEqual([v for v in app["volumes"] if v.startswith("media")], ["media/movies"])
        self.assertEqual(app["user"], "media")
        self.assertEqual(app["env"]["THEMEARR_AUTH_TOKEN"], "{secret:auth_token}")
        self.assertEqual(m["containers"][0]["env"]["THEMEARR_AUTH_TOKEN"], "{secret:auth_token}")


class Themearr(unittest.TestCase):
    def setUp(self):
        self.settings = {"selectedServers": [], "selectedLibraries": {}, "pathMappings": [], "libraryPaths": [],
                         "advanced": {"maxSearchDirs": 20000, "searchDepth": 4}, "autoDownload": False, "autoSync": False}
        self.radarr = {"source": "plex", "url": "", "configured": False}
        self.rapid = {"configured": False}
        self.done = {"setupComplete": False}

        def save_radarr(body):
            self.radarr.update(source=body["source"], url=body["url"], configured=True)
            return {"source": body["source"], "configured": True}

        def save_settings(body):
            self.settings.update(body)
            return self.settings

        def save_rapid(body):
            self.rapid["configured"] = True
            return self.rapid

        self.stand = Stand({"/api/settings/radarr": self.radarr, "/api/settings": self.settings, "/api/setup/status": self.done,
                            "/api/settings/rapidapi": self.rapid,
                            "/api/stats": {"total": 450, "downloaded": 412, "pending": 38, "ignored": 0}},
                           {"/api/settings/radarr": save_radarr, "/api/settings": save_settings,
                            "/api/setup/complete": lambda b: self.done.update(setupComplete=True) or self.done,
                            "/api/sync": {"started": True}, "/api/settings/rapidapi": save_rapid})
        self.app = load("themearr", {"THEMEARR_URL": self.stand.url, "THEMEARR_AUTH_TOKEN": "t" * 32})

    def tearDown(self):
        self.stand.shutdown()
        self.stand.server_close()
        self.app._tmp.cleanup()

    def posts(self, path):
        return [c[2] for c in self.stand.calls if c[0] == "POST" and c[1] == path]

    def test_no_reelix_key_yet(self):
        self.app.connect()
        self.assertEqual(self.app.STATE["state"], "warning")
        self.assertIn("add Reelix in Settings, Apps", self.app.STATE["said"])
        self.assertEqual(self.posts("/api/settings/radarr"), [])

    def test_gives_reelix_as_radarr_with_the_films_folder_once(self):
        write(self.app, "reelix.json", {"url": "http://host.docker.internal:7700/", "api_key": "rx-key"})
        self.app.connect()
        self.assertEqual(self.posts("/api/settings/radarr"),
                         [{"source": "radarr", "url": "http://host.docker.internal:7700/radarr", "apiKey": "rx-key"}])
        self.assertEqual(self.settings["libraryPaths"], ["/media/movies"])
        self.assertEqual(self.settings["pathMappings"], [{"source": "/data/media/movies", "target": "/media/movies"}])
        self.assertTrue(self.settings["autoSync"])
        self.assertTrue(self.settings["autoDownload"])  # the switch's default
        self.assertTrue(self.done["setupComplete"])
        self.assertEqual(len(self.posts("/api/sync")), 1)
        self.assertTrue(all(c[3] == "Bearer " + "t" * 32 for c in self.stand.calls), "every call with the access token")
        self.assertEqual(self.app.STATE["state"], "needs_setup")
        self.assertEqual(self.app.STATE["label"], "Needs a RapidAPI key")
        # A second round sends nothing again, and keeps a choice made in Themearr's own page.
        self.settings["autoDownload"] = False
        before = len([c for c in self.stand.calls if c[0] == "POST"])
        self.app.connect()
        self.assertEqual(len([c for c in self.stand.calls if c[0] == "POST"]), before)
        # A new Reelix key is given again.
        write(self.app, "reelix.json", {"url": "http://host.docker.internal:7700", "api_key": "new-key"})
        self.app.connect()
        self.assertEqual(self.posts("/api/settings/radarr")[-1]["apiKey"], "new-key")

    def test_passes_on_the_rapidapi_key_and_the_switch(self):
        write(self.app, "reelix.json", {"url": "http://rx:7700", "api_key": "k"})
        write(self.app, "settings.json", {"rapidapi_key": "rk", "rapidapi_user": "someone", "auto_download": False})
        self.app.connect()
        self.assertEqual(self.posts("/api/settings/rapidapi"), [{"key": "rk", "username": "someone"}])
        self.assertFalse(self.settings["autoDownload"])
        self.assertEqual(self.app.STATE["state"], "ok")
        card = self.app.card()
        self.assertEqual((card["value"], card["note"]), (412, "38 of 450 films still without a theme"))
        self.app.connect()
        self.assertEqual(len(self.posts("/api/settings/rapidapi")), 1)

    def test_answers_pass_starboards_checks(self):
        cleaners = starboard_cleaners()
        if not cleaners:
            self.skipTest("Starboard's source is not here (STARBOARD_SRC)")
        plugin_cards, plugin_custom = cleaners
        plugin_cards.clean("stat", self.app.card(), strict=True)
        write(self.app, "reelix.json", {"url": "http://rx:7700", "api_key": "k"})
        self.app.connect()
        plugin_cards.clean("stat", self.app.card(), strict=True)
        page = plugin_custom.clean(self.app.sign_in())
        self.assertEqual(page["items"][0]["address"], "t" * 32)
        plugin_cards.clean("stat", manifest("themearr")["cards"][0]["example"], strict=True)

    def test_not_answering_yet(self):
        self.stand.shutdown()
        self.stand.server_close()
        self.app.APP = "http://127.0.0.1:9"
        self.app.connect()
        self.assertEqual((self.app.STATE["state"], self.app.STATE["label"]), ("waiting", "Starting"))
        self.stand = Stand({})


class Checkrr(unittest.TestCase):
    def setUp(self):
        self.stats = {"filesChecked": 4, "running": False, "unknownFileCount": 1}
        self.bad = [{"Path": "/media/movies/Broken (2002)/Broken (2002).mkv",
                     "Data": {"fileExt": ".mkv", "reacquire": False, "service": "unknown", "date": 1794926812, "reason": "not recognized"}}]
        self.stand = Stand({"/api/stats/current": self.stats, "/api/files/bad": self.bad, "/api/schedule": "2026-11-22 03:30:00 +0000 UTC"},
                           {"/api/run": None})
        self.app = load("checkrr", {"CHECKRR_URL": self.stand.url})

    def tearDown(self):
        self.stand.shutdown()
        self.stand.server_close()
        self.app._tmp.cleanup()

    def test_a_bad_file_is_listed_and_nothing_else_happens(self):
        self.app.ask()
        card = self.app.card()
        self.assertEqual((card["value"], card["status"], card["status_label"]), (1, "warning", "1 bad file"))
        page = self.app.bad_files()
        self.assertEqual(page["items"][0]["address"], "/media/movies/Broken (2002)/Broken (2002).mkv")
        self.assertEqual(page["items"][0]["group"], "Films")
        self.assertIn("Nothing was deleted", page["intro"])
        self.assertEqual([c for c in self.stand.calls if c[0] == "POST"], [], "only reads")

    def test_every_file_passed_and_not_checked_yet(self):
        self.bad.clear()
        self.app.ask()
        self.assertEqual(self.app.card()["status"], "ok")
        self.stats["filesChecked"] = 0
        self.app.ask()
        self.assertEqual(self.app.card()["status"], "idle")

    def test_answers_pass_starboards_checks(self):
        cleaners = starboard_cleaners()
        if not cleaners:
            self.skipTest("Starboard's source is not here (STARBOARD_SRC)")
        plugin_cards, plugin_custom = cleaners
        plugin_cards.clean("stat", self.app.card(), strict=True)
        self.app.ask()
        plugin_cards.clean("stat", self.app.card(), strict=True)
        plugin_custom.clean(self.app.bad_files())
        plugin_cards.clean("stat", manifest("checkrr")["cards"][0]["example"], strict=True)


if __name__ == "__main__":
    unittest.main()
