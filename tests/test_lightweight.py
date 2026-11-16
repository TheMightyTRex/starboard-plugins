"""Lightweight first (16 November 2026): what keeps the plug-ins small and quiet on a small server, and that each saving
leaves what they do unchanged.

- An idle plug-in's HTTP server wakes once a minute, not twice a second (no serve_forever() with its 0.5 s default).
- A background run that works does not write /data/_error.json to say nothing went wrong.
- Library health asks Jellyfin a page of 500 titles at a time, so a large library is never one answer of over 4 MB.
- Every Python image compiles the modules its app imports when it is built, so a start does not (read-only images).
- Direct play's cards, asked every 30 seconds, read the survey only when it, the state or the devices changed, and the
  survey is not held in memory between asks.
"""
import importlib.util
import json
import os
import re
import sys
import tempfile
import time
import unittest
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT  # noqa: E402

IDS = sorted(d for d in os.listdir(ROOT) if os.path.isfile(os.path.join(ROOT, d, "app.py")))


class Idle(unittest.TestCase):
    def test_no_server_looks_for_a_shutdown_twice_a_second(self):
        for pid in IDS + ["_shared"]:
            for name in ("app.py", "sbplugin.py"):
                path = os.path.join(ROOT, pid, name)
                if not os.path.isfile(path):
                    continue
                with open(path, encoding="utf-8") as f:
                    src = f.read()
                for call in re.findall(r"serve_forever\([^)]*\)", src):
                    self.assertIn("poll_interval", call, f"{pid}/{name}")

    def test_serve_waits_a_minute_between_looks(self):
        sys.path.insert(0, os.path.join(ROOT, "_shared"))
        try:
            sys.modules.pop("sbplugin", None)
            import sbplugin
            seen = {}

            class Fake:
                def __init__(self, address, handler):
                    seen["address"] = address

                def serve_forever(self, poll_interval=0.5):
                    seen["poll"] = poll_interval
            sbplugin.ThreadingHTTPServer = Fake
            sbplugin.serve({"/card": lambda: {}}, port=8123)
            self.assertEqual(seen["poll"], 60)
            self.assertEqual(sbplugin.POLL_SECONDS, 60)
        finally:
            sys.path.remove(os.path.join(ROOT, "_shared"))
            sys.modules.pop("sbplugin", None)


class Bytecode(unittest.TestCase):
    def test_every_python_image_compiles_what_its_app_imports(self):
        files = ["Dockerfile"] + [os.path.join(pid, "Dockerfile") for pid in IDS if os.path.isfile(os.path.join(ROOT, pid, "Dockerfile"))]
        for f in files:
            with open(os.path.join(ROOT, f), encoding="utf-8") as fh:
                src = fh.read()
            run = src.index("modulefinder.ModuleFinder")
            self.assertLess(src.index("sbplugin.py"), run, f)
            self.assertLess(run, src.index("USER "), f)  # as root, before the image's own user


class Stop(Exception):
    pass


class KeptError(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        sys.path.insert(0, os.path.join(ROOT, "_shared"))
        sys.modules.pop("sbplugin", None)
        import sbplugin
        self.sb = sbplugin
        self.sb.DATA = self.tmp.name
        self.path = os.path.join(self.tmp.name, "_error.json")

    def tearDown(self):
        sys.path.remove(os.path.join(ROOT, "_shared"))
        sys.modules.pop("sbplugin", None)
        self.tmp.cleanup()

    def run_every(self, job, runs):
        """every()'s loop in this thread, for `runs` runs, with no waiting."""
        loops = []
        self.sb.threading = type("T", (), {"Thread": lambda *a, target=None, **k: loops.append(target) or type("t", (), {"start": lambda s: None})()})
        sleeps = []

        def sleep(_):
            sleeps.append(_)
            if len(sleeps) > runs:
                raise Stop
        self.sb.time = type("time", (), {"sleep": staticmethod(sleep), "time": staticmethod(time.time)})
        self.sb.every(60, job)
        with self.assertRaises(Stop):
            loops[0]()

    def test_a_run_that_works_writes_nothing(self):
        self.run_every(lambda: None, 3)
        self.assertFalse(os.path.exists(self.path))
        self.assertEqual(self.sb.last_error(), "")

    def test_an_error_is_kept_then_cleared_once(self):
        calls = []

        def job():
            calls.append(1)
            if len(calls) == 1:
                raise ValueError("Jellyfin did not answer")
        self.run_every(job, 1)
        self.assertEqual(self.sb.last_error(), "ValueError: Jellyfin did not answer")
        self.run_every(job, 1)
        self.assertEqual(self.sb.last_error(), "")
        with open(self.path) as f:
            self.assertIsNone(json.load(f))
        before = os.stat(self.path).st_mtime_ns
        time.sleep(0.01)
        self.sb.clear_error()
        self.assertEqual(os.stat(self.path).st_mtime_ns, before)


def load_example(pid):
    """An example's app.py as a module, with sbplugin's serve() and every() doing nothing (the examples serve when
    loaded), its settings and /data in a temporary folder."""
    tmp = tempfile.TemporaryDirectory()
    for d in ("run", "data"):
        os.makedirs(os.path.join(tmp.name, d))
    with open(os.path.join(tmp.name, "run", "settings.json"), "w") as f:
        json.dump({}, f)
    os.environ["PLUGIN_RUN"], os.environ["PLUGIN_DATA"] = os.path.join(tmp.name, "run"), os.path.join(tmp.name, "data")
    sys.path.insert(0, os.path.join(ROOT, "_shared"))
    sys.modules.pop("sbplugin", None)
    import sbplugin
    sbplugin.serve = sbplugin.every = lambda *a, **k: None
    spec = importlib.util.spec_from_file_location(f"app_{pid.replace('-', '_')}", os.path.join(ROOT, pid, "app.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sys.path.remove(os.path.join(ROOT, "_shared"))
    sys.modules.pop("sbplugin", None)
    mod._tmp = tmp
    return mod


class LibraryHealthPages(unittest.TestCase):
    def setUp(self):
        self.app = load_example("library-health")
        self.asked = []
        titles = [{"Name": f"Film {i}", "ProductionYear": None if i % 7 == 0 else 2000, "Overview": "" if i % 11 == 0 else "x",
                   "ImageTags": {} if i % 13 == 0 else {"Primary": "a"}} for i in range(1201)]
        self.titles = titles

        def jellyfin(path):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(path).query)
            self.asked.append(q)
            start, limit = int(q["StartIndex"][0]), int(q["Limit"][0])
            return {"Items": titles[start:start + limit], "TotalRecordCount": len(titles)}
        self.app.jellyfin = jellyfin

    def tearDown(self):
        self.app._tmp.cleanup()

    def test_a_page_at_a_time_with_the_same_result(self):
        said = self.app.check()
        self.assertEqual([int(q["StartIndex"][0]) for q in self.asked], [0, 500, 1000])
        self.assertTrue(all(q["Limit"] == ["500"] for q in self.asked))
        self.assertEqual(self.asked[0]["IncludeItemTypes"], ["Movie,Series"])
        self.assertEqual(self.asked[0]["Fields"], ["Overview,ProductionYear"])
        want = [t for t in self.titles if not t["ProductionYear"] or not t["Overview"] or "Primary" not in t["ImageTags"]]
        r = self.app.remember("result")
        self.assertEqual(r["total"], 1201)
        self.assertEqual(len(r["bad"]), len(want))
        self.assertEqual(r["bad"][0], {"title": "Film 0", "detail": "No poster, no description, no year"})
        self.assertEqual(said["said"], f"{len(want):,} titles to fix of 1,201")

    def test_a_short_answer_is_the_last_page(self):
        self.titles[:] = self.titles[:3]
        self.app.check()
        self.assertEqual(len(self.asked), 1)
        self.assertEqual(self.app.remember("result")["total"], 3)


def load_direct_play(values):
    tmp = tempfile.mkdtemp(prefix="sb-dp-light-")
    run, data = os.path.join(tmp, "run"), os.path.join(tmp, "data")
    media = {k: os.path.join(tmp, "media", k) for k in ("movies", "tv")}
    for d in (run, data, *media.values()):
        os.makedirs(d)
    with open(os.path.join(run, "settings.json"), "w") as f:
        json.dump(values, f)
    os.environ.update(PLUGIN_RUN=run, PLUGIN_DATA=data, DIRECT_PLAY_MOVIES=media["movies"], DIRECT_PLAY_TV=media["tv"])
    sys.path.insert(0, os.path.join(ROOT, "direct-play"))
    for name in ("sbplugin", "app_dp_light"):
        sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location("app_dp_light", os.path.join(ROOT, "direct-play", "app.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sys.path.pop(0)
    mod._runp = run
    return mod


class DirectPlayCards(unittest.TestCase):
    def setUp(self):
        self.app = load_direct_play({"when": "any", "device_roku_express": True})
        recs = []
        for i in range(40):
            r = {"path": f"/media/movies/F{i:02d}/F{i:02d}.mkv", "size": 1000 + i, "mtime": 1, "container": "mkv", "dur": 60,
                 "vcodec": "h264", "h": 1080, "w": 1920, "tenbit": False, "mbps": 4.0, "audio": ["aac"]}
            if i % 4 == 0:
                r["audio"] = ["dts"]
            elif i % 5 == 0:
                r.update(container="avi", path=r["path"][:-4] + ".avi")
            recs.append(r)
        self.recs = recs
        self.app.keep("survey", recs)
        s = self.app._state()
        s["surveyed"] = time.time()
        self.app.keep("state", s)
        self.reads = 0
        real = self.app.remember

        def counting(name, default=None):
            self.reads += name == "survey"
            return real(name, default)
        self.app.remember = counting

    def full(self):
        todo = self.app.todo_list()
        return len(todo), todo[:self.app.HEAD]

    def test_the_head_is_the_full_list_cut_short(self):
        self.assertEqual(self.app.todo_head(), self.full())
        self.assertEqual(self.app.todo_head()[0], 16)

    def test_cards_read_the_survey_once_while_nothing_changes(self):
        first = (self.app.card(), self.app.summary_card())
        n = self.reads
        self.assertEqual(n, 1)
        for _ in range(5):
            self.assertEqual((self.app.card()["items"], self.app.summary_card()), (first[0]["items"], first[1]))
        self.assertEqual(self.reads, n)
        self.assertEqual(first[1]["note"], "0 files fixed, 16 files to do")
        want = [f"Next: {self.app.title(r['path'])}" for r in self.app.todo_list()[:4]]
        self.assertEqual([i["title"] for i in first[0]["items"][1:5]], want)

    def test_a_new_survey_a_failure_or_new_devices_count_again(self):
        self.app.card()
        self.app.keep("survey", self.recs[:8])
        self.assertEqual(self.app.todo_head(), self.full())
        self.assertEqual(self.app.todo_head()[0], 3)
        s = self.app._state()
        s["failed"]["/media/movies/F00/F00.mkv"] = {"why": "error: x", "size": 1000, "mtime": 1}
        self.app.keep("state", s)
        self.assertEqual(self.app.todo_head()[0], 2)
        with open(os.path.join(self.app._runp, "settings.json"), "w") as f:
            json.dump({"when": "any", "device_shield": True}, f)
        self.assertEqual(self.app.todo_head(), self.full())

    def test_the_survey_is_not_kept_in_memory(self):
        self.app.card()
        self.assertFalse(any(isinstance(v, dict) and isinstance(v.get("recs"), list) and v["recs"] for v in vars(self.app).values()))
        self.assertLessEqual(len(self.app._head["head"]), self.app.HEAD)


if __name__ == "__main__":
    unittest.main()
