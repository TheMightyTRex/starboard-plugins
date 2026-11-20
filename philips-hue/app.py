"""Philips Hue: your Hue lights in Starboard, through the Hue bridge on your home network. Nothing goes to the Hue cloud.

Every screen is a list Starboard draws itself (custom settings), so each control is Starboard's own, from the shared
design system, with its focus and spoken summaries. Tabs:

- Bridge: find or give the bridge's address, then press its link button to pair (the page waits for it).
- Rooms, Zones, Device types: the same lights grouped three ways. Each light can be turned on and off, dimmed and
  given a colour or a white; each room, zone and type has a switch for every light in it, and a brightness and colour.
- Scenes: each room's and zone's scenes, to recall.
- Schedules: timed actions written in words, kept on the bridge so they run while this plug-in rests.
- When something plays: a scene to run when someone starts playing something in Jellyfin (Starboard's event).

It rests when idle ("start": "when_needed"): it reads the bridge only when Starboard asks it something.
"""
import datetime as dt
import os
import re
import threading
import time
import uuid

import hue
import words
from sbplugin import band, keep, remember, serve, setting

CACHE_SECONDS = 3
_cache = {"at": 0.0, "home": None}
_lock = threading.Lock()
PAIR_SECONDS = 90  # how long the page waits for the link button


# The bridge ---------------------------------------------------------------------------------------------------
def paired():
    b = remember("bridge") or {}
    return b if b.get("key") and b.get("address") else None


def bridge():
    b = paired()
    if not b:
        raise hue.BridgeError("Pair a bridge first, on Bridge, then reload this page")
    return hue.Bridge(b["address"], b["key"], b.get("fingerprint", ""))


class Home:
    """Everything on the bridge from one answer, joined up: which lights are in which room and zone, each group's own
    grouped light, which scenes belong where, and which lights can be reached."""

    def __init__(self, data):
        self.by = {}
        for r in data:
            self.by.setdefault(r.get("type"), {})[r.get("id")] = r
        self.lights = self.by.get("light", {})
        devices = self.by.get("device", {})
        conn = self.by.get("zigbee_connectivity", {})
        self.reach = {}
        self.light_device = {}
        for d in devices.values():
            status = next((conn[s["rid"]].get("status") for s in d.get("services") or [] if s.get("rtype") == "zigbee_connectivity" and s.get("rid") in conn), "connected")
            for s in d.get("services") or []:
                if s.get("rtype") == "light":
                    self.reach[s["rid"]] = status == "connected"
                    self.light_device[s["rid"]] = d
        self.groups = {}  # room and zone id -> {"res", "lights", "grouped"}
        for rtype in ("room", "zone"):
            for g in self.by.get(rtype, {}).values():
                lids = []
                for c in g.get("children") or []:
                    if c.get("rtype") == "light":
                        lids.append(c["rid"])
                    elif c.get("rtype") == "device" and c.get("rid") in devices:
                        lids += [s["rid"] for s in devices[c["rid"]].get("services") or [] if s.get("rtype") == "light"]
                grouped = next((s["rid"] for s in g.get("services") or [] if s.get("rtype") == "grouped_light"), None)
                self.groups[g["id"]] = {"res": g, "lights": [x for x in dict.fromkeys(lids) if x in self.lights], "grouped": grouped}
        home = next(iter(self.by.get("bridge_home", {}).values()), {})
        self.home_grouped = next((s["rid"] for s in home.get("services") or [] if s.get("rtype") == "grouped_light"), None)
        self.scenes = {}
        for s in self.by.get("scene", {}).values():
            self.scenes.setdefault((s.get("group") or {}).get("rid"), []).append(s)
        for v in self.scenes.values():
            v.sort(key=lambda s: name(s).lower())

    def rooms(self, rtype="room"):
        return sorted((g for g in self.groups.values() if g["res"].get("type") == rtype), key=lambda g: name(g["res"]).lower())

    def room_of(self, lid):
        return next((g for g in self.rooms("room") if lid in g["lights"]), None)

    def light_name(self, lid):
        light = self.lights[lid]
        return (light.get("metadata") or {}).get("name") or name(self.light_device.get(lid) or {}) or "A light"

    def grouped(self, rid):
        return self.by.get("grouped_light", {}).get(rid) or {}

    def on_count(self, lids):
        return sum(1 for x in lids if (self.lights[x].get("on") or {}).get("on"))


def name(res):
    return ((res or {}).get("metadata") or {}).get("name") or ""


def home(fresh=False):
    with _lock:
        if fresh or not _cache["home"] or time.monotonic() - _cache["at"] > CACHE_SECONDS:
            _cache["home"] = Home(bridge().resources())
            _cache["at"] = time.monotonic()
        return _cache["home"]


def forget_cache():
    _cache["at"] = 0.0


# Bridge tab: find, pair, check, forget ------------------------------------------------------------------------
_found = {"at": 0.0, "list": []}


def found_bridges():
    if time.monotonic() - _found["at"] > 60:
        _found["list"], _found["at"] = hue.discover(), time.monotonic()
    return _found["list"]


def start_pairing(address):
    b = hue.Bridge(address)
    cfg = b.config()
    keep("pairing", {"address": b.address, "fingerprint": b.seen, "name": cfg.get("name") or "Hue bridge",
                     "bridgeid": cfg.get("bridgeid", ""), "model": cfg.get("modelid", ""), "software": cfg.get("swversion", ""),
                     "started": time.time()})
    return cfg.get("name") or "Hue bridge"


def try_pairing():
    """While pairing: one try each time the page asks (every 3 seconds). Returns the notice to show, or None."""
    p = remember("pairing") or {}
    if not p.get("address") or p.get("dismissed"):
        return None
    if p.get("result") == "paired":
        return {"id": "paired", "tone": "success", "title": f"Paired with {p['name']}",
                "text": "Reload this page to fill in Rooms, Zones, Device types, Scenes and Schedules. The key stays on this server and nothing goes to the Hue cloud.",
                "dismiss": True}
    left = PAIR_SECONDS - (time.time() - p["started"])
    if p.get("result") == "timed_out" or left <= 0:
        if p.get("result") != "timed_out":
            keep("pairing", {**p, "result": "timed_out"})
        return {"id": "timed_out", "tone": "warning", "title": "The link button was not pressed in time",
                "text": f"Choose Activate beside {p['name']} to try again, then press the round button on top of the bridge.", "dismiss": True}
    b = hue.Bridge(p["address"], fingerprint=p["fingerprint"])
    try:
        key = b.pair()
    except hue.LinkButton:
        return {"id": "pairing", "tone": "info", "title": f"Press the link button on {p['name']}",
                "text": f"The round button on top of the bridge. Starboard pairs as soon as it is pressed: {round(left)} seconds left.",
                "progress": max(1, min(99, round(100 * (PAIR_SECONDS - left) / PAIR_SECONDS)))}
    except hue.BridgeError as e:
        return {"id": "pairing", "tone": "warning", "title": f"Waiting for {p['name']}", "text": f"{e}. Starboard tries again in a moment.",
                "progress": max(1, min(99, round(100 * (PAIR_SECONDS - left) / PAIR_SECONDS)))}
    keep("bridge", {"address": p["address"], "key": key, "fingerprint": p["fingerprint"], "name": p["name"],
                    "bridgeid": p.get("bridgeid", ""), "model": p.get("model", ""), "software": p.get("software", ""),
                    "paired": dt.date.today().isoformat()})
    keep("pairing", {**p, "result": "paired"})
    forget_cache()
    return try_pairing()


def bridge_screen():
    notices = [n for n in [try_pairing()] if n]
    b = paired()
    p = remember("pairing") or {}
    items = []
    if b:
        when = dt.date.fromisoformat(b["paired"]) if b.get("paired") else None
        items.append({"id": "paired", "title": b["name"], "group": "Paired",
                      "detail": f"At {b['address']}" + (f", paired on {when.day} {words.MONTHS[when.month - 1]} {when.year}" if when else ""),
                      "state": "ok", "state_label": "Paired", "actions": ["test", "remove"]})
    else:
        waiting = p.get("address") and not p.get("result")
        seen = set()
        if p.get("address"):
            seen.add(p["address"])
            items.append({"id": f"bridge:{p['address']}", "title": p["name"], "group": "Not paired yet", "on": False,
                          "detail": f"At {p['address']}", "state": "warning" if waiting else "off",
                          "state_label": "Waiting for the button" if waiting else "Not paired", "actions": [] if waiting else ["toggle"]})
        for f in found_bridges():
            if f["address"] in seen:
                continue
            items.append({"id": f"bridge:{f['address']}", "title": f.get("name") or "Hue bridge", "group": "Found on your network",
                          "detail": f"At {f['address']}", "on": False, "state": "off", "state_label": "Not paired", "actions": ["toggle"]})
    intro = ("Paired: this plug-in reaches the bridge on your home network with its own key. Nothing goes to the Hue cloud."
             if b else "Give the bridge's address, or choose Activate beside a bridge found on your network. Then press the round "
             "link button on top of the bridge: this page waits for it.")
    out = {"type": "list", "title": "Bridge", "intro": intro, "items": items, "notices": notices}
    if not b:
        out["add"] = {"label": "Pair with a bridge", "placeholder": "192.168.1.20",
                      "hint": "Its address on your home network. In the Hue app: Settings, then My Hue system, then your bridge, then IP address."}
    return out


def bridge_post(body):
    action, rid = body.get("action"), str(body.get("id") or "")
    said = ""
    if action == "add":
        name_ = start_pairing(hue.clean_address(body.get("value")))
        said = f"Found {name_}. Press the round link button on top of the bridge now"
    elif action == "toggle" and rid.startswith("bridge:"):
        name_ = start_pairing(rid.split(":", 1)[1])
        said = f"Press the round link button on top of {name_} now"
    elif action in ("test", "test_all") and paired():
        said = check_bridge()
    elif action == "remove" and rid == "paired":
        b = paired()
        keep("bridge", {})
        keep("pairing", {})
        forget_cache()
        said = f"Forgot {b['name'] if b else 'the bridge'}. Its lights, scenes and schedules stay on the bridge"
    elif action == "dismiss" and (remember("pairing") or {}).get("address"):
        keep("pairing", {**remember("pairing"), "dismissed": True})
    out = bridge_screen()
    return {**out, "said": said} if said else out


# Rooms, Zones and Device types --------------------------------------------------------------------------------
TABS = {"rooms": ("Rooms", "room"), "zones": ("Zones", "zone"), "types": ("Device types", None)}


def menus_for(h, tab):
    """The menus of a tab: [(menu id, title, light ids, grouped light id or None)]."""
    if tab == "types":
        kinds = {}
        for lid in h.lights:
            kinds.setdefault(words.type_of(h.lights[lid]), []).append(lid)
        order = [t for t, _ in words.TYPES] + ["Other lights"]
        return [(f"type:{t}", t, sorted(lids, key=lambda x: h.light_name(x).lower()), None) for t, lids in sorted(kinds.items(), key=lambda kv: order.index(kv[0]))]
    out = [(g["res"]["id"], name(g["res"]), g["lights"], g["grouped"]) for g in h.rooms(TABS[tab][1])]
    if tab == "rooms":
        loose = [x for x in h.lights if not h.room_of(x)]
        if loose:
            out.append(("room:none", "Not in a room", sorted(loose, key=lambda x: h.light_name(x).lower()), None))
    return out


def light_rows(h, menu, lid):
    light = h.lights[lid]
    reach = h.reach.get(lid, True)
    on = bool((light.get("on") or {}).get("on"))
    nm = h.light_name(lid)
    kind = words.kind_of(light)
    row = {"id": f"light:{menu}:{lid}", "title": nm, "group": "Lights", "on": on,
           "detail": f"{words.light_words(light, reach)}. {words.KIND_WORDS[kind]}",
           "state": "problem" if not reach else "ok" if on else "off",
           "state_label": "Not reachable" if not reach else "On" if on else "Off",
           # Kept for a light that cannot be reached, as in the Hue app: the bridge acts on it when it is back
           "actions": ["toggle"]}
    if reach and light.get("dimming"):
        row["choice"] = {"label": "Brightness", "value": words.nearest_brightness(light["dimming"].get("brightness"), on), "options": words.brightness_options()}
    rows = [row]
    options = words.colour_options(kind)
    if reach and options:
        now = words.colour_of(light)
        rows.append({"id": f"colour:{menu}:{lid}", "title": f"{nm} colour", "group": "Lights", "on": on,
                     "detail": f"Now {words.NAMES[now].lower()}" if now else "Choose a colour or a white",
                     "state": "ok" if on else "off", "state_label": words.NAMES.get(now, "Not set"),
                     "choice": {"label": "Colour", "value": now or options[0][0], "options": options}})
    return rows


def group_rows(h, menu, title, lids, grouped):
    """The whole room's (zone's, type's) brightness and colour, for every light in it at once."""
    if not lids:
        return []
    reach = [x for x in lids if h.reach.get(x, True)]
    on = h.on_count(lids)
    dims = [h.lights[x]["dimming"]["brightness"] for x in reach if (h.lights[x].get("on") or {}).get("on") and h.lights[x].get("dimming")]
    g = h.grouped(grouped) if grouped else {}
    bri = (g.get("dimming") or {}).get("brightness") if g else (sum(dims) / len(dims) if dims else None)
    rows = []
    where = f"in {title}" if not menu.startswith("type:") else f"of this type ({title.lower()})"
    if any(h.lights[x].get("dimming") for x in lids):
        rows.append({"id": f"gbri:{menu}", "title": f"Every light {where}", "group": "Every light at once", "on": on > 0,
                     "detail": f"{on} of {len(lids)} on" + (f", at {max(1, round(bri))}%" if bri and on else ""),
                     "state": "ok" if on else "off", "state_label": f"{on} of {len(lids)} on",
                     "choice": {"label": "Brightness", "value": words.nearest_brightness(bri, on > 0), "options": words.brightness_options()}})
    kinds = {words.kind_of(h.lights[x]) for x in lids}
    options = words.colour_options("colour" if "colour" in kinds else "ambiance" if "ambiance" in kinds else "")
    if options:
        shown = {words.colour_of(h.lights[x]) for x in reach if (h.lights[x].get("on") or {}).get("on")} - {""}
        now = next(iter(shown)) if len(shown) == 1 else ""
        rows.append({"id": f"gcol:{menu}", "title": f"Every {'colour' if 'colour' in kinds else 'white ambiance'} light {where}",
                     "group": "Every light at once", "on": on > 0, "state": "ok" if on else "off",
                     "detail": f"Now {words.NAMES[now].lower()}" if now else "Showing different colours" if len(shown) > 1 else "Choose a colour or a white",
                     "state_label": words.NAMES[now] if now else "Mixed" if len(shown) > 1 else "Not set",
                     "choice": {"label": "Colour", "value": now or options[0][0], "options": options}})
    return rows


def lights_screen(tab):
    title = TABS[tab][0]
    try:
        h = home()
    except hue.BridgeError as e:
        return {"type": "list", "title": title, "items": [], "notices": [{"id": "bridge", "tone": "warning", "title": str(e)}]}
    menus, items, bulk = [], [], []
    for mid, mtitle, lids, grouped in menus_for(h, tab):
        on = h.on_count(lids)
        g = h.grouped(grouped) if grouped else {}
        bri = (g.get("dimming") or {}).get("brightness")
        menus.append({"id": mid, "title": mtitle, "detail": "No lights" if not lids else f"At {max(1, round(bri))}%" if on and bri else ""})
        if lids:
            bulk.append({"id": f"bulk:{mid}", "label": f"Every light in {mtitle}" if tab != "types" else f"Every light: {mtitle.lower()}",
                         "kind": "", "on": on, "total": len(lids), "active": on > 0, "menu": mid,
                         "hint": f"{on} of {len(lids)} lights on. Deactivate it and every one goes off"})
        items += [{**r, "menu": mid} for r in group_rows(h, mid, mtitle, lids, grouped)]
        for lid in lids:
            items += [{**r, "menu": mid} for r in light_rows(h, mid, lid)]
    if h.lights:
        on = h.on_count(list(h.lights))
        bulk.insert(0, {"id": "bulk:home", "label": "Every light in the home", "kind": "", "on": on, "total": len(h.lights),
                        "active": on > 0, "hint": f"{on} of {len(h.lights)} lights on. Deactivate it and every one goes off"})
    intro = {"rooms": "Each room's lights. Open a room to activate or deactivate its lights, dim them or give them a colour or a white.",
             "zones": "Zones are sets of lights you made in the Hue app, such as Downstairs. A light can be in several.",
             "types": "Open a type to activate or deactivate its lights, dim them or give them a colour or a white."}[tab]
    if not menus:
        intro += f" Your bridge has no {title.lower()} yet: make them in the Hue app."
    return {"type": "list", "title": title, "intro": intro, "menus": menus, "items": items, "bulk": bulk}


def _lights_in(h, tab, mid):
    for m, mtitle, lids, grouped in menus_for(h, tab):
        if m == mid:
            return mtitle, lids, grouped
    raise hue.BridgeError("That is no longer on the bridge. Refresh the page")


def check_bridge():
    """Test all, which Starboard offers on a list with nothing to test: says whether the bridge answers."""
    if not paired():
        return "No bridge is paired yet. Pair one on Bridge, then reload this page"
    h = home(fresh=True)
    return f"{paired()['name']} answers: {words.and_list([plural(len(h.lights), 'light'), plural(len(h.rooms()), 'room'), plural(len(h.rooms('zone')), 'zone')])}"


def lights_post(tab, body):
    action, rid, value = body.get("action"), str(body.get("id") or ""), str(body.get("value") or "")
    if action == "test_all":
        return {**lights_screen(tab), "said": check_bridge()}
    h = home(fresh=True)
    b = bridge()
    said = ""
    kind, _, rest = rid.partition(":")
    if action == "bulk":
        on = value == "on"
        if rest == "home":
            if not h.home_grouped:
                raise hue.BridgeError("The bridge has no group for every light")
            b.put("grouped_light", h.home_grouped, {"on": {"on": on}})
            said = f"Every light is {'on' if on else 'off'}"
        else:
            mtitle, lids, grouped = _lights_in(h, tab, rest)
            set_lights(b, h, lids, grouped, {"on": {"on": on}})
            said = f"Every light in {mtitle} is {'on' if on else 'off'}" if tab != "types" else f"{mtitle} are {'on' if on else 'off'}"
    elif kind in ("light", "colour"):
        mid, _, lid = rest.rpartition(":")
        if lid not in h.lights:
            raise hue.BridgeError("That light is no longer on the bridge. Refresh the page")
        nm = h.light_name(lid)
        if action == "toggle" and kind == "light":
            on = not (h.lights[lid].get("on") or {}).get("on")
            b.put("light", lid, {"on": {"on": on}})
            said = f"{nm} is {'on' if on else 'off'}"
        elif action == "choose" and kind == "light" and value == "0":
            b.put("light", lid, {"on": {"on": False}})
            said = f"{nm} is off"
        elif action == "choose" and kind == "light":
            pct = _percent(value)
            b.put("light", lid, {"on": {"on": True}, "dimming": {"brightness": pct}})
            said = f"{nm} is at {pct}%"
        elif action == "choose" and kind == "colour":
            schema = ((h.lights[lid].get("color_temperature") or {}).get("mirek_schema")) or {}
            body_ = words.colour_body(value, (schema.get("mirek_minimum", 153), schema.get("mirek_maximum", 500)))
            b.put("light", lid, {"on": {"on": True}, **body_})
            said = f"{nm} is {words.NAMES[value].lower()}"
    elif kind in ("gbri", "gcol") and action == "choose":
        mtitle, lids, grouped = _lights_in(h, tab, rest)
        if kind == "gbri" and value == "0":
            set_lights(b, h, lids, grouped, {"on": {"on": False}})
            said = f"Every light in {mtitle} is off"
        elif kind == "gbri":
            pct = _percent(value)
            set_lights(b, h, lids, grouped, {"on": {"on": True}, "dimming": {"brightness": pct}})
            said = f"Every light in {mtitle} is at {pct}%"
        else:
            body_ = words.colour_body(value)
            set_lights(b, h, lids, grouped, {"on": {"on": True}, **body_}, colour=True)
            said = f"Every light in {mtitle} is {words.NAMES[value].lower()}"
    else:
        raise hue.BridgeError("That cannot be done here")
    forget_cache()
    return {**lights_screen(tab), "said": said}


def set_lights(b, h, lids, grouped, body, colour=False):
    """The room's or zone's own grouped light when it has one (one command, as the Hue app does); else each light,
    such as for a device type. Lights that cannot take a colour are left at their state for a colour change."""
    if grouped:
        b.put("grouped_light", grouped, body)
        return
    for lid in lids:
        if colour and words.kind_of(h.lights[lid]) in ("white", "plug"):
            continue
        part = dict(body)
        if "dimming" in part and not h.lights[lid].get("dimming"):
            part.pop("dimming")
        b.put("light", lid, part)


def _percent(value):
    try:
        p = int(value)
    except ValueError:
        raise hue.BridgeError("Choose a brightness from the list") from None
    if not 1 <= p <= 100:
        raise hue.BridgeError("Choose a brightness from the list")
    return p


# Scenes -------------------------------------------------------------------------------------------------------
def scenes_screen(said=""):
    try:
        h = home()
    except hue.BridgeError as e:
        return {"type": "list", "title": "Scenes", "items": [], "notices": [{"id": "bridge", "tone": "warning", "title": str(e)}]}
    menus, items = [], []
    for rtype, heading in (("room", "Rooms"), ("zone", "Zones")):
        for g in h.rooms(rtype):
            scenes = h.scenes.get(g["res"]["id"]) or []
            if not scenes:
                continue
            gid = g["res"]["id"]
            menus.append({"id": gid, "title": name(g["res"]), "group": heading, "detail": plural(len(scenes), "scene")})
            for s in scenes:
                active = ((s.get("status") or {}).get("active") or "inactive") != "inactive"
                items.append({"id": f"scene:{s['id']}", "title": name(s), "menu": gid, "on": active,
                              "detail": f"In use in {name(g['res'])}" if active else f"Activate to show it in {name(g['res'])}",
                              "state": "ok" if active else "off", "state_label": "In use" if active else "Not in use", "actions": ["toggle"]})
    out = {"type": "list", "title": "Scenes", "menus": menus, "items": items,
           "intro": "Each room's and zone's scenes, as made in the Hue app. Activate shows a scene; Deactivate turns that room's lights off."
           + ("" if menus else " Your bridge has no scenes yet: make them in the Hue app.")}
    return {**out, "said": said} if said else out


def scenes_post(body):
    if body.get("action") == "test_all":
        return scenes_screen(check_bridge())
    if body.get("action") != "toggle":
        raise hue.BridgeError("That cannot be done here")
    sid = str(body.get("id") or "").partition(":")[2]
    h = home(fresh=True)
    scene = h.by.get("scene", {}).get(sid)
    if not scene:
        raise hue.BridgeError("That scene is no longer on the bridge. Refresh the page")
    gid = (scene.get("group") or {}).get("rid")
    g = h.groups.get(gid) or {}
    where = name(g.get("res")) or "its room"
    if ((scene.get("status") or {}).get("active") or "inactive") != "inactive":
        if not g.get("grouped"):
            raise hue.BridgeError(f"{where} has no group to deactivate")
        bridge().put("grouped_light", g["grouped"], {"on": {"on": False}})
        said = f"{where} is off"
    else:
        bridge().put("scene", sid, {"recall": {"action": "active"}})
        said = f"{name(scene)} is on in {where}"
    forget_cache()
    return scenes_screen(said)


# Schedules ----------------------------------------------------------------------------------------------------
def targets(h):
    """What a schedule can name, rooms first, then zones, then lights, then every light."""
    out = []
    for rtype in ("room", "zone"):
        for g in h.rooms(rtype):
            kinds = {words.kind_of(h.lights[x]) for x in g["lights"]}
            out.append({"rtype": rtype, "rid": g["res"]["id"], "name": name(g["res"]), "v1": g["res"].get("id_v1", ""),
                        "kind": "colour" if "colour" in kinds else "ambiance" if "ambiance" in kinds else "white",
                        "scenes": [{"rid": s["id"], "name": name(s), "v1": (s.get("id_v1") or "").rsplit("/", 1)[-1]} for s in h.scenes.get(g["res"]["id"]) or []]})
    for lid, light in h.lights.items():
        out.append({"rtype": "light", "rid": lid, "name": h.light_name(lid), "v1": light.get("id_v1", ""), "kind": words.kind_of(light)})
    home_v1 = h.grouped(h.home_grouped).get("id_v1") if h.home_grouped else ""
    for alias in ("every light", "all lights", "all the lights"):
        out.append({"rtype": "bridge_home", "rid": h.home_grouped or "", "name": alias, "v1": home_v1 or "/groups/0", "kind": "colour"})
    return out


def address_of(target):
    v1 = target["v1"]
    if not re.match(r"^/(groups|lights)/\d+$", v1 or ""):
        raise hue.BridgeError(f"The bridge cannot schedule {target['name']}")
    return v1 + ("/state" if v1.startswith("/lights/") else "/action")


def bridge_now(b):
    raw = (b.v1("GET", "/config") or {}).get("localtime") or ""
    try:
        return dt.datetime.fromisoformat(raw)
    except ValueError:
        return dt.datetime.now().replace(microsecond=0)


def daylight_sensor(b):
    for sid, s in (b.v1("GET", "/sensors") or {}).items():
        if s.get("type") == "Daylight" and (s.get("config") or {}).get("configured"):
            return sid
    return None


def save_on_bridge(b, h, spec):
    """Writes the schedule to the bridge: a timed schedule, or a rule on the daylight sensor for sunrise and sunset.
    Returns {"kind", "id"}."""
    target = next(t for t in targets(h) if t["rtype"] == spec["target"]["rtype"] and t["rid"] == spec["target"]["rid"])
    text = words.describe(spec)
    ct = None
    if target["rtype"] == "light":
        schema = ((h.lights[target["rid"]].get("color_temperature") or {}).get("mirek_schema")) or {}
        ct = (schema.get("mirek_minimum", 153), schema.get("mirek_maximum", 500))
    if "scene" in spec["do"] and not target["v1"].startswith("/groups/"):
        raise hue.BridgeError("Only a room or a zone can be set to a scene")
    body = words.v1_body(spec["do"], ct)
    addr = address_of(target)
    short = f"Starboard {text}"[:32]
    if spec["time"] in ("sunrise", "sunset"):
        sensor = daylight_sensor(b)
        if not sensor:
            raise hue.BridgeError("Your bridge does not know sunrise and sunset yet. Set your location in the Hue app, then try again")
        conditions = [{"address": f"/sensors/{sensor}/state/daylight", "operator": "eq", "value": "true" if spec["time"] == "sunrise" else "false"},
                      {"address": f"/sensors/{sensor}/state/daylight", "operator": "dx"}]
        if sorted(spec["days"]) != list(range(7)):
            conditions.append({"address": "/config/localtime", "operator": "in", "value": f"W{words.bitmask(spec['days'])}/T00:00:00/T23:59:59"})
        out = b.v1("POST", "/rules", {"name": short, "conditions": conditions, "actions": [{"address": addr, "method": "PUT", "body": body}]})
        return {"kind": "rule", "id": str(out[0]["success"]["id"])}
    out = b.v1("POST", "/schedules", {"name": short, "description": text[:64], "localtime": words.localtime(spec),
                                      "command": {"address": f"/api/{b.key}{addr}", "method": "PUT", "body": body},
                                      "status": "enabled", "autodelete": bool(spec.get("once"))})
    return {"kind": "schedule", "id": str(out[0]["success"]["id"])}


def _on_bridge(b):
    return {"schedule": b.v1("GET", "/schedules") or {}, "rule": b.v1("GET", "/rules") or {}}


def schedules_screen(said=""):
    out = {"type": "list", "title": "Schedules", "items": [],
           "intro": "Timed actions, kept on your Hue bridge so they run even while Starboard or this plug-in rests. Each is written in "
                    "words: change the words to change the schedule.",
           "add": {"label": "Add a schedule", "placeholder": words.EXAMPLE, "hint": words.PATTERN + "."}}
    try:
        b = bridge()
        now = bridge_now(b)
        there = _on_bridge(b)
    except hue.BridgeError as e:
        out.pop("add")
        return {**out, "notices": [{"id": "bridge", "tone": "warning", "title": str(e)}]}
    records = remember("schedules", []) or []
    kept = [r for r in records if r["bridge"]["id"] in there[r["bridge"]["kind"]]]  # a one-off that ran has gone from the bridge
    if len(kept) != len(records):
        keep("schedules", kept)
    mine = {(r["bridge"]["kind"], r["bridge"]["id"]) for r in kept}
    for r in sorted(kept, key=lambda r: words.describe(r["spec"]).lower()):
        on = (there[r["bridge"]["kind"]][r["bridge"]["id"]].get("status") or "enabled") == "enabled"
        text = words.describe(r["spec"])
        nxt = words.when_words(words.next_run(r["spec"], now), now)
        detail = ("Runs at " + r["spec"]["time"] + ", when the bridge works it out for where you live") if not nxt and r["spec"]["time"] in ("sunrise", "sunset") \
            else f"Next {nxt}" if nxt else "Has run"
        out["items"].append({"id": r["id"], "title": text, "group": "Your schedules", "on": on,
                             "detail": detail if on else "Deactivated: it does not run until you activate it",
                             "state": "ok" if on else "off", "state_label": "On" if on else "Off",
                             "actions": ["toggle", "attach", "remove"],
                             "attach": {"label": "Change", "field": "The schedule in words", "value": text, "placeholder": words.EXAMPLE,
                                        "hint": words.PATTERN + "."}})
    for sid, s in sorted(there["schedule"].items()):
        if ("schedule", sid) in mine or str(s.get("name", "")).startswith("Starboard "):
            continue
        on = s.get("status") == "enabled"
        out["items"].append({"id": f"other:{sid}", "title": s.get("name") or "A schedule", "group": "Made in another app", "on": on,
                             "detail": "Made in the Hue app or another app. Change it there.", "state": "ok" if on else "off",
                             "state_label": "On" if on else "Off", "actions": []})
    if not kept:
        out["intro"] += " No schedules yet: add one in words in Add a schedule, such as " + words.EXAMPLE + "."
    return {**out, "said": said} if said else out


def schedules_post(body):
    action, rid, value = body.get("action"), str(body.get("id") or ""), body.get("value")
    if action == "test_all":
        return schedules_screen(check_bridge())
    b = bridge()
    records = remember("schedules", []) or []
    if action == "add" or action == "attach":
        h = home(fresh=True)
        spec = words.parse(value, targets(h), bridge_now(b).date())
        old = next((r for r in records if r["id"] == rid), None) if action == "attach" else None
        if action == "attach" and not old:
            raise hue.BridgeError("That schedule is no longer here. Refresh the page")
        new = save_on_bridge(b, h, spec)  # the new one first, so a refusal leaves the old one as it was
        if old:
            _delete(b, old)
            records = [r for r in records if r["id"] != rid]
        records.append({"id": old["id"] if old else uuid.uuid4().hex[:10], "spec": spec, "bridge": new})
        keep("schedules", records)
        return schedules_screen(f"{'Changed' if old else 'Added'}: {words.describe(spec)}")
    r = next((x for x in records if x["id"] == rid), None)
    if not r:
        raise hue.BridgeError("That schedule is no longer here. Refresh the page")
    path = f"/{r['bridge']['kind']}s/{r['bridge']['id']}"
    if action == "toggle":
        now = (b.v1("GET", path) or {}).get("status", "enabled") == "enabled"
        b.v1("PUT", path, {"status": "disabled" if now else "enabled"})
        return schedules_screen(f"{'Deactivated' if now else 'Activated'}: {words.describe(r['spec'])}")
    if action == "remove":
        _delete(b, r)
        keep("schedules", [x for x in records if x["id"] != rid])
        return schedules_screen(f"Removed: {words.describe(r['spec'])}")
    raise hue.BridgeError("That cannot be done here")


def _delete(b, record):
    try:
        b.v1("DELETE", f"/{record['bridge']['kind']}s/{record['bridge']['id']}")
    except hue.BridgeError as e:
        if "not available" not in str(e).lower():  # gone already, such as a one-off that ran
            raise


# When something plays (Starboard's playback.started event) ---------------------------------------------------
def play_screen(said=""):
    chosen = (remember("play") or {}).get("scene") or {}
    last = (remember("play") or {}).get("last") or {}
    try:
        h = home()
    except hue.BridgeError as e:
        return {"type": "list", "title": "Scene when something plays", "items": [], "notices": [{"id": "bridge", "tone": "warning", "title": str(e)}]}
    items = []
    for rtype in ("room", "zone"):
        for g in h.rooms(rtype):
            for s in h.scenes.get(g["res"]["id"]) or []:
                on = chosen.get("rid") == s["id"]
                items.append({"id": f"play:{s['id']}", "title": name(s), "group": name(g["res"]), "on": on,
                              "detail": f"Runs in {name(g['res'])} when something starts playing" if on else f"In {name(g['res'])}",
                              "state": "ok" if on else "off", "state_label": "Chosen" if on else "Not chosen", "actions": ["toggle"]})
    intro = ("Activate one scene to run when someone starts playing something in Jellyfin. Starboard checks what is playing every "
             "5 minutes, so the lights can change up to 5 minutes after it starts.")
    if last.get("at"):
        intro += f" Last ran {last['at']} for {last.get('title') or 'something'}."
    out = {"type": "list", "title": "Scene when something plays", "intro": intro, "items": items}
    return {**out, "said": said} if said else out


def play_post(body):
    if body.get("action") == "test_all":
        return play_screen(check_bridge())
    if body.get("action") != "toggle":
        raise hue.BridgeError("That cannot be done here")
    sid = str(body.get("id") or "").partition(":")[2]
    h = home()
    scene = h.by.get("scene", {}).get(sid)
    if not scene:
        raise hue.BridgeError("That scene is no longer on the bridge. Refresh the page")
    state = remember("play") or {}
    if (state.get("scene") or {}).get("rid") == sid:
        keep("play", {**state, "scene": {}})
        return play_screen("No scene runs when something plays")
    keep("play", {**state, "scene": {"rid": sid, "name": name(scene)}})
    return play_screen(f"{name(scene)} runs when something starts playing")


def events(body):
    """POST /events from Starboard. Only playback.started does anything: the chosen scene, if the conditions hold."""
    if body.get("event") != "playback.started":
        return {"ok": True}
    state = remember("play") or {}
    scene = state.get("scene") or {}
    if not scene.get("rid") or not paired():
        return {"ok": True, "said": "No scene chosen"}
    data = body.get("data") or {}
    apps = [a.strip().lower() for a in setting("only_apps", []) or [] if str(a).strip()]
    if apps and not any(a in str(data.get("client") or "").lower() for a in apps):
        return {"ok": True, "said": "Another app"}
    b = bridge()
    if setting("only_dark", True):
        sensor = daylight_sensor(b)
        if sensor and ((b.v1("GET", f"/sensors/{sensor}") or {}).get("state") or {}).get("daylight"):
            return {"ok": True, "said": "Still daylight"}
    b.put("scene", scene["rid"], {"recall": {"action": "active"}})
    title = data.get("series") or data.get("title") or ""
    keep("play", {**state, "last": {"at": dt.datetime.now().strftime("%A at %H:%M"), "title": str(title)[:80]}})
    forget_cache()
    return {"ok": True, "said": f"Ran {scene['name']}"}


# Dashboard cards and buttons ----------------------------------------------------------------------------------
def room_words(h, g):
    lids = g["lights"]
    if not lids:
        return "No lights", False
    if not any(h.reach.get(x, True) for x in lids):
        return "Not reachable", False
    on = h.on_count(lids)
    if not on:
        return "Off", False
    bri = (h.grouped(g["grouped"]).get("dimming") or {}).get("brightness") if g["grouped"] else None
    return (f"On at {max(1, round(bri))}%" if bri else "On") + (f", {on} of {len(lids)} lights" if on < len(lids) else ""), True


def rooms_card():
    if not paired():
        return band({"items": [{"title": "Pair your Hue bridge", "detail": "In Settings, Plug-ins, Philips Hue, Bridge"}]}, "needs_setup")
    try:
        h = home()
    except hue.BridgeError as e:
        return band({"items": [{"title": "The bridge did not answer", "detail": str(e)}]}, "problem", label="Not answering")
    rows, lit = [], 0
    for g in h.rooms():
        text, on = room_words(h, g)
        lit += on
        rows.append({"title": name(g["res"]), "detail": text})
    if not rows:
        return band({"items": [{"title": "No rooms yet", "detail": "Make rooms in the Hue app"}]}, "idle")
    return band({"items": rows[:10]}, "ok" if lit else "idle", time.time(), f"{plural(lit, 'room')} on" if lit else "All off")


def lights_card():
    if not paired():
        return band({"state": "warning", "text": "Pair your Hue bridge in Settings, Plug-ins, Philips Hue"}, "needs_setup")
    try:
        h = home()
    except hue.BridgeError as e:
        return band({"state": "problem", "text": str(e)}, "problem", label="Not answering")
    lit = [name(g["res"]) for g in h.rooms() if h.on_count(g["lights"])]
    away = [h.light_name(x) for x in h.lights if not h.reach.get(x, True)]
    text = f"Lights on in {words.and_list(lit)}" if lit else "Every light is off"
    if away:
        text += f". Not reachable: {words.and_list(away[:4])}"
    return band({"state": "warning" if away else "ok", "text": text}, "warning" if away else "ok", time.time(),
                f"{plural(len(lit), 'room')} on" if lit else "All off")


def every_light(on):
    def run():
        h = home(fresh=True)
        if not h.home_grouped:
            raise hue.BridgeError("The bridge has no group for every light")
        bridge().put("grouped_light", h.home_grouped, {"on": {"on": on}})
        forget_cache()
        return {"said": f"Every light is {'on' if on else 'off'}"}
    run.__name__ = f"every_light_{'on' if on else 'off'}"
    return run


def health():
    if not os.access(os.environ.get("PLUGIN_DATA", "/data"), os.W_OK):
        raise RuntimeError("Its own folder cannot be written")
    return {"ok": True}


def plural(n, one, many=None):
    return f"{n} {one if n == 1 else (many or one + 's')}"


ROUTES = {("GET", "/health"): health,
          "/bridge": bridge_screen, ("POST", "/bridge"): bridge_post,
          "/rooms": lambda: lights_screen("rooms"), ("POST", "/rooms"): lambda body: lights_post("rooms", body),
          "/zones": lambda: lights_screen("zones"), ("POST", "/zones"): lambda body: lights_post("zones", body),
          "/types": lambda: lights_screen("types"), ("POST", "/types"): lambda body: lights_post("types", body),
          "/scenes": scenes_screen, ("POST", "/scenes"): scenes_post,
          "/schedules": schedules_screen, ("POST", "/schedules"): schedules_post,
          "/play": play_screen, ("POST", "/play"): play_post,
          ("POST", "/events"): events,
          "/card/rooms": rooms_card, "/card/lights": lights_card,
          ("POST", "/actions/all-off"): every_light(False), ("POST", "/actions/all-on"): every_light(True)}

if __name__ == "__main__":
    serve(ROUTES)
