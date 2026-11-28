"""Create your own TV channel (id tv-station): your own TV channels in Jellyfin's Live TV, made from your films and
series, with idents, trailers, promos and Coming up next cards in the breaks, your own on-screen logo, and a broadcast
pack for the channels' own branding. Nothing streams until a channel is chosen.

Answers Starboard (cards, its pages, buttons and jobs) and Jellyfin (the channel list, the guide and the streams) on
port 8080, which Starboard puts on the home network. What Jellyfin reads is under /t/<token>/, a random word kept in
this plug-in's folder, so nobody else on the network can guess the addresses.
"""
import base64
import contextlib
import hashlib
import html
import json
import os
import re
import secrets
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import animate
import breakgrid
import breaks
import dog
import draw
import explain
import filelist
import flash
import grid
import guide
import library
import pack
import played
import promo
import speak
import sbplugin
import stylepage
import schedule
import stream
import three_d
import titles
import tv_words

VERSION = "0.13.3"
CLIPS = "clips"  # folder in /data for idents and clips the owner adds
LOGOS = "logos"
PACKS = "packs"  # broadcast packs: station, example, and ch-<channel> for a channel's own
PROMOS = "promos"
GRIDS = "grid"  # the schedule grid: <channel>.json, and .draft.json for a suggestion, .prev.json for Undo
MUSIC = "music"  # music for promos the owner uploads (0.2.0): station/ for every channel, ch-<channel>/ for one
HOLDING = "holding"  # holding slides (0.2.0): station.<ending> and ch-<channel>.<ending>
BACKS = "promo-backgrounds"  # background loops for promos the owner uploads (0.3.0): station/ and ch-<channel>/
PLAYED = "played"  # what each channel has played to someone watching (0.3.0): <channel>.json
NAME = "Create your own TV channel"
MAX_UPLOAD = 60 * 1024 * 1024
CLIP_TYPES = (".mp4", ".mkv", ".mov", ".ts", ".webm", ".m4v")
LOGO_TYPES = (".png", ".svg")
MUSIC_TYPES = (".mp3", ".m4a", ".ogg", ".flac")
HOLDING_TYPES = (".png", ".jpg", ".jpeg", ".mp4", ".mov", ".webm", ".mkv")
MUSIC_MOST = 20  # tracks for the station, and for each channel
BACK_TYPES = (".mp4", ".mov", ".webm", ".mkv", ".png", ".jpg", ".jpeg")
BACK_MOST = 20  # background loops for the station, and for each channel
BACK_LONGEST = 60  # seconds: a background loop's video
HOLDING_LONGEST = 120  # seconds: a holding slide's video loops (owner, 19 November 2026: 120 seconds and 90 MB)
HOLDING_MOST = 90 * 1024 * 1024  # bytes: Starboard 0.24.1 and later pass files of up to 100 MB
MUSIC_USE = {"both": "Your music and the pack's", "mine": "Only your music", "pack": "Only the pack's music"}
HOLDING_MODES = {"": "The station's waiting screen", "own": "Its own waiting screen", "none": "No waiting screen"}
COLOURS = {"0x1f5f99": "Blue", "0x2e7d32": "Green", "0xb3261e": "Red", "0x6a3d9a": "Purple", "0xb35c00": "Orange",
           "0x00695c": "Teal", "0xad1457": "Pink", "0x455a64": "Grey", "0x8d6e00": "Gold", "0x1a237e": "Navy"}
START_ON = {"0": "Back to back", "15": "On the quarter hour", "30": "On the half hour", "60": "On the hour"}
BREAKS = {"0": "No break", "60": "1 minute", "120": "2 minutes", "180": "3 minutes", "300": "5 minutes"}
MID_BREAKS = {"0": "Off", "60": "Up to 1 minute each", "120": "Up to 2 minutes each", "180": "Up to 3 minutes each"}  # 0.4.0
PLACE_HOW = breaks.METHOD_WORDS  # 0.8.0: where breaks go inside a programme
GRID_LINK = {"between": "between programmes", "inside": "breaks"}
PER_30 = {"": "Automatic", "1": "1 break", "2": "2 breaks", "3": "3 breaks", "4": "4 breaks"}  # in each 30 minutes of a programme
PER_FILM = {"": "Automatic", "1": "1 break", "2": "2 breaks", "3": "3 breaks", "4": "4 breaks", "5": "5 breaks", "6": "6 breaks"}
BREAKS_FILE = "breaks.json"  # breaks inside programmes found in quiet hours (0.4.0)
BREAKS_AHEAD = 48 * 3600  # programmes airing this soon are looked at
THREE_D_FILE = "three_d.json"  # films looked at for 3D in quiet hours (0.5.5)
THREE_D_MOST = 60  # films looked at in one quiet-hours run
TITLES_FILE = "titles.json"  # titles and descriptions in the station's language, kept per item and language (0.6.0)
TITLES_AHEAD = 3 * 3600  # programmes on a channel being watched airing this soon are asked for in that language
ROLES = {"idents": "Short title clip", "clips": "Clip", "trailers": "Trailer", "extras": "Short video of your own", "psa": "Public message"}
PER_BREAK = {"2": "Up to 2", "3": "Up to 3", "4": "Up to 4", "6": "Up to 6"}  # promos, trailers and clips in a break (0.5.0)
EXTRA_MOST = 90 * 1024 * 1024  # bytes: an extra video for the breaks (0.5.0)
_lock = threading.RLock()
_streams = stream.Streams()
_refreshing = set()
_promo_lock = threading.Lock()
_example = {"making": False, "error": "", "use": False}
_previewing = threading.Lock()  # one animation preview at a time
_record = None


def record():
    """What each channel has played (played.py), in the plug-in's folder."""
    global _record
    if _record is None or _record.folder != os.path.join(sbplugin.DATA, PLAYED):
        _record = played.Record(os.path.join(sbplugin.DATA, PLAYED))
    return _record


# Kept state ---------------------------------------------------------------------------------------------------------
def state():
    s = sbplugin.remember("station", None)
    if not isinstance(s, dict):
        s = {"channels": [], "shared": {"idents": [], "clips": [], "sources": []}, "removed": []}
    s.setdefault("channels", [])
    s.setdefault("shared", {"idents": [], "clips": [], "sources": []})
    s.setdefault("removed", [])
    s.setdefault("station_pack", "")
    s.setdefault("promos", [])
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


def language(cfg=None):
    """The station's language for the words drawn and the guide (0.6.0): its setting, English unless changed."""
    return tv_words.code((settings() if cfg is None else cfg).get("language"))


_titles = None


def titles_kept():
    """Titles in the station's language (titles.py), kept in the plug-in's folder."""
    global _titles
    path = os.path.join(sbplugin.DATA, TITLES_FILE)
    if _titles is None or _titles.path != path:
        _titles = titles.Titles(path, jf=lambda *a, **k: jf(*a, **k))  # jf looked up as it is used
    return _titles


def localiser(lang):
    """A function giving a programme its title in `lang` where one is kept; for English, the programme as it is."""
    if lang == tv_words.DEFAULT:
        return None
    kept = titles_kept()
    return lambda e: kept.localise(e, lang)


def ask_titles(entries, lang):
    """Programmes about to be drawn, asked for in `lang` on a thread of their own, within titles.PER_HOUR."""
    if lang == tv_words.DEFAULT:
        return
    kept = titles_kept()
    kept.want(entries, lang)
    kept.work_soon(stop=sbplugin.holding)  # nothing when none is waiting, or one is being asked for already


def number(s, ch):
    if ch.get("number_set"):
        return int(ch["number_set"])
    first = int(settings().get("first_number") or 1)
    return first + [c["id"] for c in s["channels"]].index(ch["id"])


def numbered(s):
    """The channels in the owner's order, each with its number and its schedule grid (for the guide)."""
    return [{**ch, "number": number(s, ch), "_grid": grid_doc(ch["id"])} for ch in s["channels"]]


_grids = {}


def grid_folder():
    return os.path.join(sbplugin.DATA, GRIDS)


def grid_doc(cid, kind=""):
    """A channel's saved grid (or its draft), read again only when its file changes. None when it has none."""
    p = grid.path(grid_folder(), cid, kind)
    try:
        mtime = os.path.getmtime(p)
    except OSError:
        return None
    got = _grids.get((cid, kind))
    if not got or got[0] != mtime:
        got = (mtime, grid.load(grid_folder(), cid, kind))
        _grids[(cid, kind)] = got
    return got[1]


def sched_of(ch):
    """What a channel shows: its schedule grid's fixed slots, over its automatic line-up."""
    return grid.channel_of(ch, grid_doc(ch["id"]))


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
    entries, left_out = without_3d(entries)
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
        else:  # the same programmes: their details (such as which sound track, 0.5.5) are brought up to date in place
            schedule.refresh_details(ch.get("eras"), entries)
        ch["refreshed"] = int(now)
        save(s)
    later_jellyfin()
    return f"{ch['name']}: {sbplugin.plural(len(entries), 'programme')}" + (
        f", {sbplugin.plural(left_out, '3D film')} left out" if left_out else "")


def found_3d():
    """Films checked for 3D so far (three_d.py), in the plug-in's folder."""
    return three_d.Found(os.path.join(sbplugin.DATA, THREE_D_FILE))


def leave_out_3d(cfg=None):
    return truthy((cfg if cfg is not None else settings()).get("leave_out_3d"), True)


def is_3d(e, found=None):
    """Why a programme is 3D: what Jellyfin or its file name says, or what the quiet-hours check found; "" for 2D."""
    return e.get("three_d") or (found or found_3d()).how(e.get("id"))


def without_3d(entries, cfg=None):
    """The line-up without 3D films, unless Leave out 3D films is off; and how many were left out."""
    if not leave_out_3d(cfg):
        return entries, 0
    found = found_3d()
    keep = [e for e in entries if not is_3d(e, found)]
    return keep, len(entries) - len(keep)


def three_d_job(now=None, limit_seconds=40 * 60, most=None):
    """In quiet hours (0.5.5): each film on a channel checked once for 3D, at the lowest priority, at most `most` in a
    run, never while anyone is watching. A channel with a film found to be 3D is read again, so the film is left out."""
    if not leave_out_3d():
        return {"said": "Leave out 3D films is off, so films are not checked"}
    if not _promo_lock.acquire(blocking=False):
        return {"said": "Coming-up trailers are being made, so the check for 3D films waits for the next quiet hour"}
    try:
        return _three_d_run(limit_seconds, most or THREE_D_MOST)
    finally:
        _promo_lock.release()


def _three_d_run(limit_seconds, most):
    if someone_watching():
        return {"said": "Someone is watching, so the check for 3D films waits for the next quiet hour"}
    s = state()
    found = found_3d()
    todo, seen, where = [], set(), {}
    for ch in s["channels"]:
        eras = ch.get("eras") or []
        for e in (eras[-1].get("lineup") if eras else None) or []:
            if e.get("kind") != "Movie" or not e.get("id") or float(e.get("dur") or 0) < 20 * 60:
                continue
            where.setdefault(e["id"], set()).add(ch["id"])
            if e["id"] not in seen and not found.known(e["id"]) and not e.get("three_d"):
                seen.add(e["id"])
                todo.append(e)
    if not todo:
        return {"said": "Every film on the channels has been checked for 3D"}
    c = jf_conf()
    three_d.begin()
    looked, new, unread, stopped, began = 0, [], 0, "", time.monotonic()
    for e in todo[:most]:
        if time.monotonic() - began > limit_seconds or sbplugin.holding() or someone_watching():
            break
        try:
            how = three_d.look(c.get("url", ""), c.get("api_key", ""), e)
        except InterruptedError as err:
            stopped = str(err)
            break
        except OSError:
            how = None
        if how is None:
            unread += 1  # checked again in the next quiet hour
            continue
        found.put(e["id"], how)
        looked += 1
        if how:
            new.append(e)
    for cid in sorted({cid for e in new for cid in where.get(e["id"], ())}):
        refresh_soon(cid)
    said = f"Checked {sbplugin.plural(looked, 'film')} for 3D: {len(new)} 3D"
    if new:
        said += " (" + ", ".join(e.get("title") or "a film" for e in new[:3]) + (", and more" if len(new) > 3 else "") + "), left out"
    left = len(todo) - looked - unread
    if left > 0:
        said += f". {left} more in the next quiet hour"
    if unread:
        said += f". {sbplugin.plural(unread, 'film')} could not be read"
    if stopped:
        said += f". {stopped}"
    return {"said": said[:200]}


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
        refresh_grid(ch["id"])
    sbplugin.clear_error()
    note = connect_jellyfin()
    got = guide_titles()
    if got:
        said.append(f"{sbplugin.plural(got, 'title')} read in the station's language")
    return {"said": ("; ".join(said) or "No channels yet") + (f". {note}" if note else "")[:160]}


def guide_titles(now=None):
    """In the nightly refresh (0.6.0): titles in the station's language for the programmes in the guide's days, so
    Jellyfin has them when it next reads the guide. Within titles.PER_HOUR; the rest wait for the next night or for
    the guide being read. Nothing for English. Returns how many were asked for."""
    cfg = settings()
    lang = language(cfg)
    if lang == tv_words.DEFAULT:
        return 0
    now = time.time() if now is None else now
    days = max(1, min(14, int(cfg.get("guide_days") or 7)))
    kept = titles_kept()
    for ch in state()["channels"]:
        if ch.get("on", True):
            kept.want([a["entry"] for a in sched_of(ch).airings(now, now + days * 86400, limit=600)], lang)
    return kept.work(stop=sbplugin.holding)


def address():
    """How Jellyfin reaches this plug-in: the setting when you gave one, else the address Starboard gives it on the
    home network (STARBOARD_HOME_ADDRESS, Starboard 0.23.0 and later), else the one learned when its page was opened."""
    a = str(settings().get("address") or "").strip().rstrip("/")
    given = str(os.environ.get("STARBOARD_HOME_ADDRESS") or "").strip().rstrip("/")
    return a or given or str((sbplugin.remember("learned", {}) or {}).get("address") or "")


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
        host = next((t for t in options.get("TunerHosts") or [] if t.get("Url") == m3u_url), None)
        tuner = (host or {}).get("Id")
        if host and host.get("FriendlyName") != station_name():
            # The station was renamed (0.2.0): the tuner in Jellyfin's Live TV takes the new name. The same tuner,
            # changed in place, so its channels and guide stay as they are.
            jf("/LiveTv/TunerHosts", method="POST", data={**host, "FriendlyName": station_name()})
            added += 1
        sbplugin.keep("tuner_name", {"name": station_name()})
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


def renamed():
    """True when the station's name is not the one Jellyfin's tuner was last given: Jellyfin is then told again."""
    return address() and (sbplugin.remember("tuner_name", {}) or {}).get("name") not in (None, station_name())


def guide_status(now=None):
    """When Jellyfin last read the guide, and how many programmes it had, in words (0.2.0)."""
    now = time.time() if now is None else now
    got = sbplugin.remember("guide_read", None) or {}
    if not got.get("at"):
        return ("Jellyfin has not read the guide yet. Select Refresh Jellyfin's guide in Actions, or wait: Jellyfin reads it about once a day."
                if address() else "Jellyfin has not read the guide yet: " + NO_ADDRESS[0].lower() + NO_ADDRESS[1:])
    when = dog.when_words(got["at"], now)
    when = when[0].lower() + when[1:] if when.startswith(("Today", "Tomorrow")) else f"on {when}"
    return (f"Jellyfin last read the guide {when}: "
            f"{sbplugin.plural(int(got.get('programmes') or 0), 'programme')} on {sbplugin.plural(int(got.get('channels') or 0), 'channel')}, "
            f"for {sbplugin.plural(int(got.get('days') or 0), 'day')}.")


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
    """The file for a clip: file:<name> in the clips folder, pack:<pack>/<path> in a broadcast pack, promo:<id>."""
    kind, _, rest = src.partition(":")
    if kind == "pack":
        name, _, rel = rest.partition("/")
        base = os.path.realpath(pack_dir(os.path.basename(name)))
        path = os.path.realpath(os.path.join(base, rel))
        if not path.startswith(base + os.sep):
            raise ValueError("Not a file in the pack")
        return path
    if kind == "promo":
        return os.path.join(sbplugin.DATA, PROMOS, re.sub(r"[^0-9a-f]", "", rest)[:20] + ".mp4")
    return os.path.join(sbplugin.DATA, CLIPS, os.path.basename(rest))


def pack_dir(name):
    return os.path.join(sbplugin.DATA, PACKS, name)


_packs = {}


def load_pack(name):
    """A checked pack by its folder's name, read again only when its checked.json changes."""
    if not name:
        return None
    path = os.path.join(pack_dir(name), "checked.json")
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return None
    got = _packs.get(name)
    if not got or got[0] != mtime:
        got = (mtime, pack.load(pack_dir(name)))
        _packs[name] = got
    return got[1]


def station_pack(s):
    return load_pack(s.get("station_pack") or "")


def station_logo_for(s, design, cfg=None):
    """The station's logo for a promo (0.5.2): its pack's logo/dog.png, for a promo made with any other design (a
    channel's own pack, or a plain promo), unless Show the station's logo on promos is off. None for promos
    made with the station's own pack, whose design carries it already."""
    if not truthy((cfg or {}).get("promo_station_logo"), True):
        return None
    sp = station_pack(s)
    if not sp or not sp.get("dog"):
        return None
    if design and design.get("folder") and os.path.realpath(design["folder"]) == os.path.realpath(sp["folder"]):
        return None
    path = os.path.join(sp["folder"], sp["dog"])
    return path if os.path.isfile(path) else None


def channel_pack(s, ch):
    """The pack a channel uses: its own, the station's, or none."""
    mode = ch.get("pack") or ""
    if mode == "none":
        return None
    if mode == "own":
        own = load_pack(f"ch-{ch['id']}")
        if own:
            return own
    return station_pack(s)


def pack_name(p):
    return os.path.basename(p["folder"])


def station_anim(s):
    """The station's animation choices (0.3.0) as settings for dog.resolve: "pack" is the broadcast pack's choice."""
    got = s.get("anim") or {}
    return {f"dog_{animate.key(i, p)}": got.get(animate.key(i, p)) or "pack" for i in animate.ITEMS for p in animate.PARTS}


def opts_for(s, ch, cfg=None, pk=None):
    """Everything drawn on a channel: its own choices, the station's, then its broadcast pack's."""
    return dog.resolve({**(settings() if cfg is None else cfg), **station_anim(s)}, ch, pk)


def truthy(v, default=True):
    if v in (None, ""):
        return default
    return v if isinstance(v, bool) else str(v).lower() in ("1", "true", "yes", "on")


def promo_design_key(s, ch, cfg=None):
    """Which design a channel's promos are made with now: its pack (promo.design_of), and the station's language when
    that is not English (0.6.0), so a change of language makes its promos again in the next quiet hours."""
    d = promo.design_of(promo_design(s, ch))
    lang = language(cfg)
    d = f"{d}|{lang}" if d and lang != tv_words.DEFAULT else d
    # 0.7.0: with Audio description on promos turned on, promos made without the voice are made again, and the other
    # way round. Turned off (as it is unless changed), the key is as it was, so an update alone keeps every promo.
    return f"{d}|ad" if d and promo_described(cfg) else d


def promo_described(cfg=None):
    """True when Audio description on promos is on (0.7.0); it is not unless changed."""
    return truthy((cfg if cfg is not None else settings()).get("promo_audio_description"), False)


def promo_clips(s, ch, cfg=None):
    """The promos a channel shows in its breaks: its own, and the other channels' unless that is off."""
    cfg = cfg or settings()
    others = truthy(cfg.get("promo_other"), True)
    on = {c["id"]: c for c in s["channels"] if c.get("on", True)}
    designs = {cid: promo_design_key(s, c, cfg) for cid, c in on.items()}
    out = []
    for p in s.get("promos") or []:
        if p.get("cid") not in on or (p["cid"] != ch["id"] and not others):
            continue
        if not promo.current(p, designs):  # made with a pack the channel no longer uses (0.5.1): not shown, made again
            continue
        out.append({"id": f"promo-{p['id']}", "src": f"promo:{p['id']}", "dur": float(p.get("dur") or 15), "title": f"Coming-up trailer: {p.get('title')}",
                    "has_audio": True, "airs": float(p.get("airs") or 0), "role": "promo", "cid": p["cid"]})
    return out


_lengths = {"seen": None, "said": set()}


def lengths_seen():
    """The length last seen for each clip (0.9.0, DASH-550), read once from lengths.json in the plug-in's folder."""
    if _lengths["seen"] is None:
        try:
            with open(os.path.join(sbplugin.DATA, "lengths.json")) as f:
                _lengths["seen"] = {str(k): float(v) for k, v in json.load(f).items()}
        except (OSError, ValueError, AttributeError):
            _lengths["seen"] = {}
    return _lengths["seen"]


def note_lengths(clips):
    """Keep each clip's length for the day one cannot be read, and say so in the log once for each clip. The file is only
    written when a length is new or has changed."""
    seen = lengths_seen()
    before = dict(seen)
    for line in schedule.remember_lengths(clips, seen):
        if line not in _lengths["said"]:
            _lengths["said"].add(line)
            print(line, flush=True)
    if seen != before:
        try:
            tmp = os.path.join(sbplugin.DATA, "lengths.json.tmp")
            with open(tmp, "w") as f:
                json.dump(seen, f)
            os.replace(tmp, os.path.join(sbplugin.DATA, "lengths.json"))
        except OSError:
            pass


def clips_for(s, ch, p=None, cfg=None):
    out = clips_made(s, ch, p, cfg)
    note_lengths(out)
    return out


def clips_made(s, ch, p=None, cfg=None):
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
    fillers += promo_clips(s, ch, cfg)
    extras = []  # 0.5.0: the owner's extra videos, one at random after the promos
    if (ch.get("extras") or "both") in ("own", "both"):
        extras += own.get("extras") or []
    if (ch.get("extras") or "both") in ("shared", "both"):
        extras += shared.get("extras") or []
    psa = []  # 0.9.0 (DASH-545): the owner's public service announcements, chosen in the grids like the extra videos
    if (ch.get("psa") or "both") in ("own", "both"):
        psa += own.get("psa") or []
    if (ch.get("psa") or "both") in ("shared", "both"):
        psa += shared.get("psa") or []
    out = {"idents": idents, "fillers": fillers, "sting": None, "random_idents": False, "holding": holding_for(s, ch), "bumpers": [],
           "extras": extras, "psa": psa}
    if p:
        name = pack_name(p)
        out["bumpers"] = [{"id": f"pk-{b['path']}", "src": f"pack:{name}/{b['path']}", "dur": b["dur"], "title": os.path.basename(b["path"]),
                           "has_audio": False} for b in p.get("bumpers") or []]
        if ch.get("idents") != "none" and p.get("idents"):
            out["idents"] = idents + [{"id": f"pk-{i['path']}", "src": f"pack:{name}/{i['path']}", "dur": i["dur"],
                                       "title": os.path.basename(i["path"]), "has_audio": i.get("has_audio", True), "gain": i.get("gain", 0)}
                                      for i in p["idents"]]
            out["random_idents"] = True  # a pack's idents always play in a random order
        if p.get("sting"):
            st = p["sting"]
            out["sting"] = {"id": "pk-sting", "src": f"pack:{name}/{st['path']}", "dur": st["dur"], "title": "The logo with music",
                            "has_audio": True, "gain": st.get("gain", 0)}
    return out


def holding_for(s, ch):
    """The holding slide a channel's breaks end on (0.2.0): its own when it uses its own and has one, else the
    station's, else none; with the words over it. None when there is no slide, so the breaks end on cards as before."""
    mode = ch.get("holding_mode") or ""
    if mode == "none":
        return None
    h = (ch.get("holding") if mode == "own" else None) or s.get("holding")
    if not h:
        return None
    path = os.path.join(sbplugin.DATA, HOLDING, os.path.basename(h.get("file") or ""))
    if not os.path.isfile(path):
        return None
    words = ch.get("holding_words") or s.get("holding_words") or "countdown"
    return {"file": path, "still": bool(h.get("still")), "has_audio": bool(h.get("has_audio")), "gain": float(h.get("gain") or 0),
            "words": words if words in dog.HOLDING_WORDS else "countdown"}


def holding_words(h):
    if not h:
        return ""
    return f"{h.get('title') or 'A slide'}, " + ("a picture" if h.get("still") else f"a {round(h.get('dur') or 0)} second video")


def add_holding(key, name, length, rfile):
    """A holding slide's picture or short video, checked with ffprobe like a pack's files: key is station or
    ch-<channel>. The one before it is replaced. Returns what is kept about it."""
    folder = os.path.join(sbplugin.DATA, HOLDING)
    path, base = save_upload(name, length, rfile, os.path.join(folder, ".new"), HOLDING_TYPES, most=HOLDING_MOST)
    try:
        info = pack.probe(path)
        v = info["video"]
        if not info["ok"] or not v:
            raise ValueError(f"{base} has no picture FFmpeg can read")
        still = v.get("codec_name") in ("png", "mjpeg")
        if not still and not 1 <= info["duration"] <= HOLDING_LONGEST:
            raise ValueError(f"{base} is {round(info['duration'])} seconds long. Choose a picture, or a video of up to {HOLDING_LONGEST} seconds")
        if int(v.get("width") or 0) > 4096 or int(v.get("height") or 0) > 4096:
            raise ValueError(f"{base} is {v.get('width')} by {v.get('height')} pixels. Choose one of up to 1920 by 1080")
        ending = os.path.splitext(base)[1].lower()
        for f in os.listdir(folder):
            if f.startswith(key + "."):
                with contextlib.suppress(OSError):
                    os.remove(os.path.join(folder, f))
        final = os.path.join(folder, key + ending)
        os.replace(path, final)
    finally:
        with contextlib.suppress(OSError):
            os.remove(path)
    sound = bool(info["audio"]) and not still
    return {"file": key + ending, "title": base, "still": still, "dur": round(info["duration"], 2), "has_audio": sound,
            "gain": pack.gain_for(pack.loudness(final)) if sound else 0.0}


def drop_holding(h):
    if h:
        with contextlib.suppress(OSError):
            os.remove(os.path.join(sbplugin.DATA, HOLDING, os.path.basename(h.get("file") or "")))


def music_files(tracks):
    """Uploaded music that is still there, as promo.py takes it: [{"file", "gain"}]."""
    out = []
    for m in tracks or []:
        path = os.path.join(sbplugin.DATA, MUSIC, m.get("file") or "")
        if os.path.realpath(path).startswith(os.path.realpath(os.path.join(sbplugin.DATA, MUSIC)) + os.sep) and os.path.isfile(path):
            out.append({"file": path, "gain": float(m.get("gain") or 0)})
    return out


def add_music(tracks, key, name, length, rfile):
    """One music track for promos (mp3, m4a, ogg or flac, up to 60 MB), checked with ffprobe: it must have sound and
    last 5 seconds to 10 minutes. Its loudness is measured, so it plays at -23 LUFS like a pack's music. key is station
    or ch-<channel>. Returns (the tracks with it added, the words said)."""
    if len(tracks or []) >= MUSIC_MOST:
        raise ValueError(f"There are {MUSIC_MOST} tracks already, the most. Remove one first")
    folder = os.path.join(sbplugin.DATA, MUSIC, key)
    path, base = save_upload(name, length, rfile, folder, MUSIC_TYPES)
    info = pack.probe(path)
    if not info["ok"] or not info["audio"]:
        os.remove(path)
        raise ValueError(f"{base} has no sound FFmpeg can read")
    if not 5 <= info["duration"] <= 600:
        os.remove(path)
        raise ValueError(f"{base} is {round(info['duration'])} seconds long. Choose music of 5 seconds to 10 minutes")
    mid = hashlib.sha256(f"{key}/{base}".encode()).hexdigest()[:10]
    track = {"id": mid, "file": f"{key}/{base}", "title": base, "dur": round(info["duration"], 1), "gain": pack.gain_for(pack.loudness(path))}
    return [m for m in tracks or [] if m["id"] != mid] + [track], f"Added {base}, {round(info['duration'])} seconds"


def drop_music(tracks, mid):
    """The tracks without one; its file goes from the plug-in's folder."""
    keep = []
    for m in tracks or []:
        if m.get("id") == mid:
            with contextlib.suppress(OSError):
                path = os.path.join(sbplugin.DATA, MUSIC, m.get("file") or "")
                if os.path.realpath(path).startswith(os.path.realpath(os.path.join(sbplugin.DATA, MUSIC)) + os.sep):
                    os.remove(path)
        else:
            keep.append(m)
    return keep


def back_files(backs):
    """Uploaded background loops that are still there, as promo.py takes them: [{"file", "still"}]."""
    out, top = [], os.path.realpath(os.path.join(sbplugin.DATA, BACKS))
    for b in backs or []:
        path = os.path.join(top, b.get("file") or "")
        if os.path.realpath(path).startswith(top + os.sep) and os.path.isfile(path):
            out.append({"file": path, "still": bool(b.get("still"))})
    return out


def add_background(backs, key, name, length, rfile):
    """One background loop for promos (0.3.0): a picture, or a video of 2 to 60 seconds, up to 90 MB, checked with
    ffprobe. key is station or ch-<channel>. Returns (the loops with it added, the words said)."""
    if len(backs or []) >= BACK_MOST:
        raise ValueError(f"There are {BACK_MOST} background loops already, the most. Remove one first")
    path, base = save_upload(name, length, rfile, os.path.join(sbplugin.DATA, BACKS, key), BACK_TYPES, most=HOLDING_MOST)
    still = base.lower().endswith((".png", ".jpg", ".jpeg"))
    info = pack.probe(path)
    if not info["ok"] or not info["video"]:
        os.remove(path)
        raise ValueError(f"{base} is not a picture or video FFmpeg can read")
    if not still and not 2 <= info["duration"] <= BACK_LONGEST:
        os.remove(path)
        raise ValueError(f"{base} is {round(info['duration'])} seconds long. Choose a picture, or a video of 2 to {BACK_LONGEST} seconds")
    bid = hashlib.sha256(f"{key}/{base}".encode()).hexdigest()[:10]
    item = {"id": bid, "file": f"{key}/{base}", "title": base, "still": still, "dur": 0 if still else round(info["duration"], 1)}
    words = "a picture" if still else f"{round(info['duration'])} seconds"
    return [b for b in backs or [] if b["id"] != bid] + [item], f"Added {base}, {words}"


def drop_background(backs, bid):
    """The loops without one; its file goes from the plug-in's folder."""
    keep, top = [], os.path.realpath(os.path.join(sbplugin.DATA, BACKS))
    for b in backs or []:
        if b.get("id") == bid:
            path = os.path.join(top, b.get("file") or "")
            if os.path.realpath(path).startswith(top + os.sep):
                with contextlib.suppress(OSError):
                    os.remove(path)
        else:
            keep.append(b)
    return keep


def back_words(b):
    return "a picture" if b.get("still") else f"{round(b.get('dur') or 0)} seconds, looped"


def promo_design(s, ch):
    """What a channel's promos are made with: its pack when the pack has a promo, else a plain design (the default
    layout on its colour) when there is music or a background loop uploaded for it or for the station (0.2.0, loops
    0.3.0), else nothing, so it has no promos."""
    pk = channel_pack(s, ch)
    if pk and pk.get("promo"):
        return pk
    if (music_files(ch.get("music")) or music_files(s.get("music")) or back_files(ch.get("promo_backgrounds"))
            or back_files(s.get("promo_backgrounds"))):
        return promo.plain_pack(ch.get("colour"))
    return None


def backgrounds_for(s, ch, design):
    """The background loops a promo chooses from (0.3.0): the channel's own and the station's uploaded loops, and the
    pack's promo background (None in the list, as promo.command takes it). With no loops uploaded, only the pack's."""
    pool = back_files(ch.get("promo_backgrounds")) + back_files(s.get("promo_backgrounds"))
    if (design or {}).get("promo", {}).get("background"):
        pool.append(None)
    return pool


def promo_seconds(cfg):
    """The setting Promo length (0.3.0): seconds, or None for what the pack says (15 unless it says otherwise)."""
    try:
        v = int(cfg.get("promo_seconds") or 0)
    except (TypeError, ValueError):
        return None
    return max(promo.SHORTEST, min(promo.LONGEST, v)) if v else None


def music_for(s, ch, design):
    use = s.get("music_use") or "both"
    return promo.music_pool((design or {}).get("music"), (design or {}).get("folder") or "", music_files(ch.get("music")),
                            music_files(s.get("music")), use if use in MUSIC_USE else "both")


def logo_file(cid, p=None):
    """The on-screen logo: the channel's own picture, else its broadcast pack's logo/dog.png."""
    own = os.path.join(sbplugin.DATA, LOGOS, f"{cid}.png")
    if os.path.isfile(own):
        return own
    if p and p.get("dog"):
        path = os.path.join(p["folder"], p["dog"])
        return path if os.path.isfile(path) else None
    return None


def logo_thumb(path, alt):
    """A small copy of a logo for the page (64 pixels tall), as a data address with its words, made once for each
    version of the file and kept beside it (0.2.0, owner: "Once you upload a logo, I want you to show it")."""
    if not path or not os.path.isfile(path):
        return None
    which = hashlib.sha256(path.encode()).hexdigest()[:8]
    key = hashlib.sha256(f"{path}|{os.path.getmtime(path)}".encode()).hexdigest()[:8]
    folder = os.path.join(sbplugin.DATA, LOGOS)
    thumb = os.path.join(folder, f"thumb-{which}-{key}.png")
    if not os.path.isfile(thumb):
        os.makedirs(folder, exist_ok=True)
        for f in os.listdir(folder):  # the copy of the logo before this one
            if f.startswith(f"thumb-{which}-"):
                with contextlib.suppress(OSError):
                    os.remove(os.path.join(folder, f))
        subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", path, "-vf", "scale=-1:64", "-frames:v", "1", "-y", thumb],
                       capture_output=True, timeout=30, check=False)
    try:
        with open(thumb, "rb") as f:
            data = f.read()
    except OSError:
        return None
    if len(data) > 45000:
        return None
    return {"src": "data:image/png;base64," + base64.b64encode(data).decode(), "alt": alt[:120]}


def own_logo(cid):
    p = os.path.join(sbplugin.DATA, LOGOS, f"{cid}.png")
    return p if os.path.isfile(p) else None


def pick_transition(p, seed, at):
    """The same transition for both halves of one cut: chosen from the boundary's time and the channel's seed."""
    tr = (p or {}).get("transitions") or []
    if not tr:
        return None
    t = tr[schedule.Rng(schedule.seed_of(seed, "cut", int(at))).below(len(tr))]
    return {"file": os.path.join(p["folder"], t["path"]), "dur": float(t["dur"]), "codec": t.get("codec", "")}


def found_breaks():
    """Breaks inside programmes found so far (breaks.py), in the plug-in's folder."""
    return breaks.Found(os.path.join(sbplugin.DATA, BREAKS_FILE))


def break_options(ch, opts):
    """What schedule.pieces_at needs to plan a channel's breaks."""
    out = {"seed": ch["seed"], "cards": opts["cards"], "ident_order": ch.get("ident_order", "in_order"),
           "fill_most": int(ch.get("per_break") or 3), "cid": ch["id"]}  # 0.5.0: each once, up to this many
    grids = {w: g for w in breakgrid.GRIDS if (g := breakgrid.grid_of(ch, w))}  # 0.8.0: a saved grid replaces the classic order
    if grids:
        out["grids"] = grids
    mid = int(ch.get("mid_break_seconds") or 0)
    if mid:
        found = found_breaks()
        how, per_30, per_film = place_choice(ch)
        out["mid_seconds"] = mid
        out["breaks_in"] = lambda e: found.places(e, how, per_30, per_film)  # reads the small file: nothing is run
    return out


def place_choice(ch):
    """Where and how many (0.8.0): At silence unless chosen, and the number automatic unless chosen."""
    how = ch.get("place_how") if ch.get("place_how") in PLACE_HOW else "silence"
    return how, int(ch.get("breaks_per_30") or 0), int(ch.get("breaks_per_film") or 0)


def breaks_job(now=None, limit_seconds=40 * 60, most=12):
    """In quiet hours (0.4.0): breaks inside programmes looked for, for channels with Breaks inside programmes on and
    the programmes they air in the next 48 hours, one at a time at the lowest priority, at most `most` in a run, and
    never while anyone is watching."""
    if not _promo_lock.acquire(blocking=False):
        return {"said": "Coming-up trailers are being made, so the search for breaks waits for the next quiet hour"}
    try:
        return _breaks_run(now, limit_seconds, most)
    finally:
        _promo_lock.release()


def _breaks_run(now, limit_seconds, most):
    now = time.time() if now is None else now
    if someone_watching():
        return {"said": "Someone is watching, so the search for breaks waits for the next quiet hour"}
    s = state()
    found = found_breaks()
    wanted, first = {}, {}
    for ch in s["channels"]:
        if not ch.get("on", True) or not int(ch.get("mid_break_seconds") or 0):
            continue
        how = place_choice(ch)[0]
        for a in sched_of(ch).airings(now, now + BREAKS_AHEAD, limit=400):
            e = a["entry"]
            if e.get("id") and float(e.get("dur") or 0) >= 15 * 60:
                wanted.setdefault(e["id"], (e, set()))[1].add(how)
                first.setdefault(e["id"], a["start"])
    # Each programme once for what its channels need: At set times needs no search at all (0.8.0).
    todo = [(first[i], e, tuple(sorted(m - {"times"}))) for i, (e, m) in wanted.items() if not found.has(i, m)]
    if not todo:
        return {"said": "Nothing new to check for breaks inside programmes"}
    todo.sort(key=lambda x: x[0])
    c = jf_conf()
    breaks.begin()
    looked, with_breaks, failed, began = 0, 0, "", time.monotonic()
    for _, e, methods in todo[:most]:
        if time.monotonic() - began > limit_seconds or sbplugin.holding() or someone_watching():
            break
        try:
            got = breaks.look(c.get("url", ""), c.get("api_key", ""), e, methods)
        except InterruptedError as err:
            failed = str(err)
            break
        except (OSError, ValueError) as err:
            failed = str(err)[:100]
            continue
        found.put_survey(e["id"], got)
        looked += 1
        with_breaks += any(got.get(k) for k in ("sil", "scn", "seg"))
    said = f"Checked {sbplugin.plural(looked, 'programme')}: {with_breaks} with breaks inside"
    if len(todo) > looked:
        said += f". {len(todo) - looked} more in the next quiet hour"
    if failed:
        said += f". Stopped: {failed}"
    return {"said": said[:200]}


def with_transitions(pieces, p, seed):
    """The pieces with a pack's transitions at each cut between programme and break. A transition's second half
    plays over the start of the programme and of the break, its first half over the end of each, and the cut is at
    its middle. The last half of a piece that ends on a cut becomes a piece of its own (its tail, with "tail_from"),
    so every FFmpeg run starts its transition at its own start and never holds frames waiting."""
    if not (p and p.get("transitions")) or not pieces:
        return pieces
    out = [dict(x) for x in pieces]
    prog = out[0]
    prog["trans_in_at"] = prog["airing"]["start"]
    if len(out) > 1:
        # Every cut between the programme (or a part of it, 0.4.0) and a break, and the start of the next programme.
        for x, y in zip(out, out[1:]):
            if (x["kind"] == "programme") != (y["kind"] == "programme"):
                x["trans_out_at"] = x["end"]
                y["trans_in_at"] = x["end"]
        out[-1]["trans_out_at"] = out[-1]["end"]
    else:
        prog["trans_out_at"] = prog["airing"]["end"]
    final = []
    for piece in out:
        at = piece.pop("trans_out_at", None)
        tr = pick_transition(p, seed, at) if at is not None else None
        half = tr["dur"] / 2 if tr else 0.0
        if tr and piece["end"] - half - piece["start"] > 1.0:
            final.append({**piece, "end": piece["end"] - half})
            tail = {k: v for k, v in piece.items() if k != "trans_in_at"}
            final.append({**tail, "tail_from": piece["end"] - half, "trans_out_at": at})
        else:
            final.append(piece)
    return final


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
        sched = sched_of(ch)
        pk = channel_pack(s, ch)
        opts = opts_for(s, ch, cfg, pk)
        if piece is None:
            a, pieces = schedule.pieces_at(sched, now, clips_for(s, ch, pk, cfg), break_options(ch, opts))
            if not a:
                return None, None, None
            pieces = with_transitions(pieces, pk, ch["seed"])
            piece = next((p for p in pieces if p["start"] <= now < p["end"] and now >= p.get("tail_from", p["start"])), None)
            piece = piece or {"kind": "slate", "start": now, "end": a["end"]}
        else:
            a = sched.airing(now)
        W, H, kbps = stream.SIZES.get(str(cfg.get("picture") or "720"), stream.SIZES["720"])
        folder = os.path.join("/tmp", "tv-station", f"{cid}-{secrets.token_hex(3)}")
        texts = dog.Texts(folder)
        names = {"channel": ch["name"], "station": station_name(cfg)}
        c = jf_conf()
        lang = language(cfg)
        localise = localiser(lang)
        ctx = {"W": W, "H": H, "kbps": kbps, "opts": opts, "names": names, "logo": logo_file(cid, pk), "jf_url": c.get("url", ""),
               "jf_key": c.get("api_key", ""), "ts_offset": max(0.0, now - started) + 1.0, "texts": texts, "clip_path": clip_path,
               "colour": ch.get("colour"), "copy_ok": bool(cfg.get("copy_plain", True)), "still": still, "lang": lang}
        if localise:
            ctx["localise"] = localise
            ask_titles([x["entry"] for x in sched.airings(now, now + TITLES_AHEAD, limit=60)], lang)
        if pk and pk.get("coming_next") and piece["kind"] == "card":
            lay = pk["coming_next"]
            ctx["layout"] = {**lay, "file": os.path.join(pk["folder"], lay["background"])}
        if "trans_in_at" in piece:
            ctx["trans_in"] = pick_transition(pk, ch["seed"], piece["trans_in_at"])
        if "trans_out_at" in piece:
            ctx["trans_out"] = pick_transition(pk, ch["seed"], piece["trans_out_at"])
        if a:
            nxt = sched.airing(a["end"])
            if nxt:
                ctx["next_words"] = tv_words.up_next(nxt["start"], (localise(nxt["entry"]) if localise else nxt["entry"]).get("title"), lang)
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
    """One frame of the channel as it would be drawn now, as a PNG: the DOG on the programme, a Coming up next card, or
    from its broadcast pack an ident (kind ident) or the logo with music (sting), or one of its promos (promo)."""
    s = state()
    ch = find(s, cid)
    if not ch:
        raise LookupError("No such channel")
    now = time.time() if at is None else at
    a = sched_of(ch).airing(now)
    if not a:
        raise LookupError("The channel has nothing to show yet")
    if kind in ("ident", "sting", "promo"):
        got = clips_for(s, ch, channel_pack(s, ch))
        pool = {"ident": got["idents"], "sting": [got["sting"]] if got["sting"] else [],
                "promo": [c for c in got["fillers"] if c.get("role") == "promo" and c.get("cid") == cid] or
                         [c for c in got["fillers"] if c.get("role") == "promo"]}[kind]
        if not pool:
            raise LookupError({"ident": "No short title clips yet", "sting": "No logo with music in the pack", "promo": "No coming-up trailers yet"}[kind])
        clip = pool[int(now) % len(pool)]
        seek = min(clip["dur"] * 0.55, clip["dur"] - 0.5)
        piece = {"kind": "clip", "clip": clip, "role": kind, "start": now - seek, "end": now - seek + clip["dur"], "airing": a}
    elif kind == "card":
        nxt = sched_of(ch).airing(a["end"]) or a
        piece = {"kind": "card", "card": "next", "start": now, "end": now + 10, "airing": nxt}
    elif kind == "holding":
        h = holding_for(s, ch)
        if not h:
            raise LookupError("No waiting screen yet")
        nxt = sched_of(ch).airing(a["end"]) or a
        piece = {"kind": "holding", "holding": h, "start": now, "end": now + 272, "airing": nxt}
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


# Animation (0.3.0) -----------------------------------------------------------------------------------------------------
ANIM_DETAIL = {
    "cards": "The words, the bar and the programme's picture on each card, over its background: on as the card starts, off by its end.",
    "straps": "The programme's name as it starts, and Up next during the end credits: on as each starts, off by its end.",
    "logo": "As a programme starts and ends, when it shows only during programmes or with cards; and when it appears after the opening.",
    "clock": "With the corner logo: as a programme starts and ends, when it shows only then.",
    "label": "New, Repeat or Live: on as the programme starts, off at 2 minutes.",
    "holding": "Back soon or the countdown: on as the slide starts, off by the time the next programme starts."}
PREVIEW_SECONDS = {"straps": 8.0}  # the start strap shows for 8 seconds; everything else for 5
PACK_ANIM = "The branding's, or none"
PACK_SPEED = "The branding's, or normal"


def anim_words(item, part, value):
    if part == "speed":
        return animate.SPEED_WORDS.get(value, value)
    return animate.MOVES.get(value, (value, value))[0 if part == "in" else 1]


def anim_options(part):
    if part == "speed":
        return dict(animate.SPEED_WORDS)
    return {k: v[0 if part == "in" else 1] for k, v in animate.MOVES.items()}


def anim_rows(s, ch, base, group):
    """The rows for each thing that animates: how it comes on, how it goes off, its speed, and a preview link. For a
    channel (ch) each starts at Station default; for the station (ch None) at the broadcast pack's choice."""
    rows = []
    own = ((ch or {}).get("dog") or {}) if ch else (s.get("anim") or {})
    where = ch["id"] if ch else "station"
    for item, name in animate.ITEMS.items():
        for part, label in (("in", "Coming on"), ("out", "Going off"), ("speed", "Speed")):
            k = animate.key(item, part)
            if ch:
                st = (s.get("anim") or {}).get(k) or "pack"
                dw = "the pack's" if st == "pack" else anim_words(item, part, st)
                choice = _choice(label, own.get(k, ""), anim_options(part), dw)
            else:
                choice = _choice(label, own.get(k) or "pack", {"pack": PACK_SPEED if part == "speed" else PACK_ANIM, **anim_options(part)})
            row = {"id": f"{where}:anim-{item}-{part}", "title": f"{name}: {label.lower()}", "group": group,
                   "state": "ok", "state_label": "Saved", "choice": choice}
            if part == "in":
                row["detail"] = ANIM_DETAIL[item]
                if base:
                    row["link"] = {"url": f"{base}/t/{s['token']}/animation/{where}/{item}.mp4",
                                   "label": f"Preview: {name}, on and off, in a new tab"}
            if ch:
                row["menu"] = ch["id"]
            rows.append(row)
    return rows


def set_anim(holder, key, value):
    """Saves one animation choice: holder is a channel's "dog" (where "" is the station's choice) or the station's
    "anim" (where "pack" is the pack's). Returns the words for what was saved."""
    m = re.match(r"^anim-([a-z]+)-(in|out|speed)$", key)
    if not m or m.group(1) not in animate.ITEMS:
        raise ValueError("That is not one of the choices")
    item, part = m.groups()
    allowed = animate.SPEEDS if part == "speed" else animate.MOVES
    k = animate.key(item, part)
    v = "" if value is None else str(value)
    if v in ("", "pack"):
        holder.pop(k, None)
    elif v in allowed:
        holder[k] = v
    else:
        raise ValueError("That is not one of the choices")
    words = anim_words(item, part, v) if v in allowed else ("the station's choice" if v == "" else "the branding's choice")
    return f"{animate.ITEMS[item]}, {('coming on' if part == 'in' else 'going off' if part == 'out' else 'speed')}: {words}. Saved"


def anim_preview(target, item):
    """A few seconds of one thing animating on and off, with the choices saved for a channel (target: its id) or the
    station ("station"), as an MP4. Drawn over a made-up picture, so it needs nothing from Jellyfin; everything else
    stays still, so the one thing chosen is what moves."""
    if item not in animate.ITEMS:
        raise LookupError("No such thing to animate")
    s = state()
    cfg = settings()
    ch = None if target == "station" else find(s, target)
    if target != "station" and not ch:
        raise LookupError("No such channel")
    pk = channel_pack(s, ch) if ch else station_pack(s)
    opts = opts_for(s, ch, cfg, pk)
    for i in animate.ITEMS:
        if i != item:
            opts[animate.key(i, "in")] = opts[animate.key(i, "out")] = "none"
    if item in ("logo", "clock"):
        opts.update({"when": "programmes", "fade_in": 0})
        if item == "logo" and opts["kind"] == "none":
            opts["kind"] = "channel_name"
        if item == "clock":
            opts["clock"] = True
    if item == "label" and opts["label"] == "none":
        opts["label"] = "new_repeat"
    # Only the start strap for Straps, and none for the rest, so the one thing chosen is all that moves.
    opts.update({"strap_start": item == "straps", "strap_end": False})
    W, H, kbps = stream.SIZES.get(str(cfg.get("picture") or "720"), stream.SIZES["720"])
    lang = language(cfg)
    secs = PREVIEW_SECONDS.get(item, 5.0)
    now = time.time()
    entry = {"id": "0" * 32, "title": "Your next programme", "kind": "Episode", "s": 1, "e": 2, "ep": "The middle",
             "plot": "What the programme is about, in a sentence or two, from Jellyfin.", "has_audio": False, "premiere": "2000-01-01"}
    airing = {"entry": entry, "start": now, "end": now + secs, "content_end": now + secs}
    folder = os.path.join("/tmp", "tv-station", f"anim-{secrets.token_hex(4)}")
    texts = dog.Texts(folder)
    out = os.path.join(folder, "preview.mp4")
    names = {"channel": ch["name"] if ch else "Your channel", "station": station_name(cfg)}
    ctx = {"W": W, "H": H, "kbps": kbps, "opts": opts, "names": names, "texts": texts, "ts_offset": 0.0, "to_file": out,
           "colour": (ch or {}).get("colour") or "0x1f5f99", "logo": logo_file(ch["id"], pk) if ch else logo_file("station", pk),
           "start_words": "Your programme" + tv_words.sep(lang) + tv_words.episode(1, 2, lang),
           "next_words": tv_words.up_next(time.mktime(time.localtime()[:3] + (21, 0, 0, 0, 0, -1)), "Your next programme", lang), "lang": lang}
    if item == "cards":
        piece = {"kind": "card", "card": "next", "start": now, "end": now + secs, "airing": {**airing, "start": now + 300}}
        if pk and pk.get("coming_next"):
            ctx["layout"] = {**pk["coming_next"], "file": os.path.join(pk["folder"], pk["coming_next"]["background"])}
    elif item == "holding":
        h = holding_for(s, ch) if ch else None
        if not h:
            bg = os.path.join(folder, "slide.png")
            subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c=0x10202c:s={W}x{H}", "-frames:v", "1",
                            "-y", bg], capture_output=True, timeout=30, check=False)
            words = ((ch or {}).get("holding_words") or s.get("holding_words") or "countdown")
            h = {"file": bg, "still": True, "has_audio": False, "words": words if words in dog.HOLDING_WORDS else "countdown"}
        piece = {"kind": "holding", "holding": {**h, "has_audio": False}, "start": now, "end": now + secs, "airing": airing}
    else:
        piece = {"kind": "programme", "start": now, "end": now + secs, "airing": airing}
        ctx["stand_in"] = ["-f", "lavfi", "-t", f"{secs + 1:.0f}", "-i",
                           f"gradients=s={W}x{H}:r={stream.FPS}:c0=0x1f5f99:c1=0x10202c:nb_colors=2:speed=0.02"]
    if not _previewing.acquire(timeout=60):
        raise RuntimeError("Another preview is being made. Try again in a moment")
    try:
        r = subprocess.run(stream.piece_command(piece, now, ctx), capture_output=True, timeout=120, check=False)
        if r.returncode != 0 or not os.path.isfile(out):
            raise RuntimeError((r.stderr.decode("utf-8", "replace").strip().splitlines() or ["FFmpeg did not make the preview"])[-1][:200])
        with open(out, "rb") as f:
            return f.read()
    finally:
        _previewing.release()
        shutil.rmtree(folder, ignore_errors=True)


def animation_page(said=None):
    """The Animation page (0.3.0): the station's choices, which every channel uses unless it has its own."""
    s = state()
    base = address()
    items = []
    for row in anim_rows(s, None, base, ""):
        item = row["id"].split("-")[1]
        row["group"] = animate.ITEMS[item]
        if not base and row["id"].endswith("-in"):
            row["detail"] = row.get("detail", "") + " " + NO_ADDRESS
        items.append(row)
    p = station_pack(s)
    out = {"type": "list", "title": "Animation", "items": items,
           "intro": ("How each thing drawn over the picture comes on and goes off, for every channel unless it has its own choice. "
                     + ("The station's branding, " + p["name"] + ", chooses for anything left at The branding's. " if p and p.get("animation")
                        else "Anything left at The branding's has no animation, unless the station's branding chooses one. ")
                     + "Each preview opens a few seconds of it in a new tab.")}
    if said:
        out["said"] = said[:200]
    return out


def animation_post(body):
    action, rid, value = body.get("action"), str(body.get("id") or ""), body.get("value")
    where, _, key = rid.partition(":")
    if action != "choose" or where != "station":
        raise ValueError("That cannot be changed here")
    with _lock:
        s = state()
        said = set_anim(s.setdefault("anim", {}), key, value)
        save(s)
    return animation_page(said)


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


# What the Starboard drawing the page can do, from its X-Starboard-Can header (Starboard 0.24.0 and later): partial
# (an answer for one channel only), picker (Choose from your library, a slide-out) and cards (each group on a card of
# its own). An older Starboard sends none, and gets the pages as before.
_req = threading.local()


def can(what):
    return what in getattr(_req, "can", frozenset())


# Each card on an opened channel: its heading and one sentence on what it is for (owner, 19 November 2026: "Break the
# channels section into smaller cards and look at making it easier to understand once you select the channel").
CARDS = (("Name and number", "Its name and number in Jellyfin's Live TV, whether it is on air, and its colour."),
         ("What it shows", "The series, films, collections, playlists, genres and decades it plays. Choose from your library to add several at once."),
         ("Breaks", "What plays between programmes: when programmes start, how long the break is, short title clips, trailers and your clips."),
         ("Corner logo and branding", "The logo in the corner, the title bars and cards, and the branding they come from. "
                                         "Each one follows the station's setting until you choose another."),
         ("Animation", "How the cards, title bars, corner logo, clock, label and waiting screen words come on and go off. "
                       "Each one follows the station's choice until you choose another."),
         ("Waiting screen and coming-up trailers", "The slide that loops at the end of a break until the next programme starts, and the music for its coming-up trailers."),
         ("Today and tomorrow", "What it shows in the next 24 hours, worked out from what it shows and its breaks."),
         ("Played on this channel", "What it has played to someone watching, which From the next episode not watched can count as watched. "
                                    "Jellyfin's own watched marks are never changed."))
PICK_KINDS = (("series", "Series"), ("film", "Films"), ("collection", "Collections"), ("playlist", "Playlists"), ("genre", "Genres"),
              ("decade", "Decades"))


def channel_rows(s, ch, cfg, base, now):
    """One channel's menu row and its items, card by card."""
    cid, n = ch["id"], ch["number"]
    sched = sched_of(ch)
    a = sched.airing(now)
    on = bool(ch.get("on", True))
    detail = (f"Now: {describe(a['entry'])}" if a else "Nothing to show yet: open it and choose what it shows")
    if not on:
        detail = "Off air. " + detail
    menu = {"id": cid, "title": f"{n}  {ch['name']}", "group": "Channels", "detail": detail[:200], "active": on}
    items = []

    def row(key, title, group, **more):
        # Each row's state in words (plug-in API 1.12), so no row reads "Not tested", which suits a list of sources.
        more.setdefault("state", "ok")
        more.setdefault("state_label", "Saved")
        items.append({"id": f"{cid}:{key}", "title": title[:120], "group": group, "menu": cid, **more})

    # Name and number
    g = "Name and number"
    row("on", "On air" if on else "Off air", g, on=on, state="ok" if on else "off", state_label="On air" if on else "Off air",
        detail="Turn on puts it in Jellyfin's Live TV. Move up and Move down change its place in the list, and so its number.",
        actions=["toggle", "up", "down", "remove"])
    row("name", f"Name: {ch['name']}", g, actions=["attach"], attach={"label": "Rename", "field": "Name", "hint": "Up to 40 characters", "value": ch["name"]})
    row("number", f"Number: {n}", g, actions=["attach"],
        detail="Its number in Jellyfin's Live TV. Numbers from 1 put the channels first, before the free channels from 101.",
        attach={"label": "Change number", "field": "Number", "hint": "A whole number from 1 to 9999. Leave it empty to number by its place.",
                "value": str(ch.get("number_set") or "")})
    row("colour", "Colour", g, choice=_choice("Colour", ch.get("colour"), COLOURS),
        detail="On its cards, its made logo and plain coming-up trailers. Words always say what each thing is, so the colour is never the only sign.")

    # What it shows
    g = "What it shows"
    if can("picker"):
        row("pick", "Choose from your library", g, actions=["pick"], state="unknown", state_label="Add",
            detail=("Nothing yet. " if not ch["sources"] else "") + "Every series, film, collection, playlist, genre and decade, with search. Tick several and add them at once.",
            picker={"label": "Choose from your library", "title": f"Add to {ch['name']}"[:80], "search": "Search by name",
                    "filters": [list(k) for k in PICK_KINDS], "submit": "Add the ticked ones"})
    else:
        for kind, label in (("series", "Add a series"), ("film", "Add a film"), ("collection", "Add a collection"),
                            ("playlist", "Add a playlist"), ("genre", "Add a genre")):
            hint = {"genre": "Such as Comedy"}.get(kind, "Its name, or the start of it")
            row(f"add-{kind}", label, g, actions=["attach"], attach={"label": label, "field": "Name", "hint": hint}, state="unknown", state_label="Add one")
    for i, src in enumerate(ch["sources"]):
        row(f"src{i}", source_words(src), g, detail=src.get("detail", ""), actions=["remove", "up", "down"], state_label="In the line-up")
    if not can("picker"):
        row("add-decade", "Add a decade", g, actions=["attach"], attach={"label": "Add a decade", "field": "Decade", "hint": "Such as 1980s"},
            state="unknown", state_label="Add one", detail="Every film and series from those 10 years.")
    row("order", "Order", g, choice=_choice("Order", ch.get("order"), {"in_order": "In order", "shuffle": "Shuffled"}))
    row("run", "Episodes of a series in a row", g, choice=_choice("In a row", ch.get("run"), {str(k): str(k) for k in (1, 2, 3, 4, 6)}))
    # Create initial schedule (0.3.2, owner, 19 November 2026: "a Create initial schedule to put something together to
    # edit in the schedule grid"): a week from this channel's own series and films, kept as an unsaved suggestion.
    draft = grid_doc(cid, "draft") is not None
    grid_link = {"url": f"{base}/t/{s['token']}/grid?channel={cid}", "label": f"Open the schedule grid for {ch['name']}"} if base else None
    row("initial", "Plan the week for me", g, actions=["attach"], state="unknown" if not draft else "ok",
        state_label="Waiting to be saved" if draft else "Make one",
        detail=("Made: open the schedule grid to change it, then save it. " if draft else "") +
               "Fills the hours you give with this channel's series and films: series on weekdays, films at the weekend.",
        attach={"label": "Plan the week for me", "field": "Hours to fill", "value": initial_hours_words(ch),
                "hint": "Weekdays 18:00 to 23:00, weekends 12:00 to 23:00, on the quarter hour"},
        **({"link": grid_link} if grid_link else {}))

    # Breaks
    g = "Breaks"
    row("start_on", "Programmes start", g, choice=_choice("Start", ch.get("start_on"), START_ON),
        detail="On the quarter, half or whole hour, the break fills the time to the next one.")
    row("break_seconds", "Break between programmes", g, choice=_choice("Break", ch.get("break_seconds"), BREAKS),
        detail="Added after each programme. With programmes on the half hour, the break also fills the rest of the slot.")
    row("mid_break_seconds", "Breaks inside programmes", g, choice=_choice("Breaks inside", str(ch.get("mid_break_seconds") or 0), MID_BREAKS),
        detail="Where a programme fades to black for its own short videos, found in quiet hours. Their time comes from the break after it.")
    how_now, per_30, per_film = place_choice(ch)
    row("place_how", "Where breaks go inside a programme", g, choice=_choice("Where", how_now, PLACE_HOW),
        detail="Found once for each programme, in quiet hours. A break with no place found goes to its set time.")
    row("breaks_per_30", "Breaks in each 30 minutes", g, choice=_choice("Breaks in 30 minutes", str(per_30 or ""), PER_30),
        detail="This many for every 30 minutes, at least 1. Automatic is 1 up to 40 minutes, 2 up to 75 minutes and 3 after that. A film has its own number.")
    row("breaks_per_film", "Breaks in a film", g, choice=_choice("Breaks in a film", str(per_film or ""), PER_FILM),
        detail="How many breaks a film has, whatever its length. Their time comes from the break after it, so a film with many needs a long one.")
    for which in breakgrid.GRIDS:
        saved = breakgrid.grid_of(ch, which) is not None
        row(f"grid-{which}", f"{breakgrid.GRID_WORDS[which]} grid", g, state="ok" if saved else "unknown",
            state_label="Your grid" if saved else "Standard order",
            detail=("What plays between one programme and the next: " if which == "between" else "What plays in a break inside a programme: ") +
                   ("your grid is in use." if saved else "the order it has always had. Open the grid to change it.") +
                   " Drag items into columns, or use the buttons and the keyboard.",
            **({"link": {"url": f"{base}/t/{s['token']}/breaks?channel={cid}&grid={which}",
                         "label": f"Open the {GRID_LINK[which]} grid for {ch['name']}"}} if base else {}))
    both = {"none": "None", "own": "This channel's", "shared": "The station's", "both": "This channel's and the station's"}
    row("idents", "Short title clips", g, choice=_choice("Short title clips", ch.get("idents"), both))
    row("ident_order", "Short title clips play", g, choice=_choice("Short title clips play", ch.get("ident_order"), {"in_order": "In order", "random": "In a random order"}))
    row("trailers", "Trailers", g, choice=_choice("Trailers", "on" if ch.get("trailers") else "off", {"off": "None", "on": "Trailers of its films, from Jellyfin"}))
    row("clips", "Your clips", g, choice=_choice("Clips", ch.get("clips"), both))
    row("per_break", "Coming-up trailers and clips in each break", g, choice=_choice("In each break", str(ch.get("per_break") or 3), PER_BREAK),
        detail="Each plays once at most, in a random order, after the very short title clip. The waiting screen fills the rest of the break.")
    row("extras", "Your own short videos", g, choice=_choice("Your own short videos", ch.get("extras") or "both", both),
        detail="One plays at random after the coming-up trailers in each break, when it fits.")
    own = ch.get("own") or {}
    for role in ("idents", "clips", "extras", "psa"):
        for c in own.get(role) or []:
            row(f"clip-{c['id']}", f"{ROLES[role]}: {c['title']}", g, detail=f"{round(c['dur'])} seconds", actions=["remove"], state_label="Ready")
    row("add-ident", "Add a short title clip", g, actions=["attach"], state="unknown", state_label="Add one",
        attach={"label": "Add a short title clip", "field": "Short title clip", "hint": "A short video, up to 60 MB, or the name of a Jellyfin collection of them",
                "accept": ",".join(CLIP_TYPES)})
    row("add-clip", "Add a clip", g, actions=["attach"], state="unknown", state_label="Add one",
        attach={"label": "Add a clip", "field": "Clip", "hint": "A trailer or clip, up to 60 MB, or the name of a Jellyfin collection of them",
                "accept": ",".join(CLIP_TYPES)})
    row("psa", "Public messages", g, choice=_choice("Public messages", ch.get("psa") or "both", both),
        detail="Public service announcements for the Public message item in the break layouts: this channel's, the station's or both.")
    row("add-psa", "Add a public message", g, actions=["attach"], state="unknown", state_label="Add one",
        detail="A video with sound, up to 10 minutes and 90 MB. It is checked when it is added.",
        attach={"label": "Upload a public message", "field": "Public message", "hint": "A video with a picture and a sound track, up to 10 minutes and 90 MB",
                "accept": ",".join(CLIP_TYPES)})
    row("add-extra", "Add a short video of your own", g, actions=["attach"], state="unknown", state_label="Add one",
        detail="As many as you like. One plays at random after the coming-up trailers in each break.",
        attach={"label": "Upload a short video of your own", "field": "Short video of your own", "hint": "A video of up to 10 minutes and 90 MB",
                "accept": ",".join(CLIP_TYPES)})

    # On-screen logo and branding
    g = "Corner logo and branding"
    st = dog.resolve(cfg, None)
    own_dog = ch.get("dog") or {}
    yesno = {"true": "Yes", "false": "No"}
    for key, label, options in (("kind", "Corner logo", dog.KINDS), ("corner", "Corner", dog.CORNERS),
                                ("size", "Size", {"small": "Small", "medium": "Medium", "large": "Large"}),
                                ("margin", "Distance from the edge", {"small": "Close", "medium": "Inside the safe area", "large": "Further in"}),
                                ("opacity", "Opacity", {str(p): f"{p}%" for p in (40, 50, 60, 70, 80, 90, 100)}),
                                ("when", "When it shows", dog.WHEN),
                                ("fade_in", "Fades in after the opening", {"0": "No, at once", "30": "After 30 seconds", "60": "After 1 minute", "120": "After 2 minutes"}),
                                ("clock", "Clock", yesno), ("label", "Label", dog.LABELS), ("plate", "Dark box behind the logo", yesno),
                                ("strap_start", "Programme name at the start", yesno), ("strap_end", "Up next during the end credits", yesno),
                                ("cards", "Coming up next and Later cards", yesno)):
        dv = st[key]
        dw = (options.get(str(dv).lower()) if isinstance(dv, bool) else options.get(str(dv))) or str(dv)
        v = own_dog.get(key, "")
        row(f"dog-{key}", label, g, choice=_choice(label, str(v).lower() if isinstance(v, bool) else v, options, dw))
    row("logo", "Logo: " + ("your picture" if own_logo(cid) else "the pack's" if logo_file(cid, channel_pack(s, ch)) else
                            "made from its number and name"), g,
        actions=["attach", "detach"] if own_logo(cid) else ["attach"],
        **({"image": img} if (img := logo_thumb(logo_file(cid, channel_pack(s, ch)) or made_logo(ch), f"{ch['name']}'s logo")) else {}),
        attach={"label": "Add logo", "field": "Logo", "detach_label": "Remove the logo", "hint": "A PNG with a clear background, at least 256 pixels tall", "accept": ".png"})
    row("pack", "Branding", g, choice=_choice("Branding", ch.get("pack") or "", PACK_MODES),
        detail=f"Now {pack_words(s, ch)}. A pack gives the corner logo, short title clips, transitions, the Coming up next card and coming-up trailers.")
    own_pk = load_pack(f"ch-{cid}")
    row("pack-own", f"Its own pack: {own_pk['name']}" if own_pk else "Its own pack: none yet", g,
        actions=["attach", "detach"] if own_pk else ["attach"], detail=pack.summary(own_pk) if own_pk else
        "For branding of its own: a zip made from the template, in Branding. Then choose Its own pack.",
        attach={"label": "Upload its own pack", "field": "Pack", "detach_label": "Remove its pack", "hint": "A zip of up to 60 MB, made from the template", "accept": ".zip"})
    prev = {"detail": "Opens a frame as it would be drawn now, with these settings."}
    if base:
        prev["link"] = {"url": f"{base}/t/{s['token']}/preview/{cid}.png", "label": f"Preview a frame of {ch['name']}"}
        items.append({"id": f"{cid}:preview-card", "title": "Preview a Coming up next card", "group": g, "menu": cid, "state": "unknown",
                      "state_label": "Preview", "link": {"url": f"{base}/t/{s['token']}/preview/{cid}.png?kind=card",
                                                         "label": f"Preview a Coming up next card on {ch['name']}"}})
    else:
        prev["detail"] = NO_ADDRESS
    row("preview", "Preview a frame", g, state="unknown", state_label="Preview", **prev)

    # Animation (0.3.0)
    items += anim_rows(s, ch, base, "Animation")

    # Holding slide and promos
    g = "Waiting screen and coming-up trailers"
    h = holding_for(s, ch)
    mode = ch.get("holding_mode") or ""
    row("holding_mode", "Waiting screen", g, choice=_choice("Waiting screen", mode, HOLDING_MODES),
        detail=(f"Now {holding_words(ch.get('holding') if mode == 'own' and ch.get('holding') else s.get('holding'))}. " if h else
                "None yet, so breaks end on Coming up next cards. ") + "It loops after the coming-up trailers until the next programme starts.")
    row("holding-own", "Its own waiting screen: " + (holding_words(ch["holding"]) if ch.get("holding") else "none yet"), g,
        actions=["attach", "detach"] if ch.get("holding") else ["attach"], state="ok" if ch.get("holding") else "unknown",
        state_label="Ready" if ch.get("holding") else "Add one", detail="A picture, or a video of up to 120 seconds that loops. The station's is in What plays between programmes.",
        attach={"label": "Upload a waiting screen", "field": "Waiting screen", "detach_label": "Remove the waiting screen", "hint": "A PNG or JPEG picture, or a video of up to 120 seconds and 90 MB",
                "accept": ",".join(HOLDING_TYPES)})
    st_words = dog.HOLDING_WORDS.get(s.get("holding_words") or "countdown")
    row("holding_words", "Words on the waiting screen", g, choice=_choice("Words", ch.get("holding_words") or "", dog.HOLDING_WORDS, st_words),
        detail="A countdown says Next programme in 4:32 with the programme's name, and reaches 0:00 as it starts.")
    if base and h:
        row("preview-holding", "Preview the waiting screen", g, state="unknown", state_label="Preview",
            link={"url": f"{base}/t/{s['token']}/preview/{cid}.png?kind=holding", "label": f"Preview the waiting screen on {ch['name']}"})
    design = promo_design(s, ch)
    kept = [p for p in s.get("promos") or [] if p.get("cid") == cid]
    how = ("Made in quiet hours with its branding." if design and design.get("name") != "Plain" else
           "Made in quiet hours on its colour, with your music." if design else
           "To have coming-up trailers, upload music for them here or in What plays between programmes, or use a pack with a coming-up trailer.")
    row("promos", f"Coming-up trailers: {len(kept)} kept" if design else "Coming-up trailers: none yet", g, state="ok" if design else "off",
        state_label="Made in quiet hours" if design else "None", detail=how)
    for m in ch.get("music") or []:
        row(f"music-{m['id']}", f"Music: {m['title']}", g, detail=f"{round(m.get('dur') or 0)} seconds. Used for this channel's coming-up trailers.",
            actions=["remove"], state_label="Ready")
    for b in ch.get("promo_backgrounds") or []:
        row(f"back-{b['id']}", f"Background loop: {b['title']}", g, detail=f"{back_words(b).capitalize()}. Each coming-up trailer chooses one at random.",
            actions=["remove"], state_label="Ready")
    row("add-back", "Add a background loop for its coming-up trailers", g, actions=["attach"], state="unknown", state_label="Add one",
        detail="Used with the station's and the pack's, one chosen at random for each coming-up trailer. Leave the clip area and the words' places clear.",
        attach={"label": "Upload a background loop", "field": "Background loop", "accept": ",".join(BACK_TYPES),
                "hint": "A video of 2 to 60 seconds that loops, or a PNG or JPEG picture, 1920 by 1080, up to 90 MB"})
    row("add-music", "Add music for its coming-up trailers", g, actions=["attach"], state="unknown", state_label="Add one",
        detail="Its own music, used in place of the station's. " + MUSIC_USE.get(s.get("music_use") or "both", "") + " are used.",
        attach={"label": "Upload music", "field": "Music", "hint": "An MP3, M4A, OGG or FLAC file of 5 seconds to 10 minutes, up to 60 MB",
                "accept": ",".join(MUSIC_TYPES)})

    # Today and tomorrow
    g = "Today and tomorrow"
    got = sched.airings(now, now + 86400, limit=60)
    for k, a2 in enumerate(got):
        e = a2["entry"]
        new = guide.is_new(e, a2["start"])
        row(f"today{k}", f"{day_hm(a2['start'], now)} to {hm(a2['end'])}  {e.get('title')}", g,
            detail=(guide.episode_words(e) + ". " if guide.episode_words(e) else "") + (e.get("plot") or "")[:120],
            state="ok" if new else "unknown", state_label="New" if new else "Repeat")
    if not got:
        row("today-none", "Nothing yet", g, state="unknown", state_label="Empty", detail="Choose what it shows, and its programmes are listed here.")

    # Played on this channel (0.3.0)
    g = "Played on this channel"
    row("count_played", "Count what this channel has played as watched", g,
        choice=_choice("Count as watched", "on" if ch.get("count_played", True) else "off", {"on": "Yes", "off": "No"}),
        detail="For From the next episode not watched: an episode it played to someone watching, 70% or more of it, counts as watched. "
               "Jellyfin's own watched marks are never changed.")
    rec = record()
    for k, r in enumerate(rec.latest(cid, PLAYED_SHOWN)):
        row(f"played{k}", f"{day_hm(r['at'], now)}  {r['title']}" + (f", {r['ep']}" if r.get("ep") else ""), g,
            detail=f"{round(r['seconds'] / 60)} of {round(r['length'] / 60)} minutes played to someone watching",
            state="ok" if r.get("seen") else "unknown", state_label="Watched" if r.get("seen") else "Part watched")
    n = rec.count(cid)
    if n:
        row("forget-played", "The record of what it has played", g, actions=["remove"], state="ok",
            state_label=sbplugin.plural(n, "programme"),
            detail="Remove forgets it all, so every episode counts as watched only when Jellyfin says it is. Jellyfin is not changed.")
    else:
        row("played-none", "Nothing played yet", g, state="unknown", state_label="Empty",
            detail="Once someone watches it in Jellyfin's Live TV, what it plays is listed here.")
    return menu, items


PLAYED_SHOWN = 5  # programmes listed in Played on this channel


NO_ADDRESS = ("It does not know its address yet. Update Starboard in Settings, Updates (0.23.0 and later give it), "
              "or open this plug-in's web page once from its page in Settings, Plug-ins.")


def channels_page(said=None, now=None, only=None):
    """The Channels page. only: one channel's id, for an answer with that channel alone (partial, Starboard 0.24.0)."""
    now = time.time() if now is None else now
    s = state()
    cfg = settings()
    base = address()
    menus, items = [], []
    for ch in numbered(s):
        if only and ch["id"] != only:
            continue
        m, its = channel_rows(s, ch, cfg, base, now)
        menus.append(m)
        items += its
    if only:
        out = {"type": "list", "title": "Channels", "partial": {"menus": [only]}, "menus": menus, "items": items}
        if said:
            out["said"] = said[:200]
        return out
    out = {"type": "list", "title": "Channels", "intro": (f"{station_name(cfg)}: {sbplugin.plural(len(s['channels']), 'channel')}. "
                                                          "Open a channel to change it. Each of its cards is one part of it: its name, what it shows, "
                                                          "its breaks, its corner logo, its waiting screen and coming-up trailers, and its programmes."),
           "add": {"label": "Add a channel", "hint": "Its name, such as Comedy. Up to 40 characters", "placeholder": "Channel name"},
           "menus": menus, "items": items, "hints": dict(CARDS)}
    if can("cards"):
        out["layout"] = "cards"
    if said:
        out["said"] = said[:200]
    err = sbplugin.last_error()
    out["notices"] = ([{"id": "error", "tone": "warning", "title": "The last refresh did not finish", "text": err, "dismiss": True}] if err else []) \
        + explain.notices(s, "channels")
    if not out["notices"]:
        del out["notices"]
    return out


def browse(ch, words, kind, start):
    """A page of the library for the slide-out (Choose from your library, Starboard 0.23.0): what is on the channel
    already is ticked and cannot be ticked again."""
    kind = kind if kind in dict(PICK_KINDS) else "series"
    try:
        start = max(0, min(100000, int(start or 0)))
    except (TypeError, ValueError):
        start = 0
    got, total = library.browse(jf, kind, words, start)
    have = {f"{src['kind']}:{src['id']}" for src in ch["sources"]}
    items = [{"id": f"{kind}:{iid}", "title": title[:120], "detail": detail[:200], "on": f"{kind}:{iid}" in have} for iid, title, detail in got]
    return {"type": "picker", "filter": kind, "start": start, "total": total, "more": start + len(items) < total, "items": items}


def pick_sources(ch, ids):
    """Adds every ticked series, film, collection, genre or playlist (up to 100 at once) to what the channel shows."""
    wanted = []
    for raw in [str(i) for i in ids][:100]:
        kind, _, iid = raw.partition(":")
        if kind not in dict(PICK_KINDS) or not iid or len(iid) > 80:
            continue
        if kind not in ("genre", "decade") and not library.ID.match(iid):
            continue
        if kind == "decade" and not re.fullmatch(r"(1[89]|20)[0-9]0", iid):
            continue
        if any(src["kind"] == kind and str(src["id"]) == iid for src in ch["sources"]) or (kind, iid) in wanted:
            continue
        wanted.append((kind, iid))
    if not wanted:
        raise ValueError("Tick at least one that is not on this channel already")
    found = library.names(jf, [iid for kind, iid in wanted if kind not in ("genre", "decade")])
    added = []
    for kind, iid in wanted:
        name = iid if kind == "genre" else f"The {iid}s" if kind == "decade" else found.get(iid)
        if not name:
            continue
        ch["sources"].append({"kind": kind, "id": iid, "name": name})
        added.append(name)
    if not added:
        raise ValueError("Jellyfin did not find the ones ticked. Search again")
    words = ", ".join(added[:-1]) + f" and {added[-1]}" if len(added) > 1 else added[0]
    return f"Added {len(added)} to {ch['name']}: {words}"[:160]


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


def initial_hours_words(ch):
    """The hours Create initial schedule fills, in words, from the hours last chosen for this channel's suggestions."""
    h = ch.get("suggest_hours") or suggest_defaults()
    parts = [f"{name} {h[k][0]} to {h[k][1]}" for k, name in (("weekdays", "Weekdays"), ("weekends", "weekends")) if h.get(k)]
    return ", ".join(parts) or "Weekdays 18:00 to 23:00, weekends 12:00 to 23:00"


def initial_hours(words):
    """'Weekdays 18:00 to 23:00, weekends 12:00 to 23:00' -> {"weekdays": [...], "weekends": [...]} for suggest.parse_hours.
    Times are read in order: the first two are weekdays, the next two the weekend; with only two, both. A part that
    names weekends only fills the weekend. Raises ValueError in words."""
    text = str(words or "").lower()
    times = [f"{int(h):02d}:{m}" for h, m in re.findall(r"\b(\d{1,2})[:.](\d{2})\b", text)]
    if len(times) < 2:
        raise ValueError("Give the hours as a start and an end, such as Weekdays 18:00 to 23:00, weekends 12:00 to 23:00")
    if "weekend" in text and "weekday" not in text:
        return {"weekdays": None, "weekends": times[:2]}
    if "weekday" in text and "weekend" not in text and len(times) == 2:
        return {"weekdays": times[:2], "weekends": None}
    return {"weekdays": times[:2], "weekends": times[2:4] if len(times) >= 4 else times[:2]}


def create_initial(cid, words, now):
    """Create initial schedule: a week from the channel's own line-up, kept as the grid's unsaved suggestion. Worked
    out outside the lock: it asks Jellyfin for each series' episodes."""
    import suggest  # only when asked
    try:
        hours = suggest.parse_hours(initial_hours(words))
    except ValueError as e:
        raise ValueError(str(e)) from None
    s = state()
    ch = find(s, cid)
    if not ch:
        raise ValueError("That channel has gone")
    if not ch.get("eras"):
        raise ValueError("This channel shows nothing yet. Add series or films first, then create its schedule")
    doc, notes = suggest_for(s, ch, now, "channel", hours)
    if not doc["slots"]:
        raise ValueError(notes[-1] if notes else "Nothing fitted those hours")
    with _lock:
        s2 = state()
        c2 = find(s2, cid)
        if c2:
            c2["suggest_from"] = "channel"
            c2["suggest_hours"] = {k: ([suggest.hm24(v[0]), suggest.hm24(v[1])] if v else None) for k, v in hours.items()}
            save(s2)
    grid.store(grid_folder(), cid, doc, "draft")
    n = len(doc["slots"])
    saved = bool((grid_doc(cid) or {}).get("slots"))
    return (f"Made a schedule of {n} slot{'s' if n != 1 else ''} from this channel's line-up. Open the schedule grid to change it, then save it"
            + (". Your saved grid stays as it is until then" if saved else ""))


def channels_post(body, now=None):
    action, rid, value = body.get("action"), str(body.get("id") or ""), body.get("value")
    if action == "attach" and rid.endswith(":initial"):
        cid = rid.partition(":")[0]
        said = create_initial(cid, value, time.time() if now is None else now)
        return channels_page(said, now, only=cid if can("partial") else None)
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
            if explain.dismiss(s, rid):
                save(s)
            else:
                sbplugin.clear_error()
            return channels_page(None, now)
        cid, _, key = rid.partition(":")
        ch = find(s, cid)
        if not ch:
            raise ValueError("That channel has gone")
        if action == "browse" and key == "pick":
            return browse(ch, str(value or ""), str(body.get("filter") or ""), body.get("start"))
        said, refresh, whole = "Saved", False, False
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
            whole = True  # every channel's number may change
            later_jellyfin()
        elif key == "on" and action == "remove":
            s["channels"].remove(ch)
            s["removed"] = (s["removed"] + [{**ch, "removed": int(time.time())}])[-10:]
            said = f"Removed {ch['name']}. Its settings are kept in the plug-in's folder"
            whole = True
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
        elif key == "pack-own" and action == "detach":
            shutil.rmtree(pack_dir(f"ch-{cid}"), ignore_errors=True)
            _packs.pop(f"ch-{cid}", None)
            if ch.get("pack") == "own":
                ch["pack"] = ""
            said = "Its own pack is removed: it uses the station's pack"
        elif key == "logo" and action == "detach":
            with contextlib.suppress(OSError):
                os.remove(os.path.join(sbplugin.DATA, LOGOS, f"{cid}.png"))
            said = "Logo removed: the made logo is used"
        elif key.startswith("add-") and action == "attach" and key[4:] in library.KINDS:
            said = add_source(ch, key[4:], str(value or ""))
            refresh = True
        elif key == "pick" and action == "pick":
            said = pick_sources(ch, body.get("ids") or [])
            refresh = True
        elif key == "holding-own" and action == "detach":
            drop_holding(ch.pop("holding", None))
            if ch.get("holding_mode") == "own":
                ch["holding_mode"] = ""
            said = "Its own waiting screen is removed: it uses the station's" + ("" if s.get("holding") else ", and there is none, so breaks end on cards")
        elif key.startswith("music-") and action == "remove":
            ch["music"] = drop_music(ch.get("music"), key[6:])
            said = "Removed the music"
        elif key.startswith("back-") and action == "remove":
            ch["promo_backgrounds"] = drop_background(ch.get("promo_backgrounds"), key[5:])
            said = "Removed the background loop"
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
            for role in ("idents", "clips", "extras", "psa"):
                own[role] = [c for c in own.get(role) or [] if c["id"] != key[5:]]
            said = "Removed the clip. Its file stays in the plug-in's folder until you add another with the same name"
        elif key == "forget-played" and action == "remove":
            record().forget(cid)
            said = f"{ch['name']} has forgotten what it played. Jellyfin's watched marks are as they were"
        elif action == "choose":
            said = choose(ch, key, value)
            refresh = key in ("order", "run", "start_on", "break_seconds", "trailers")
        else:
            raise ValueError("That cannot be changed here")
        save(s)
    if refresh:
        refresh_soon(cid)
        said += ". The new line-up starts after the programme on now"
    out = channels_page(said, now, only=None if whole or not can("partial") else cid)
    if action == "choose" and said.startswith("Saved"):  # say what was saved in the row's own words: "Corner: Bottom left"
        it = next((x for x in out["items"] if x["id"] == rid and x.get("choice")), None)
        if it:
            words = next((w for k, w in it["choice"]["options"] if k == it["choice"]["value"]), "")
            out["said"] = f"{it['choice']['label']}: {words}. Saved for {ch['name']}{said[5:]}"[:200]
    return out


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
    elif key == "mid_break_seconds" and v in MID_BREAKS:
        ch["mid_break_seconds"] = int(v)
    elif key == "place_how" and v in PLACE_HOW:
        ch["place_how"] = v
        return f"Saved: breaks go {PLACE_HOW[v].lower()}"
    elif key == "breaks_per_30" and v in PER_30:
        ch["breaks_per_30"] = int(v or 0)
    elif key == "breaks_per_film" and v in PER_FILM:
        ch["breaks_per_film"] = int(v or 0)
    elif key in ("idents", "clips") and v in ("none", "own", "shared", "both"):
        ch[key] = v
    elif key == "per_break" and v in PER_BREAK:
        ch["per_break"] = int(v)
    elif key in ("extras", "psa") and v in ("none", "own", "shared", "both"):
        ch[key] = v
    elif key == "ident_order" and v in ("in_order", "random"):
        ch["ident_order"] = v
    elif key == "trailers" and v in ("on", "off"):
        ch["trailers"] = v == "on"
    elif key == "pack" and v in PACK_MODES:
        ch["pack"] = v
        return f"{ch['name']} now uses {PACK_MODES[v].lower()}"
    elif key == "holding_mode" and v in HOLDING_MODES:
        ch["holding_mode"] = v
        return f"{ch['name']} now uses {HOLDING_MODES[v].lower()}"
    elif key == "holding_words" and (v == "" or v in dog.HOLDING_WORDS):
        ch["holding_words"] = v
        return "Saved: " + (dog.HOLDING_WORDS[v] if v else "the station's words") + " on the waiting screen"
    elif key.startswith("anim-"):
        return set_anim(ch.setdefault("dog", {}), key, v)
    elif key == "count_played" and v in ("on", "off"):
        ch["count_played"] = v == "on"
        return ("What it plays counts as watched" if v == "on" else "Only Jellyfin's watched marks count") + " for From the next episode not watched"
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


def save_upload(name, length, rfile, folder, types, most=MAX_UPLOAD):
    if length <= 0 or length > most:
        raise ValueError(f"Choose a file of up to {most // (1024 * 1024)} MB")
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
    path, base = save_upload(name, length, rfile, os.path.join(sbplugin.DATA, CLIPS), CLIP_TYPES,
                             most=EXTRA_MOST if role in ("extras", "psa") else MAX_UPLOAD)
    dur, has_audio, has_video = probe_seconds(path)
    if not has_video or dur <= 0:
        raise ValueError(f"{base} has no picture FFmpeg can read")
    if role == "psa" and not has_audio:
        raise ValueError(f"{base} has no sound track: a public message needs one")
    if dur > 600:
        raise ValueError(f"{base} is over 10 minutes: too long for a break")
    cid = hashlib.sha256(base.encode()).hexdigest()[:10]
    holder[role] = [c for c in holder.get(role) or [] if c["id"] != cid] + [
        {"id": cid, "src": f"file:{base}", "dur": round(dur, 2), "title": base, "role": role, "has_audio": has_audio, "audio": None}]
    warn = flash.words(flash.check(path)) if has_video else ""  # 0.13.0: said, never refused
    return f"Added {base}, {round(dur)} seconds" + (f". Warning: {warn}" if warn else "")


def channels_file(name, item, length, rfile):
    cid, _, key = item.partition(":")
    if key == "pack-own":
        # Checked outside the lock: reading every file with ffprobe takes a while, and nothing else need wait for it.
        if not find(state(), cid):
            raise ValueError("That channel has gone")
        got = install_pack(f"ch-{cid}", name, length, rfile)
        with _lock:
            s = state()
            ch = find(s, cid)
            if ch:
                ch["pack"] = "own"
                save(s)
        whose = f"{ch['name']}'s" if ch else "the channel's"
        return channels_page(f"{got['pack']['name']} is now {whose} own pack: {pack.summary(got['pack']).lower()}", only=cid if can("partial") and ch else None)
    if key in ("holding-own", "add-music", "add-back"):
        # Checked outside the lock too: ffprobe, and FFmpeg measuring the loudness, take a moment.
        ch = find(state(), cid)
        if not ch:
            raise ValueError("That channel has gone")
        if key == "holding-own":
            got = add_holding(f"ch-{cid}", name, length, rfile)
        elif key == "add-back":
            backs, said = add_background(ch.get("promo_backgrounds"), f"ch-{cid}", name, length, rfile)
        else:
            tracks, said = add_music(ch.get("music"), f"ch-{cid}", name, length, rfile)
        with _lock:
            s = state()
            ch = find(s, cid)
            if not ch:
                raise ValueError("That channel has gone")
            if key == "holding-own":
                ch["holding"], ch["holding_mode"] = got, "own"
                said = f"{got['title']} is {ch['name']}'s waiting screen. It loops after the coming-up trailers until the next programme starts"
            elif key == "add-back":
                ch["promo_backgrounds"] = backs
                said += f". {ch['name']}'s coming-up trailers use it from the next quiet hour"
            else:
                ch["music"] = tracks
                said += f". {ch['name']}'s coming-up trailers use it from the next quiet hour"
            save(s)
        return channels_page(said, only=cid if can("partial") else None)
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
        elif key in ("add-ident", "add-clip", "add-extra", "add-psa"):
            said = add_clip_file(ch.setdefault("own", {"idents": [], "clips": [], "sources": []}),
                                 {"add-ident": "idents", "add-clip": "clips", "add-extra": "extras", "add-psa": "psa"}[key], name, length, rfile)
        else:
            raise ValueError("That row takes no file")
        save(s)
    return channels_page(said, only=cid if can("partial") else None)


def _sub(out, menu, title, page, prefix, detail=None, group="More"):
    """The items of another page, in a sub menu of this one (0.11.0, fewer tabs). Each id gets the prefix, so a change finds its page again."""
    out.setdefault("menus", []).append({"id": menu, "title": title, "detail": (detail or page.get("intro") or "")[:200], "group": group})
    for it in page.get("items", []):
        out["items"].append({**it, "id": prefix + str(it["id"]), "menu": menu})


def guide_rows(now=None):
    """The guide as plain rows, for a sub menu: a group for each channel, a row for each programme in the next 24 hours."""
    now = time.time() if now is None else now
    items = []
    for ch in numbered(state()):
        if not ch.get("on", True):
            continue
        for k, a in enumerate(sched_of(ch).airings(now, now + 86400, limit=100)):
            e = a["entry"]
            more = [guide.episode_words(e)[:60], "New" if guide.is_new(e, a["start"]) else "Repeat"]
            items.append({"id": f"{ch['id']}:{k}", "title": (e.get("title") or "Programme")[:120], "group": f"{ch['number']} {ch['name']}"[:40],
                          "detail": (f"{day_hm(a['start'], now)} to {hm(a['end'])}. " + ". ".join(x for x in more if x))[:200]})
    if not items:
        items.append({"id": "none", "title": "Nothing is on yet", "group": "The next 24 hours", "state": "unknown", "state_label": "None",
                      "detail": "Add a channel and a series or film to it, and its programmes are listed here."})
    return {"items": items, "intro": f"What is on {station_name()} in the next 24 hours. Jellyfin's guide has the next 7 days. " + guide_status(now)}


def _explain(out, s, page):
    """Adds the one-time explainers for a page to its notices (explain.py)."""
    got = explain.notices(s, page)
    if got:
        out["notices"] = (out.get("notices") or []) + got


def clips_page(said=None):
    """What plays between programmes, in the order a person thinks of it (0.10.0, DASH-642): short title clips, clips, music,
    the waiting screen, then the advanced things. No group called Add: each group has its own add row."""
    s = state()
    sh = s["shared"]
    items = []
    no_file = "The file name is not shown."
    empty = not (sh.get("idents") or sh.get("clips") or s.get("music") or s.get("holding") or sh.get("extras") or sh.get("psa"))
    if empty:
        using = s.get("station_pack") == "example"
        items.append({"id": "use-example", "title": "Use the example files", "group": "Start here", "on": using, "actions": ["toggle"],
                      "state": "ok" if using else "unknown", "state_label": "In use" if using else "Not used",
                      "detail": "Adds ready-made branding with 3 short title clips, a logo with music and a Coming up next card. You can stop using it any time."})

    def listed(role, group):
        for c in sh.get(role) or []:
            items.append({"id": f"{role}:{c['id']}", "title": c["title"][:120], "detail": f"{round(c['dur'])} seconds",
                          "group": group, "actions": ["remove"], "state": "ok", "state_label": "Ready"})

    g = "Short title clips"
    listed("idents", g)
    items.append({"id": "add:idents", "title": "Add a short title clip", "group": g, "actions": ["attach"], "state": "unknown", "state_label": "Add one",
                  "detail": "A few seconds of video with your station name, played between programmes.",
                  "attach": {"label": "Add a short title clip", "field": "Name", "hint": f"A video up to 60 MB, or the name of a Jellyfin collection or folder. {no_file}",
                             "accept": ",".join(CLIP_TYPES)}})
    g = "Clips"
    listed("clips", g)
    items.append({"id": "add:clips", "title": "Add a clip", "group": g, "actions": ["attach"], "state": "unknown", "state_label": "Add one",
                  "detail": "A short video of a film or series, played in a break after the short title clip.",
                  "attach": {"label": "Add a clip", "field": "Name", "hint": f"A video up to 60 MB, or the name of a Jellyfin collection or folder. {no_file}",
                             "accept": ",".join(CLIP_TYPES)}})
    g = "Music"
    items.append({"id": "music-use", "title": "Music the coming-up trailers use", "group": g, "state": "ok", "state_label": "Saved",
                  "detail": "A channel's own music comes first, then this. A change shows in the next coming-up trailers.",
                  "choice": _choice("Music", s.get("music_use") or "both", MUSIC_USE)})
    for m in s.get("music") or []:
        items.append({"id": f"music:{m['id']}", "title": m["title"][:120], "group": g, "actions": ["remove"], "state": "ok",
                      "state_label": "Ready", "detail": f"{round(m.get('dur') or 0)} seconds, played at the same loudness as the rest"})
    items.append({"id": "add:music", "title": "Add music", "group": g, "actions": ["attach"], "state": "unknown", "state_label": "Add one",
                  "detail": "Quiet music under the coming-up trailers. With music here, a channel without branding of its own still gets trailers.",
                  "attach": {"label": "Upload music", "field": "Music", "accept": ",".join(MUSIC_TYPES),
                             "hint": f"An MP3, M4A, OGG or FLAC file of 5 seconds to 10 minutes, up to 60 MB. {no_file}"}})
    g = "Waiting screen"
    h = s.get("holding")
    items.append({"id": "holding", "title": "The station's waiting screen: " + (holding_words(h) if h else "none yet"), "group": g,
                  "state": "ok" if h else "unknown", "state_label": "In use" if h else "None yet",
                  "detail": ("Loops at the end of each break until the next programme starts, on every channel without its own."
                             if h else "A picture or short video that loops, with a countdown, until the next programme starts.")[:200],
                  "actions": ["attach", "detach"] if h else ["attach"],
                  "attach": {"label": "Upload a waiting screen", "field": "Waiting screen", "accept": ",".join(HOLDING_TYPES),
                             "detach_label": "Remove the waiting screen",
                             "hint": f"A PNG or JPEG picture, or a video of up to 120 seconds and 90 MB. {no_file}"}})
    items.append({"id": "holding-words", "title": "Words on the waiting screen", "group": g, "state": "ok", "state_label": "Saved",
                  "detail": "A countdown says Next programme in 4:32 with the programme's name. Each channel can choose its own.",
                  "choice": _choice("Words", s.get("holding_words") or "countdown", dog.HOLDING_WORDS)})
    g = "More: your own short videos"
    listed("extras", g)
    items.append({"id": "add:extras", "title": "Add a short video of your own", "group": g, "actions": ["attach"], "state": "unknown", "state_label": "Add one",
                  "detail": "One plays at random after the coming-up trailers in each break, on every channel that uses the station's.",
                  "attach": {"label": "Upload a short video of your own", "field": "Short video of your own", "accept": ",".join(CLIP_TYPES),
                             "hint": f"A video of up to 10 minutes and 90 MB. {no_file}"}})
    g = "More: public messages"
    listed("psa", g)
    items.append({"id": "add:psa", "title": "Add a public message", "group": g, "actions": ["attach"], "state": "unknown", "state_label": "Add one",
                  "detail": "A short video with a message, such as a safety tip. Every channel can use it in a break layout.",
                  "attach": {"label": "Upload a public message", "field": "Public message", "accept": ",".join(CLIP_TYPES),
                             "hint": f"A video with a picture and a sound track, up to 10 minutes and 90 MB. {no_file}"}})
    g = "More: background loops"
    for b in s.get("promo_backgrounds") or []:
        items.append({"id": f"back:{b['id']}", "title": b["title"][:120], "group": g, "actions": ["remove"],
                      "state": "ok", "state_label": "Ready", "detail": f"{back_words(b).capitalize()}. Each coming-up trailer chooses one at random"})
    items.append({"id": "add:back", "title": "Add a background loop for coming-up trailers", "group": g, "actions": ["attach"],
                  "state": "unknown", "state_label": "Add one",
                  "detail": "A picture or video behind the words of each trailer. Keep the middle and the places for words clear.",
                  "attach": {"label": "Upload a background loop", "field": "Background loop", "accept": ",".join(BACK_TYPES),
                             "hint": f"A video of 2 to 60 seconds that loops, or a PNG or JPEG picture, 1920 by 1080, up to 90 MB. {no_file}"}})
    out = {"type": "list", "title": "What plays between programmes", "items": items,
           "intro": "Everything here plays between programmes on every channel. Each channel can use these, its own, or both."}
    _sub(out, "layouts", "Break layouts", grids_page(), "layouts~", "What plays between programmes and in breaks inside programmes, for each channel.")
    _sub(out, "files", "All your files in one list", files_page(), "files~", "Every short title clip, trailer clip, short video and public message, to search and sort.")
    _explain(out, s, "clips")
    if said:
        out["said"] = said[:200]
    return out


def clips_post(body):
    action, rid, value = body.get("action"), str(body.get("id") or ""), body.get("value")
    if action == "toggle" and rid == "use-example":  # the empty page's Use the example files: the example branding, as in Branding
        return clips_page((pack_post({"action": "toggle", "id": "example"}) or {}).get("said"))
    with _lock:
        s = state()
        if action == "dismiss" and explain.dismiss(s, rid):
            save(s)
            return clips_page()
        role, _, cid = rid.partition(":")
        if action == "remove" and role in ("idents", "clips", "extras", "psa"):
            s["shared"][role] = [c for c in s["shared"].get(role) or [] if c["id"] != cid]
            said = "Removed"
        elif action == "remove" and role == "music":
            s["music"] = drop_music(s.get("music"), cid)
            said = "Removed the music"
        elif action == "remove" and role == "back":
            s["promo_backgrounds"] = drop_background(s.get("promo_backgrounds"), cid)
            said = "Removed the background loop"
        elif action == "attach" and role == "add" and cid in ("idents", "clips"):
            said = add_jellyfin_clips(s["shared"], cid, str(value or ""))
        elif action == "attach" and rid in ("add:music", "add:back", "add:extras", "add:psa", "holding"):
            raise ValueError("Choose a file, then Upload")
        elif action == "detach" and rid == "holding":
            drop_holding(s.pop("holding", None))
            said = "The station's waiting screen is removed. Breaks end on Coming up next cards, unless a channel has its own waiting screen"
        elif action == "choose" and rid == "holding-words" and str(value) in dog.HOLDING_WORDS:
            s["holding_words"] = str(value)
            said = f"Words on the waiting screen: {dog.HOLDING_WORDS[str(value)]}. Saved"
        elif action == "choose" and rid == "music-use" and str(value) in MUSIC_USE:
            s["music_use"] = str(value)
            said = f"Music the coming-up trailers use: {MUSIC_USE[str(value)]}. Saved"
        else:
            raise ValueError("That cannot be changed here")
        save(s)
    return clips_page(said)


def clips_file(name, item, length, rfile):
    if item == "holding":
        got = add_holding("station", name, length, rfile)
        with _lock:
            s = state()
            s["holding"] = got
            save(s)
        return clips_page(f"{got['title']} is the station's waiting screen. It loops at the end of each break until the next programme starts")
    if item == "add:back":
        backs, said = add_background(state().get("promo_backgrounds"), "station", name, length, rfile)
        with _lock:
            s = state()
            s["promo_backgrounds"] = backs
            save(s)
        return clips_page(said + ". Coming-up trailers use it from the next quiet hour")
    if item == "add:music":
        tracks, said = add_music(state().get("music"), "station", name, length, rfile)
        with _lock:
            s = state()
            s["music"] = tracks
            save(s)
        return clips_page(said + ". Coming-up trailers use it from the next quiet hour")
    role = item.partition(":")[2]
    if role not in ("idents", "clips", "extras", "psa"):
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
        for k, a in enumerate(sched_of(ch).airings(now, now + 86400, limit=100)):
            e = a["entry"]
            items.append({"id": f"{ch['id']}:{k}", "title": e.get("title") or "Programme", "group": f"{ch['number']} {ch['name']}"[:40],
                          "cells": {"time": f"{day_hm(a['start'], now)} to {hm(a['end'])}", "programme": (e.get("title") or "")[:80],
                                    "episode": guide.episode_words(e)[:80], "shown": "New" if guide.is_new(e, a["start"]) else "Repeat",
                                    "synopsis": (e.get("plot") or "")[:80]}})
    return {"type": "list", "title": "Guide", "layout": "folds", "readonly": True,
            "intro": f"What is on {station_name()} in the next 24 hours. Jellyfin's guide has the next 7 days.",
            "notices": [{"id": "read", "tone": "success" if (sbplugin.remember("guide_read", None) or {}).get("at") else "info",
                         "title": "Jellyfin's guide", "text": guide_status(now)[:400]}],
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
        sched = sched_of(ch)
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
    if renamed():
        later_jellyfin()
    if not s["channels"]:
        return sbplugin.band({"items": [], "note": "No channels yet. Add one in Settings, Plug-ins, Create your own TV channel, Channels"}, "needs_setup")
    note = ""
    if not address():
        note = "Open the plug-in's web page once from its page in Settings, Plug-ins, so Jellyfin can be given its channels"
    elif sbplugin.last_error():
        note = f"Last refresh: {sbplugin.last_error()}"
    status = "running" if playing else "ok"
    label = f"{sbplugin.plural(len(playing), 'channel')} playing" if playing else "Nothing streaming"
    return sbplugin.band({"items": items[:12], "note": note[:160]}, "warning" if note else status, label=label, refresh=60)


# Broadcast packs ------------------------------------------------------------------------------------------------------
PACK_MODES = {"": "The station's pack", "own": "Its own pack", "none": "No pack"}


def pack_words(s, ch):
    mode = ch.get("pack") or ""
    if mode == "none":
        return "no pack"
    if mode == "own" and load_pack(f"ch-{ch['id']}"):
        return f"its own pack, {load_pack(f'ch-' + ch['id'])['name']}"
    sp = station_pack(s)
    return f"the station's pack, {sp['name']}" if sp else "the station's pack, none yet"


def install_pack(name, filename, length, rfile):
    """A pack zip from Starboard: saved, unpacked, checked, and put in place of the pack called `name`."""
    work = os.path.join(sbplugin.DATA, PACKS, ".work")
    os.makedirs(work, exist_ok=True)
    if length > pack.MAX_ZIP:
        raise ValueError("Choose a zip of up to 60 MB")
    zpath, base = save_upload(filename, length, rfile, work, (".zip",), most=pack.MAX_ZIP)
    try:
        got = pack.install_zip(zpath, pack_dir(name), work)
    except pack.PackError as e:
        sbplugin.keep("pack_check", {"at": int(time.time()), "file": base, "ok": False, "problems": str(e).split("; ")[:12], "notes": []})
        raise ValueError(f"{base} cannot be used: {e}"[:200]) from None
    finally:
        with contextlib.suppress(OSError):
            os.remove(zpath)
    _packs.pop(name, None)
    sbplugin.keep("pack_check", {"at": int(time.time()), "file": base, "ok": True, "problems": [], "notes": got["notes"]})
    return got


def make_example(use=True):
    """Makes the Example TV pack once, at the lowest priority, then uses it as the station's pack when asked."""
    with _lock:
        if _example["making"]:
            _example["use"] = _example["use"] or use
            return False
        if _streams.playing():  # it takes up to about 500 MB for a minute or so: never beside a channel playing
            _example.update({"error": "A channel is playing. Try the example pack again when nothing is", "making": False})
            return False
        _example.update({"making": True, "error": "", "use": use, "since": time.time()})

    def run():
        try:
            with sbplugin.working("the example pack being made"):
                import example_pack  # only when it is made, so it takes no memory at rest
                if not load_pack("example"):
                    tmp = pack_dir(".example-new")
                    example_pack.make(tmp)
                    got = pack.install_folder(tmp, tmp)
                    if not got["ok"]:
                        raise RuntimeError("; ".join(got["problems"][:3]))
                    shutil.rmtree(pack_dir("example"), ignore_errors=True)
                    os.replace(tmp, pack_dir("example"))
                    _packs.pop("example", None)
                if _example["use"]:
                    with _lock:
                        s = state()
                        if s.get("station_pack") and s["station_pack"] != "example":
                            s["pack_before_example"] = s["station_pack"]
                        s["station_pack"] = "example"
                        save(s)
        except Exception as e:  # noqa: BLE001 - shown on the page
            _example["error"] = f"{e}"[:200]
        finally:
            _example["making"] = False
    threading.Thread(target=run, name="example-pack", daemon=True).start()
    return True


def downloads_base(s):
    base = address()
    return f"{base}/t/{s['token']}/download" if base else ""


def pack_page(said=None):
    s = state()
    sp = station_pack(s)
    items = []
    using_example = s.get("station_pack") == "example"
    title = f"Station's pack: {sp['name']}" + (" (the example pack)" if using_example else "") if sp else "Station's pack: none yet"
    detail = (pack.summary(sp) + (f". Made {sp['made']}" if sp.get("made") else "") + ". Used by every channel without its own."
              if sp else "Upload a zip made from the template: every channel uses it unless it has its own, or none.")
    pic = logo_thumb(os.path.join(sp["folder"], sp["dog"]), f"The corner logo in {sp['name']}") if sp and sp.get("dog") else None
    items.append({"id": "station", "title": title[:120], "detail": detail[:200], "group": "The station's pack", **({"image": pic} if pic else {}),
                  "state": "ok" if sp else "unknown", "state_label": "In use" if sp else "None yet",
                  "actions": ["attach", "detach"] if sp and not using_example else ["attach"],
                  "attach": {"label": "Upload a pack", "field": "Pack", "detach_label": "Stop using the pack", "hint": "A zip of up to 60 MB, made from the template", "accept": ".zip"}})
    if _example["making"]:
        ex_state, ex_label, ex_detail = "unknown", "Being made", "Making the example pack at the lowest priority: about 2 minutes. Open this page again then."
    elif _example["error"]:
        ex_state, ex_label, ex_detail = "problem", "Not made", f"The example pack was not made: {_example['error']}"
    else:
        ex_state, ex_label = ("ok", "In use") if using_example else ("off", "Not in use")
        ex_detail = ("Example TV, made in code: a logo, the logo with music, 3 short title clips, a Coming up next card, a coming-up trailer with 2 background tracks "
                     "and 3 transitions. " + ("Turn off to go back to your own pack, or none." if using_example else
                                              "Turn on to use it for every channel without its own pack."))
    items.append({"id": "example", "title": "Try the example pack", "detail": ex_detail[:200], "group": "The station's pack",
                  "on": using_example, "actions": ["toggle"], "state": ex_state, "state_label": ex_label})
    chk = sbplugin.remember("pack_check", None) or {}
    if chk:
        lines = chk.get("problems") or chk.get("notes") or []
        head = (f"{chk.get('file')}: " + ("checked and in use" if chk.get("ok") else "not used")) if chk.get("file") else "The last check"
        items.append({"id": "check", "title": head[:120], "group": "The last pack checked", "state": "ok" if chk.get("ok") else "problem",
                      "state_label": "Passed" if chk.get("ok") else "Not used",
                      "detail": (f"{sbplugin.plural(len(lines), 'note')} follow" if lines else "Nothing to change")[:200]})
        for i, line in enumerate(lines[:12]):
            items.append({"id": f"check{i}", "title": line[:120], "detail": line[120:320], "group": "The last pack checked",
                          "state": "problem" if not chk.get("ok") else "warning", "state_label": "To change" if not chk.get("ok") else "Note"})
    base = downloads_base(s)
    pk = "?pack=" + (s.get("station_pack") or "") if sp else ""
    downloads = [("template", "The template: folders, pack.json, its schema and a README", "template.zip"),
                 ("coming-next", "Placement guide: Coming up next card", f"placement-coming-next.png{pk}"),
                 ("promo", "Placement guide: coming-up trailer", f"placement-promo.png{pk}"),
                 ("logo", "Placement guide: corner logo", "placement-logo.png")]
    if load_pack("example"):
        downloads.append(("example-zip", "The example pack, as a zip", "example-pack.zip"))
    for key, words, path in downloads:
        it = {"id": f"dl-{key}", "title": words, "group": "Downloads", "state": "ok", "state_label": "Ready"}
        if base:
            it["link"] = {"url": f"{base}/{path}", "label": f"Download {words[0].lower() + words[1:]}"}
            it["detail"] = ("Where the clip area, each text field and the title safe area go" + (", on your pack's own background"
                            if pk and key in ("coming-next", "promo") else "")) if key in ("coming-next", "promo") else (
                "Where the logo sits in each corner, and its size" if key == "logo" else
                "Unzip it, add your files with the same names, zip the folder and upload it" if key == "template" else
                "Unzip it to change it, then upload it as your own pack")
        else:
            it["detail"] = ("It does not know its address yet. Update Starboard in Settings, Updates (0.23.0 and later give it), "
                            "or open this plug-in's web page once from its page in Settings, Plug-ins.")
        items.append(it)
    if not load_pack("example") and base:
        items.append({"id": "dl-example-later", "title": "The example pack, as a zip", "group": "Downloads", "state": "unknown",
                      "state_label": "Not made yet", "detail": "Turn on Try the example pack first, and it is made."})
    names = {c["id"]: c["name"] for c in s["channels"]}
    for p in sorted(s.get("promos") or [], key=lambda x: x.get("airs") or 0):
        items.append({"id": f"promo-{p['id']}", "title": f"{p.get('title')}: {dog.day_time_words(p['airs'])}"[:120], "group": "Coming-up trailers kept",
                      "detail": f"On {names.get(p['cid'], 'a channel')}. Made {day_hm(p['made'])}. {round(p.get('dur') or 0)} seconds"[:200],
                      "state": "ok", "state_label": "Ready"})
    if not s.get("promos"):
        items.append({"id": "promo-none", "title": "No coming-up trailers yet", "group": "Coming-up trailers kept", "state": "unknown", "state_label": "None",
                      "detail": ("Coming-up trailers are made in quiet hours, for channels whose pack has a coming-up trailer background, while nobody is watching."
                                 if truthy(settings().get("promos"), True) else "Making coming-up trailers is off in the settings.")})
    for ch in numbered(s):
        items.append({"id": f"ch-{ch['id']}", "title": f"{ch['number']}  {ch['name']}: {pack_words(s, ch)}"[:120], "group": "Each channel's pack",
                      "detail": "Change it in Channels, on the channel's page, under Channel.", "state": "ok" if channel_pack(s, ch) else "off",
                      "state_label": "Uses a pack" if channel_pack(s, ch) else "No pack"})
    out = {"type": "list", "title": "Branding", "items": items,
           "intro": ("Your own branding for the channels: the corner logo, short title clips, the logo with music, Coming up next and coming-up trailer backgrounds, "
                     "music for the coming-up trailers, and transitions. Upload a zip made from the template, or try the example pack.")}
    _sub(out, "animation", "Animation", animation_page(), "anim~", "How the cards, title bars, corner logo, clock, label and waiting screen words come on and go off.")
    _explain(out, s, "pack")
    if said:
        out["said"] = said[:200]
    return out


def pack_post(body):
    action, rid = body.get("action"), str(body.get("id") or "")
    if rid.startswith("anim~"):  # the Animation sub menu (0.11.0): the same change as before, answered with this page
        return pack_page((animation_post({**body, "id": rid[5:]}) or {}).get("said"))
    if rid == "example" and action == "toggle":
        with _lock:
            s = state()
            if s.get("station_pack") == "example":
                s["station_pack"] = s.pop("pack_before_example", "") if load_pack(s.get("pack_before_example", "")) else ""
                s.pop("pack_before_example", None)
                save(s)
                return pack_page("The example pack is no longer in use" + (". The station's own pack is back" if s["station_pack"] else ""))
        if load_pack("example"):
            make_example(use=True)
            time.sleep(0.2)
            return pack_page("Every channel without a pack of its own now uses the example pack")
        if not make_example(use=True) and _example["error"]:
            return pack_page(_example["error"])
        return pack_page("Making the example pack at the lowest priority: about 2 minutes. It is used as soon as it is ready")
    if rid == "station" and action == "detach":
        with _lock:
            s = state()
            if s.get("station_pack") == "station":
                prev = pack_dir(".previous-station")
                shutil.rmtree(prev, ignore_errors=True)
                with contextlib.suppress(OSError):
                    os.replace(pack_dir("station"), prev)
                _packs.pop("station", None)
                s["station_pack"] = ""
                save(s)
        return pack_page("The station's pack is no longer in use. A copy is kept in the plug-in's folder until the next is removed")
    if action == "dismiss":
        if rid.startswith(explain.PREFIX):
            with _lock:
                s = state()
                explain.dismiss(s, rid)
                save(s)
        else:
            sbplugin.keep("pack_check", None)
        return pack_page()
    raise ValueError("That cannot be changed here")


def pack_file(name, item, length, rfile):
    if item != "station":
        raise ValueError("That row takes no file")
    got = install_pack("station", name, length, rfile)
    with _lock:
        s = state()
        s["station_pack"] = "station"
        s.pop("pack_before_example", None)
        save(s)
    note = f". {sbplugin.plural(len(got['notes']), 'note')} on this page" if got["notes"] else ""
    return pack_page(f"{got['pack']['name']} is the station's pack: {pack.summary(got['pack']).lower()}{note}")


def download(name, query):
    """The downloads on the pack's page: (bytes, type, file name)."""
    which = (query.get("pack") or [""])[0]
    pk = load_pack(which) if re.fullmatch(r"(station|example|ch-[0-9a-f]{8})", which or "") else None
    if name == "template.zip":
        return pack.template_zip(dog.FONT), "application/zip", "broadcast-pack-template.zip"
    if name in ("placement-coming-next.png", "placement-promo.png"):
        part = "coming_next" if "coming" in name else "promo"
        lay, bg = pack.DEFAULT_LAYOUT[part], None
        if pk and pk.get(part):
            lay = pk[part]
            bg = os.path.join(pk["folder"], lay["background"])
        return pack.placement_png(part, lay, dog.FONT, background=bg), "image/png", name
    if name == "placement-logo.png":
        return pack.placement_png("logo", {}, dog.FONT), "image/png", name
    if name == "example-pack.zip":
        ex = load_pack("example")
        if not ex:
            raise LookupError("The example pack is not made yet: turn on Try the example pack first")
        cached = os.path.join(sbplugin.DATA, PACKS, "example-pack.zip")
        if not os.path.isfile(cached) or os.path.getmtime(cached) < os.path.getmtime(os.path.join(ex["folder"], "checked.json")):
            with open(cached + ".part", "wb") as f:
                f.write(pack.zip_folder(ex["folder"], "Example-TV"))
            os.replace(cached + ".part", cached)
        with open(cached, "rb") as f:
            return f.read(), "application/zip", "example-tv-broadcast-pack.zip"
    raise LookupError("No such download")


# Promos ---------------------------------------------------------------------------------------------------------------
def someone_watching():
    """True while a channel plays, or anyone plays anything in Jellyfin: promos are never made then."""
    if _streams.playing():
        return True
    try:
        return any(x.get("NowPlayingItem") for x in jf("/Sessions?activeWithinSeconds=300") or [])
    except (urllib.error.URLError, OSError, ValueError, LookupError):
        return False


def promo_settings(cfg=None):
    cfg = cfg or settings()
    keep = max(1, min(6, int(cfg.get("promo_keep") or 3)))
    days = str(cfg.get("promo_replace_days") or "2")
    return keep, int(days) if days in ("1", "2", "3", "7") else 2


def promos_job(now=None, limit_seconds=40 * 60):
    """In quiet hours, from Starboard's quiet-hours job: old promos replaced, new ones made, one at a time."""
    cfg = settings()
    if not truthy(cfg.get("promos"), True):
        return {"said": "Making coming-up trailers is off"}
    if not _promo_lock.acquire(blocking=False):
        return {"said": "Coming-up trailers are being made already"}
    try:
        if someone_watching():
            return {"said": "Someone is watching, so coming-up trailers wait for the next quiet hour"}
        keep, days = promo_settings(cfg)
        now = time.time() if now is None else now
        s = state()
        chans = [{"id": ch["id"], "sched": sched_of(ch), "can": bool(promo_design(s, ch)) and ch.get("on", True),
                  "design": promo_design_key(s, ch, cfg)}
                 for ch in s["channels"]]
        remove, make = promo.plan(chans, s.get("promos") or [], keep, days, now)
        gone = {p["id"] for p in remove}
        for p in remove:
            with contextlib.suppress(OSError):
                os.remove(clip_path(f"promo:{p['id']}"))
        with _lock:
            s = state()
            s["promos"] = [p for p in s.get("promos") or [] if p["id"] not in gone]
            save(s)
        made, failed, began = 0, "", time.monotonic()
        W, H, _ = stream.SIZES.get(str(cfg.get("picture") or "720"), stream.SIZES["720"])
        c = jf_conf()
        os.makedirs(os.path.join(sbplugin.DATA, PROMOS), exist_ok=True)
        for job in make:
            if time.monotonic() - began > limit_seconds or sbplugin.holding() or someone_watching():
                break
            s = state()
            ch = find(s, job["cid"])
            pk = promo_design(s, ch) if ch else None
            if not pk:
                continue
            pid = promo.new_id()
            a = job["airing"]
            out = clip_path(f"promo:{pid}")
            texts = dog.Texts(os.path.join("/tmp", "tv-station", f"promo-{pid}"))
            seed = schedule.seed_of(ch["seed"], "promo", a["start"])
            how = dict(seed=seed, seconds=promo_seconds(cfg), level=promo.music_level(cfg.get("promo_music_level") or 20),
                       clips=int(cfg.get("promo_clips") or 0) or None,
                       background=promo.pick_background(backgrounds_for(s, ch, pk), schedule.seed_of(ch["seed"], "back", a["start"])),
                       station_logo=station_logo_for(s, pk, cfg))
            music = promo.pick_music(music_for(s, ch, pk), schedule.seed_of(ch["seed"], "music", a["start"]))
            sound = truthy(cfg.get("promo_sound"), True)
            lang = language(cfg)
            if lang != tv_words.DEFAULT:  # its title in the station's language, asked for now (0.6.0), within the hourly limit
                titles_kept().want([a["entry"]], lang, first=True)
                titles_kept().work(most=1, stop=sbplugin.holding)
                a = {**a, "entry": localiser(lang)(a["entry"])}
            how["lang"] = lang
            if promo_described(cfg):  # 0.7.0: the promo's words spoken; with no speech program the promo is made without
                length = max(promo.SHORTEST, min(promo.LONGEST, int(how["seconds"] or (pk.get("promo") or {}).get("seconds") or 15)))
                how["voice"] = speak.fitting(promo.spoken(a, ch["name"], lang), lang, texts.folder, promo.voice_room(length))
            argv, seconds = promo.command(pk, a, ch["name"], music, W, H, c.get("url", ""), c.get("api_key", ""), texts, out + ".part",
                                          clip_sound=sound, **how)
            ok, why = promo.run(argv)
            if not ok and sound and "watching" not in (why or ""):
                # A programme with no sound FFmpeg can read: made again with the music alone.
                argv, seconds = promo.command(pk, a, ch["name"], music, W, H, c.get("url", ""), c.get("api_key", ""), texts, out + ".part",
                                              clip_sound=False, **how)
                ok, why = promo.run(argv)
            shutil.rmtree(texts.folder, ignore_errors=True)
            if not ok:
                with contextlib.suppress(OSError):
                    os.remove(out + ".part")
                failed = why or "FFmpeg did not finish"
                if "watching" in failed:
                    break
                continue
            os.replace(out + ".part", out)
            e = a["entry"]
            with _lock:
                s = state()
                s["promos"] = (s.get("promos") or []) + [{"id": pid, "cid": job["cid"], "group": promo.group_of(e), "entry": e["id"],
                                                          "title": e.get("title") or "Programme", "airs": int(a["start"]), "made": int(time.time()),
                                                          "dur": seconds, "design": promo_design_key(s, ch, cfg)}]
                save(s)
            made += 1
        said = f"Made {sbplugin.plural(made, 'promo')}" + (f", removed {len(remove)}" if remove else "")
        if failed:
            said += f". One did not finish: {failed}"
        if made < len(make) and not failed:
            said += f". {len(make) - made} more in the next quiet hour"
        return {"said": said[:200]}
    finally:
        _promo_lock.release()


# The schedule grid ----------------------------------------------------------------------------------------------------
_grid_lock = threading.Lock()


def grid_target(cid):
    """What a change applies to: the suggestion being looked over, when there is one, else the saved grid."""
    draft = grid_doc(cid, "draft")
    return (draft, "draft") if draft is not None else (grid_doc(cid) or grid.empty(), "")


def grid_state(cid, said="", now=None):
    now = time.time() if now is None else now
    s = state()
    chans = numbered(s)
    if not chans:
        # Every field the grid page reads, so it says what to do in place of failing to draw (0.2.0).
        return {"channels": [], "cid": "", "monday": grid.week_start(now), "today": time.localtime(now).tm_wday, "days": list(grid.DAYS),
                "draft": False, "can_undo": False, "slots": [], "series": {},
                "said": "Add a channel first, in Starboard: Settings, Plug-ins, Create your own TV channel, Channels"}
    if not find(s, cid):
        cid = chans[0]["id"]
    doc, kind = grid_target(cid)
    monday = grid.week_start(now)
    out = {"channels": [{"id": c["id"], "name": c["name"], "number": c["number"]} for c in chans], "cid": cid, "monday": monday,
           "today": time.localtime(now).tm_wday, "days": list(grid.DAYS), "draft": kind == "draft",
           "can_undo": kind == "" and grid_doc(cid, "prev") is not None, "said": said, **grid.view(doc, monday),
           "suggest_from": find(s, cid).get("suggest_from") or "history",
           "suggest_hours": find(s, cid).get("suggest_hours") or suggest_defaults()}
    if kind == "draft":
        out["note"] = doc.get("note") or []
    return out


def note_played(cid, piece, seconds):
    """From a channel's stream: `seconds` of a programme piece were streamed to someone watching. (None, 0) as the
    stream stops, so the record is written then. Only kept in the plug-in's folder: nothing goes to Jellyfin."""
    if piece is None:
        record().flush(cid, force=True)
        return
    a = piece.get("airing") or {}
    e = a.get("entry") or {}
    if e.get("id") and a.get("content_end"):
        record().note(cid, e, a["start"], a["content_end"] - a["start"], seconds)


def seen_on(cid):
    """What a channel has played to someone watching, when it counts that as watched (its setting, Yes unless changed)."""
    ch = find(state(), cid) if cid else None
    return record().seen_ids(cid) if ch and ch.get("count_played", True) else set()


def unwatched_index(series_id, episodes, seen=None):
    """The position of the next episode not watched: the first, in the channel's order, that the first Jellyfin
    administrator has not played and that the channel has not played to someone watching (seen, from played.py)."""
    seen = seen or set()

    def first(watched):
        return next((i for i, e in enumerate(episodes) if not watched(e["id"])), 0)
    try:
        users = jf("/Users") or []
        admin = next((u for u in users if (u.get("Policy") or {}).get("IsAdministrator")), users[0] if users else None)
        if not admin:
            return first(seen.__contains__)
        got = jf(f"/Users/{admin['Id']}/Items?" + urllib.parse.urlencode({
            "ParentId": series_id, "IncludeItemTypes": "Episode", "Recursive": "true", "Filters": "IsUnplayed",
            "SortBy": "ParentIndexNumber,IndexNumber", "Limit": 2000})) or {}
        unplayed = {i.get("Id") for i in got.get("Items") or []}
        return first(lambda iid: iid not in unplayed or iid in seen)
    except (urllib.error.URLError, OSError, ValueError, LookupError):
        return first(seen.__contains__)


def grid_search(words):
    """Films and series in Jellyfin for the grid's search: [{"id", "kind", "name"}]."""
    out = []
    for kind in ("series", "film"):
        for iid, name in library.search(jf, kind, words)[:8]:
            out.append({"id": iid, "kind": kind, "name": name})
    return out[:16]


def _int(v, lo, hi, what):
    try:
        n = int(v)
    except (TypeError, ValueError):
        raise grid.GridError(f"Choose {what}") from None
    if not lo <= n <= hi:
        raise grid.GridError(f"Choose {what}")
    return n


def grid_op(body, now=None):
    """One change to a channel's grid, from the grid page. Every change is kept at once (a suggestion stays a draft
    until it is saved); the change before is kept for Undo."""
    now = time.time() if now is None else now
    cid = str(body.get("cid") or "")
    op = str(body.get("op") or "")
    with _grid_lock:
        s = state()
        ch = find(s, cid)
        if not ch:
            raise grid.GridError("That channel has gone")
        doc, kind = grid_target(cid)
        focus = str(body.get("slot") or "")
        if op == "add":
            day, start = _int(body.get("day"), 0, 6, "a day"), _int(body.get("start"), 0, grid.DAY - grid.STEP, "a time")
            item_kind, iid = str(body.get("kind") or ""), str(body.get("id") or "")
            if not library.ID.match(iid):
                raise grid.GridError("Choose a film or series from the search")
            if item_kind == "series":
                eps = library.lineup(jf, [{"kind": "series", "id": iid}])
                if not eps:
                    raise grid.GridError("Jellyfin has no episodes of that series to play")
                mode = str(body.get("start_mode") or "first")
                sm = {"mode": mode}
                if mode == "episode":
                    sm.update({"s": _int(body.get("s"), 0, 999, "a series number"), "e": _int(body.get("e"), 0, 9999, "an episode number")})
                elif mode == "unwatched":
                    sm["unwatched_index"] = unwatched_index(iid, eps, seen_on(cid))
                doc, focus, said = grid.add(doc, day, start, "series", {"id": iid, "name": eps[0]["title"]}, now, eps,
                                            start_mode=sm if iid not in doc["series"] else None)
            elif item_kind == "film":
                got = library.lineup(jf, [{"kind": "film", "id": iid}])
                if not got:
                    raise grid.GridError("Jellyfin cannot play that film")
                doc, focus, said = grid.add(doc, day, start, "film", got[0], now)
            else:
                raise grid.GridError("Choose a film or series from the search")
        elif op == "move":
            doc, said = grid.move(doc, focus, _int(body.get("day"), 0, 6, "a day"), _int(body.get("start"), 0, grid.DAY - grid.STEP, "a time"), now)
        elif op == "nudge":
            doc, said = grid.nudge(doc, focus, _int(body.get("minutes"), -grid.DAY, grid.DAY, "how far"), now)
        elif op == "remove":
            doc, said = grid.remove(doc, focus, now)
            focus = ""
        elif op == "copy_day":
            to = [int(d) for d in body.get("to") or [] if str(d).isdigit()]
            doc, said = grid.copy_day(doc, _int(body.get("from"), 0, 6, "a day to copy"), to, now)
            focus = ""
        elif op == "stripe":
            days = [int(d) for d in body.get("weekdays") or [] if str(d).isdigit()]
            doc, said = grid.stripe(doc, focus, days, _int(body.get("per_day"), 1, 6, "how many episodes a day"),
                                    bool(body.get("weekends")), now)
        elif op == "set_start":
            sid = str(body.get("series") or "")
            mode = str(body.get("mode") or "first")
            extra = {}
            if mode == "episode":
                extra = {"s": _int(body.get("s"), 0, 999, "a series number"), "e": _int(body.get("e"), 0, 9999, "an episode number")}
            elif mode == "unwatched":
                extra = {"unwatched_index": unwatched_index(sid, (doc["series"].get(sid) or {}).get("episodes") or [], seen_on(cid))}
            doc, said = grid.set_start(doc, sid, mode, now, **extra)
        elif op == "undo":
            prev = grid_doc(cid, "prev")
            if kind == "draft" or prev is None:
                raise grid.GridError("Nothing to undo")
            grid.store(grid_folder(), cid, prev)
            grid.drop(grid_folder(), cid, "prev")
            return grid_state(cid, "Undone: the grid is as it was before the last change", now)
        elif op == "suggest":
            import suggest  # only when asked
            source = str(body.get("from") or ch.get("suggest_from") or "history")
            if source not in suggest.SOURCES:
                raise grid.GridError("Choose what to make the schedule from")
            raw_hours = body.get("hours")
            try:
                hours = suggest.parse_hours(raw_hours) if raw_hours else None
            except ValueError as e:
                raise grid.GridError(str(e)) from None
            doc, notes = suggest_for(s, ch, now, source, hours)
            with _lock:  # the choice and the hours are remembered for the channel, for next time
                s2 = state()
                c2 = find(s2, cid)
                if c2:
                    c2["suggest_from"] = source
                    if hours:
                        c2["suggest_hours"] = {k: ([suggest.hm24(v[0]), suggest.hm24(v[1])] if v else None) for k, v in hours.items()}
                    save(s2)
            grid.store(grid_folder(), cid, doc, "draft")
            n = len(doc["slots"])
            return grid_state(cid, (f"Suggested {n} slot{'s' if n != 1 else ''} from {suggest.SOURCES[source]}. Change them, then save or discard the suggestion"
                                    if n else notes[-1]), now)
        elif op == "save_draft":
            if kind != "draft":
                raise grid.GridError("There is no suggestion to save")
            old = grid_doc(cid)
            if old is not None:
                grid.store(grid_folder(), cid, old, "prev")
            doc = {k: v for k, v in doc.items() if k not in ("suggested", "note")}
            grid.store(grid_folder(), cid, doc)
            grid.drop(grid_folder(), cid, "draft")
            later_jellyfin()
            return grid_state(cid, "Saved the suggestion: it is the grid now. Undo goes back to the grid before it", now)
        elif op == "discard_draft":
            grid.drop(grid_folder(), cid, "draft")
            return grid_state(cid, "Discarded the suggestion. The saved grid is as it was", now)
        else:
            raise grid.GridError("That is not something the grid does")
        if kind == "draft":
            grid.store(grid_folder(), cid, doc, "draft")
        else:
            old = grid_doc(cid)
            grid.store(grid_folder(), cid, old or grid.empty(), "prev")
            doc["saved"] = int(now)
            grid.store(grid_folder(), cid, doc)
            later_jellyfin()
    out = grid_state(cid, said, now)
    out["focus"] = focus
    return out


def suggest_defaults():
    """The hours a suggestion fills until the owner chooses others, as the page shows them."""
    import suggest  # only when asked
    return {k: [suggest.hm24(a), suggest.hm24(b)] for k, (a, b) in suggest.DEFAULT_HOURS.items()}


def suggest_for(s, ch, now, source="history", hours=None):
    """A proposed week for one channel (suggest.py), not saved, from watch history, everyone's watch history, or the
    whole library (All TV, All films, TV and Films)."""
    import suggest  # only when asked
    groups = {e.get("group") or e["id"] for era in ch.get("eras") or [] for e in era.get("lineup") or []} or None
    if groups is not None:
        groups |= {e["id"] for era in ch.get("eras") or [] for e in era.get("lineup") or [] if e.get("kind") == "Movie"}
    c = jf_conf()

    def jf_post(path, body):
        return sbplugin.fetch(c["url"].rstrip("/") + path, sbplugin.jellyfin_headers(c["api_key"]), data=body, method="POST")
    plays = suggest.history(jf, jf_post)
    cache = {}
    seen = seen_on(ch["id"])

    def series_info(sid):
        if sid not in cache:
            eps = library.lineup(jf, [{"kind": "series", "id": sid}])
            cache[sid] = {"id": sid, "name": eps[0]["title"], "episodes": eps, "unwatched": unwatched_index(sid, eps, seen)} if eps else None
        return cache[sid]

    def film_info(fid):
        got = library.lineup(jf, [{"kind": "film", "id": fid}])
        return got[0] if got else None
    pool = suggest.library_pool(jf, source) if source in ("tv", "films", "both") else None
    if source == "channel":  # the channel's own series and films, in its order (0.3.2)
        pool, seen_ids = [], set()
        for era in (ch.get("eras") or [])[-1:]:
            for e in era.get("lineup") or []:
                kind = "film" if e.get("kind") == "Movie" else "series"
                key = (kind, str(e["id"] if kind == "film" else (e.get("group") or e["id"])))
                title = (e.get("title") or "").strip().lower()
                if key not in seen_ids and not (kind == "film" and title and ("title", title) in seen_ids):
                    seen_ids.add(key)
                    if kind == "film":
                        seen_ids.add(("title", title))  # two copies of one film in Jellyfin are used once
                    pool.append((key[0], key[1], e.get("title") or ""))
        if ch.get("order") == "shuffle":  # a shuffled channel gets a shuffled week, the same each time for a day
            pool = schedule.shuffled(pool, schedule.seed_of(ch.get("seed", 0), "initial", int(now // 86400)))
    return suggest.propose(groups, plays, now, series_info, film_info, source=source, pool=pool, hours=hours)


def refresh_grid(cid):
    """Once a night with the line-up: each series on the grid has its new episodes, and carries on where it was."""
    doc = grid_doc(cid)
    if not doc or not doc["series"]:
        return
    now = time.time()
    changed = False
    for sid, item in doc["series"].items():
        try:
            eps = library.lineup(jf, [{"kind": "series", "id": sid}])
        except (urllib.error.URLError, OSError, ValueError, LookupError):
            continue
        if eps and [e["id"] for e in eps] != [e["id"] for e in item["episodes"]]:
            occ = grid.occurrences(doc, sid)
            due = item["episodes"][grid.episode_index(doc, sid, occ[0]["id"], grid.week_start(now))]["id"] if occ else None
            item["episodes"] = eps[:grid.MAX_EPISODES]
            item["first"] = next((i for i, e in enumerate(eps) if e["id"] == due), 0)
            item["anchor"] = grid.week_start(now)
            changed = True
    if changed:
        grid.store(grid_folder(), cid, doc)


def breaks_available(s, ch, cfg=None):
    """How many of each kind of thing a channel has to play in its breaks now, for the grids' page."""
    clips = clips_for(s, ch, channel_pack(s, ch), cfg)
    made = [c for c in clips["fillers"] if c.get("role") == "promo"]
    return {"bumper": len(clips["bumpers"]), "promo": len(clips["fillers"]), "adverts": len(clips["extras"]), "psa": len(clips["psa"]),
            "ident": len(clips["idents"]) or (1 if clips.get("sting") else 0), "other_promo": sum(1 for c in made if c.get("cid") != ch["id"]),
            "coming_promo": sum(1 for c in made if c.get("cid") == ch["id"]), "holding": 1 if clips.get("holding") else 0,
            "back_soon": 1 if clips.get("holding") else 0}


def breaks_shortest(s, ch, cfg=None):
    """The shortest clip of each kind a channel has, in seconds, for the grids' warnings (a kind with none is missing)."""
    clips = clips_for(s, ch, channel_pack(s, ch), cfg)
    made = [c for c in clips["fillers"] if c.get("role") == "promo"]
    pools = {"bumper": clips["bumpers"], "promo": clips["fillers"], "adverts": clips["extras"], "psa": clips["psa"],
             "ident": clips["idents"] or ([clips["sting"]] if clips.get("sting") else []),
             "other_promo": [c for c in made if c.get("cid") != ch["id"]], "coming_promo": [c for c in made if c.get("cid") == ch["id"]]}
    return {k: min(float(c["dur"]) for c in v) for k, v in pools.items() if v and all(float(c.get("dur") or 0) > 0 for c in v)}


def breaks_grid_view(ch, which, shortest=None):
    """One grid for the grids' page: its mode, its columns as shown, and what each holds."""
    saved = breakgrid.grid_of(ch, which)
    g = saved or breakgrid.view_of(ch, which)
    names = breakgrid.column_names(g)
    cols = []
    for i, name in enumerate(names):
        cols.append({"name": name, "length": breakgrid.length_of(g, i), "length_words": breakgrid.length_words(breakgrid.length_of(g, i)),
                     "warning": breakgrid.warning(g, i, shortest or {}),
                     "items": [{"kind": it["kind"], "name": breakgrid.KINDS[it["kind"]][0], "times": it["times"], "fit": bool(it.get("fit")),
                                "counts": breakgrid.KINDS[it["kind"]][1]} for it in g["columns"][i]]})
    kept = sum(len(c) for c in g["columns"][len(names):])
    return {"which": which, "name": breakgrid.GRID_WORDS[which], "saved": saved is not None, "mode": g["mode"], "count": g["count"],
            "columns": cols, "unused_items": kept, "fixed_count": g["mode"] in ("day", "time")}


def breaks_state(cid, said="", now=None):
    s = state()
    chans = numbered(s)
    if not chans:
        return {"channels": [], "cid": "", "grids": [], "kinds": breakgrid.kinds_words(), "modes": [],
                "said": "Add a channel first, in Starboard: Settings, Plug-ins, Create your own TV channel, Channels"}
    ch = find(s, cid) or chans[0]
    shortest = breaks_shortest(s, ch)
    return {"channels": [{"id": c["id"], "name": c["name"], "number": c["number"]} for c in chans], "cid": ch["id"],
            "grids": [breaks_grid_view(ch, w, shortest) for w in breakgrid.GRIDS], "lengths": [{"seconds": 0, "name": "Automatic"}] + [
                {"seconds": n, "name": breakgrid.length_words(n)} for n in breakgrid.LENGTHS], "kinds": breakgrid.kinds_words(), "available": breaks_available(s, ch),
            "modes": [{"mode": m, "name": breakgrid.MODE_WORDS[m], "help": breakgrid.MODE_HELP[m]} for m in breakgrid.MODES],
            "most_columns": breakgrid.MOST_COLUMNS, "said": said}


def breaks_op(body):
    """One change to a channel's break grid, from its page. Kept at once. reset: the channel goes back to the order it had
    before grids, and the page shows that order as its grid again."""
    cid, which = str(body.get("cid") or ""), str(body.get("grid") or "")
    op = body.get("op") if isinstance(body.get("op"), dict) else {}
    with _grid_lock:
        s = state()
        ch = find(s, cid)
        if not ch:
            raise breakgrid.GridError("That channel has gone")
        if which not in breakgrid.GRIDS:
            raise breakgrid.GridError("That grid is not known")
        if op.get("op") == "reset":
            (ch.get("break_grids") or {}).pop(which, None)
        else:
            ch.setdefault("break_grids", {})[which] = breakgrid.apply(breakgrid.view_of(ch, which), op)
        save(s)
    return breaks_state(cid)


def schedule_page(said=None):
    """Starboard's page for the grid: a link to each channel's grid, which opens on this plug-in's own web page."""
    s = state()
    base = address()
    items = []
    for ch in numbered(s):
        doc = ch.get("_grid") or grid.empty()
        n = len(doc["slots"])
        draft = grid_doc(ch["id"], "draft") is not None
        it = {"id": f"grid-{ch['id']}", "title": f"{ch['number']}  {ch['name']}"[:120], "group": "Each channel's grid",
              "state": "ok" if n else "unknown", "state_label": (f"{n} slot{'s' if n != 1 else ''}" if n else "Automatic only"),
              "detail": ("A suggestion is waiting to be saved or discarded. " if draft else "") +
                        ("Fixed slots, with the automatic line-up between them" if n else "Its automatic line-up only, until slots are added")}
        if base:
            it["link"] = {"url": f"{base}/t/{s['token']}/grid?channel={ch['id']}", "label": f"Open the schedule grid for {ch['name']}"}
        else:
            it["detail"] = ("It does not know its address yet. Update Starboard in Settings, Updates (0.23.0 and later give it), "
                            "or open this plug-in's web page once from its page in Settings, Plug-ins.")
        items.append(it)
    if not items:
        items.append({"id": "none", "title": "No channels yet", "group": "Each channel's grid", "state": "unknown", "state_label": "None",
                      "detail": "Add a channel in Channels first."})
    out = {"type": "list", "title": "What plays when", "items": items,
           "intro": ("Select Open the schedule grid under a channel: its week opens in a new tab, on this plug-in's own page, in a desktop "
                     "browser. Place films and series at set times by dragging or with buttons and the keyboard, copy a day, stripe a series "
                     "across weekdays, or suggest a week from watch history.")}
    g = guide_rows()
    _sub(out, "guide", "What is on in the next 24 hours", g, "guide~", g["intro"], group="Guide")
    if said:
        out["said"] = said[:200]
    return out


def grids_page(said=None):
    """Starboard's page for the break grids: a link to each channel's two grids, which open on this plug-in's own page."""
    s = state()
    base = address()
    items = []
    for ch in numbered(s):
        for which in breakgrid.GRIDS:
            saved = breakgrid.grid_of(ch, which)
            words = breakgrid.GRID_WORDS[which]
            it = {"id": f"grid-{ch['id']}-{which}", "title": words, "group": f"{ch['number']}  {ch['name']}"[:80],
                  "state": "ok" if saved else "unknown", "state_label": (breakgrid.MODE_WORDS[saved["mode"]] if saved else "Standard order"),
                  "detail": ("Your grid is in use." if saved else "It plays the order it has always had. Open the grid to change it.")}
            if base:
                it["link"] = {"url": f"{base}/t/{s['token']}/breaks?channel={ch['id']}&grid={which}", "label": f"Open the {GRID_LINK[which]} grid for {ch['name']}"}
            else:
                it["detail"] = NO_ADDRESS
            items.append(it)
    if not items:
        items.append({"id": "none", "title": "No channels yet", "group": "Each channel's grids", "state": "unknown", "state_label": "None",
                      "detail": "Add a channel in Channels first."})
    out = {"type": "list", "title": "Break layouts", "items": items,
           "intro": ("Two grids for each channel: In between programmes, what plays after a programme before the next one starts, and Breaks, "
                     "what plays in a break inside a programme. Choose Open the grid under a channel: it opens in a new tab. Choose how a break "
                     "picks its column (Random, Sequence, Day of week, or Morning, afternoon and evening), then drag items into the columns, "
                     "or use the buttons and the keyboard.")}
    if said:
        out["said"] = said[:200]
    return out


def files_page(said=None):
    """Starboard's page for the file lists: a link to the plug-in's own page, which opens in a new tab."""
    s, base = state(), address()
    item = {"id": "files", "title": "File lists", "group": "Files", "state": "ok", "state_label": "Ready",
            "detail": "Every short title clip, trailer clip, short video of your own and public message, to search, sort and filter, and to add to channels together."}
    if base:
        item["link"] = {"url": f"{base}/t/{s['token']}/files", "label": "Open the file lists"}
    else:
        item["detail"] = NO_ADDRESS
    out = {"type": "list", "title": "File lists", "items": [item],
           "intro": "One list for each kind of file you add, with a search, sorting, filters and a tick box on each file. Choose Open the file lists: it opens in a new tab."}
    if said:
        out["said"] = said[:200]
    return out


def styles_page(said=None):
    """Starboard's page for styles: a link to the plug-in's own page Choose a style for my channel, which opens in a new tab."""
    s, base = state(), address()
    item = {"id": "styles", "title": "Choose a style for my channel", "group": "Styles", "state": "ok", "state_label": "Ready",
            "detail": "Add the video and picture files you made in Canva, Figma or another tool, or a zip of them, and turn them into your channel's branding."}
    if base:
        item["link"] = {"url": f"{base}/t/{s['token']}/style", "label": "Choose a style for my channel"}
    else:
        item["detail"] = NO_ADDRESS
    out = {"type": "list", "title": "Styles", "items": [item],
           "intro": ("This page is for a computer screen. It is not made for phones. Choose Choose a style for my channel: it opens in a new tab. "
                     "Nothing is sent anywhere: the files are checked and the branding is made on your own server.")}
    if said:
        out["said"] = said[:200]
    return out


def file_sizes():
    """What each file in the plug-in's clips folder weighs and when it was added: {name: (bytes, seconds since 1970)}."""
    out = {}
    try:
        with os.scandir(os.path.join(sbplugin.DATA, CLIPS)) as it:
            for e in it:
                if e.is_file():
                    st = e.stat()
                    out[e.name] = (st.st_size, st.st_mtime)
    except OSError:
        pass
    return out


def files_state(query, said=""):
    """One page of the file lists for the page: the rows asked for and what it needs to draw its filters."""
    s = state()
    chans = numbered(s)
    names = {c["id"]: c["name"] for c in chans}
    cid = str(query.get("channel") or "")
    cid = cid if cid in names else (chans[0]["id"] if chans else "")

    def one(k, allowed, default):
        v = str(query.get(k) or default)
        return v if v in allowed else default
    try:
        page = int(query.get("page") or 1)
    except ValueError:
        page = 1
    got = filelist.query(filelist.rows(s, file_sizes()), str(query.get("q") or "")[:80], one("kind", filelist.KINDS, ""), cid,
                         one("scope", filelist.SCOPES, "all"), one("length", filelist.LENGTHS, "any"), one("sound", filelist.SOUNDS, "any"),
                         one("sort", filelist.SORTS, "name"), str(query.get("order") or "") == "desc", page)
    for r in got["rows"]:
        r["held_names"] = ["The station" if h == "station" else names.get(h, "A removed channel") for h in r["held"]]
        r["used_names"] = [names[u] for u in r["used_by"] if u in names]
    return {**got, "cid": cid, "channels": [{"id": c["id"], "name": c["name"], "number": c["number"]} for c in chans],
            "kinds": filelist.KINDS, "sorts": filelist.SORTS, "scopes": filelist.SCOPES, "lengths": filelist.LENGTHS, "sounds": filelist.SOUNDS, "said": said}


def files_op(body):
    """Several files added to, or taken off, one channel's own list (or the station's), in one change."""
    with _lock:
        s = state()
        where = str(body.get("to") or "")
        n = filelist.change(s, body.get("keys"), where, str(body.get("op") or ""))
        save(s)
    name = "the station" if where == "station" else (find(s, where) or {}).get("name", "the channel")
    verb = "Added to" if body.get("op") == "add" else "Removed from"
    return {"said": f"{verb} {name}: {sbplugin.plural(n, 'file')}. Files stay in the plug-in's folder", "changed": n}


# The web server -------------------------------------------------------------------------------------------------------
HOME = """<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{name}</title><style>body{{font:1.125rem/1.5 system-ui,sans-serif;margin:0;padding:24px 16px;background:#fff;color:#1a1a1a}}
@media (prefers-color-scheme:dark){{body{{background:#121417;color:#f2f2f2}}}}main{{max-width:40rem;margin:auto}}</style></head>
<body><main><h1>{name}</h1><p>{count}. They are in Jellyfin's Live TV, at the top of the channel list.</p>
<p>Change the channels in Starboard: Settings, Plug-ins, Create your own TV channel.</p>
<p>The schedule grid opens from there too, in <strong>Schedule grid</strong>: each channel has an
<strong>Open the schedule grid</strong> link, in a desktop browser.</p></main></body></html>"""


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

    def _can(self):
        _req.can = frozenset(w.strip() for w in (self.headers.get("X-Starboard-Can") or "").split(",") if w.strip())

    def do_GET(self):  # noqa: N802
        self._can()
        url = urllib.parse.urlparse(self.path)
        p = url.path
        try:
            if p == "/health":
                return self._json(200, {"ok": True, "ffmpeg": stream.has_ffmpeg()})
            if p == "/card":
                return self._json(200, card())
            if p in ("/channels", "/clips", "/guide", "/pack", "/schedule", "/animation", "/grids", "/files", "/styles"):
                if not self._keyed():
                    return self._json(403, {"error": "Only Starboard may open this"})
                return self._json(200, {"/channels": channels_page, "/clips": clips_page, "/guide": guide_page, "/pack": pack_page,
                                        "/schedule": schedule_page, "/animation": animation_page, "/grids": grids_page, "/files": files_page,
                                        "/styles": styles_page}[p]())
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
            cfg = settings()
            days = max(1, min(14, int(cfg.get("guide_days") or 7)))
            lang = language(cfg)
            xml = guide.xmltv(chans, base, station_name(cfg), days=days, lang=lang, localise=localiser(lang))
            ask_titles([], lang)  # programmes with no title in the language yet were put in the queue: asked for now
            # Kept for the pages (0.2.0): when Jellyfin last read it and how many programmes it held, so the owner can
            # tell it worked. About once a day, so the small file is rarely written.
            sbplugin.keep("guide_read", {"at": int(time.time()), "programmes": xml.count("<programme "), "days": days,
                                         "channels": sum(1 for c in chans if c.get("on", True))})
            if renamed():
                later_jellyfin()
            return self._bytes(200, xml.encode(), "application/xml; charset=utf-8")
        m = re.match(r"^logo/([0-9a-f]{8})\.png$", rest)
        if m:
            ch = find(s, m.group(1))
            path = ch and (logo_file(ch["id"], channel_pack(s, ch)) or made_logo(ch))
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
            kind = (query.get("kind") or [""])[0]
            kind = kind if kind in ("card", "ident", "sting", "promo", "holding") else "programme"
            return self._bytes(200, preview(m.group(1), kind), "image/png", "no-store")
        m = re.match(r"^animation/([0-9a-f]{8}|station)/([a-z]+)\.mp4$", rest)
        if m:
            return self._bytes(200, anim_preview(m.group(1), m.group(2)), "video/mp4", "no-store")
        m = re.match(r"^stream/([0-9a-f]{8})\.ts$", rest)
        if m:
            return self._stream(m.group(1))
        if rest == "grid" or rest.startswith("grid/"):
            return self._grid_get(rest, query)
        if rest == "breaks" or rest.startswith("breaks/"):
            return self._breaks_get(rest, query)
        if rest == "files" or rest.startswith("files/"):
            return self._files_get(rest, query)
        if rest == "style" or rest.startswith("style/"):
            return self._style_get(rest, query)
        m = re.match(r"^download/([a-z-]+\.(png|zip))$", rest)
        if m:
            data, kind, filename = download(m.group(1), query)
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
            return None
        return self._json(404, {"error": "Not found"})

    def _grid_get(self, rest, query):
        """The schedule grid's own page, its script, style and font, and the answers it reads."""
        static = {"grid": ("grid.html", "text/html; charset=utf-8"), "grid/grid.js": ("grid.js", "text/javascript; charset=utf-8"),
                  "grid/grid.css": ("grid.css", "text/css; charset=utf-8"),
                  "grid/tokens.css": ("ds-tokens.css", "text/css; charset=utf-8"),
                  "grid/font.woff2": ("atkinson-hyperlegible-next.woff2", "font/woff2")}
        if rest in static:
            name, kind = static[rest]
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), name), "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)
            return None
        one = {k: (v or [""])[0] for k, v in query.items()}
        if rest == "grid/api/state":
            return self._json(200, grid_state(one.get("channel", "")))
        if rest == "grid/api/search":
            return self._json(200, {"items": grid_search(one.get("q", "")[:80])})
        if rest == "grid/api/episodes":
            doc, _ = grid_target(one.get("channel", ""))
            eps = (doc["series"].get(one.get("series", "")) or {}).get("episodes") or []
            return self._json(200, {"items": [{"s": e.get("s"), "e": e.get("e"), "name": e.get("ep") or ""} for e in eps[:2000]]})
        return self._json(404, {"error": "Not found"})

    def _breaks_get(self, rest, query):
        """The break grids' own page (0.8.0), its script, style and font, and the answer it reads."""
        static = {"breaks": ("breaks.html", "text/html; charset=utf-8"), "breaks/breaks.js": ("breaks.js", "text/javascript; charset=utf-8"),
                  "breaks/breaks.css": ("breaks.css", "text/css; charset=utf-8"), "breaks/tokens.css": ("ds-tokens.css", "text/css; charset=utf-8"),
                  "breaks/font.woff2": ("atkinson-hyperlegible-next.woff2", "font/woff2")}
        if rest in static:
            name, kind = static[rest]
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), name), "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)
            return None
        if rest == "breaks/api/state":
            return self._json(200, breaks_state({k: v[0] for k, v in query.items() if v}.get("channel", "")))
        return self._json(404, {"error": "Not found"})

    def _files_get(self, rest, query):
        """The file lists' own page (0.9.0), its script, style and font, and the page of rows it asks for."""
        static = {"files": ("files.html", "text/html; charset=utf-8"), "files/files.js": ("files.js", "text/javascript; charset=utf-8"),
                  "files/files.css": ("files.css", "text/css; charset=utf-8"), "files/tokens.css": ("ds-tokens.css", "text/css; charset=utf-8"),
                  "files/font.woff2": ("atkinson-hyperlegible-next.woff2", "font/woff2")}
        if rest in static:
            name, kind = static[rest]
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), name), "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)
            return None
        if rest == "files/api/state":
            return self._json(200, files_state({k: v[0] for k, v in query.items() if v}))
        return self._json(404, {"error": "Not found"})

    def _style_get(self, rest, query):
        """The style page's own page (0.13.0), its script, styles and font, and the answer it reads."""
        static = {"style": ("style.html", "text/html; charset=utf-8"), "style/style.js": ("style.js", "text/javascript; charset=utf-8"),
                  "style/style.css": ("style.css", "text/css; charset=utf-8"), "style/tokens.css": ("ds-tokens.css", "text/css; charset=utf-8"),
                  "style/components.css": ("ds-components.css", "text/css; charset=utf-8"),
                  "style/font.woff2": ("atkinson-hyperlegible-next.woff2", "font/woff2")}
        if rest in static:
            name, kind = static[rest]
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), name), "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data: blob:; frame-ancestors 'none'; base-uri 'none'")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)
            return None
        one = {k: (v or [""])[0] for k, v in query.items()}
        if rest == "style/api/preview":
            try:
                return self._bytes(200, stylepage.preview(one), "image/png", "no-store")
            except ValueError as e:
                return self._json(409, {"error": str(e)})
        if rest == "style/api/state":
            try:
                return self._json(200, stylepage.overview(one.get("kit", "")))
            except ValueError:
                return self._json(200, stylepage.overview(""))
        return self._json(404, {"error": "Not found"})

    def _stream(self, cid):
        s = state()
        ch = find(s, cid)
        if not ch or not ch.get("on", True):
            return self._json(404, {"error": "No such channel"})
        cfg = settings()
        most = max(1, min(6, int(cfg.get("most_at_once") or 2)))
        grace = max(5, min(300, int(cfg.get("stop_after") or 30)))
        if _example["making"]:
            return self._json(503, {"error": "The example pack is being made, which takes a minute or two. Choose the channel again then"})
        promo.stop()  # a promo being made gives way at once: nothing is made while anyone watches
        draw.stop()  # and so does a style being made (0.13.0)
        breaks.stop()  # and so does a search for breaks inside programmes (0.4.0)
        three_d.stop()  # and a check for 3D films (0.5.5)
        try:
            hub = _streams.get(cid, plan_for(cid), most, grace, on_piece=lambda piece, secs: note_played(cid, piece, secs))
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
        self._can()
        url = urllib.parse.urlparse(self.path)
        p = url.path
        try:
            if p in ("/update/before", "/update/after"):
                body = self._body()
                if p == "/update/before":
                    _streams.stop_all()
                    return self._json(200, sbplugin.before_update(body))
                return self._json(200, sbplugin.after_update(body))
            if p in ("/channels", "/clips", "/guide", "/pack", "/animation", "/channels/file", "/clips/file", "/pack/file"):
                if not self._keyed():
                    return self._json(403, {"error": "Only Starboard may change this"})
                if p.endswith("/file"):
                    q = urllib.parse.parse_qs(url.query)
                    fn = {"/channels/file": channels_file, "/clips/file": clips_file, "/pack/file": pack_file}[p]
                    with sbplugin.working("a file being added"):
                        return self._json(200, fn((q.get("name") or [""])[0], (q.get("id") or [""])[0],
                                                  int(self.headers.get("Content-Length") or 0), self.rfile))
                body = self._body()
                return self._json(200, {"/channels": lambda: channels_post(body), "/clips": lambda: clips_post(body),
                                        "/pack": lambda: pack_post(body), "/animation": lambda: animation_post(body), "/guide": guide_page}[p]())
            if p == "/jobs/refresh":
                if sbplugin.holding():
                    return self._json(200, {"said": "Not started: the plug-in is about to be updated"})
                with sbplugin.working("refresh"):
                    return self._json(200, refresh_all())
            m = re.match(r"^/t/([A-Za-z0-9_-]+)/grid/api/op$", p)
            if m:
                if not secrets.compare_digest(m.group(1), state()["token"]):
                    return self._json(404, {"error": "Not found"})
                if (self.headers.get("Content-Type") or "").split(";")[0] != "application/json":
                    return self._json(415, {"error": "Send JSON"})
                return self._json(200, grid_op(self._body()))
            m = re.match(r"^/t/([A-Za-z0-9_-]+)/files/api/op$", p)
            if m:
                if not secrets.compare_digest(m.group(1), state()["token"]):
                    return self._json(404, {"error": "Not found"})
                if (self.headers.get("Content-Type") or "").split(";")[0] != "application/json":
                    return self._json(415, {"error": "Send JSON"})
                try:
                    return self._json(200, files_op(self._body()))
                except filelist.ListError as e:
                    return self._json(400, {"error": str(e)})
            m = re.match(r"^/t/([A-Za-z0-9_-]+)/style/api/(op|upload)$", p)
            if m:
                if not secrets.compare_digest(m.group(1), state()["token"]):
                    return self._json(404, {"error": "Not found"})
                if m.group(2) == "upload":
                    q = urllib.parse.parse_qs(url.query)
                    with sbplugin.working("a file being added"):
                        return self._json(200, stylepage.upload((q.get("kit") or [""])[0], (q.get("name") or [""])[0],
                                                                int(self.headers.get("Content-Length") or 0), self.rfile))
                if (self.headers.get("Content-Type") or "").split(";")[0] != "application/json":
                    return self._json(415, {"error": "Send JSON"})
                return self._json(200, stylepage.op(self._body()))
            m = re.match(r"^/t/([A-Za-z0-9_-]+)/breaks/api/op$", p)
            if m:
                if not secrets.compare_digest(m.group(1), state()["token"]):
                    return self._json(404, {"error": "Not found"})
                if (self.headers.get("Content-Type") or "").split(";")[0] != "application/json":
                    return self._json(415, {"error": "Send JSON"})
                try:
                    return self._json(200, breaks_op(self._body()))
                except breakgrid.GridError as e:
                    return self._json(400, {"error": str(e)})
            if p == "/schedule":
                if not self._keyed():
                    return self._json(403, {"error": "Only Starboard may change this"})
                return self._json(200, schedule_page())
            if p == "/jobs/promos":
                if sbplugin.holding():
                    return self._json(200, {"said": "Not started: the plug-in is about to be updated"})
                with sbplugin.working("promos"):
                    return self._json(200, promos_job())
            if p == "/jobs/three-d":
                if sbplugin.holding():
                    return self._json(200, {"said": "Not started: the plug-in is about to be updated"})
                with sbplugin.working("3D films"):
                    return self._json(200, three_d_job())
            if p == "/jobs/breaks":
                if sbplugin.holding():
                    return self._json(200, {"said": "Not started: the plug-in is about to be updated"})
                with sbplugin.working("breaks"):
                    return self._json(200, breaks_job())
            if p == "/actions/promos":
                threading.Thread(target=lambda: _safe(promos_job), daemon=True).start()
                return self._json(200, {"said": "Making coming-up trailers one at a time, at the lowest priority, unless someone is watching"})
            if p == "/actions/example":
                if load_pack("example") and state().get("station_pack") == "example":
                    return self._json(200, {"said": "The example pack is in use already"})
                make_example(use=True)
                return self._json(200, {"said": "The example pack is being made, and is used for every channel without a pack of its own"})
            if p == "/actions/refresh":
                threading.Thread(target=lambda: _safe(refresh_all), daemon=True).start()
                return self._json(200, {"said": "Reading every channel's programmes from Jellyfin again"})
            if p == "/actions/guide":
                def again():
                    note = connect_jellyfin()
                    if not note and address():
                        refresh_jellyfin_guide()
                threading.Thread(target=lambda: _safe(again), daemon=True).start()
                return self._json(200, {"said": "Jellyfin is reading the guide again. The Guide page says when it has, and how many programmes it read"})
            if p == "/actions/stop":
                n = _streams.stop_all()
                return self._json(200, {"said": f"Stopped {sbplugin.plural(n, 'channel')}" if n else "Nothing was streaming"})
            return self._json(404, {"error": "Not found"})
        except ValueError as e:
            return self._json(400, {"error": f"{e}"[:200]})
        except Exception as e:  # noqa: BLE001 - Starboard shows the sentence
            return self._json(502, {"error": f"{e}"[:200]})


stylepage.bind(state=lambda: state(), save=lambda s: save(s), lock=_lock, pack_dir=lambda n: pack_dir(n),
               drop_pack=lambda n: _packs.pop(n, None), playing=lambda: _streams.playing())


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
    print(f"Create your own TV channel {VERSION} listening on {port}", flush=True)

    class Server(ThreadingHTTPServer):
        daemon_threads = True
    Server(("0.0.0.0", port), Handler).serve_forever(poll_interval=60)  # inside its own container  # nosec B104


if __name__ == "__main__":
    main()
