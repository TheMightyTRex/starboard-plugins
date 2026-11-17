"""TV station: your own TV channels in Jellyfin's Live TV, made from your films and series, with idents, trailers and
Coming up next cards in the breaks, and your own on-screen logo. Nothing streams until a channel is chosen.

Answers Starboard (cards, its pages, buttons and jobs) and Jellyfin (the channel list, the guide and the streams) on
port 8080, which Starboard puts on the home network. What Jellyfin reads is under /t/<token>/, a random word kept in
this plug-in's folder, so nobody else on the network can guess the addresses.
"""
import contextlib
import hashlib
import html
import json
import os
import re
import secrets
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import dog
import guide
import library
import sbplugin
import schedule
import stream

VERSION = "0.1.0"
CLIPS = "clips"  # folder in /data for idents and clips the owner adds
LOGOS = "logos"
MAX_UPLOAD = 60 * 1024 * 1024
CLIP_TYPES = (".mp4", ".mkv", ".mov", ".ts", ".webm", ".m4v")
LOGO_TYPES = (".png", ".svg")
COLOURS = {"0x1f5f99": "Blue", "0x2e7d32": "Green", "0xb3261e": "Red", "0x6a3d9a": "Purple", "0xb35c00": "Orange",
           "0x00695c": "Teal", "0xad1457": "Pink", "0x455a64": "Grey", "0x8d6e00": "Gold", "0x1a237e": "Navy"}
START_ON = {"0": "Back to back", "15": "On the quarter hour", "30": "On the half hour", "60": "On the hour"}
BREAKS = {"0": "No break", "60": "1 minute", "120": "2 minutes", "180": "3 minutes", "300": "5 minutes"}
ROLES = {"idents": "Ident", "clips": "Clip", "trailers": "Trailer"}
_lock = threading.RLock()
_streams = stream.Streams()
_refreshing = set()


# Kept state ---------------------------------------------------------------------------------------------------------
def state():
    s = sbplugin.remember("station", None)
    if not isinstance(s, dict):
        s = {"channels": [], "shared": {"idents": [], "clips": [], "sources": []}, "removed": []}
    s.setdefault("channels", [])
    s.setdefault("shared", {"idents": [], "clips": [], "sources": []})
    s.setdefault("removed", [])
    if not s.get("token"):
        s["token"] = secrets.token_urlsafe(18)
        sbplugin.keep("station", s)
    return s


def save(s):
    sbplugin.keep("station", s)


def settings():
    return sbplugin.settings()


def station_name(cfg=None):
    return str((cfg or settings()).get("station_name") or "Home TV").strip()[:40] or "Home TV"


def number(s, ch):
    if ch.get("number_set"):
        return int(ch["number_set"])
    first = int(settings().get("first_number") or 1)
    return first + [c["id"] for c in s["channels"]].index(ch["id"])


def numbered(s):
    """The channels in the owner's order, each with its number."""
    return [{**ch, "number": number(s, ch)} for ch in s["channels"]]


def find(s, cid):
    return next((c for c in s["channels"] if c["id"] == cid), None)


def new_channel(s, name):
    cid = secrets.token_hex(4)
    colour = list(COLOURS)[len(s["channels"]) % len(COLOURS)]
    return {"id": cid, "name": name.strip()[:40] or "Channel", "colour": colour, "on": True, "sources": [],
            "order": "in_order", "run": 1, "start_on": 30, "break_seconds": 0, "seed": secrets.randbits(48),
            "idents": "both", "ident_order": "in_order", "trailers": False, "clips": "both", "dog": {},
            "own": {"idents": [], "clips": [], "sources": []}, "eras": [], "lineup_hash": "", "trailer_clips": []}


# Jellyfin -----------------------------------------------------------------------------------------------------------
def jf_conf():
    return sbplugin._json_file(os.path.join(sbplugin.RUN, "jellyfin.json"), {}) or {}


def jf(path, method=None, data=None):
    c = jf_conf()
    if not c.get("url") or not c.get("api_key"):
        raise LookupError("Starboard has no Jellyfin key to give yet: add Jellyfin in Settings, Apps")
    return sbplugin.fetch(c["url"].rstrip("/") + path, sbplugin.jellyfin_headers(c["api_key"]), data=data, method=method)


def refresh_channel(cid, now=None):
    """Reads the channel's programmes from Jellyfin again. A changed line-up starts at the end of the programme on air,
    so new episodes join at the next boundary and nobody watching sees a jump."""
    now = time.time() if now is None else now
    with _lock:
        s = state()
        ch = find(s, cid)
        if not ch:
            return "That channel has gone"
        sources = list(ch["sources"])
    entries = library.lineup(jf, sources)
    trailers = library.trailers(jf, entries) if ch.get("trailers") else []
    with _lock:
        s = state()
        ch = find(s, cid)
        if not ch:
            return "That channel has gone"
        ch["trailer_clips"] = trailers
        h = schedule.lineup_hash(entries) + f":{ch['order']}:{ch['run']}:{ch['start_on']}:{ch['break_seconds']}"
        if h != ch.get("lineup_hash"):
            ch["eras"] = schedule.new_era(ch, entries, now)
            ch["lineup_hash"] = h
        ch["refreshed"] = int(now)
        save(s)
    later_jellyfin()
    return f"{ch['name']}: {sbplugin.plural(len(entries), 'programme')}"


def refresh_soon(cid):
    if cid in _refreshing:
        return

    def run():
        try:
            with sbplugin.working("a channel refresh"):
                refresh_channel(cid)
        except Exception as e:  # noqa: BLE001 - kept for the card and the page
            sbplugin.keep("_error", {"at": time.time(), "text": f"{type(e).__name__}: {e}"[:200]})
        finally:
            _refreshing.discard(cid)
    _refreshing.add(cid)
    threading.Thread(target=run, daemon=True).start()


def refresh_all(body=None):
    said = []
    for ch in list(state()["channels"]):
        said.append(refresh_channel(ch["id"]))
    sbplugin.clear_error()
    note = connect_jellyfin()
    return {"said": ("; ".join(said) or "No channels yet") + (f". {note}" if note else "")[:160]}


def address():
    a = str(settings().get("address") or "").strip().rstrip("/")
    return a or str((sbplugin.remember("learned", {}) or {}).get("address") or "")


def connect_jellyfin():
    """Adds the channel list and the guide to Jellyfin's Live TV, once, by address: the guide linked to this list only.
    Safe to run again; the owner's own tuners and guides are left alone."""
    base = address()
    if not base or not jf_conf().get("api_key"):
        return ""
    s = state()
    m3u_url, xml_url = f"{base}/t/{s['token']}/channels.m3u", f"{base}/t/{s['token']}/guide.xml"
    try:
        options = jf("/System/Configuration/livetv") or {}
        tuners = {t.get("Url"): t for t in options.get("TunerHosts") or []}
        added = 0
        most = int(settings().get("most_at_once") or 2)
        if m3u_url not in tuners:
            jf("/LiveTv/TunerHosts", method="POST", data={"Type": "m3u", "Url": m3u_url, "FriendlyName": station_name(), "TunerCount": most,
                                                          "ImportFavoritesOnly": False, "AllowHWTranscoding": True,
                                                          "EnableStreamLooping": False, "IgnoreDts": True})
            added += 1
            options = jf("/System/Configuration/livetv") or {}
        tuner = next((t.get("Id") for t in options.get("TunerHosts") or [] if t.get("Url") == m3u_url), None)
        if not any(g.get("Path") == xml_url for g in options.get("ListingProviders") or []):
            want = {"EnableAllTuners": False, "EnabledTuners": [tuner]} if tuner else {"EnableAllTuners": True}
            jf("/LiveTv/ListingProviders?validateListings=false&validateLogin=false", method="POST",
               data={"Type": "xmltv", "Path": xml_url, **want})
            added += 1
        if added:
            refresh_jellyfin_guide()
            return "Added to Jellyfin's Live TV"
        return ""
    except (urllib.error.URLError, OSError, ValueError, LookupError) as e:
        return f"Jellyfin did not take the channels: {getattr(e, 'reason', e)}"[:160]


def refresh_jellyfin_guide():
    tasks = jf("/ScheduledTasks?isHidden=false") or []
    task = next((t.get("Id") for t in tasks if t.get("Key") == "RefreshGuide"), None)
    if task:
        jf(f"/ScheduledTasks/Running/{task}", method="POST")


_later = {"timer": None}


def later_jellyfin():
    """After a change to the channels, Jellyfin reads the list and the guide again, once, a minute later."""
    t = _later["timer"]
    if t and t.is_alive():
        return

    def go():
        with contextlib.suppress(Exception):
            if not connect_jellyfin() and address():
                refresh_jellyfin_guide()
    _later["timer"] = threading.Timer(60, go)
    _later["timer"].daemon = True
    _later["timer"].start()


# What plays ---------------------------------------------------------------------------------------------------------
def clip_path(src):
    name = os.path.basename(src.split(":", 1)[1])
    return os.path.join(sbplugin.DATA, CLIPS, name)


def clips_for(s, ch):
    shared, own = s["shared"], ch.get("own") or {}
    idents = []
    if ch.get("idents") in ("own", "both"):
        idents += own.get("idents") or []
    if ch.get("idents") in ("shared", "both"):
        idents += shared.get("idents") or []
    fillers = list(ch.get("trailer_clips") or [])
    if ch.get("clips") in ("own", "both"):
        fillers += own.get("clips") or []
    if ch.get("clips") in ("shared", "both"):
        fillers += shared.get("clips") or []
    return {"idents": idents, "fillers": fillers}


def logo_file(cid):
    p = os.path.join(sbplugin.DATA, LOGOS, f"{cid}.png")
    return p if os.path.isfile(p) else None


def _art_ok(url, key):
    try:
        req = urllib.request.Request(url, method="HEAD", headers=sbplugin.jellyfin_headers(key))
        with urllib.request.urlopen(req, timeout=3) as r:  # Jellyfin, from Starboard's settings  # nosec B310
            return r.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


def plan_for(cid, still=False):
    """For a channel's Hub: what to play at a moment, with all it needs to draw it."""
    def plan(now, started, piece=None):
        s = state()
        ch = find(s, cid)
        cfg = settings()
        if not ch:
            return None, None, None
        sched = schedule.Channel(ch)
        opts = dog.resolve(cfg, ch)
        if piece is None:
            a, pieces = schedule.pieces_at(sched, now, clips_for(s, ch), {"seed": ch["seed"], "cards": opts["cards"],
                                                                         "ident_order": ch.get("ident_order", "in_order")})
            if not a:
                return None, None, None
            piece = next((p for p in pieces if p["start"] <= now < p["end"]), None) or {"kind": "slate", "start": now, "end": a["end"]}
        else:
            a = sched.airing(now)
        W, H, kbps = stream.SIZES.get(str(cfg.get("picture") or "720"), stream.SIZES["720"])
        folder = os.path.join("/tmp", "tv-station", f"{cid}-{secrets.token_hex(3)}")
        texts = dog.Texts(folder)
        names = {"channel": ch["name"], "station": station_name(cfg)}
        c = jf_conf()
        ctx = {"W": W, "H": H, "kbps": kbps, "opts": opts, "names": names, "logo": logo_file(cid), "jf_url": c.get("url", ""),
               "jf_key": c.get("api_key", ""), "ts_offset": max(0.0, now - started) + 1.0, "texts": texts, "clip_path": clip_path,
               "colour": ch.get("colour"), "copy_ok": bool(cfg.get("copy_plain", True)), "still": still}
        if a:
            nxt = sched.airing(a["end"])
            if nxt:
                ctx["next_words"] = f"Up next at {time.strftime('%H:%M', time.localtime(nxt['start']))}: {nxt['entry'].get('title')}"
        if piece["kind"] == "card":
            url = f"{c.get('url', '').rstrip('/')}/Items/{piece['airing']['entry'].get('backdrop')}/Images/Backdrop?maxWidth={W}&quality=85"
            if c.get("url") and _art_ok(url, c.get("api_key", "")):
                ctx["art"] = url

        def cleanup():
            with contextlib.suppress(OSError):
                for f in os.listdir(folder):
                    os.remove(os.path.join(folder, f))
                os.rmdir(folder)
        return piece, ctx, cleanup
    return plan


def preview(cid, kind="programme", at=None):
    """One frame of the channel as it would look now, as a PNG: the DOG on the programme, or a Coming up next card."""
    s = state()
    ch = find(s, cid)
    if not ch:
        raise LookupError("No such channel")
    now = time.time() if at is None else at
    a = schedule.Channel(ch).airing(now)
    if not a:
        raise LookupError("The channel has nothing to show yet")
    if kind == "card":
        nxt = schedule.Channel(ch).airing(a["end"]) or a
        piece = {"kind": "card", "card": "next", "start": now, "end": now + 10, "airing": nxt}
    else:
        piece = {"kind": "programme", "start": a["start"], "end": a["content_end"], "airing": a}
        early = a["start"] + min(90.0, (a["content_end"] - a["start"]) / 2)
        now = now if early <= now < a["content_end"] - 5 else early  # in a break: a frame from the programme
    piece, ctx, cleanup = plan_for(cid, still=True)(now, now, piece=piece)
    try:
        r = subprocess.run(stream.piece_command(piece, now, ctx), capture_output=True, timeout=60, check=False)
    finally:
        cleanup()
    if r.returncode != 0 or not r.stdout:
        raise RuntimeError((r.stderr.decode("utf-8", "replace").strip().splitlines() or ["FFmpeg did not draw the frame"])[-1][:200])
    return r.stdout


def made_logo(ch):
    """A plain logo for a channel with none of its own: its number and name on its colour, made once and kept."""
    s = state()
    n = number(s, ch)
    key = hashlib.sha256(f"{n}|{ch['name']}|{ch.get('colour')}".encode()).hexdigest()[:10]
    path = os.path.join(sbplugin.DATA, LOGOS, f"made-{ch['id']}-{key}.png")
    if os.path.isfile(path):
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    texts = dog.Texts(os.path.join("/tmp", "tv-station", "logo-" + key))
    graph = ",".join([dog._text(texts.file(str(n)), 120, "(w-tw)/2", "60", border=False),
                      dog._text(texts.file(ch["name"][:14]), 30, "(w-tw)/2", "200", border=False)])
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c={ch.get('colour') or '0x1f5f99'}:s=256x256",
                    "-vf", graph, "-frames:v", "1", "-y", path], capture_output=True, timeout=30, check=False)
    for f in os.listdir(os.path.dirname(path)):
        if f.startswith(f"made-{ch['id']}-") and f != os.path.basename(path):
            with contextlib.suppress(OSError):
                os.remove(os.path.join(os.path.dirname(path), f))
    return path if os.path.isfile(path) else None


# Words for the pages --------------------------------------------------------------------------------------------------
def hm(t):
    return time.strftime("%H:%M", time.localtime(t))


def day_hm(t, now=None):
    now = time.time() if now is None else now
    words = dog.when_words(t, now)
    return words.replace(" at ", " ")


def describe(e):
    return f"{e.get('title')}" + (f", {guide.episode_words(e)}" if guide.episode_words(e) else "")


def source_words(src):
    return f"{library.KINDS.get(src['kind'], 'Source')}: {src.get('name') or src.get('id')}"


def _choice(label, value, options, default_words=None):
    first = f"Station default ({default_words})" if default_words else ""
    first = first if len(first) <= 40 else "Station default"
    opts = ([["", first]] if default_words else []) + [[k, v] for k, v in options.items()]
    return {"label": label, "value": "" if value in (None, "") else str(value), "options": opts[:12]}


def channels_page(said=None, now=None):
    now = time.time() if now is None else now
    s = state()
    cfg = settings()
    base = address()
    menus, items = [], []
    for ch in numbered(s):
        cid, n = ch["id"], ch["number"]
        sched = schedule.Channel(ch)
        a = sched.airing(now)
        detail = (f"Now: {describe(a['entry'])}" if a else "Nothing to show yet: add a series, film, collection or playlist")
        menus.append({"id": cid, "title": f"{n}  {ch['name']}", "group": "Channels", "detail": detail[:200], "active": bool(ch.get("on", True))})

        def row(key, title, group, **more):
            # Each row's state in words (plug-in API 1.12), so no row reads "Not tested", which suits a list of sources.
            more.setdefault("state", "ok")
            more.setdefault("state_label", "Saved")
            items.append({"id": f"{cid}:{key}", "title": title[:120], "group": group, "menu": cid, **more})
        row("on", "On air" if ch.get("on", True) else "Off air", "Channel", on=bool(ch.get("on", True)),
            state="ok" if ch.get("on", True) else "off", state_label="On air" if ch.get("on", True) else "Off air",
            detail="Activate to put it in Jellyfin's Live TV. Up and Down move it in the list, which sets its number.",
            actions=["toggle", "up", "down", "remove"])
        row("name", f"Name: {ch['name']}", "Channel", actions=["attach"],
            attach={"label": "Rename", "field": "Name", "hint": "Up to 40 characters", "value": ch["name"]})
        row("number", f"Number: {n}", "Channel", actions=["attach"],
            detail="Its number in Jellyfin's Live TV. Numbers from 1 put the channels first, before the free channels from 101.",
            attach={"label": "Change number", "field": "Number", "hint": "A whole number from 1 to 9999. Leave it empty to number by its place.",
                    "value": str(ch.get("number_set") or "")})
        row("colour", "Colour", "Channel", choice=_choice("Colour", ch.get("colour"), COLOURS),
            detail="On its cards and its made logo. Words always say what each thing is, so the colour is never the only sign.")
        row("logo", "Logo: " + ("your picture" if logo_file(cid) else "made from its number and name"), "Channel",
            actions=["attach", "detach"] if logo_file(cid) else ["attach"],
            attach={"label": "Add logo", "field": "Logo", "hint": "A PNG with a clear background, at least 256 pixels tall", "accept": ".png"})
        for i, src in enumerate(ch["sources"]):
            row(f"src{i}", source_words(src), "What it shows", detail=src.get("detail", ""), actions=["remove", "up", "down"],
                state_label="In the line-up")
        for kind, label in (("series", "Add a series"), ("film", "Add a film"), ("collection", "Add a collection"),
                            ("playlist", "Add a playlist"), ("genre", "Add a genre"), ("decade", "Add a decade")):
            hint = {"decade": "Such as 1980s", "genre": "Such as Comedy"}.get(kind, "Its name, or the start of it")
            row(f"add-{kind}", label, "What it shows", actions=["attach"], attach={"label": label, "field": "Name", "hint": hint},
                state="unknown", state_label="Add one")
        row("order", "Order", "Order and times", choice=_choice("Order", ch.get("order"), {"in_order": "In order", "shuffle": "Shuffled"}))
        row("run", "Episodes of a series in a row", "Order and times",
            choice=_choice("In a row", ch.get("run"), {str(k): str(k) for k in (1, 2, 3, 4, 6)}))
        row("start_on", "Programmes start", "Order and times", choice=_choice("Start", ch.get("start_on"), START_ON),
            detail="On the quarter, half or whole hour, the break fills the time to the next one.")
        row("break_seconds", "Break between programmes", "Order and times", choice=_choice("Break", ch.get("break_seconds"), BREAKS),
            detail="Added after each programme. With programmes on the half hour, the break also fills the rest of the slot.")
        both = {"none": "None", "own": "This channel's", "shared": "The station's", "both": "This channel's and the station's"}
        row("idents", "Idents", "Breaks", choice=_choice("Idents", ch.get("idents"), both))
        row("ident_order", "Idents play", "Breaks", choice=_choice("Idents play", ch.get("ident_order"), {"in_order": "In order", "random": "In a random order"}))
        row("trailers", "Trailers", "Breaks", choice=_choice("Trailers", "on" if ch.get("trailers") else "off",
                                                              {"off": "None", "on": "Trailers of its films, from Jellyfin"}))
        row("clips", "Your clips", "Breaks", choice=_choice("Clips", ch.get("clips"), both))
        own = ch.get("own") or {}
        for role in ("idents", "clips"):
            for c in own.get(role) or []:
                row(f"clip-{c['id']}", f"{ROLES[role]}: {c['title']}", "Breaks", detail=f"{round(c['dur'])} seconds", actions=["remove"],
                    state_label="Ready")
        row("add-ident", "Add an ident", "Breaks", actions=["attach"], state="unknown", state_label="Add one",
            attach={"label": "Add an ident", "field": "Ident", "hint": "A short video, up to 60 MB, or the name of a Jellyfin collection of them",
                    "accept": ",".join(CLIP_TYPES)})
        row("add-clip", "Add a clip", "Breaks", actions=["attach"], state="unknown", state_label="Add one",
            attach={"label": "Add a clip", "field": "Clip", "hint": "A trailer or clip, up to 60 MB, or the name of a Jellyfin collection of them",
                    "accept": ",".join(CLIP_TYPES)})
        st = dog.resolve(cfg, None)
        own_dog = ch.get("dog") or {}
        yesno = {"true": "Yes", "false": "No"}
        for key, label, options in (("kind", "On-screen logo", dog.KINDS), ("corner", "Corner", dog.CORNERS),
                                    ("size", "Size", {"small": "Small", "medium": "Medium", "large": "Large"}),
                                    ("margin", "Distance from the edge", {"small": "Close", "medium": "Inside the safe area", "large": "Further in"}),
                                    ("opacity", "Opacity", {str(p): f"{p}%" for p in (40, 50, 60, 70, 80, 90, 100)}),
                                    ("when", "When it shows", dog.WHEN),
                                    ("fade_in", "Fades in after the opening", {"0": "No, at once", "30": "After 30 seconds", "60": "After 1 minute", "120": "After 2 minutes"}),
                                    ("clock", "Clock", yesno), ("label", "Label", dog.LABELS), ("plate", "Backing plate", yesno),
                                    ("strap_start", "Programme name at the start", yesno), ("strap_end", "Up next during the end credits", yesno),
                                    ("cards", "Coming up next and Later cards", yesno)):
            dv = st[key]
            dw = (options.get(str(dv).lower()) if isinstance(dv, bool) else options.get(str(dv))) or str(dv)
            v = own_dog.get(key, "")
            row(f"dog-{key}", label, "On-screen logo and straps", choice=_choice(label, str(v).lower() if isinstance(v, bool) else v, options, dw))
        prev = {"title": "Preview a frame", "detail": "Opens a frame as it would be drawn now, with these settings. Nothing changes until you choose an option."}
        if base:
            prev["link"] = {"url": f"{base}/t/{s['token']}/preview/{cid}.png", "label": f"Preview a frame of {ch['name']}"}
            items.append({"id": f"{cid}:preview-card", "title": "Preview a Coming up next card", "group": "On-screen logo and straps", "menu": cid,
                          "state": "unknown", "state_label": "Preview",
                          "link": {"url": f"{base}/t/{s['token']}/preview/{cid}.png?kind=card", "label": f"Preview a Coming up next card on {ch['name']}"}})
        else:
            prev["detail"] = "Open this plug-in's web page once from its page in Settings, Plug-ins, so it knows its address."
        row("preview", prev.pop("title"), "On-screen logo and straps", state="unknown", state_label="Preview", **prev)
        for k, a2 in enumerate(sched.airings(now, now + 86400, limit=60)):
            e = a2["entry"]
            new = guide.is_new(e, a2["start"])
            row(f"today{k}", f"{day_hm(a2['start'], now)} to {hm(a2['end'])}  {e.get('title')}", "Today and tomorrow",
                detail=(guide.episode_words(e) + ". " if guide.episode_words(e) else "") + (e.get("plot") or "")[:120],
                state="ok" if new else "unknown", state_label="New" if new else "Repeat")
    out = {"type": "list", "title": "Channels", "intro": (f"{station_name(cfg)}: {sbplugin.plural(len(s['channels']), 'channel')}. "
                                                          "Each channel opens to its name, what it shows, its breaks, its on-screen logo "
                                                          "and its programmes for today and tomorrow."),
           "add": {"label": "Add a channel", "hint": "Its name, such as Comedy. Up to 40 characters", "placeholder": "Channel name"},
           "menus": menus, "items": items}
    if said:
        out["said"] = said[:200]
    err = sbplugin.last_error()
    if err:
        out["notices"] = [{"id": "error", "tone": "warning", "title": "The last refresh did not finish", "text": err, "dismiss": True}]
    return out


def add_source(ch, kind, words):
    matches = library.search(jf, kind, words)
    m = library.best(matches, words)
    if not m:
        raise ValueError(f"Nothing in Jellyfin matches {words}")
    if any(src["kind"] == kind and str(src["id"]) == str(m[0]) for src in ch["sources"]):
        raise ValueError(f"{m[1]} is on this channel already")
    ch["sources"].append({"kind": kind, "id": m[0], "name": m[1]})
    others = [x[1] for x in matches if x != m][:3]
    return f"Added {m[1]}" + (f". Also found: {', '.join(others)}" if others else "")


def channels_post(body, now=None):
    action, rid, value = body.get("action"), str(body.get("id") or ""), body.get("value")
    with _lock:
        s = state()
        if action == "add":
            name = str(value or "").strip()
            if not name:
                raise ValueError("Enter the channel's name")
            ch = new_channel(s, name)
            s["channels"].append(ch)
            save(s)
            return channels_page(f"Added {ch['name']}. Open it to add a series, film, collection or playlist", now)
        if action == "dismiss":
            sbplugin.clear_error()
            return channels_page(None, now)
        cid, _, key = rid.partition(":")
        ch = find(s, cid)
        if not ch:
            raise ValueError("That channel has gone")
        said, refresh = "Saved", False
        if key == "on" and action == "toggle":
            ch["on"] = not ch.get("on", True)
            said = f"{ch['name']} is {'on' if ch['on'] else 'off'} air"
            later_jellyfin()
        elif key == "on" and action in ("up", "down"):
            i = s["channels"].index(ch)
            j = i - 1 if action == "up" else i + 1
            if 0 <= j < len(s["channels"]):
                s["channels"][i], s["channels"][j] = s["channels"][j], s["channels"][i]
            said = f"{ch['name']} moved {action}"
            later_jellyfin()
        elif key == "on" and action == "remove":
            s["channels"].remove(ch)
            s["removed"] = (s["removed"] + [{**ch, "removed": int(time.time())}])[-10:]
            said = f"Removed {ch['name']}. Its settings are kept in the plug-in's folder"
            later_jellyfin()
        elif key == "name" and action == "attach":
            name = str(value or "").strip()[:40]
            if not name:
                raise ValueError("Enter a name")
            ch["name"] = name
            said = f"Renamed {name}"
            later_jellyfin()
        elif key == "number" and action == "attach":
            v = str(value or "").strip()
            if v and not (v.isdigit() and 1 <= int(v) <= 9999):
                raise ValueError("Enter a whole number from 1 to 9999")
            ch["number_set"] = int(v) if v else 0
            said = f"{ch['name']} is number {number(s, ch)}"
            later_jellyfin()
        elif key == "logo" and action == "detach":
            with contextlib.suppress(OSError):
                os.remove(os.path.join(sbplugin.DATA, LOGOS, f"{cid}.png"))
            said = "Logo removed: the made logo is used"
        elif key.startswith("add-") and action == "attach" and key[4:] in library.KINDS:
            said = add_source(ch, key[4:], str(value or ""))
            refresh = True
        elif key in ("add-ident", "add-clip") and action == "attach":
            role = "idents" if key == "add-ident" else "clips"
            said = add_jellyfin_clips(ch.setdefault("own", {"idents": [], "clips": [], "sources": []}), role, str(value or ""))
        elif key.startswith("src") and action in ("remove", "up", "down"):
            i = int(key[3:])
            if 0 <= i < len(ch["sources"]):
                if action == "remove":
                    gone = ch["sources"].pop(i)
                    said = f"Removed {gone.get('name')}"
                else:
                    j = i - 1 if action == "up" else i + 1
                    if 0 <= j < len(ch["sources"]):
                        ch["sources"][i], ch["sources"][j] = ch["sources"][j], ch["sources"][i]
                refresh = True
        elif key.startswith("clip-") and action == "remove":
            own = ch.get("own") or {}
            for role in ("idents", "clips"):
                own[role] = [c for c in own.get(role) or [] if c["id"] != key[5:]]
            said = "Removed the clip. Its file stays in the plug-in's folder until you add another with the same name"
        elif action == "choose":
            said = choose(ch, key, value)
            refresh = key in ("order", "run", "start_on", "break_seconds", "trailers")
        else:
            raise ValueError("That cannot be changed here")
        save(s)
    if refresh:
        refresh_soon(cid)
        said += ". The new line-up starts after the programme on now"
    return channels_page(said, now)


def choose(ch, key, value):
    v = "" if value is None else str(value)
    if key == "colour" and v in COLOURS:
        ch["colour"] = v
    elif key == "order" and v in ("in_order", "shuffle"):
        ch["order"] = v
    elif key == "run" and v.isdigit():
        ch["run"] = max(1, min(6, int(v)))
    elif key == "start_on" and v in START_ON:
        ch["start_on"] = int(v)
    elif key == "break_seconds" and v in BREAKS:
        ch["break_seconds"] = int(v)
    elif key in ("idents", "clips") and v in ("none", "own", "shared", "both"):
        ch[key] = v
    elif key == "ident_order" and v in ("in_order", "random"):
        ch["ident_order"] = v
    elif key == "trailers" and v in ("on", "off"):
        ch["trailers"] = v == "on"
    elif key.startswith("dog-") and key[4:] in dog.DEFAULTS:
        k = key[4:]
        d = dog.DEFAULTS[k]
        if v == "":
            (ch.setdefault("dog", {})).pop(k, None)
        elif isinstance(d, bool):
            ch.setdefault("dog", {})[k] = v == "true"
        elif isinstance(d, int):
            ch.setdefault("dog", {})[k] = int(v) if v.isdigit() else d
        else:
            ch.setdefault("dog", {})[k] = v
    else:
        raise ValueError("That is not one of the choices")
    return "Saved"


def add_jellyfin_clips(holder, role, words):
    matches = library.search(jf, "clips", words)
    m = library.best(matches, words)
    if not m:
        raise ValueError(f"No Jellyfin collection or folder matches {words}. To add a file, choose one in place of a name")
    got = library.jellyfin_clips(jf, m[0], role)
    if not got:
        raise ValueError(f"{m[1]} has no videos of 10 minutes or less")
    have = {c["id"] for c in holder.get(role) or []}
    holder[role] = (holder.get(role) or []) + [c for c in got if c["id"] not in have]
    return f"Added {sbplugin.plural(len(got), ROLES[role].lower())} from {m[1]}"


def probe_seconds(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type", "-of", "json", path],
                       capture_output=True, timeout=30, check=False)
    info = json.loads(r.stdout or b"{}")
    dur = float((info.get("format") or {}).get("duration") or 0)
    has_audio = any(st.get("codec_type") == "audio" for st in info.get("streams") or [])
    has_video = any(st.get("codec_type") == "video" for st in info.get("streams") or [])
    return dur, has_audio, has_video


def save_upload(name, length, rfile, folder, types):
    if length <= 0 or length > MAX_UPLOAD:
        raise ValueError("Choose a file of up to 60 MB")
    base = re.sub(r"[^A-Za-z0-9._ -]", "", os.path.basename(name or ""))[:80].strip() or "file"
    if not base.lower().endswith(types):
        raise ValueError(f"Choose a file ending {', '.join(types)}")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, base)
    left = length
    with open(path + ".part", "wb") as f:
        while left > 0:
            got = rfile.read(min(65536, left))
            if not got:
                break
            f.write(got)
            left -= len(got)
    if left:
        os.remove(path + ".part")
        raise ValueError("The file did not arrive whole. Try again")
    os.replace(path + ".part", path)
    return path, base


def add_clip_file(holder, role, name, length, rfile):
    path, base = save_upload(name, length, rfile, os.path.join(sbplugin.DATA, CLIPS), CLIP_TYPES)
    dur, has_audio, has_video = probe_seconds(path)
    if not has_video or dur <= 0:
        raise ValueError(f"{base} has no picture FFmpeg can read")
    if dur > 600:
        raise ValueError(f"{base} is over 10 minutes: too long for a break")
    cid = hashlib.sha256(base.encode()).hexdigest()[:10]
    holder[role] = [c for c in holder.get(role) or [] if c["id"] != cid] + [
        {"id": cid, "src": f"file:{base}", "dur": round(dur, 2), "title": base, "role": role, "has_audio": has_audio, "audio": None}]
    return f"Added {base}, {round(dur)} seconds"


def channels_file(name, item, length, rfile):
    with _lock:
        s = state()
        cid, _, key = item.partition(":")
        ch = find(s, cid)
        if not ch:
            raise ValueError("That channel has gone")
        if key == "logo":
            path, base = save_upload(name, length, rfile, os.path.join("/tmp", "tv-station", "up"), LOGO_TYPES)
            out = os.path.join(sbplugin.DATA, LOGOS, f"{cid}.png")
            os.makedirs(os.path.dirname(out), exist_ok=True)
            r = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", path, "-vf", "scale=-1:256", "-frames:v", "1", "-y", out],
                               capture_output=True, timeout=30, check=False)
            os.remove(path)
            if r.returncode != 0:
                raise ValueError(f"{base} could not be read as a picture. Choose a PNG")
            said = f"Added the logo {base}"
        elif key in ("add-ident", "add-clip"):
            said = add_clip_file(ch.setdefault("own", {"idents": [], "clips": [], "sources": []}),
                                 "idents" if key == "add-ident" else "clips", name, length, rfile)
        else:
            raise ValueError("That row takes no file")
        save(s)
    return channels_page(said)


def clips_page(said=None):
    s = state()
    sh = s["shared"]
    items = []
    for role in ("idents", "clips"):
        for c in sh.get(role) or []:
            items.append({"id": f"{role}:{c['id']}", "title": c["title"][:120], "detail": f"{round(c['dur'])} seconds",
                          "group": "The station's idents" if role == "idents" else "The station's clips", "actions": ["remove"],
                          "state": "ok", "state_label": "Ready"})
    for role, label in (("idents", "Add the station's idents"), ("clips", "Add the station's clips")):
        items.append({"id": f"add:{role}", "title": label, "group": "Add", "actions": ["attach"], "state": "unknown", "state_label": "Add one",
                      "attach": {"label": label, "field": "Name", "hint": "A video up to 60 MB, or the name of a Jellyfin collection or folder",
                                 "accept": ",".join(CLIP_TYPES)}})
    out = {"type": "list", "title": "Idents and clips", "items": items,
           "intro": "Idents and clips every channel can use in its breaks. Each channel chooses whether to use these, its own or both."}
    if said:
        out["said"] = said[:200]
    return out


def clips_post(body):
    action, rid, value = body.get("action"), str(body.get("id") or ""), body.get("value")
    with _lock:
        s = state()
        role, _, cid = rid.partition(":")
        if action == "remove" and role in ("idents", "clips"):
            s["shared"][role] = [c for c in s["shared"].get(role) or [] if c["id"] != cid]
            said = "Removed"
        elif action == "attach" and role == "add" and cid in ("idents", "clips"):
            said = add_jellyfin_clips(s["shared"], cid, str(value or ""))
        else:
            raise ValueError("That cannot be changed here")
        save(s)
    return clips_page(said)


def clips_file(name, item, length, rfile):
    role = item.partition(":")[2]
    if role not in ("idents", "clips"):
        raise ValueError("That row takes no file")
    with _lock:
        s = state()
        said = add_clip_file(s["shared"], role, name, length, rfile)
        save(s)
    return clips_page(said)


def guide_page(now=None):
    """The guide as tables to read: a section for each channel, a row for each programme in the next 24 hours, the
    time as each row's header."""
    now = time.time() if now is None else now
    s = state()
    items = []
    for ch in numbered(s):
        if not ch.get("on", True):
            continue
        for k, a in enumerate(schedule.Channel(ch).airings(now, now + 86400, limit=100)):
            e = a["entry"]
            items.append({"id": f"{ch['id']}:{k}", "title": e.get("title") or "Programme", "group": f"{ch['number']} {ch['name']}"[:40],
                          "cells": {"time": f"{day_hm(a['start'], now)} to {hm(a['end'])}", "programme": (e.get("title") or "")[:80],
                                    "episode": guide.episode_words(e)[:80], "shown": "New" if guide.is_new(e, a["start"]) else "Repeat",
                                    "synopsis": (e.get("plot") or "")[:80]}})
    return {"type": "list", "title": "Guide", "layout": "folds", "readonly": True,
            "intro": f"What is on {station_name()} in the next 24 hours. Jellyfin's guide has the next 7 days.",
            "columns": [{"key": "time", "label": "Time"}, {"key": "programme", "label": "Programme"},
                        {"key": "episode", "label": "Episode"}, {"key": "shown", "label": "New or repeat"},
                        {"key": "synopsis", "label": "About it"}],
            "filters": [{"key": "shown", "label": "New or repeat"}], "items": items}


def card(now=None):
    """What is on now: each channel's programme, how far through, and what is next."""
    now = time.time() if now is None else now
    s = state()
    playing = _streams.playing()
    items = []
    for ch in numbered(s):
        if not ch.get("on", True):
            continue
        sched = schedule.Channel(ch)
        a = sched.airing(now)
        if not a:
            continue
        nxt = sched.airing(a["end"])
        e = a["entry"]
        name = ch["name"] + (f" ({sbplugin.plural(playing[ch['id']], 'viewer')})" if ch["id"] in playing else "")
        item = {"channel": name, "number": str(ch["number"]), "now": describe(e), "start": int(a["start"]), "stop": int(a["end"])}
        if nxt:
            item.update({"next": describe(nxt["entry"]), "next_start": int(nxt["start"])})
        items.append(item)
    if not s["channels"]:
        return sbplugin.band({"items": [], "note": "No channels yet. Add one in Settings, Plug-ins, TV station, Channels"}, "needs_setup")
    note = ""
    if not address():
        note = "Open the plug-in's web page once from its page in Settings, Plug-ins, so Jellyfin can be given its channels"
    elif sbplugin.last_error():
        note = f"Last refresh: {sbplugin.last_error()}"
    status = "running" if playing else "ok"
    label = f"{sbplugin.plural(len(playing), 'channel')} playing" if playing else "Nothing streaming"
    return sbplugin.band({"items": items[:12], "note": note[:160]}, "warning" if note else status, label=label, refresh=60)


# The web server -------------------------------------------------------------------------------------------------------
HOME = """<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{name}</title><style>body{{font:1.125rem/1.5 system-ui,sans-serif;margin:0;padding:24px 16px;background:#fff;color:#1a1a1a}}
@media (prefers-color-scheme:dark){{body{{background:#121417;color:#f2f2f2}}}}main{{max-width:40rem;margin:auto}}</style></head>
<body><main><h1>{name}</h1><p>{count}. They are in Jellyfin's Live TV, at the top of the channel list.</p>
<p>Change the channels in Starboard: Settings, Plug-ins, TV station.</p></main></body></html>"""


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _json(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _bytes(self, status, data, kind, cache=None):
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        if cache:
            self.send_header("Cache-Control", cache)
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        try:
            got = json.loads(self.rfile.read(min(n, 65536)) or b"{}") if n else {}
        except ValueError:
            got = {}
        return got if isinstance(got, dict) else {}

    def _keyed(self):
        return secrets.compare_digest(self.headers.get("X-Api-Key") or "", sbplugin._key() or secrets.token_hex(8))

    def _base(self, token):
        host = self.headers.get("Host") or ""
        if not re.match(r"^[A-Za-z0-9.\-\[\]:]+$", host):
            return address() + f"/t/{token}"
        return f"http://{host}/t/{token}"

    def do_GET(self):  # noqa: N802
        url = urllib.parse.urlparse(self.path)
        p = url.path
        try:
            if p == "/health":
                return self._json(200, {"ok": True, "ffmpeg": stream.has_ffmpeg()})
            if p == "/card":
                return self._json(200, card())
            if p in ("/channels", "/clips", "/guide"):
                if not self._keyed():
                    return self._json(403, {"error": "Only Starboard may open this"})
                return self._json(200, {"/channels": channels_page, "/clips": clips_page, "/guide": guide_page}[p]())
            if p == "/":
                self._learn()
                s = state()
                page = HOME.format(name=html.escape(station_name()), count=html.escape(sbplugin.plural(len(s["channels"]), "channel").capitalize()))
                return self._bytes(200, page.encode(), "text/html; charset=utf-8")
            m = re.match(r"^/t/([A-Za-z0-9_-]+)/(.+)$", p)
            if m:
                return self._tv(m.group(1), m.group(2), urllib.parse.parse_qs(url.query))
            return self._json(404, {"error": "Not found"})
        except (BrokenPipeError, ConnectionResetError):
            return None
        except Exception as e:  # noqa: BLE001 - the caller reads why
            return self._json(502, {"error": f"{e}"[:200]})

    def _learn(self):
        host = self.headers.get("Host") or ""
        if re.match(r"^[A-Za-z0-9.\-]+:\d+$", host) and not host.startswith(("localhost", "127.")):
            learned = sbplugin.remember("learned", {}) or {}
            if learned.get("address") != f"http://{host}":
                sbplugin.keep("learned", {"address": f"http://{host}", "at": int(time.time())})
                threading.Thread(target=connect_jellyfin, daemon=True).start()

    def _tv(self, token, rest, query):
        s = state()
        if not secrets.compare_digest(token, s["token"]):
            return self._json(404, {"error": "Not found"})
        base = self._base(token)
        chans = numbered(s)
        if rest == "channels.m3u":
            return self._bytes(200, guide.m3u(chans, base, station_name()).encode(), "audio/x-mpegurl; charset=utf-8")
        if rest == "guide.xml":
            days = max(1, min(14, int(settings().get("guide_days") or 7)))
            return self._bytes(200, guide.xmltv(chans, base, station_name(), days=days).encode(), "application/xml; charset=utf-8")
        m = re.match(r"^logo/([0-9a-f]{8})\.png$", rest)
        if m:
            ch = find(s, m.group(1))
            path = ch and (logo_file(ch["id"]) or made_logo(ch))
            if not path:
                return self._json(404, {"error": "No logo"})
            with open(path, "rb") as f:
                return self._bytes(200, f.read(), "image/png", "max-age=3600")
        m = re.match(r"^art/([0-9a-fA-F]{32})\.jpg$", rest)
        if m:
            c = jf_conf()
            data = sbplugin.fetch(f"{c.get('url', '').rstrip('/')}/Items/{m.group(1)}/Images/Primary?maxWidth=600&quality=85",
                                  sbplugin.jellyfin_headers(c.get("api_key", "")), raw=True)
            return self._bytes(200, data, "image/jpeg", "max-age=86400")
        m = re.match(r"^preview/([0-9a-f]{8})\.png$", rest)
        if m:
            kind = "card" if (query.get("kind") or [""])[0] == "card" else "programme"
            return self._bytes(200, preview(m.group(1), kind), "image/png", "no-store")
        m = re.match(r"^stream/([0-9a-f]{8})\.ts$", rest)
        if m:
            return self._stream(m.group(1))
        return self._json(404, {"error": "Not found"})

    def _stream(self, cid):
        s = state()
        ch = find(s, cid)
        if not ch or not ch.get("on", True):
            return self._json(404, {"error": "No such channel"})
        cfg = settings()
        most = max(1, min(6, int(cfg.get("most_at_once") or 2)))
        grace = max(5, min(300, int(cfg.get("stop_after") or 30)))
        try:
            hub = _streams.get(cid, plan_for(cid), most, grace)
        except stream.Busy as e:
            return self._json(503, {"error": str(e)})
        q = hub.join()
        self.send_response(200)
        self.send_header("Content-Type", "video/mp2t")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        try:
            while True:
                chunk = q.get(timeout=60)
                if chunk is None:
                    break
                self.wfile.write(chunk)
        except Exception:  # noqa: BLE001 - the viewer went, or nothing came for a minute
            pass
        finally:
            hub.leave(q)

    def do_POST(self):  # noqa: N802
        url = urllib.parse.urlparse(self.path)
        p = url.path
        try:
            if p in ("/update/before", "/update/after"):
                body = self._body()
                if p == "/update/before":
                    _streams.stop_all()
                    return self._json(200, sbplugin.before_update(body))
                return self._json(200, sbplugin.after_update(body))
            if p in ("/channels", "/clips", "/guide", "/channels/file", "/clips/file"):
                if not self._keyed():
                    return self._json(403, {"error": "Only Starboard may change this"})
                if p.endswith("/file"):
                    q = urllib.parse.parse_qs(url.query)
                    fn = channels_file if p.startswith("/channels") else clips_file
                    with sbplugin.working("a file being added"):
                        return self._json(200, fn((q.get("name") or [""])[0], (q.get("id") or [""])[0],
                                                  int(self.headers.get("Content-Length") or 0), self.rfile))
                body = self._body()
                return self._json(200, {"/channels": lambda: channels_post(body), "/clips": lambda: clips_post(body),
                                        "/guide": guide_page}[p]())
            if p == "/jobs/refresh":
                if sbplugin.holding():
                    return self._json(200, {"said": "Not started: the plug-in is about to be updated"})
                with sbplugin.working("refresh"):
                    return self._json(200, refresh_all())
            if p == "/actions/refresh":
                threading.Thread(target=lambda: _safe(refresh_all), daemon=True).start()
                return self._json(200, {"said": "Reading every channel's programmes from Jellyfin again"})
            if p == "/actions/stop":
                n = _streams.stop_all()
                return self._json(200, {"said": f"Stopped {sbplugin.plural(n, 'channel')}" if n else "Nothing was streaming"})
            return self._json(404, {"error": "Not found"})
        except ValueError as e:
            return self._json(400, {"error": f"{e}"[:200]})
        except Exception as e:  # noqa: BLE001 - Starboard shows the sentence
            return self._json(502, {"error": f"{e}"[:200]})


def _safe(fn):
    try:
        fn()
    except Exception as e:  # noqa: BLE001 - kept for the card
        sbplugin.keep("_error", {"at": time.time(), "text": f"{type(e).__name__}: {e}"[:200]})


def main():
    os.makedirs(os.path.join("/tmp", "tv-station"), exist_ok=True)
    state()
    # Once after a start, the channels are added to Jellyfin if they are not there yet. Nothing else runs at rest.
    threading.Timer(20, lambda: _safe(connect_jellyfin)).start()
    port = int(os.environ.get("PORT", 8080))
    print(f"TV station {VERSION} listening on {port}", flush=True)

    class Server(ThreadingHTTPServer):
        daemon_threads = True
    Server(("0.0.0.0", port), Handler).serve_forever(poll_interval=60)  # inside its own container  # nosec B104


if __name__ == "__main__":
    main()
