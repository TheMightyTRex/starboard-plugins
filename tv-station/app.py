"""Create your own TV channel (id tv-station): your own TV channels in Jellyfin's Live TV, made from your films and
series, with idents, trailers, promos and Coming up next cards in the breaks, your own on-screen logo, and a broadcast
pack for the channels' own branding. Nothing streams until a channel is chosen.

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
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import dog
import grid
import guide
import library
import pack
import promo
import sbplugin
import schedule
import stream

VERSION = "0.1.0"
CLIPS = "clips"  # folder in /data for idents and clips the owner adds
LOGOS = "logos"
PACKS = "packs"  # broadcast packs: station, example, and ch-<channel> for a channel's own
PROMOS = "promos"
GRIDS = "grid"  # the schedule grid: <channel>.json, and .draft.json for a suggestion, .prev.json for Undo
NAME = "Create your own TV channel"
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
_promo_lock = threading.Lock()
_example = {"making": False, "error": "", "use": False}


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
        refresh_grid(ch["id"])
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


def truthy(v, default=True):
    if v in (None, ""):
        return default
    return v if isinstance(v, bool) else str(v).lower() in ("1", "true", "yes", "on")


def promo_clips(s, ch, cfg=None):
    """The promos a channel shows in its breaks: its own, and the other channels' unless that is deactivated."""
    cfg = cfg or settings()
    others = truthy(cfg.get("promo_other"), True)
    on = {c["id"]: c for c in s["channels"] if c.get("on", True)}
    out = []
    for p in s.get("promos") or []:
        if p.get("cid") not in on or (p["cid"] != ch["id"] and not others):
            continue
        out.append({"id": f"promo-{p['id']}", "src": f"promo:{p['id']}", "dur": float(p.get("dur") or 15), "title": f"Promo: {p.get('title')}",
                    "has_audio": True, "airs": float(p.get("airs") or 0), "role": "promo", "cid": p["cid"]})
    return out


def clips_for(s, ch, p=None, cfg=None):
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
    out = {"idents": idents, "fillers": fillers, "sting": None, "random_idents": False}
    if p:
        name = pack_name(p)
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


def logo_file(cid, p=None):
    """The on-screen logo: the channel's own picture, else its broadcast pack's logo/dog.png."""
    own = os.path.join(sbplugin.DATA, LOGOS, f"{cid}.png")
    if os.path.isfile(own):
        return own
    if p and p.get("dog"):
        path = os.path.join(p["folder"], p["dog"])
        return path if os.path.isfile(path) else None
    return None


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
        prog["trans_out_at"] = prog["end"]
        out[1]["trans_in_at"] = prog["end"]
        out[-1]["trans_out_at"] = out[-1]["end"]  # the start of the next programme
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
        opts = dog.resolve(cfg, ch)
        pk = channel_pack(s, ch)
        if piece is None:
            a, pieces = schedule.pieces_at(sched, now, clips_for(s, ch, pk, cfg), {"seed": ch["seed"], "cards": opts["cards"],
                                                                                  "ident_order": ch.get("ident_order", "in_order")})
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
        ctx = {"W": W, "H": H, "kbps": kbps, "opts": opts, "names": names, "logo": logo_file(cid, pk), "jf_url": c.get("url", ""),
               "jf_key": c.get("api_key", ""), "ts_offset": max(0.0, now - started) + 1.0, "texts": texts, "clip_path": clip_path,
               "colour": ch.get("colour"), "copy_ok": bool(cfg.get("copy_plain", True)), "still": still}
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
            raise LookupError({"ident": "No idents yet", "sting": "No logo with music in the pack", "promo": "No promos yet"}[kind])
        clip = pool[int(now) % len(pool)]
        seek = min(clip["dur"] * 0.55, clip["dur"] - 0.5)
        piece = {"kind": "clip", "clip": clip, "role": kind, "start": now - seek, "end": now - seek + clip["dur"], "airing": a}
    elif kind == "card":
        nxt = sched_of(ch).airing(a["end"]) or a
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
        sched = sched_of(ch)
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
        row("pack", "Broadcast pack", "Channel", choice=_choice("Broadcast pack", ch.get("pack") or "", PACK_MODES),
            detail=f"Now {pack_words(s, ch)}. A pack gives the on-screen logo, idents, transitions, the Coming up next card and promos.")
        own_pk = load_pack(f"ch-{cid}")
        row("pack-own", f"Its own pack: {own_pk['name']}" if own_pk else "Its own pack: none yet", "Channel",
            actions=["attach", "detach"] if own_pk else ["attach"], detail=pack.summary(own_pk) if own_pk else
            "For branding of its own: a zip made from the template, in Broadcast pack. Then choose Its own pack.",
            attach={"label": "Upload its own pack", "field": "Pack", "hint": "A zip of up to 60 MB, made from the template", "accept": ".zip"})
        row("logo", "Logo: " + ("your picture" if own_logo(cid) else "the pack's" if logo_file(cid, channel_pack(s, ch)) else
                                "made from its number and name"), "Channel",
            actions=["attach", "detach"] if own_logo(cid) else ["attach"],
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
    elif key == "pack" and v in PACK_MODES:
        ch["pack"] = v
        return f"{ch['name']} now uses {PACK_MODES[v].lower()}"
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
        return channels_page(f"{got['pack']['name']} is now {whose} own pack: {pack.summary(got['pack']).lower()}")
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
        for k, a in enumerate(sched_of(ch).airings(now, now + 86400, limit=100)):
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
    items.append({"id": "station", "title": title[:120], "detail": detail[:200], "group": "The station's pack",
                  "state": "ok" if sp else "unknown", "state_label": "In use" if sp else "None yet",
                  "actions": ["attach", "detach"] if sp and not using_example else ["attach"],
                  "attach": {"label": "Upload a pack", "field": "Pack", "hint": "A zip of up to 60 MB, made from the template", "accept": ".zip"}})
    if _example["making"]:
        ex_state, ex_label, ex_detail = "unknown", "Being made", "Making the example pack at the lowest priority: about 2 minutes. Open this page again then."
    elif _example["error"]:
        ex_state, ex_label, ex_detail = "problem", "Not made", f"The example pack was not made: {_example['error']}"
    else:
        ex_state, ex_label = ("ok", "In use") if using_example else ("off", "Not in use")
        ex_detail = ("Example TV, made in code: a logo, the logo with music, 3 idents, a Coming up next card, a promo with 2 music beds "
                     "and 3 transitions. " + ("Deactivate to go back to your own pack, or none." if using_example else
                                              "Activate to use it for every channel without its own pack."))
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
                 ("promo", "Placement guide: promo", f"placement-promo.png{pk}"),
                 ("logo", "Placement guide: on-screen logo", "placement-logo.png")]
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
            it["detail"] = "Open this plug-in's web page once from its page in Settings, Plug-ins, so it knows its address."
        items.append(it)
    if not load_pack("example") and base:
        items.append({"id": "dl-example-later", "title": "The example pack, as a zip", "group": "Downloads", "state": "unknown",
                      "state_label": "Not made yet", "detail": "Activate Try the example pack first, and it is made."})
    names = {c["id"]: c["name"] for c in s["channels"]}
    for p in sorted(s.get("promos") or [], key=lambda x: x.get("airs") or 0):
        items.append({"id": f"promo-{p['id']}", "title": f"{p.get('title')}: {dog.day_time_words(p['airs'])}"[:120], "group": "Promos kept",
                      "detail": f"On {names.get(p['cid'], 'a channel')}. Made {day_hm(p['made'])}. {round(p.get('dur') or 0)} seconds"[:200],
                      "state": "ok", "state_label": "Ready"})
    if not s.get("promos"):
        items.append({"id": "promo-none", "title": "No promos yet", "group": "Promos kept", "state": "unknown", "state_label": "None",
                      "detail": ("Promos are made in quiet hours, for channels whose pack has a promo background, while nobody is watching."
                                 if truthy(settings().get("promos"), True) else "Making promos is deactivated in the settings.")})
    for ch in numbered(s):
        items.append({"id": f"ch-{ch['id']}", "title": f"{ch['number']}  {ch['name']}: {pack_words(s, ch)}"[:120], "group": "Each channel's pack",
                      "detail": "Change it in Channels, on the channel's page, under Channel.", "state": "ok" if channel_pack(s, ch) else "off",
                      "state_label": "Uses a pack" if channel_pack(s, ch) else "No pack"})
    out = {"type": "list", "title": "Broadcast pack", "items": items,
           "intro": ("Your own branding for the channels: the on-screen logo, idents, the logo with music, Coming up next and promo backgrounds, "
                     "music for the promos, and transitions. Upload a zip made from the template, or try the example pack.")}
    if said:
        out["said"] = said[:200]
    return out


def pack_post(body):
    action, rid = body.get("action"), str(body.get("id") or "")
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
            raise LookupError("The example pack is not made yet: activate Try the example pack first")
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
        return {"said": "Making promos is deactivated"}
    if not _promo_lock.acquire(blocking=False):
        return {"said": "Promos are being made already"}
    try:
        if someone_watching():
            return {"said": "Someone is watching, so promos wait for the next quiet hour"}
        keep, days = promo_settings(cfg)
        now = time.time() if now is None else now
        s = state()
        chans = [{"id": ch["id"], "sched": sched_of(ch), "can": bool((channel_pack(s, ch) or {}).get("promo")) and ch.get("on", True)}
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
            pk = channel_pack(s, ch) if ch else None
            if not pk or not pk.get("promo"):
                continue
            pid = promo.new_id()
            a = job["airing"]
            out = clip_path(f"promo:{pid}")
            texts = dog.Texts(os.path.join("/tmp", "tv-station", f"promo-{pid}"))
            argv, seconds = promo.command(pk, a, ch["name"], promo.pick_music(pk, schedule.seed_of(ch["seed"], "music", a["start"])), W, H,
                                          c.get("url", ""), c.get("api_key", ""), texts, out + ".part")
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
                                                          "dur": seconds}]
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
        return {"channels": [], "cid": "", "said": "Add a channel first, in Settings, Plug-ins, Create your own TV channel, Channels"}
    if not find(s, cid):
        cid = chans[0]["id"]
    doc, kind = grid_target(cid)
    monday = grid.week_start(now)
    out = {"channels": [{"id": c["id"], "name": c["name"], "number": c["number"]} for c in chans], "cid": cid, "monday": monday,
           "today": time.localtime(now).tm_wday, "days": list(grid.DAYS), "draft": kind == "draft",
           "can_undo": kind == "" and grid_doc(cid, "prev") is not None, "said": said, **grid.view(doc, monday)}
    if kind == "draft":
        out["note"] = doc.get("note") or []
    return out


def unwatched_index(series_id, episodes):
    """The position of the next episode nobody has watched, from the first Jellyfin administrator's played list."""
    try:
        users = jf("/Users") or []
        admin = next((u for u in users if (u.get("Policy") or {}).get("IsAdministrator")), users[0] if users else None)
        if not admin:
            return 0
        got = jf(f"/Users/{admin['Id']}/Items?" + urllib.parse.urlencode({
            "ParentId": series_id, "IncludeItemTypes": "Episode", "Recursive": "true", "Filters": "IsUnplayed",
            "SortBy": "ParentIndexNumber,IndexNumber", "Limit": 1})) or {}
        first = (got.get("Items") or [{}])[0].get("Id")
        return next((i for i, e in enumerate(episodes) if e["id"] == first), 0)
    except (urllib.error.URLError, OSError, ValueError, LookupError):
        return 0


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
                    sm["unwatched_index"] = unwatched_index(iid, eps)
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
                extra = {"unwatched_index": unwatched_index(sid, (doc["series"].get(sid) or {}).get("episodes") or [])}
            doc, said = grid.set_start(doc, sid, mode, now, **extra)
        elif op == "undo":
            prev = grid_doc(cid, "prev")
            if kind == "draft" or prev is None:
                raise grid.GridError("Nothing to undo")
            grid.store(grid_folder(), cid, prev)
            grid.drop(grid_folder(), cid, "prev")
            return grid_state(cid, "Undone: the grid is as it was before the last change", now)
        elif op == "suggest":
            doc, notes = suggest_for(s, ch, now)
            grid.store(grid_folder(), cid, doc, "draft")
            n = len(doc["slots"])
            return grid_state(cid, (f"Suggested {n} slot{'s' if n != 1 else ''} from watch history. Change them, then save or discard the suggestion"
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


def suggest_for(s, ch, now):
    """A proposed week for one channel from watch history (suggest.py), not saved."""
    import suggest  # only when asked
    groups = {e.get("group") or e["id"] for era in ch.get("eras") or [] for e in era.get("lineup") or []} or None
    if groups is not None:
        groups |= {e["id"] for era in ch.get("eras") or [] for e in era.get("lineup") or [] if e.get("kind") == "Movie"}
    c = jf_conf()

    def jf_post(path, body):
        return sbplugin.fetch(c["url"].rstrip("/") + path, sbplugin.jellyfin_headers(c["api_key"]), data=body, method="POST")
    plays = suggest.history(jf, jf_post)
    cache = {}

    def series_info(sid):
        if sid not in cache:
            eps = library.lineup(jf, [{"kind": "series", "id": sid}])
            cache[sid] = {"id": sid, "name": eps[0]["title"], "episodes": eps, "unwatched": unwatched_index(sid, eps)} if eps else None
        return cache[sid]

    def film_info(fid):
        got = library.lineup(jf, [{"kind": "film", "id": fid}])
        return got[0] if got else None
    return suggest.propose(groups, plays, now, series_info, film_info)


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
            it["detail"] = "Open this plug-in's web page once from its page in Settings, Plug-ins, so it knows its address."
        items.append(it)
    if not items:
        items.append({"id": "none", "title": "No channels yet", "group": "Each channel's grid", "state": "unknown", "state_label": "None",
                      "detail": "Add a channel in Channels first."})
    out = {"type": "list", "title": "Schedule grid", "items": items,
           "intro": ("Place films and series at set times on a week's grid, by dragging or with buttons and the keyboard. Copy a day, "
                     "stripe a series across weekdays, or suggest a week from watch history. It opens in a new tab, in a desktop browser.")}
    if said:
        out["said"] = said[:200]
    return out


# The web server -------------------------------------------------------------------------------------------------------
HOME = """<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{name}</title><style>body{{font:1.125rem/1.5 system-ui,sans-serif;margin:0;padding:24px 16px;background:#fff;color:#1a1a1a}}
@media (prefers-color-scheme:dark){{body{{background:#121417;color:#f2f2f2}}}}main{{max-width:40rem;margin:auto}}</style></head>
<body><main><h1>{name}</h1><p>{count}. They are in Jellyfin's Live TV, at the top of the channel list.</p>
<p>Change the channels in Starboard: Settings, Plug-ins, Create your own TV channel.</p></main></body></html>"""


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
            if p in ("/channels", "/clips", "/guide", "/pack", "/schedule"):
                if not self._keyed():
                    return self._json(403, {"error": "Only Starboard may open this"})
                return self._json(200, {"/channels": channels_page, "/clips": clips_page, "/guide": guide_page, "/pack": pack_page,
                                        "/schedule": schedule_page}[p]())
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
            kind = kind if kind in ("card", "ident", "sting", "promo") else "programme"
            return self._bytes(200, preview(m.group(1), kind), "image/png", "no-store")
        m = re.match(r"^stream/([0-9a-f]{8})\.ts$", rest)
        if m:
            return self._stream(m.group(1))
        if rest == "grid" or rest.startswith("grid/"):
            return self._grid_get(rest, query)
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
            if p in ("/channels", "/clips", "/guide", "/pack", "/channels/file", "/clips/file", "/pack/file"):
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
                                        "/pack": lambda: pack_post(body), "/guide": guide_page}[p]())
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
            if p == "/schedule":
                if not self._keyed():
                    return self._json(403, {"error": "Only Starboard may change this"})
                return self._json(200, schedule_page())
            if p == "/jobs/promos":
                if sbplugin.holding():
                    return self._json(200, {"said": "Not started: the plug-in is about to be updated"})
                with sbplugin.working("promos"):
                    return self._json(200, promos_job())
            if p == "/actions/promos":
                threading.Thread(target=lambda: _safe(promos_job), daemon=True).start()
                return self._json(200, {"said": "Making promos one at a time, at the lowest priority, unless someone is watching"})
            if p == "/actions/example":
                if load_pack("example") and state().get("station_pack") == "example":
                    return self._json(200, {"said": "The example pack is in use already"})
                make_example(use=True)
                return self._json(200, {"said": "The example pack is being made, and is used for every channel without a pack of its own"})
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
    print(f"Create your own TV channel {VERSION} listening on {port}", flush=True)

    class Server(ThreadingHTTPServer):
        daemon_threads = True
    Server(("0.0.0.0", port), Handler).serve_forever(poll_interval=60)  # inside its own container  # nosec B104


if __name__ == "__main__":
    main()
