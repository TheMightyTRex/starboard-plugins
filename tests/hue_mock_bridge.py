#!/usr/bin/env python3
"""A made-up Hue bridge for the Philips Hue plug-in's tests and pictures: HTTPS with its own certificate, the link
button, CLIP v2 resources (lights, rooms, zones, devices, scenes, grouped lights, connectivity) and the version 1
schedules, rules, sensors and config. Nothing real is touched.

    python3 tests/hue_mock_bridge.py [port] [--press-after SECONDS] [--paired-key KEY]

Run on its own, it prints READY and serves until stopped. In a test, MockBridge().start() gives the address."""
import copy
import json
import os
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def rid(name):
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{name}.hue.invalid"))


# name, room, archetype, kind (colour, ambiance, white, plug), on, brightness, colour, reachable
LIGHTS = [("Ceiling", "Kitchen", "ceiling_round", "colour", True, 80, ("ct", 370), True),
          ("Spots", "Kitchen", "spot_bulb", "ambiance", True, 80, ("ct", 250), True),
          ("Under cupboard", "Kitchen", "hue_lightstrip", "colour", False, 40, ("xy", (0.675, 0.322)), True),
          ("Floor lamp", "Lounge", "floor_shade", "colour", True, 35, ("xy", (0.2725, 0.1096)), True),
          ("Table lamp", "Lounge", "table_shade", "white", False, 60, None, True),
          ("Christmas tree", "Lounge", "plug", "plug", False, None, None, True),
          ("Bedside", "Bedroom", "candle_bulb", "ambiance", False, 20, ("ct", 454), True),
          ("Porch", "Hall", "classic_bulb", "white", False, 100, None, False)]
ROOMS = [("Kitchen", "kitchen", 1), ("Lounge", "living_room", 2), ("Bedroom", "bedroom", 3), ("Hall", "hallway", 4)]
ZONES = [("Downstairs", ["Ceiling", "Spots", "Floor lamp", "Table lamp", "Porch"], 5), ("Reading corner", ["Floor lamp", "Table lamp"], 6)]
SCENES = [("Bright", "Kitchen"), ("Cooking", "Kitchen"), ("Relax", "Kitchen"), ("Film night", "Lounge"), ("Read", "Lounge"),
          ("Relax", "Lounge"), ("Nightlight", "Bedroom"), ("Wake up", "Bedroom"), ("Welcome home", "Downstairs")]


def make_cert(folder):
    key, crt = os.path.join(folder, "bridge.key"), os.path.join(folder, "bridge.crt")
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "2", "-subj", "/CN=001788fffe123456",
                    "-keyout", key, "-out", crt], check=True, capture_output=True)
    return key, crt


class State:
    def __init__(self, paired_key=""):
        self.keys = {paired_key} if paired_key else set()
        self.pressed = False
        self.press_at = None
        self.calls = []
        self.schedules, self.rules = {}, {}
        self.next_id = 1
        self.daylight = False
        self.localtime = "2026-11-20T18:05:00"
        self.res = []
        lights, devices, conn = {}, {}, []
        for i, (name, room, arche, kind, on, bri, col, reach) in enumerate(LIGHTS, start=1):
            lid, did, zid = rid(f"light-{name}"), rid(f"device-{name}"), rid(f"zigbee-{name}")
            light = {"id": lid, "id_v1": f"/lights/{i}", "type": "light", "owner": {"rid": did, "rtype": "device"},
                     "metadata": {"name": name, "archetype": arche}, "on": {"on": on}, "mode": "normal"}
            if bri is not None:
                light["dimming"] = {"brightness": float(bri), "min_dim_level": 0.5}
            if kind in ("colour", "ambiance"):
                light["color_temperature"] = {"mirek": col[1] if col and col[0] == "ct" else None,
                                              "mirek_valid": bool(col and col[0] == "ct"),
                                              "mirek_schema": {"mirek_minimum": 153, "mirek_maximum": 500}}
            if kind == "colour":
                xy = col[1] if col and col[0] == "xy" else (0.4599, 0.4106)
                light["color"] = {"xy": {"x": xy[0], "y": xy[1]}, "gamut_type": "C"}
            lights[name] = light
            devices[name] = {"id": did, "type": "device", "metadata": {"name": name, "archetype": arche},
                             "services": [{"rid": lid, "rtype": "light"}, {"rid": zid, "rtype": "zigbee_connectivity"}]}
            conn.append({"id": zid, "type": "zigbee_connectivity", "owner": {"rid": did, "rtype": "device"},
                         "status": "connected" if reach else "connectivity_issue"})
        self.res += list(lights.values()) + list(devices.values()) + conn
        groups = []
        for name, arche, n in ROOMS:
            gl = {"id": rid(f"grouped-{name}"), "id_v1": f"/groups/{n}", "type": "grouped_light", "on": {"on": False}, "dimming": {"brightness": 0.0}}
            room = {"id": rid(f"room-{name}"), "id_v1": f"/groups/{n}", "type": "room", "metadata": {"name": name, "archetype": arche},
                    "children": [{"rid": devices[x[0]]["id"], "rtype": "device"} for x in LIGHTS if x[1] == name],
                    "services": [{"rid": gl["id"], "rtype": "grouped_light"}]}
            gl["owner"] = {"rid": room["id"], "rtype": "room"}
            groups.append((room, gl, [lights[x[0]] for x in LIGHTS if x[1] == name]))
        for name, members, n in ZONES:
            gl = {"id": rid(f"grouped-{name}"), "id_v1": f"/groups/{n}", "type": "grouped_light", "on": {"on": False}, "dimming": {"brightness": 0.0}}
            zone = {"id": rid(f"zone-{name}"), "id_v1": f"/groups/{n}", "type": "zone", "metadata": {"name": name, "archetype": "downstairs"},
                    "children": [{"rid": lights[x]["id"], "rtype": "light"} for x in members], "services": [{"rid": gl["id"], "rtype": "grouped_light"}]}
            gl["owner"] = {"rid": zone["id"], "rtype": "zone"}
            groups.append((zone, gl, [lights[x] for x in members]))
        home_gl = {"id": rid("grouped-home"), "id_v1": "/groups/0", "type": "grouped_light", "on": {"on": True}, "dimming": {"brightness": 60.0}}
        home = {"id": rid("bridge-home"), "type": "bridge_home", "children": [{"rid": r[0]["id"], "rtype": "room"} for r in groups if r[0]["type"] == "room"],
                "services": [{"rid": home_gl["id"], "rtype": "grouped_light"}]}
        home_gl["owner"] = {"rid": home["id"], "rtype": "bridge_home"}
        self.groups = groups + [(home, home_gl, list(lights.values()))]
        self.res += [x for g in groups for x in g[:2]] + [home, home_gl]
        for i, (name, group) in enumerate(SCENES, start=1):
            g = next(x for x in self.groups if (x[0].get("metadata") or {}).get("name") == group)
            self.res.append({"id": rid(f"scene-{group}-{name}"), "id_v1": f"/scenes/S{i:02d}abc", "type": "scene", "metadata": {"name": name},
                             "group": {"rid": g[0]["id"], "rtype": g[0]["type"]}, "status": {"active": "static" if (name, group) == ("Relax", "Kitchen") else "inactive"}})
        self.lights = lights
        self.sync_groups()

    def sync_groups(self):
        for _, gl, members in self.groups:
            on = [m for m in members if m["on"]["on"]]
            gl["on"] = {"on": bool(on)}
            dims = [m["dimming"]["brightness"] for m in on if m.get("dimming")]
            gl["dimming"] = {"brightness": round(sum(dims) / len(dims), 1) if dims else 0.0}

    def find(self, rtype, rid_):
        return next((r for r in self.res if r["type"] == rtype and r["id"] == rid_), None)

    def apply(self, light, body):
        if "on" in body:
            light["on"] = {"on": bool(body["on"]["on"])}
        if "dimming" in body and light.get("dimming"):
            light["dimming"]["brightness"] = float(body["dimming"]["brightness"])
        if "color_temperature" in body and light.get("color_temperature"):
            light["color_temperature"].update(mirek=body["color_temperature"]["mirek"], mirek_valid=True)
        if "color" in body and light.get("color"):
            light["color"]["xy"] = dict(body["color"]["xy"])
            if light.get("color_temperature"):
                light["color_temperature"].update(mirek=None, mirek_valid=False)

    def put(self, rtype, rid_, body):
        r = self.find(rtype, rid_)
        if not r:
            return 404, {"errors": [{"description": "Not found"}], "data": []}
        if rtype == "light":
            self.apply(r, body)
        elif rtype == "grouped_light":
            members = next(g[2] for g in self.groups if g[1]["id"] == rid_)
            for m in members:
                self.apply(m, body)
        elif rtype == "scene" and body.get("recall"):
            group = next(g for g in self.groups if g[0]["id"] == r["group"]["rid"])
            for s in self.res:
                if s["type"] == "scene" and s["group"]["rid"] == r["group"]["rid"]:
                    s["status"] = {"active": "static" if s is r else "inactive"}
            for m in group[2]:
                self.apply(m, {"on": {"on": True}, "dimming": {"brightness": 50}})
        self.sync_groups()
        return 200, {"errors": [], "data": [{"rid": rid_, "rtype": rtype}]}


class MockBridge:
    def __init__(self, port=0, paired_key="", press_after=None):
        self.state = State(paired_key)
        self.press_after = press_after
        self.started = time.time()
        self.tmp = tempfile.TemporaryDirectory()
        key, crt = make_cert(self.tmp.name)
        state, outer = self.state, self

        class Handler(BaseHTTPRequestHandler):
            def _body(self):
                n = int(self.headers.get("Content-Length") or 0)
                return json.loads(self.rfile.read(n) or b"{}") if n else {}

            def _send(self, status, body):
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _go(self, method):
                path = self.path.split("?")[0]
                body = self._body() if method in ("POST", "PUT") else None
                state.calls.append((method, path, body))
                if outer.press_after is not None and time.time() - outer.started > outer.press_after:
                    state.pressed = True
                if path == "/_press":  # the pictures press the link button here, as a person would on the bridge
                    state.pressed = True
                    return self._send(200, {"pressed": True})
                if path == "/api/0/config" and method == "GET":
                    return self._send(200, {"name": "Hue Bridge", "bridgeid": "001788FFFE123456", "modelid": "BSB002",
                                            "swversion": "1968096020", "apiversion": "1.68.0"})
                if path == "/api" and method == "POST":
                    if not state.pressed:
                        return self._send(200, [{"error": {"type": 101, "address": "", "description": "link button not pressed"}}])
                    k = "made-up-key-" + uuid.uuid4().hex[:12]
                    state.keys.add(k)
                    return self._send(200, [{"success": {"username": k, "clientkey": "C0FFEE"}}])
                if path.startswith("/clip/v2/"):
                    if self.headers.get("hue-application-key") not in state.keys:
                        return self._send(403, {"errors": [{"description": "unauthorized user"}]})
                    parts = path.split("/")[3:]
                    if method == "GET" and parts == ["resource"]:
                        return self._send(200, {"errors": [], "data": copy.deepcopy(state.res)})
                    if method == "PUT" and len(parts) == 3:
                        return self._send(*state.put(parts[1], parts[2], body))
                    return self._send(404, {"errors": [{"description": "Not found"}]})
                if path.startswith("/api/"):
                    parts = path.split("/")[2:]
                    if parts[0] not in state.keys:
                        return self._send(200, [{"error": {"type": 1, "description": "unauthorized user"}}])
                    return self._send(200, self._v1(method, parts[1:], body))
                return self._send(404, {"error": "not found"})

            def _v1(self, method, parts, body):
                if parts == ["config"]:
                    return {"name": "Hue Bridge", "localtime": state.localtime, "bridgeid": "001788FFFE123456"}
                if parts and parts[0] == "sensors":
                    sensor = {"type": "Daylight", "name": "Daylight", "config": {"configured": True, "on": True},
                              "state": {"daylight": state.daylight}}
                    return {"1": sensor} if len(parts) == 1 else sensor
                if parts and parts[0] in ("schedules", "rules"):
                    store = state.schedules if parts[0] == "schedules" else state.rules
                    if method == "GET" and len(parts) == 1:
                        return store
                    if method == "POST":
                        sid = str(state.next_id)
                        state.next_id += 1
                        store[sid] = {**body, "status": body.get("status", "enabled")}
                        return [{"success": {"id": sid}}]
                    sid = parts[1] if len(parts) > 1 else ""
                    if sid not in store:
                        return [{"error": {"type": 3, "description": f"resource, /{parts[0]}/{sid}, not available"}}]
                    if method == "GET":
                        return store[sid]
                    if method == "PUT":
                        store[sid].update(body)
                        return [{"success": {f"/{parts[0]}/{sid}/{k}": v} for k, v in body.items()}]
                    if method == "DELETE":
                        del store[sid]
                        return [{"success": f"/{parts[0]}/{sid} deleted"}]
                return [{"error": {"type": 4, "description": "method not available"}}]

            def do_GET(self):  # noqa: N802
                self._go("GET")

            def do_POST(self):  # noqa: N802
                self._go("POST")

            def do_PUT(self):  # noqa: N802
                self._go("PUT")

            def do_DELETE(self):  # noqa: N802
                self._go("DELETE")

            def log_message(self, *a):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(crt, key)
        self.server.socket = ctx.wrap_socket(self.server.socket, server_side=True)
        self.address = f"127.0.0.1:{self.server.server_address[1]}"

    def start(self):
        threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True).start()
        return self

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()


if __name__ == "__main__":
    args = sys.argv[1:]
    port = int(args[0]) if args and args[0].isdigit() else 8443
    press = float(args[args.index("--press-after") + 1]) if "--press-after" in args else None
    key = args[args.index("--paired-key") + 1] if "--paired-key" in args else ""
    b = MockBridge(port, key, press).start()
    print(f"READY {b.address}", flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        b.stop()
