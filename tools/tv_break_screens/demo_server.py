#!/usr/bin/env python3
"""The break grids' page on made-up data, for checking and pictures (DASH-537): python3 tools/tv_break_screens/demo_server.py PORT [DATA]
Runs tv-station/app.py's own web server with two made-up channels, Comedy and Films (example titles only, nothing real, no
Jellyfin), and prints the address of the page and READY. The page itself is the real one."""
import json
import os
import sys
import tempfile
import threading
import time

here = os.path.dirname(os.path.abspath(__file__))
port = int(sys.argv[1])
data = sys.argv[2] if len(sys.argv) > 2 else tempfile.mkdtemp(prefix="tv-break-demo-")
run = os.path.join(data, "run")
os.makedirs(run, exist_ok=True)
os.makedirs(os.path.join(data, "data"), exist_ok=True)
json.dump({"station_name": "Example TV"}, open(os.path.join(run, "settings.json"), "w"))
json.dump({"url": "http://jellyfin.invalid:8096", "api_key": "k"}, open(os.path.join(run, "jellyfin.json"), "w"))
open(os.path.join(run, "key"), "w").write("sbk_example")
os.environ.update({"PLUGIN_RUN": run, "PLUGIN_DATA": os.path.join(data, "data"), "PORT": str(port), "STARBOARD_HOME_ADDRESS": f"http://127.0.0.1:{port}"})
sys.path.insert(0, os.path.join(here, "..", "..", "tv-station"))
import app  # noqa: E402
import schedule  # noqa: E402

app.later_jellyfin = lambda: None
app.refresh_soon = lambda cid: None
app.connect_jellyfin = lambda: None
now = time.time()
for name, kind, dur in (("Comedy", "Episode", 1500), ("Films", "Movie", 5400)):
    page = app.channels_post({"action": "add", "value": name}, now=now)
    cid = page["menus"][-1]["id"]
    s = app.state()
    ch = app.find(s, cid)
    lineup = [{"id": f"{name[0].lower()}{i}", "dur": dur, "title": f"{'Kestrel Valley' if kind == 'Episode' else 'Tidewater Lane'} {i}", "group": name, "s": 1, "e": i,
               "ep": f"Part {i}", "plot": "", "kind": kind, "premiere": "2020-01-01", "art": "", "backdrop": ""} for i in range(1, 9)]
    ch["eras"] = schedule.new_era(ch, lineup, now)
    app.save(s)
# Made-up files for the file lists' pictures (DASH-546): adverts, promo clips, idents and PSAs with example names only.
s = app.state()
names = {"extras": ["Spring sale", "Garden centre", "Local bakery", "Car wash", "Window cleaner", "Tidewater Cafe"],
         "clips": ["Kestrel Valley trailer", "Tidewater Lane trailer", "Weekend preview", "Station fun clip"], "idents": ["Example ident blue", "Example ident gold"],
         "psa": ["Fire safety", "Road safety", "Recycling week"]}
for role, titles in names.items():
    s["shared"][role] = [{"id": f"{role[:2]}{i}", "src": f"file:{t}.mp4", "dur": float(8 + 7 * i + (30 if role == 'psa' else 0)), "title": f"{t}.mp4", "role": role,
                          "has_audio": role != "idents" and i != 2} for i, t in enumerate(titles)]
s["channels"][0]["own"]["extras"] = [{"id": "ex-own", "src": "file:Comedy club night.mp4", "dur": 22.0, "title": "Comedy club night.mp4", "role": "extras", "has_audio": True}]
app.save(s)
print(f"http://127.0.0.1:{port}/t/{app.state()['token']}/breaks", flush=True)
print("READY", flush=True)
app.main()
