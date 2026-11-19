"""Broadcast packs: a channel's own branding, as a folder of files with a pack.json, uploaded as a zip.

    pack.json                           the pack's name and where each text goes (pack.schema.json)
    logo/dog.png                        the on-screen logo (DOG), a PNG with a transparent background
    logo/logo-with-music.mp4 or .mov    the logo with its music baked in, played as a sting in the breaks
    idents/identNN.mp4 (.mov .mkv .webm) as many as you like, numbered, played in a random order
    coming-next/background.mp4 (or .mov, .png, .jpg)  the Coming up next card, with a clip area and text fields
    promo/background.mp4 (or .mov, .png, .jpg)        the promo, with a clip area and text fields
    promo/music/*.m4a (.mp3 .wav .flac .ogg .opus)     music beds; each promo has one, chosen at random
    transitions/*.webm (VP9 with alpha) or *.mov (ProRes 4444)  wipes and stings between programme and break

A zip is checked before anything in it is used: its names, types, sizes and lengths, no path outside its folder, no
links, and a total size limit. Every media file is read with ffprobe, and the loudness of each sound is measured, so
it plays at -23 LUFS. Nothing in a pack is run; pictures and sounds are only ever decoded by FFmpeg.

The placement guides (where the clip and each text field go, and the safe areas) and the template are made here too,
with FFmpeg only, so the plug-in's image needs nothing more.
"""
import io
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import threading
import time
import zipfile

import dog

W, H, FPS = 1920, 1080, 25
TITLE_SAFE = (96, 54, 1824, 1026)  # 5% in from each edge (EBU R 95 graphics safe)
ACTION_SAFE = (67, 38, 1853, 1042)  # 3.5% in from each edge (EBU R 95 action safe)
LOUDNESS = -23.0  # LUFS, EBU R 128
MOST_GAIN = 12.0  # dB: a sound further from -23 LUFS than this is brought this far and no further
MAX_ZIP = 60 * 1024 * 1024  # Starboard's upload limit for a plug-in page
MAX_TOTAL = 400 * 1024 * 1024  # every file in the pack, unpacked
MAX_FILE = 100 * 1024 * 1024
MAX_FILES = 150
MAX_RATIO = 200  # a file packed smaller than 1/200 of its size is refused (a zip bomb)
HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA = os.path.join(HERE, "pack.schema.json")
FIELDS = ("Heading", "Title", "Episode", "Day and time", "Synopsis", "Channel name")
LINES = {"Title": 2, "Synopsis": 3}
VIDEO = r"(mp4|mov|mkv|webm)"
STILL_OR_VIDEO = r"(mp4|mov|png|jpg|jpeg)"
AUDIO = r"(m4a|mp3|wav|flac|ogg|opus)"
# Every file a pack may hold, and its role. Anything else is refused, so a misspelt name is found at once.
NAMES = [
    (r"pack\.json", "json"),
    (r"logo/dog\.png", "dog"),
    (r"logo/logo-with-music\.(mp4|mov)", "sting"),
    (r"idents/ident[0-9]{2,3}\." + VIDEO, "ident"),
    (r"coming-next/background\." + STILL_OR_VIDEO, "coming_next"),
    (r"promo/background\." + STILL_OR_VIDEO, "promo"),
    (r"promo/music/[A-Za-z0-9 _.-]{1,60}\." + AUDIO, "music"),
    (r"transitions/[A-Za-z0-9_-]{1,40}\.(webm|mov)", "transition"),
]
# Files a pack may carry for the people making it, which are never used.
IGNORED = [r"(README|readme|LICENCE|LICENSE)(\.(txt|md))?", r"pack\.schema\.json", r"([a-z-]+/)?placement\.png",
           r"([a-z-]+/){0,2}what-goes-here\.txt", r"examples/[^/]{1,80}"]
JUNK = re.compile(r"(^|/)(__MACOSX|\.DS_Store|Thumbs\.db|desktop\.ini|\._[^/]*)(/|$)")
# Lengths in seconds: (shortest, longest).
LENGTHS = {"sting": (1, 20), "ident": (2, 60), "coming_next": (2, 60), "promo": (2, 60), "music": (5, 300), "transition": (0.2, 5)}
MOST = {"ident": 99, "music": 20, "transition": 20}
DEFAULT_LAYOUT = {
    "coming_next": {"background": "coming-next/background.mp4", "clip": [980, 210, 1780, 660],
                    "fields": {"Heading": [140, 200, 940, 280], "Title": [140, 330, 940, 470], "Episode": [140, 500, 940, 560],
                               "Day and time": [140, 590, 940, 650], "Synopsis": [140, 680, 940, 840]}},
    "promo": {"background": "promo/background.mp4", "clip": [980, 210, 1780, 660], "music": ["promo/music/music01.m4a"], "seconds": 15,
              "fields": {"Heading": [140, 200, 940, 280], "Title": [140, 330, 940, 470], "Day and time": [140, 500, 940, 640],
                         "Channel name": [140, 680, 940, 740]}},
}
WORDS = {"Heading": "Coming up next, or Later on and the channel's name", "Title": "The programme's title",
         "Episode": "Series 2, episode 4: its name", "Day and time": "Sunday at 21:00, from the schedule",
         "Synopsis": "A short synopsis", "Channel name": "The channel's name"}


_TEXTS = [None]
_placing = threading.Lock()


def _tmp():
    d = os.path.join(tempfile.gettempdir(), "tv-station")
    os.makedirs(d, exist_ok=True)
    return d


class PackError(ValueError):
    pass


# pack.json against pack.schema.json -----------------------------------------------------------------------------
_TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}


def _schema():
    with open(SCHEMA, encoding="utf-8") as f:
        return json.load(f)


def validate(doc, schema=None):
    """The problems with pack.json, checked against pack.schema.json: a list of sentences, empty when it is right.
    Covers the parts of JSON Schema the schema uses, so no library is needed."""
    root = schema or _schema()
    out = []

    def where(path):
        return "pack.json" + "".join(f"[{p!r}]" if isinstance(p, int) else f", {p}" for p in path)

    def check(v, s, path):
        if "$ref" in s:
            ref = root
            for part in s["$ref"].lstrip("#/").split("/"):
                ref = ref[part]
            return check(v, ref, path)
        bad = []
        if "const" in s and v != s["const"]:
            bad.append(f"{where(path)} should be {json.dumps(s['const'])}")
        if "enum" in s and v not in s["enum"]:
            bad.append(f"{where(path)} should be one of {', '.join(map(str, s['enum']))}")
        t = s.get("type")
        if t:
            ok = (isinstance(v, int) and not isinstance(v, bool)) if t == "integer" else (
                isinstance(v, (int, float)) and not isinstance(v, bool)) if t == "number" else isinstance(v, _TYPES[t])
            if not ok:
                return bad + [f"{where(path)} should be {'a whole number' if t == 'integer' else 'a list' if t == 'array' else 'a ' + t}"]
        if isinstance(v, str):
            if len(v) < s.get("minLength", 0) or len(v) > s.get("maxLength", 10 ** 9):
                bad.append(f"{where(path)} should be {s.get('minLength', 0)} to {s.get('maxLength')} characters")
            if "pattern" in s and not re.search(s["pattern"], v):
                bad.append(f"{where(path)} is not a name a pack may use: {v[:60]}")
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            if v < s.get("minimum", -10 ** 12) or v > s.get("maximum", 10 ** 12):
                bad.append(f"{where(path)} should be from {s.get('minimum')} to {s.get('maximum')}")
        if isinstance(v, list):
            if len(v) < s.get("minItems", 0) or len(v) > s.get("maxItems", 10 ** 9):
                bad.append(f"{where(path)} should have {s.get('minItems', 0)} to {s.get('maxItems')} items")
            if "items" in s:
                for i, x in enumerate(v):
                    bad += check(x, s["items"], path + [i])
        if isinstance(v, dict):
            for k in s.get("required", []):
                if k not in v:
                    bad.append(f"{where(path)} needs {k}")
            if len(v) < s.get("minProperties", 0):
                bad.append(f"{where(path)} needs at least {s['minProperties']} entry")
            props = s.get("properties", {})
            for k, x in v.items():
                if "propertyNames" in s:
                    bad += [f"{where(path)}: {k} is not a field a pack may use" for _ in check(k, s["propertyNames"], path + [k])][:1]
                if k in props:
                    bad += check(x, props[k], path + [k])
                elif s.get("additionalProperties") is False:
                    bad.append(f"{where(path)}: {k} is not something a pack may set")
                elif isinstance(s.get("additionalProperties"), dict):
                    bad += check(x, s["additionalProperties"], path + [k])
        for sub in s.get("allOf", []):
            bad += check(v, sub, path)
        if "oneOf" in s:
            fits = [sub for sub in s["oneOf"] if not check(v, sub, path)]
            if len(fits) != 1:
                bad.append(f"{where(path)} should be [left, top, right, bottom], or an object with a box")
        return bad

    out += check(doc, root, [])
    # What a schema cannot say: each box inside the picture, left before right and top before bottom.
    for part in ("coming_next", "promo"):
        lay = doc.get(part) if isinstance(doc, dict) else None
        if not isinstance(lay, dict):
            continue
        boxes = [("clip", lay.get("clip"))] + [(k, f.get("box") if isinstance(f, dict) else f) for k, f in (lay.get("fields") or {}).items()]
        for name, r in boxes:
            if isinstance(r, list) and len(r) == 4 and all(isinstance(n, int) for n in r):
                if not (0 <= r[0] < r[2] <= W and 0 <= r[1] < r[3] <= H):
                    out.append(f"pack.json, {part}, {name}: the box should be inside 1920 by 1080, left before right and top before bottom")
                elif r[2] - r[0] < 40 or r[3] - r[1] < 20:
                    out.append(f"pack.json, {part}, {name}: the box is too small to hold words or a picture")
    return out


def rect_of(field):
    return list(field["box"] if isinstance(field, dict) else field)


def field_style(name, field, colours):
    """A field's box, colour, alignment and number of lines, with the defaults filled in."""
    f = field if isinstance(field, dict) else {"box": field}
    accent = colours.get("accent") or "#FFFFFF"
    return {"box": rect_of(f), "colour": f.get("colour") or (accent if name == "Day and time" else colours.get("text") or "#FFFFFF"),
            "align": f.get("align") or "left", "lines": int(f.get("lines") or LINES.get(name, 1))}


# Reading files with ffprobe and FFmpeg ---------------------------------------------------------------------------
def _nice():
    try:
        os.nice(19)
    except OSError:
        pass


def probe(path):
    """What ffprobe says of a file: {"video": {...} or None, "audio": bool, "duration": seconds, "format": name}."""
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration,format_name:stream=codec_type,codec_name,width,height,pix_fmt,r_frame_rate:stream_tags=alpha_mode",
                        "-of", "json", path], capture_output=True, timeout=60, check=False, preexec_fn=_nice)
    try:
        info = json.loads(r.stdout or b"{}")
    except ValueError:
        info = {}
    streams = info.get("streams") or []
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    fmt = info.get("format") or {}
    try:
        dur = float(fmt.get("duration") or 0)
    except ValueError:
        dur = 0.0
    if v:
        num, _, den = str(v.get("r_frame_rate") or "0/1").partition("/")
        try:
            v["fps"] = float(num) / float(den or 1)
        except (ValueError, ZeroDivisionError):
            v["fps"] = 0.0
        v["alpha_mode"] = str((v.get("tags") or {}).get("alpha_mode") or "")
    return {"video": v, "audio": any(s.get("codec_type") == "audio" for s in streams), "duration": dur,
            "format": str(fmt.get("format_name") or ""), "ok": r.returncode == 0}


def loudness(path):
    """The integrated loudness of a file's sound, in LUFS (EBU R 128), or None with no sound to measure."""
    r = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-nostats", "-i", path, "-vn", "-af", "ebur128=framelog=quiet",
                        "-f", "null", "-"], capture_output=True, timeout=180, check=False, preexec_fn=_nice)
    m = re.findall(r"I:\s+(-?[\d.]+|-inf) LUFS", r.stderr.decode("utf-8", "replace"))
    if not m or m[-1] == "-inf":
        return None
    return float(m[-1])


def gain_for(lufs):
    if lufs is None:
        return 0.0
    return round(max(-MOST_GAIN, min(MOST_GAIN, LOUDNESS - lufs)), 1)


def has_transparency(path):
    """Whether a picture has clear parts: read small, as RGBA, and any pixel less than solid."""
    r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", path, "-vf", "scale=96:-1,format=rgba", "-frames:v", "1",
                        "-f", "rawvideo", "-"], capture_output=True, timeout=30, check=False, preexec_fn=_nice)
    data = r.stdout
    return bool(data) and min(data[3::4]) < 250


def alpha_video(info):
    """Whether a transition carries transparency: VP9 with its alpha channel, or ProRes 4444 with alpha."""
    v = info.get("video") or {}
    if v.get("codec_name") == "vp9":
        return v.get("alpha_mode") == "1"
    if v.get("codec_name") == "prores":
        return str(v.get("pix_fmt") or "").startswith("yuva")
    return False


# Unpacking a zip -------------------------------------------------------------------------------------------------
def role_of(name):
    for pat, role in NAMES:
        if re.fullmatch(pat, name):
            return role
    if any(re.fullmatch(p, name) for p in IGNORED):
        return "ignored"
    return None


def _safe_name(raw):
    """A member's name as a path inside the pack, or a reason it may not be one."""
    if "\\" in raw or "\x00" in raw:
        return None, "a name with a backslash"
    if raw.startswith("/") or re.match(r"^[A-Za-z]:", raw):
        return None, "a path from the top of a disk"
    parts = [p for p in raw.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        return None, "a path outside the pack's folder"
    return "/".join(parts), None


def unpack(zip_path, dest):
    """Unpacks a broadcast pack zip into dest (which must not exist yet), after checking every name and size. A zip
    with its files in one folder (such as Example-TV/pack.json) is unpacked from inside that folder. Raises PackError
    with every problem found."""
    if not zipfile.is_zipfile(zip_path):
        raise PackError("That file is not a zip. Choose the zip of the pack's folder")
    if os.path.getsize(zip_path) > MAX_ZIP:
        raise PackError("The zip is over 60 MB, the most Starboard takes")
    problems = []
    with zipfile.ZipFile(zip_path) as z:
        members = []
        for info in z.infolist():
            if info.is_dir() or JUNK.search(info.filename):
                continue
            name, why = _safe_name(info.filename)
            if why:
                problems.append(f"{info.filename[:80]}: {why}")
                continue
            if stat.S_ISLNK(info.external_attr >> 16):
                problems.append(f"{name}: a link, which a pack may not hold")
                continue
            if info.flag_bits & 0x1:
                problems.append(f"{name}: has a password")
                continue
            members.append((name, info))
        if len(members) > MAX_FILES:
            raise PackError(f"The zip has {len(members)} files, more than the {MAX_FILES} a pack may hold")
        names = [n for n, _ in members]
        top = {n.split("/", 1)[0] for n in names}
        strip = ""
        if "pack.json" not in names and len(top) == 1 and all("/" in n for n in names):
            strip = top.pop() + "/"
        total = 0
        plan = []
        for name, info in members:
            rel = name[len(strip):] if strip else name
            role = role_of(rel)
            if role is None:
                problems.append(f"{rel[:80]}: not a name a pack uses. The template's README lists every name")
                continue
            if role == "ignored":
                continue
            if info.file_size > MAX_FILE:
                problems.append(f"{rel}: over {MAX_FILE // (1024 * 1024)} MB")
            if info.file_size > 1024 * 1024 and info.file_size / max(1, info.compress_size) > MAX_RATIO:
                problems.append(f"{rel}: packed far smaller than it is, which a real picture or sound never is")
            total += info.file_size
            plan.append((rel, info))
        if total > MAX_TOTAL:
            problems.append(f"The files come to {total // (1024 * 1024)} MB unpacked, more than the {MAX_TOTAL // (1024 * 1024)} MB a pack may be")
        if not any(rel == "pack.json" for rel, _ in plan):
            problems.append("pack.json is missing from the top of the pack")
        if problems:
            raise PackError("; ".join(problems[:6]) + (f"; and {len(problems) - 6} more" if len(problems) > 6 else ""))
        os.makedirs(dest)
        real = os.path.realpath(dest)
        for rel, info in plan:
            out = os.path.realpath(os.path.join(dest, rel))
            if not out.startswith(real + os.sep):
                raise PackError(f"{rel}: a path outside the pack's folder")
            os.makedirs(os.path.dirname(out), exist_ok=True)
            left = info.file_size
            with z.open(info) as src, open(out, "wb") as f:
                while True:
                    chunk = src.read(1 << 20)
                    if not chunk:
                        break
                    left -= len(chunk)
                    if left < 0:  # more than the zip said: never trusted
                        raise PackError(f"{rel}: bigger than the zip says")
                    f.write(chunk)


# Checking a pack's folder ----------------------------------------------------------------------------------------
def files_in(folder):
    out = {}
    for base, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            rel = os.path.relpath(os.path.join(base, f), folder).replace(os.sep, "/")
            if os.path.islink(os.path.join(base, f)) or rel == "checked.json":
                continue
            role = role_of(rel)
            if role and role != "ignored":
                out[rel] = role
    return out


def _size_notes(rel, v, problems, notes):
    w, h = int(v.get("width") or 0), int(v.get("height") or 0)
    if w < 320 or h < 180 or w > 3840 or h > 2160:
        problems.append(f"{rel}: {w} by {h} pixels. Make it 1920 by 1080")
        return
    if (w, h) != (W, H):
        if abs(w / h - W / H) > 0.01:
            notes.append(f"{rel}: {w} by {h}, not 16:9, so it is fitted inside the picture with black bars")
        else:
            notes.append(f"{rel}: {w} by {h}, so it is scaled to the picture")
    fps = float(v.get("fps") or 0)
    if v.get("codec_name") not in ("png", "mjpeg") and fps and abs(fps - FPS) > 0.05:
        notes.append(f"{rel}: {fps:g} frames a second, so it is played at 25")


def check(folder):
    """Checks an unpacked pack. Returns {"ok", "problems", "notes", "pack"}; "pack" is what the stream uses, kept as
    checked.json in the folder when the pack is good."""
    problems, notes = [], []
    try:
        with open(os.path.join(folder, "pack.json"), encoding="utf-8") as f:
            raw = f.read(65537)
        doc = json.loads(raw) if len(raw) <= 65536 else None
        if doc is None:
            problems.append("pack.json is over 64 KB")
            doc = {}
    except FileNotFoundError:
        doc = {}
        problems.append("pack.json is missing from the top of the pack")
    except (OSError, ValueError) as e:
        doc = {}
        problems.append(f"pack.json is not JSON: {str(e)[:100]}")
    if doc:
        problems += validate(doc)
    have = files_in(folder)
    by_role = {}
    for rel, role in sorted(have.items()):
        by_role.setdefault(role, []).append(rel)
    for role, most in MOST.items():
        if len(by_role.get(role, [])) > most:
            problems.append(f"{len(by_role[role])} files in {role}s, more than the {most} a pack may have")
    if "dog" not in by_role:
        problems.append("logo/dog.png is missing: every pack has the on-screen logo")
    out = {"name": str(doc.get("name") or "Broadcast pack")[:40], "made": str(doc.get("made") or "")[:40],
           "colours": doc.get("colours") or {}, "dog": None, "sting": None, "idents": [], "coming_next": None, "promo": None,
           "music": [], "transitions": [], "checked": int(time.time())}
    # Listed in pack.json but not in the folder: a name changed on one and not the other.
    listed = [f"idents/{n}" for n in doc.get("idents") or [] if isinstance(n, str)]
    listed += [f"transitions/{n}" for n in doc.get("transitions") or [] if isinstance(n, str)]
    listed += [n for n in ((doc.get("logo") or {}).get("dog"), (doc.get("logo") or {}).get("with_music")) if isinstance(n, str)]
    listed += [n for n in (doc.get("promo") or {}).get("music") or [] if isinstance(n, str)]
    for part in ("coming_next", "promo"):
        b = (doc.get(part) or {}).get("background")
        if isinstance(b, str):
            listed.append(b)
    for n in listed:
        if n not in have:
            problems.append(f"pack.json names {n[:80]}, which is not in the pack")

    def media(rel, role):
        info = probe(os.path.join(folder, rel))
        lo, hi = LENGTHS.get(role, (0, 10 ** 6))
        v = info["video"]
        if not info["ok"] or (role != "music" and not v):
            problems.append(f"{rel}: FFmpeg cannot read a picture in it")
            return None
        if role == "music":
            if not info["audio"]:
                problems.append(f"{rel}: has no sound")
                return None
        elif v.get("codec_name") not in ("png", "mjpeg") and not lo <= info["duration"] <= hi:
            problems.append(f"{rel}: {info['duration']:.1f} seconds. It should be {lo:g} to {hi:g} seconds")
            return None
        if v:
            _size_notes(rel, v, problems, notes)
        item = {"path": rel, "dur": round(info["duration"], 2), "has_audio": info["audio"], "gain": 0.0,
                "still": bool(v) and v.get("codec_name") in ("png", "mjpeg"), "codec": (v or {}).get("codec_name", "")}
        if info["audio"] and role in ("sting", "ident", "music"):
            lufs = loudness(os.path.join(folder, rel))
            item["lufs"] = lufs
            item["gain"] = gain_for(lufs)
            if lufs is not None and abs(lufs - LOUDNESS) > 2:
                notes.append(f"{rel}: {lufs:.0f} LUFS, so it is played {abs(item['gain']):g} dB {'louder' if item['gain'] > 0 else 'quieter'}"
                             " to match -23 LUFS")
        return item

    for rel in by_role.get("dog", []):
        info = probe(os.path.join(folder, rel))
        v = info["video"] or {}
        if v.get("codec_name") != "png":
            problems.append(f"{rel}: not a PNG")
        elif int(v.get("height") or 0) < 64 or int(v.get("width") or 0) > W or int(v.get("height") or 0) > H:
            problems.append(f"{rel}: {v.get('width')} by {v.get('height')} pixels. Make it at least 64 pixels tall and at most 1920 by 1080")
        elif not has_transparency(os.path.join(folder, rel)):
            problems.append(f"{rel}: has no transparent parts. Save it with a transparent background")
        else:
            out["dog"] = rel
    for rel in by_role.get("sting", []):
        item = media(rel, "sting")
        if item and not item["has_audio"]:
            problems.append(f"{rel}: has no sound. The logo's music is baked into this file")
        elif item:
            out["sting"] = item
    for rel in by_role.get("ident", []):
        item = media(rel, "ident")
        if item and item["still"]:
            problems.append(f"{rel}: a still picture. An ident is a video")
        elif item:
            out["idents"].append(item)
    for rel in by_role.get("music", []):
        item = media(rel, "music")
        if item:
            out["music"].append(item)
    for rel in by_role.get("transition", []):
        info = probe(os.path.join(folder, rel))
        lo, hi = LENGTHS["transition"]
        if not info["video"]:
            problems.append(f"{rel}: FFmpeg cannot read a picture in it")
        elif not alpha_video(info):
            problems.append(f"{rel}: has no transparency. Save it as WebM VP9 with alpha, or ProRes 4444 with alpha")
        elif not lo <= info["duration"] <= hi:
            problems.append(f"{rel}: {info['duration']:.1f} seconds. A transition is {lo:g} to {hi:g} seconds")
        else:
            _size_notes(rel, info["video"], problems, notes)
            out["transitions"].append({"path": rel, "dur": round(info["duration"], 2), "codec": info["video"]["codec_name"]})
    colours = doc.get("colours") or {}
    for part in ("coming_next", "promo"):
        bgs = by_role.get(part, [])
        lay = doc.get(part)
        if bgs and not isinstance(lay, dict):
            problems.append(f"{bgs[0]} is in the pack, but pack.json has no {part} part saying where the clip and the words go")
            continue
        if isinstance(lay, dict) and lay.get("background") not in bgs:
            continue  # reported as missing
        if not bgs:
            continue
        item = media(lay["background"], part)
        if not item:
            continue
        fields = {k: field_style(k, f, colours) for k, f in (lay.get("fields") or {}).items() if k in FIELDS}
        out[part] = {"background": item["path"], "still": item["still"], "dur": item["dur"], "clip": list(lay.get("clip") or [0, 0, W, H]),
                     "fields": fields}
        if part == "promo":
            out[part]["seconds"] = int(lay.get("seconds") or 15)
            if not out["music"]:
                notes.append("promo/music has no music, so promos have none")
        if "Title" not in fields:
            notes.append(f"pack.json, {part}: no Title field, so the programme's title is not drawn")
    for part in ("coming_next", "promo"):
        clip = (out.get(part) or {}).get("clip")
        if clip and (clip[0] < TITLE_SAFE[0] or clip[1] < TITLE_SAFE[1] or clip[2] > TITLE_SAFE[2] or clip[3] > TITLE_SAFE[3]):
            notes.append(f"pack.json, {part}: the clip area goes outside the title safe area, so some televisions cut its edge")
        for k, f in ((out.get(part) or {}).get("fields") or {}).items():
            b = f["box"]
            if b[0] < TITLE_SAFE[0] or b[1] < TITLE_SAFE[1] or b[2] > TITLE_SAFE[2] or b[3] > TITLE_SAFE[3]:
                notes.append(f"pack.json, {part}, {k}: outside the title safe area, so some televisions cut it")
    return {"ok": not problems, "problems": problems, "notes": notes[:20], "pack": out}


def install_zip(zip_path, folder, work):
    """Unpacks and checks a zip, then puts it in place of the pack in `folder`. The pack there is kept until the new
    one has passed. Returns the check's answer; raises PackError when the zip cannot be used."""
    stage = os.path.join(work, f"stage-{os.getpid()}-{int(time.time() * 1000)}")
    shutil.rmtree(stage, ignore_errors=True)
    try:
        unpack(zip_path, stage)
        got = check(stage)
        if not got["ok"]:
            raise PackError("; ".join(got["problems"][:6]) + (f"; and {len(got['problems']) - 6} more" if len(got["problems"]) > 6 else ""))
        with open(os.path.join(stage, "checked.json"), "w", encoding="utf-8") as f:
            json.dump({**got["pack"], "notes": got["notes"]}, f)
        old = folder + ".old"
        shutil.rmtree(old, ignore_errors=True)
        if os.path.isdir(folder):
            os.replace(folder, old)
        os.replace(stage, folder)
        shutil.rmtree(old, ignore_errors=True)
        return got
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def install_folder(src, folder):
    """Checks a pack made here (the example) and keeps its answer beside it."""
    got = check(src)
    if got["ok"]:
        with open(os.path.join(src, "checked.json"), "w", encoding="utf-8") as f:
            json.dump({**got["pack"], "notes": got["notes"]}, f)
        if os.path.realpath(src) != os.path.realpath(folder):
            shutil.rmtree(folder, ignore_errors=True)
            shutil.copytree(src, folder)
    return got


def load(folder):
    """The checked pack in a folder, as the stream uses it, with its folder; None when there is none."""
    try:
        with open(os.path.join(folder, "checked.json"), encoding="utf-8") as f:
            p = json.load(f)
    except (OSError, ValueError):
        return None
    p["folder"] = folder
    return p


def summary(p):
    """What a pack holds, in words."""
    if not p:
        return "No pack"
    bits = ["the on-screen logo" if p.get("dog") else "",
            "the logo with music" if p.get("sting") else "",
            f"{len(p['idents'])} ident{'s' if len(p['idents']) != 1 else ''}" if p.get("idents") else "",
            "a Coming up next card" if p.get("coming_next") else "",
            ("a promo" + (f" with {len(p['music'])} music bed{'s' if len(p['music']) != 1 else ''}" if p.get("music") else "")) if p.get("promo") else "",
            f"{len(p['transitions'])} transition{'s' if len(p['transitions']) != 1 else ''}" if p.get("transitions") else ""]
    bits = [b for b in bits if b]
    words = ", ".join(bits[:-1]) + " and " + bits[-1] if len(bits) > 1 else bits[0] if bits else "nothing"
    return words[0].upper() + words[1:]


# Placement guides and the template --------------------------------------------------------------------------------
def _ff_text(font, words, size, x, y, colour="white", box=None):
    parts = [f"fontfile={font}", f"textfile={_TEXTS[0].file(words)}", "expansion=none", f"fontsize={int(size)}", f"fontcolor={colour}", f"x={x}", f"y={y}"]
    if box:
        parts += ["box=1", f"boxcolor={box}", f"boxborderw={max(4, int(size / 4))}"]
    return "drawtext=" + ":".join(parts)


def _rect_filters(font, r, label, colour, thick=6, size=30):
    x0, y0, x1, y1 = r
    return [f"drawbox=x={x0}:y={y0}:w={x1 - x0}:h={y1 - y0}:color={colour}@0.22:t=fill",
            f"drawbox=x={x0}:y={y0}:w={x1 - x0}:h={y1 - y0}:color={colour}:t={thick}",
            _ff_text(font, label, size, x0 + 12, y0 + 12, "black", box=colour)]


def placement_filters(which, layout, font, dog_box=None):
    """FFmpeg filters that draw a placement guide on a 1920 by 1080 picture: the safe areas, the clip area and each
    text field with its name, its size and its place, or, for the on-screen logo, where it sits in each corner."""
    out = [f"drawbox=x={ACTION_SAFE[0]}:y={ACTION_SAFE[1]}:w={ACTION_SAFE[2] - ACTION_SAFE[0]}:h={ACTION_SAFE[3] - ACTION_SAFE[1]}:color=0xff8a80:t=2",
           f"drawbox=x={TITLE_SAFE[0]}:y={TITLE_SAFE[1]}:w={TITLE_SAFE[2] - TITLE_SAFE[0]}:h={TITLE_SAFE[3] - TITLE_SAFE[1]}:color=white:t=3",
           _ff_text(font, "Title safe area: 5% in from each edge. Keep every word inside it", 26, "(w-tw)/2", TITLE_SAFE[3] - 44, "white",
                    box="black@0.6"),
           _ff_text(font, "Action safe area: 3.5% in", 22, ACTION_SAFE[0] + 8, ACTION_SAFE[1] + 6, "0xff8a80", box="black@0.6")]
    if which == "logo":
        bw, bh = dog_box or (300, 92)
        m, mx = int(H * 0.05), int(W * 0.05)  # Inside the safe area, the default distance from the edge
        for i, (x, y, words) in enumerate(((W - bw - mx, m, "Top right, the default"), (mx, m, "Top left"), (W - bw - mx, H - bh - m, "Bottom right"),
                                           (mx, H - bh - m, "Bottom left"))):
            out += _rect_filters(font, (x, y, x + bw, y + bh), "", "0xffd54f" if i == 0 else "0x80cbc4", thick=4)
            out.append(_ff_text(font, words, 26, x, y + bh + 12 if y < H / 2 else y - 44, "white", box="black@0.6"))
        out.append(_ff_text(font, "logo/dog.png: a PNG with a transparent background, at least 256 pixels tall", 40, "(w-tw)/2", 430, "white", box="black@0.6"))
        out.append(_ff_text(font, "Drawn 8.5% of the picture's height (92 pixels at 1080) unless the size is changed", 32, "(w-tw)/2", 500, "white", box="black@0.6"))
        out.append(_ff_text(font, "Keep it simple and light: it sits on every programme", 32, "(w-tw)/2", 556, "white", box="black@0.6"))
        return out
    clip = layout.get("clip") or [0, 0, W, H]
    out += _rect_filters(font, clip, f"Clip area: {clip[2] - clip[0]} by {clip[3] - clip[1]}, at {clip[0]}, {clip[1]}", "0xffd54f")
    out.append(_ff_text(font, "The programme's picture plays here" if which == "coming_next" else "Short clips of the programme play here",
                        30, f"{clip[0]}+({clip[2] - clip[0]}-tw)/2", f"{clip[1]}+({clip[3] - clip[1]}-th)/2", "white", box="black@0.6"))
    for name, f in (layout.get("fields") or {}).items():
        r = rect_of(f)
        lines = (f.get("lines") if isinstance(f, dict) else None) or LINES.get(name, 1)
        label = f"{name}: {r[2] - r[0]} by {r[3] - r[1]}, at {r[0]}, {r[1]}" + (f", up to {lines} lines" if lines > 1 else "")
        out += _rect_filters(font, r, label, "0x69f0ae", size=26)
    head = "Coming up next card" if which == "coming_next" else "Promo, with music from promo/music"
    out.append(_ff_text(font, f"{head}: 1920 by 1080, 25 frames a second", 30, "(w-tw)/2", TITLE_SAFE[1] + 40, "white", box="black@0.6"))
    return out


def placement_png(which, layout, font, background=None, dog_box=None):
    """A placement guide as PNG bytes. background: a pack's own background file to draw it on, or None for plain."""
    if background and os.path.isfile(background):
        inp = ["-i", background]
        base = f"[0:v]scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=rgb24"
    else:
        inp = ["-f", "lavfi", "-i", f"color=c=0x2b323b:s={W}x{H}"]
        base = "[0:v]format=rgb24"
    folder = tempfile.mkdtemp(prefix="placement-", dir=_tmp())
    with _placing:  # one guide at a time: the text files are named in turn
        _TEXTS[0] = dog.Texts(folder)
        try:
            graph = base + "," + ",".join(placement_filters(which, layout, font, dog_box)) + "[v]"
            r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", *inp, "-filter_complex", graph, "-map", "[v]", "-frames:v", "1",
                                "-c:v", "png", "-f", "image2", "pipe:1"], capture_output=True, timeout=60, check=False, preexec_fn=_nice)
        finally:
            shutil.rmtree(folder, ignore_errors=True)
    if r.returncode != 0 or not r.stdout:
        raise RuntimeError((r.stderr.decode("utf-8", "replace").strip().splitlines() or ["FFmpeg did not draw the guide"])[-1][:200])
    return r.stdout


def template_pack_json(name="Your channel"):
    return {"pack": 1, "name": name, "made": "", "size": [W, H], "fps": FPS, "colours": {"text": "#FFFFFF", "accent": "#FFD54F"},
            "logo": {"dog": "logo/dog.png", "with_music": "logo/logo-with-music.mp4"},
            "idents": ["ident01.mp4", "ident02.mp4"],
            "coming_next": json.loads(json.dumps(DEFAULT_LAYOUT["coming_next"])), "promo": json.loads(json.dumps(DEFAULT_LAYOUT["promo"])),
            "transitions": ["wipe01.webm"]}


README = """Broadcast pack template, for Create your own TV channel
==========================================================

Put your files in these folders with these names, zip the folder, and add the zip in Starboard:
Settings, Plug-ins, Create your own TV channel, Broadcast pack, Upload a pack.

Every picture is 1920 by 1080 pixels at 25 frames a second. Other sizes are scaled to fit, and a picture that is
not 16:9 is fitted inside with black bars. Keep words inside the title safe area, 5% in from each edge
(96 pixels at the sides, 54 at the top and bottom). Sound is played at -23 LUFS (EBU R 128): the plug-in measures
each file and brings it to that, by up to 12 dB.

pack.json                         Required. The pack's name, and where the clip and each text field go.
                                  Checked against pack.schema.json.
logo/dog.png                      Required. The on-screen logo: a PNG with a transparent background, at least
                                  256 pixels tall. Drawn in a corner of every programme.
logo/logo-with-music.mp4 (.mov)   The logo animated, with its music baked in: 1 to 20 seconds, with sound.
                                  Played as a sting at the start of a break.
idents/ident01.mp4, ident02.mp4   As many as you like (up to 99), each named ident and a number of 2 or 3 digits.
                                  2 to 60 seconds each. Played in a random order. Also .mov, .mkv or .webm.
coming-next/background.mp4        The Coming up next card: a video of 2 to 60 seconds that loops, or a .png or
                                  .jpg still. Leave the clip area and the text fields clear: the plug-in draws
                                  them. coming-next/placement.png shows where they go.
promo/background.mp4              The promo: as the Coming up next card. promo/placement.png shows where they go.
promo/music/music01.m4a           Music beds for the promos, 5 to 300 seconds each (up to 20). Each promo has
                                  one, chosen at random. Also .mp3, .wav, .flac, .ogg or .opus.
transitions/wipe01.webm           Wipes and stings between a programme and a break, 0.2 to 5 seconds, with
                                  transparency: WebM VP9 with alpha (yuva420p) or ProRes 4444 with alpha (.mov).
                                  The cut happens halfway through, so cover the picture then. Played in a random
                                  order.

Text fields, in pack.json under coming_next and promo, "fields":
  Heading        Coming up next, or Later on and the channel's name (a promo says Coming soon)
  Title          The programme's title, up to 2 lines
  Episode        Series 2, episode 4: its name
  Day and time   From the schedule, such as Sunday at 21:00
  Synopsis       Up to 3 lines
  Channel name   The channel it is on

Each field is a box, [left, top, right, bottom] in pixels of 1920 by 1080, such as "Title": [140, 330, 940, 470].
For more control, give an object: {"box": [140, 330, 940, 470], "colour": "#FFFFFF", "align": "left", "lines": 2}.
align is left, centre or right. The words are made as large as the box allows, on as many lines as it says.
"clip" is the box where the programme's picture (Coming up next) or its clips (promo) play: keep it 16:9.
"colours": {"text": "#FFFFFF", "accent": "#FFD54F"}: words are the text colour, Day and time the accent.
promo "seconds" is how long each promo is: 10 to 30, 15 unless you change it.

The zip may be up to 60 MB, and 400 MB unpacked, with up to 150 files. A zip with its files inside one folder is
read from inside that folder. Files with other names, links and paths outside the folder are refused.
README files, placement.png files and an examples folder may stay in the pack: they are not used.

The full specification is in the plug-in's help: Make a broadcast pack.
"""

WHAT_GOES_HERE = {
    "logo": "dog.png: the on-screen logo, a PNG with a transparent background.\nlogo-with-music.mp4: the logo with its music baked in, 1 to 20 seconds.\n",
    "idents": "ident01.mp4, ident02.mp4 and so on: as many as you like, 2 to 60 seconds each, played in a random order.\n",
    "coming-next": "background.mp4 (or .png, .jpg): the Coming up next card. placement.png shows where the clip and the words go.\n",
    "promo": "background.mp4 (or .png, .jpg): the promo. placement.png shows where the clips and the words go.\n",
    "promo/music": "music01.m4a and so on: music beds for the promos, 5 to 300 seconds each.\n",
    "transitions": "wipe01.webm and so on: 0.2 to 5 seconds, WebM VP9 with alpha or ProRes 4444 with alpha.\n",
}


def template_zip(font):
    """The template as zip bytes: the folders, pack.json, pack.schema.json, the README and the placement guides."""
    buf = io.BytesIO()
    lay = template_pack_json()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        top = "broadcast-pack/"
        z.writestr(top + "README.txt", README)
        z.writestr(top + "pack.json", json.dumps(lay, indent=1) + "\n")
        with open(SCHEMA, encoding="utf-8") as f:
            z.writestr(top + "pack.schema.json", f.read())
        for folder, words in WHAT_GOES_HERE.items():
            z.writestr(f"{top}{folder}/what-goes-here.txt", words)
        z.writestr(top + "coming-next/placement.png", placement_png("coming_next", lay["coming_next"], font), zipfile.ZIP_STORED)
        z.writestr(top + "promo/placement.png", placement_png("promo", lay["promo"], font), zipfile.ZIP_STORED)
        z.writestr(top + "logo/placement.png", placement_png("logo", {}, font), zipfile.ZIP_STORED)
    return buf.getvalue()


def zip_folder(folder, top):
    """A pack's folder as zip bytes, inside one folder named `top`, leaving out what the plug-in keeps beside it."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for base, dirs, files in os.walk(folder):
            dirs[:] = sorted(d for d in dirs if not d.startswith("."))
            for f in sorted(files):
                rel = os.path.relpath(os.path.join(base, f), folder).replace(os.sep, "/")
                if rel == "checked.json" or f.startswith("."):
                    continue
                kind = zipfile.ZIP_STORED if f.endswith((".mp4", ".webm", ".m4a", ".png", ".mov")) else zipfile.ZIP_DEFLATED
                z.write(os.path.join(base, f), f"{top}/{rel}", kind)
    return buf.getvalue()
