"""Break styles (0.12.0, DASH-644 and DASH-645, owner 28 November 2026): Quiet, Classic TV and Busy.

A style is a set of values for the break settings a channel already has, so a channel that follows a style plays through
exactly the code it always has. Nothing here runs by itself: a style is applied when a person chooses it, and a channel
saved before styles existed keeps every value it has.

A channel's style is one of:
  ""        it uses the station's style (new channels, and channels that never changed a break setting);
  a preset  its own style, one of PRESETS;
  "custom"  its own settings, set one by one (a channel saved before 0.12.0 that has any break setting changed).
The channel's own values are kept when it moves to a preset, so "Your own settings" brings them back.
"""

# key -> what a channel that never changed it has (new_channel and the readers in app.py).
DEFAULTS = {"break_seconds": 0, "per_break": 3, "ident_order": "in_order", "idents": "both", "clips": "both", "extras": "both", "trailers": False}
KEYS = tuple(DEFAULTS)

# The numbers are the ones the break rows already offer (BREAKS 0, 60, 120, 180 or 300 seconds; PER_BREAK 2, 3, 4 or 6).
PRESETS = {
    "quiet": {"name": "Quiet", "values": {"break_seconds": 60, "per_break": 2, "ident_order": "in_order", "idents": "both", "clips": "both",
                                           "extras": "none", "trailers": False}},
    "classic": {"name": "Classic TV", "values": {"break_seconds": 120, "per_break": 3, "ident_order": "random", "idents": "both", "clips": "both",
                                                 "extras": "both", "trailers": False}},
    "busy": {"name": "Busy", "values": {"break_seconds": 300, "per_break": 6, "ident_order": "random", "idents": "both", "clips": "both",
                                        "extras": "both", "trailers": True}},
}
CUSTOM = "custom"
OWN = "Your own settings"


def name(style):
    return PRESETS[style]["name"] if style in PRESETS else (OWN if style == CUSTOM else "")


def minutes(seconds):
    seconds = int(seconds or 0)
    if seconds <= 0:
        return "no break"
    if seconds % 60 == 0:
        n = seconds // 60
        return f"a break of {n} minute{'s' if n != 1 else ''}"
    return f"a break of {seconds} seconds"


def words(style):
    """What a style does, in plain words, for the sentence under the choice."""
    v = PRESETS[style]["values"]
    first = minutes(v["break_seconds"])
    out = [f"{first[0].upper()}{first[1:]} after each programme.",
           f"A short title clip, then up to {v['per_break']} coming-up trailers and clips" + (", then one of your own short videos" if v["extras"] != "none" else "") + "."]
    if v["trailers"]:
        out.append("Trailers of the channel's films play too.")
    return " ".join(out)


def values_of(ch):
    """The break settings a channel has now, with what it starts with for any it never changed."""
    return {k: (ch.get(k) if ch.get(k) not in (None, "") else d) if k != "trailers" else bool(ch.get(k, d)) for k, d in DEFAULTS.items()}


def is_default(ch):
    return values_of(ch) == DEFAULTS


def matching(ch):
    """The preset whose values a channel has exactly, or an empty string."""
    now = values_of(ch)
    for sid, p in PRESETS.items():
        if all(now[k] == v for k, v in p["values"].items()):
            return sid
    return ""


def style_of(ch):
    """A channel's style: its own saved choice, or, for a channel saved before 0.12.0, the station's when it never
    changed a break setting and its own settings when it did."""
    v = ch.get("style")
    if v is None:
        return "" if is_default(ch) else CUSTOM
    return v if (v == "" or v == CUSTOM or v in PRESETS) else ""


def apply(ch, style):
    """Puts a preset's values on a channel. Nothing else of the channel changes."""
    if style in PRESETS:
        for k, v in PRESETS[style]["values"].items():
            ch[k] = v


def keep_own(ch):
    """Remembers the channel's own settings before a style replaces them, so Your own settings can bring them back."""
    ch["own_style"] = {k: v for k, v in values_of(ch).items()}


def move(ch, to, station):
    """Moves a channel to a style: "" (the station's), a preset or custom. Returns what changed, in words."""
    was = style_of(ch)
    if to not in ("", CUSTOM) and to not in PRESETS:
        raise ValueError("That is not one of the styles")
    if to == was and (to != "" or not station):
        return ""
    if was == CUSTOM and to != CUSTOM:
        keep_own(ch)
    if to == CUSTOM:
        for k, v in (ch.get("own_style") or {}).items():
            if k in DEFAULTS:
                ch[k] = v
    elif to == "":
        apply(ch, station)
    else:
        apply(ch, to)
    ch["style"] = to
    return to


def follow(channels, station):
    """Applies the station's style to every channel that uses it. Returns (changed, own): how many follow it and how many have their own."""
    changed = own = 0
    for ch in channels:
        if style_of(ch) == "":
            apply(ch, station)
            ch["style"] = ""
            changed += 1
        else:
            own += 1
    return changed, own


def edited(ch):
    """A break setting was changed by hand: the channel now has its own settings."""
    if style_of(ch) != CUSTOM:
        ch["style"] = CUSTOM
