"""Light and schedule words: what a light's colour is called, and schedules written and read in one sentence.

A schedule is shown as the words it is written in, so the same words can be changed and saved again:

    Every weekday at 07:00, Kitchen to 80%
    Every Monday, Wednesday and Friday at sunset, Lounge to Relax
    Every day at 22:30, every light off
    Once on 24 December at 18:00, Hall to warm white at 40%
"""
import datetime as dt
import math
import re

# Colours ------------------------------------------------------------------------------------------------------
# Whites by colour temperature: mirek is a million divided by kelvin.
WHITES = [("warm", "Warm white", 2700), ("soft", "Soft white", 3000), ("neutral", "Neutral white", 4000),
          ("cool", "Cool white", 5000), ("daylight", "Daylight", 6500)]
# Colours by their place on the CIE xy chart; the bridge keeps each inside what the light can show.
COLOURS = [("red", "Red", (0.675, 0.322)), ("orange", "Orange", (0.58, 0.39)), ("yellow", "Yellow", (0.443, 0.515)),
           ("green", "Green", (0.17, 0.70)), ("blue", "Blue", (0.153, 0.048)), ("purple", "Purple", (0.2725, 0.1096)),
           ("pink", "Pink", (0.45, 0.26))]
# Where each white sits on the same chart, so a light set by xy to a white is called by the white's name.
WHITE_XY = {"warm": (0.4599, 0.4106), "soft": (0.4369, 0.4041), "neutral": (0.3805, 0.3768), "cool": (0.3451, 0.3516),
            "daylight": (0.3127, 0.3290)}
NAMES = {k: w for k, w, _ in WHITES} | {k: w for k, w, _ in COLOURS}


def mirek(kelvin):
    return round(1_000_000 / kelvin)


def colour_options(light_kind):
    """The colours a light can take, as [value, words]: every one for a colour light, the whites for white ambiance."""
    whites = [[k, w] for k, w, _ in WHITES]
    return whites + [[k, w] for k, w, _ in COLOURS] if light_kind == "colour" else whites if light_kind == "ambiance" else []


def colour_body(name, ct_range=None):
    """The CLIP v2 body for a colour by its value, such as {"color_temperature": {"mirek": 370}}."""
    for k, _, kelvin in WHITES:
        if k == name:
            m = mirek(kelvin)
            if ct_range:
                m = max(ct_range[0], min(ct_range[1], m))
            return {"color_temperature": {"mirek": m}}
    for k, _, (x, y) in COLOURS:
        if k == name:
            return {"color": {"xy": {"x": x, "y": y}}}
    raise ValueError("Choose a colour from the list")


def colour_of(light):
    """A light's colour as a value from colour_options, or "" when it has none or shows none."""
    ct = light.get("color_temperature") or {}
    if ct.get("mirek_valid") and ct.get("mirek"):
        kelvin = 1_000_000 / ct["mirek"]
        return min(WHITES, key=lambda w: abs(w[2] - kelvin))[0]
    xy = ((light.get("color") or {}).get("xy")) or {}
    if "x" in xy and "y" in xy:
        points = [(k, p) for k, _, p in COLOURS] + list(WHITE_XY.items())
        return min(points, key=lambda kp: math.dist(kp[1], (xy["x"], xy["y"])))[0]
    return ""


def kind_of(light):
    """colour, ambiance (whites only), white (brightness only) or plug (on and off only)."""
    if light.get("color"):
        return "colour"
    if light.get("color_temperature"):
        return "ambiance"
    if light.get("dimming"):
        return "white"
    return "plug"


KIND_WORDS = {"colour": "Colour", "ambiance": "White ambiance", "white": "White", "plug": "Smart plug"}

# What a light is, from the bridge's archetype, for the Device types tab
TYPES = [("Bulbs", ("classic_bulb", "sultan_bulb", "vintage_bulb", "globe_bulb", "edison_bulb", "christmas_tree", "hue_tube")),
         ("Candle bulbs", ("candle_bulb", "luster_bulb")),
         ("Spot lights", ("spot_bulb", "flood_bulb", "recessed_ceiling", "recessed_floor", "single_spot", "double_spot", "ceiling_spot")),
         ("Light strips", ("hue_lightstrip", "hue_lightstrip_tv", "hue_lightstrip_pc", "hue_play", "string_light", "hue_signe", "hue_centris")),
         ("Lamps", ("table_shade", "table_wash", "floor_shade", "floor_lantern", "hue_go", "hue_iris", "hue_bloom", "flexible_lamp", "pendant_spot")),
         ("Ceiling lights", ("ceiling_round", "ceiling_square", "ceiling_horizontal", "ceiling_tube", "pendant_round", "pendant_long")),
         ("Outdoor lights", ("wall_lantern", "wall_shade", "wall_spot", "bollard", "ground_spot", "wall_washer", "hue_impress", "hue_lily")),
         ("Smart plugs", ("plug",))]


def type_of(light):
    arche = ((light.get("metadata") or {}).get("archetype")) or ""
    if kind_of(light) == "plug":
        return "Smart plugs"
    return next((name for name, archetypes in TYPES if arche in archetypes), "Other lights")


def light_words(light, reachable=True):
    """A light's state in words, its colour named: "On at 80%, warm white", "Off", "Not reachable"."""
    if not reachable:
        return "Not reachable"
    if not (light.get("on") or {}).get("on"):
        return "Off"
    parts = ["On"]
    bri = (light.get("dimming") or {}).get("brightness")
    if bri is not None:
        parts = [f"On at {max(1, round(bri))}%"]
    colour = colour_of(light)
    if colour:
        parts.append(NAMES[colour].lower() if colour != "daylight" else "daylight")
    return ", ".join(parts)


BRIGHTNESS = [1] + list(range(10, 101, 10))


def brightness_options():
    """Off, then 1% and 10% to 100%: 12 choices, as many as Starboard draws in a row's list."""
    return [["0", "Off"]] + [[str(p), f"{p}%"] for p in BRIGHTNESS]


def nearest_brightness(value, on=True):
    if not on or not value:
        return "0"
    return str(min(BRIGHTNESS, key=lambda p: abs(p - value)))


def and_list(items):
    items = list(items)
    if len(items) < 2:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


# Schedules ----------------------------------------------------------------------------------------------------
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
EXAMPLE = "Every weekday at 07:00, Kitchen to 80%"
PATTERN = ("Write when, at what time, then what: such as Every weekday at 07:00, Kitchen to 80%. Or Every day at sunset, "
           "Lounge to Relax. Or Once on 24 December at 18:00, Hall off")


class ScheduleError(ValueError):
    """A sentence saying what to change."""


def _day(word):
    w = word.strip().lower().rstrip("s") if len(word.strip()) > 4 else word.strip().lower()
    for i, d in enumerate(DAYS):
        if w in (d.lower(), d.lower()[:3]) or (len(w) >= 3 and d.lower().startswith(w)):
            return i
    raise ScheduleError(f"{word.strip()} is not a day of the week. {PATTERN}")


def _date(text, today):
    t = text.strip().lower()
    if t == "today":
        return today
    if t == "tomorrow":
        return today + dt.timedelta(days=1)
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", t)
    if m:
        return dt.date(int(m[1]), int(m[2]), int(m[3]))
    t = re.sub(r"^(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+", "", t)
    m = re.match(r"^(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]+)(?:\s+(\d{4}))?$", t)
    if m:
        month = next((i + 1 for i, name in enumerate(MONTHS) if name.lower().startswith(m[2][:3]) and len(m[2]) >= 3), 0)
        if month:
            year = int(m[3]) if m[3] else today.year
            try:
                day = dt.date(year, month, int(m[1]))
            except ValueError:
                raise ScheduleError(f"{text.strip()} is not a date") from None
            if not m[3] and day < today:
                day = dt.date(year + 1, month, int(m[1]))
            return day
    raise ScheduleError(f"Give the date as a day and a month, such as 24 December. {PATTERN}")


def parse_when(text, today):
    """The part before "at": {"days": [0..6]} for a schedule that repeats, or {"once": date}."""
    t = " ".join(text.split()).strip().rstrip(",")
    low = t.lower()
    if low in ("every day", "daily", "each day"):
        return {"days": list(range(7))}
    if low in ("every weekday", "weekdays", "every weekdays", "on weekdays"):
        return {"days": list(range(5))}
    if low in ("every weekend", "weekends", "at weekends", "every weekend day"):
        return {"days": [5, 6]}
    m = re.match(r"^(every|on)\s+(.+)$", t, flags=re.I)
    if m:
        try:
            days = sorted({_day(d) for d in re.split(r",|\band\b", m[2], flags=re.I) if d.strip()})
            if days:
                return {"days": days}
        except ScheduleError:
            if m[1].lower() == "every":
                raise
    if low in ("once", "today", "tomorrow") or low.startswith("once on ") or low.startswith("on "):
        rest = re.sub(r"^(once\s+on|once|on)\s*", "", low) or "today"
        return {"once": _date(rest if low not in ("today", "tomorrow") else low, today).isoformat()}
    raise ScheduleError(f"Start with Every, such as Every day or Every Monday and Friday, or with Once. {PATTERN}")


def parse_time(text):
    t = text.strip().lower()
    if t in ("sunrise", "sunset", "dawn", "dusk"):
        return {"dawn": "sunrise", "dusk": "sunset"}.get(t, t)
    m = re.match(r"^(\d{1,2})[:.](\d{2})$", t) or re.match(r"^(\d{1,2})(\d{2})$", t)
    if m and int(m[1]) < 24 and int(m[2]) < 60:
        return f"{int(m[1]):02d}:{m[2]}"
    m = re.match(r"^(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)$", t)
    if m and 1 <= int(m[1]) <= 12 and int(m[2] or 0) < 60:
        h = int(m[1]) % 12 + (12 if m[3] == "pm" else 0)
        return f"{h:02d}:{int(m[2] or 0):02d}"
    raise ScheduleError(f"Give the time as hours and minutes, such as 07:00 or 18:30, or say sunrise or sunset. {PATTERN}")


def parse(text, targets, today):
    """One schedule from its words. `targets`: [{"rtype", "rid", "name", "scenes": [{"rid", "name"}], "kind"}],
    rooms first, then zones, then lights, then every light. Returns {"when", "time", "target", "do"}."""
    t = " ".join(str(text or "").split())
    if not t:
        raise ScheduleError(PATTERN)
    m = re.match(r"^(.*?)\s+at\s+(.+?)\s*,\s*(.+)$", t, flags=re.I)
    if not m:
        raise ScheduleError(PATTERN)
    when = parse_when(m[1], today)
    at = parse_time(m[2])
    if at in ("sunrise", "sunset") and "once" in when:
        raise ScheduleError("Sunrise and sunset work with a schedule that repeats, such as Every day at sunset")
    rest = m[3].strip().rstrip(".")
    target = None
    for cand in sorted(targets, key=lambda c: -len(c["name"])):  # the longest name first: "Kitchen spots" before "Kitchen"
        if rest.lower().startswith(cand["name"].lower() + " ") or rest.lower() == cand["name"].lower():
            same = [c for c in targets if c["name"].lower() == cand["name"].lower() and c["rtype"] == cand["rtype"]]
            if len(same) > 1:
                raise ScheduleError(f"Two {('lights' if cand['rtype'] == 'light' else 'places')} are called {cand['name']}: "
                                    "rename one in the Hue app, then try again")
            target = next(c for c in targets if c["name"].lower() == cand["name"].lower())  # rooms before zones before lights
            rest = rest[len(cand["name"]):].strip()
            break
    if not target:
        names = and_list([c["name"] for c in targets if c["rtype"] in ("room", "zone")][:4])
        raise ScheduleError(f"Name a room, a zone, a light or every light after the comma{', such as ' + names if names else ''}")
    return {**when, "time": at, "target": {k: target[k] for k in ("rtype", "rid", "name")}, "do": parse_action(rest, target)}


def parse_action(text, target):
    original = text.strip()
    t = original.lower()
    if t in ("on", "turns on", "turn on"):
        return {"on": True}
    if t in ("off", "turns off", "turn off"):
        return {"on": False}
    m = re.match(r"^to\s+(.+)$", t)
    if not m:
        raise ScheduleError("Say what happens after the name: on, off, to 80%, to warm white or to a scene's name")
    what = m[1].strip()
    p = re.match(r"^(\d{1,3})\s*%$", what)
    if p:
        return {"on": True, "bri": _percent(p[1])}
    p = re.match(r"^(.+?)(?:\s+at\s+(\d{1,3})\s*%)?$", what)
    colour = next((k for k, w in NAMES.items() if w.lower() == p[1] or k == p[1]), None) if p else None
    if colour:
        if target.get("kind") in ("white", "plug"):
            raise ScheduleError(f"{target['name']} cannot change colour")
        if target.get("kind") == "ambiance" and colour not in dict((k, 1) for k, _, _ in WHITES):
            raise ScheduleError(f"{target['name']} shows whites only, such as warm white or daylight")
        return {"on": True, "colour": colour, **({"bri": _percent(p[2])} if p[2] else {})}
    scene = next((s for s in target.get("scenes") or [] if s["name"].lower() == what), None)
    if scene:
        return {"scene": {"rid": scene["rid"], "name": scene["name"], "v1": scene.get("v1", "")}}
    if target["rtype"] in ("room", "zone") and target.get("scenes"):
        raise ScheduleError(f"{target['name']} has no scene called {original[3:].strip()}. Its scenes: {and_list([s['name'] for s in target['scenes']][:6])}")
    raise ScheduleError("After to, give a brightness such as 80%, a colour such as warm white, or a scene's name")


def _percent(text):
    p = int(text)
    if not 1 <= p <= 100:
        raise ScheduleError("Give a brightness from 1% to 100%")
    return p


def days_words(days):
    days = sorted(days)
    if days == list(range(7)):
        return "Every day"
    if days == list(range(5)):
        return "Every weekday"
    if days == [5, 6]:
        return "Every weekend"
    return "Every " + and_list(DAYS[d] for d in days)


def date_words(iso):
    d = dt.date.fromisoformat(iso)
    return f"{DAYS[d.weekday()]} {d.day} {MONTHS[d.month - 1]}"


def describe(spec):
    """The schedule in the words it is written in, such as "Every weekday at 07:00, Kitchen to 80%"."""
    when = days_words(spec["days"]) if spec.get("days") is not None else f"Once on {date_words(spec['once'])}"
    do = spec["do"]
    target = "every light" if spec["target"]["rtype"] == "bridge_home" else spec["target"]["name"]
    if "scene" in do:
        what = f"to {do['scene']['name']}"
    elif do.get("colour"):
        what = f"to {NAMES[do['colour']].lower()}" + (f" at {do['bri']}%" if do.get("bri") else "")
    elif do.get("bri"):
        what = f"to {do['bri']}%"
    else:
        what = "on" if do.get("on") else "off"
    return f"{when} at {spec['time']}, {target} {what}"


# To the bridge's version 1 schedules and rules -----------------------------------------------------------------
def bitmask(days):
    """The bridge's weekday mask: Monday 64, Tuesday 32, down to Sunday 1."""
    return sum(1 << (6 - d) for d in days)


def localtime(spec):
    if spec.get("once"):
        return f"{spec['once']}T{spec['time']}:00"
    return f"W{bitmask(spec['days'])}/T{spec['time']}:00"


def v1_body(do, ct_range=None):
    """The version 1 body for a light's state or a group's action."""
    if "scene" in do:
        return {"scene": do["scene"]["v1"]}
    body = {"on": bool(do.get("on", True))}
    if do.get("bri"):
        body["bri"] = max(1, min(254, round(do["bri"] * 254 / 100)))
    if do.get("colour"):
        c = colour_body(do["colour"], ct_range)
        if "color_temperature" in c:
            body["ct"] = c["color_temperature"]["mirek"]
        else:
            body["xy"] = [c["color"]["xy"]["x"], c["color"]["xy"]["y"]]
    return body


def next_run(spec, now):
    """When a timed schedule runs next, from the bridge's own local time, or None for sunrise and sunset."""
    if spec["time"] in ("sunrise", "sunset"):
        return None
    h, m = map(int, spec["time"].split(":"))
    if spec.get("once"):
        at = dt.datetime.combine(dt.date.fromisoformat(spec["once"]), dt.time(h, m))
        return at if at > now else None
    for ahead in range(8):
        day = now.date() + dt.timedelta(days=ahead)
        at = dt.datetime.combine(day, dt.time(h, m))
        if day.weekday() in spec["days"] and at > now:
            return at
    return None


def when_words(at, now):
    if at is None:
        return ""
    if at.date() == now.date():
        day = "today"
    elif at.date() == now.date() + dt.timedelta(days=1):
        day = "tomorrow"
    else:
        day = date_words(at.date().isoformat())
    return f"{day} at {at:%H:%M}"
