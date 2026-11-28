"""A made-up TV channel plug-in for the accessibility checks: the real app.py answering with made-up Jellyfin data (nothing real is read).
Usage: serve.py PORT DATA_DIR. Prints "token <token>" and "READY" when it answers."""
import json
import os
import sys

PORT, DATA = int(sys.argv[1]), os.path.abspath(sys.argv[2])
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
os.makedirs(DATA + "/run", exist_ok=True)
os.makedirs(DATA + "/data", exist_ok=True)
os.environ["PLUGIN_RUN"], os.environ["PLUGIN_DATA"] = DATA + "/run", DATA + "/data"
os.environ["STARBOARD_HOME_ADDRESS"] = f"http://127.0.0.1:{PORT}"
json.dump({"station_name": "Home TV"}, open(DATA + "/run/settings.json", "w"))
json.dump({"url": "http://jellyfin.invalid:8096", "api_key": "k"}, open(DATA + "/run/jellyfin.json", "w"))
open(DATA + "/run/key", "w").write("sbk_test")
sys.path.insert(0, os.path.join(ROOT, "tv-station"))
sys.path.insert(0, os.path.join(ROOT, "_shared"))
import app  # noqa: E402

SID, FID = "a" * 32, "c" * 32


def eps(n):
    return [{"id": f"{SID[:30]}{i:02d}", "dur": 1500, "title": "Harbour lights", "group": SID, "kind": "Episode", "s": 1, "e": i,
             "ep": f"Part {i}", "plot": "", "art": SID, "backdrop": SID} for i in range(1, n + 1)]


app.library.search = lambda jf, kind, words: [(SID, "Harbour lights")] if kind == "series" else [(FID, "A quiet harbour")]
app.library.lineup = lambda jf, src: eps(12) if src[0]["kind"] == "series" else [
    {"id": FID, "dur": 6000, "title": "A quiet harbour", "group": FID, "kind": "Movie", "year": 1999}]
app.jf = lambda *a, **k: {}
app.later_jellyfin = lambda: None
app.refresh_soon = lambda cid: None
if not app.state()["channels"]:
    app.channels_post({"action": "add", "value": "Comedy"})
print("token", app.state()["token"], flush=True)
from http.server import ThreadingHTTPServer  # noqa: E402
srv = ThreadingHTTPServer(("127.0.0.1", PORT), app.Handler)
print("READY", flush=True)
srv.serve_forever()
