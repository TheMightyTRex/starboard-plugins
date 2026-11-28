"""Import a kit (0.10.0, DASH-620): video and picture files made in Canva, Figma, Descript, Adobe Express or anywhere else, or
a zip of them, marked for what each one is, turned into a broadcast pack with a LICENCE.txt that says where each came from.

Nothing leaves the home and nothing here runs a file: every file is read with ffprobe (not trusted by its name), copied
without its metadata, and the pack is checked by the same checks as an uploaded pack (pack.check). A still picture
becomes a short title clip. The licence step writes LICENCE.txt, and kit.json (a name, two colours and where each file
came from) travels with the pack so a style can be shared as a file.
"""
import json
import os
import re
import shutil
import stat
import time
import zipfile

import draw
import flash
import pack

MAX_FILE = 90 * 1024 * 1024  # one file
MAX_FILES = 60  # in a kit
VIDEO_EXT = {"mp4", "mov", "webm", "mkv"}
STILL_EXT = {"png", "jpg", "jpeg"}
AUDIO_EXT = {"mp3", "m4a", "wav", "flac", "ogg", "opus"}
ALL_EXT = VIDEO_EXT | STILL_EXT | AUDIO_EXT
ROLES = {
    "ident": "Short title clip",
    "bumper": "Bumper",
    "logo": "Logo with a clear background",
    "coming_next": "Background for the Coming up next card",
    "promo": "Background for coming-up trailers",
    "music": "Music for coming-up trailers",
    "skip": "Leave it out",
}
ORIGINS = {
    "made": "I made it",
    "stock": "A free stock site",
    "template": "A template or kit from a design tool",
    "other": "Something else",
}
REMINDER = "Check you have the right to use it on your own channel. Starboard cannot know."


class KitError(ValueError):
    pass


def safe_name(raw):
    """A file's name made safe to keep: letters, numbers, spaces, dots, dashes and underscores, 80 characters at most."""
    base = os.path.basename(str(raw or "").replace("\\", "/"))
    base = re.sub(r"[^A-Za-z0-9 ._-]", "_", base).strip(" .")[:80]
    return base or "file"


def extension(name):
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def inspect(path):
    """What a file really is, by ffprobe: {"kind": video, still or audio, "dur", "w", "h", "audio"}. Raises KitError."""
    ext = extension(path)
    if ext == "svg":
        raise KitError("an SVG may hold links and scripts, so it is not used. Export a PNG instead")
    if ext not in ALL_EXT:
        raise KitError("not a file type Starboard uses here. Use MP4, MOV, WebM, MKV, PNG, JPG, MP3, M4A, WAV, FLAC, OGG or OPUS")
    info = pack.probe(path)
    v = info["video"]
    if not info["ok"] or (not v and not info["audio"]):
        raise KitError("FFmpeg cannot read it. It may be damaged, or not what its name says")
    if v and v.get("codec_name") in ("png", "mjpeg"):
        if ext not in STILL_EXT:
            raise KitError("it is a picture, but its name says it is something else")
        kind = "still"
    elif v:
        if ext not in VIDEO_EXT:
            raise KitError("it is a video, but its name says it is something else")
        kind = "video"
    else:
        if ext not in AUDIO_EXT:
            raise KitError("it is sound, but its name says it is something else")
        kind = "audio"
    return {"kind": kind, "dur": round(info["duration"], 2) if kind != "still" else 0.0, "w": int((v or {}).get("width") or 0),
            "h": int((v or {}).get("height") or 0), "audio": bool(info["audio"])}


def guess_role(name, info):
    """A first answer to What is this?, which the person can change."""
    n = name.lower()
    if info["kind"] == "audio":
        return "music"
    if info["kind"] == "still":
        if "logo" in n or "dog" in n or "bug" in n:
            return "logo"
        if "background" in n or "backdrop" in n:
            return "coming_next"
        return "ident"
    if "bumper" in n or (0 < info["dur"] <= 2.5):
        return "bumper"
    if "background" in n or "backdrop" in n:
        return "coming_next"
    return "ident"


def roles_for(kind):
    """The answers that make sense for a kind of file."""
    if kind == "audio":
        return ["music", "skip"]
    if kind == "still":
        return ["ident", "bumper", "logo", "coming_next", "promo", "skip"]
    return ["ident", "bumper", "coming_next", "promo", "skip"]


# kit.json ---------------------------------------------------------------------------------------------------------
def read_kit_json(raw):
    """A kit.json's text as {"name", "colours": [c1, c2], "files": {file name: {"origin", "link"}}}, with anything wrong left out.
    Raises KitError when it is not JSON or is over 64 KB."""
    if len(raw) > 65536:
        raise KitError("kit.json is over 64 KB")
    try:
        doc = json.loads(raw)
    except ValueError:
        raise KitError("kit.json is not JSON") from None
    if not isinstance(doc, dict):
        raise KitError("kit.json should be an object")
    out = {"name": draw.clean_words(doc.get("name"))}
    cols = doc.get("colours")
    if isinstance(cols, list) and len(cols) == 2 and all(re.fullmatch(r"#[0-9A-Fa-f]{6}", str(c)) for c in cols):
        out["colours"] = [draw.colour(c) for c in cols]
    files = {}
    given = doc.get("files")
    for k, v in (given.items() if isinstance(given, dict) else []):
        if isinstance(v, dict) and v.get("origin") in ORIGINS and len(files) < 200:
            files[safe_name(k)] = {"origin": v["origin"], "link": link_of(v.get("link"))}
    out["files"] = files
    return out


def link_of(raw):
    """A web address worth writing down: http or https, one line, 300 characters at most. Never fetched."""
    raw = str(raw or "").strip()
    return raw[:300] if re.fullmatch(r"https?://[^\s<>\"']+", raw) else ""


def kit_json(name, colours, files):
    return json.dumps({"kit": 1, "name": name, "colours": colours,
                       "files": {f["name"]: {"origin": f["origin"], "link": f.get("link", "")} for f in files if f.get("role") != "skip"}},
                      indent=1) + "\n"


# LICENCE.txt ------------------------------------------------------------------------------------------------------
def licence_text(name, files, made_on):
    """Where each file came from, in words. Written into the pack as LICENCE.txt."""
    lines = [f"{name}: where each file came from", "=" * (len(name) + 28), "",
             f"This branding was put together on {made_on} with Create your own TV channel, from files the person who runs the channel added.",
             "Starboard did not check any of these claims. The person who added a file said where it came from.", ""]
    for f in files:
        if f.get("role") == "skip":
            continue
        lines.append(f"{f['name']} ({ROLES.get(f['role'], f['role']).lower()})")
        lines.append(f"  Came from: {ORIGINS.get(f.get('origin'), ORIGINS['other'])}" + (f", {f['link']}" if f.get("link") else ""))
        if f.get("origin") == "other" or not f.get("origin"):
            lines.append(f"  Note: {REMINDER}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# Zips of loose files ------------------------------------------------------------------------------------------------
def unzip_into(zip_path, folder):
    """Unpacks the pictures, videos and sounds of a zip into a folder, after checking every name and size, as pack.unpack does.
    Returns ({"saved": [names], "skipped": [reasons], "kit": kit.json's text or ""}). A zip of a ready pack (pack.json at its top)
    is the caller's to send to pack.install_zip instead."""
    if not zipfile.is_zipfile(zip_path):
        raise KitError("That file is not a zip")
    saved, skipped, kit_text, total = [], [], "", 0
    with zipfile.ZipFile(zip_path) as z:
        members = [i for i in z.infolist() if not i.is_dir() and not pack.JUNK.search(i.filename)]
        if len(members) > pack.MAX_FILES:
            raise KitError(f"The zip has {len(members)} files, more than the {pack.MAX_FILES} Starboard reads")
        for info in members:
            name, why = pack._safe_name(info.filename)
            if why:
                raise KitError(f"{info.filename[:80]}: {why}")
            if stat.S_ISLNK(info.external_attr >> 16):
                raise KitError(f"{name}: a link, which a kit may not hold")
            if info.flag_bits & 0x1:
                raise KitError(f"{name}: has a password")
            total += info.file_size
            if total > pack.MAX_TOTAL:
                raise KitError("The files come to more than 400 MB unpacked")
            if info.file_size > 1024 * 1024 and info.file_size / max(1, info.compress_size) > pack.MAX_RATIO:
                raise KitError(f"{name}: packed far smaller than it is, which a real picture or sound never is")
            leaf = os.path.basename(name)
            if leaf.lower() == "kit.json":
                if info.file_size <= 65536:
                    kit_text = z.read(info).decode("utf-8", "replace")
                continue
            if extension(leaf) not in ALL_EXT:
                skipped.append(f"{safe_name(leaf)}: not a picture, video or sound Starboard uses")
                continue
            if info.file_size > MAX_FILE:
                skipped.append(f"{safe_name(leaf)}: over 90 MB")
                continue
            target = unique(folder, safe_name(leaf))
            left = info.file_size
            with z.open(info) as src, open(os.path.join(folder, target), "wb") as out:
                while True:
                    chunk = src.read(1 << 20)
                    if not chunk:
                        break
                    left -= len(chunk)
                    if left < 0:
                        raise KitError(f"{name}: bigger than the zip says")
                    out.write(chunk)
            saved.append(target)
    return {"saved": saved, "skipped": skipped, "kit": kit_text}


def has_pack_json(zip_path):
    try:
        with zipfile.ZipFile(zip_path) as z:
            names = [i.filename for i in z.infolist()]
    except (zipfile.BadZipFile, OSError):
        return False
    top = {n.split("/", 1)[0] for n in names if n and not pack.JUNK.search(n)}
    return "pack.json" in names or (len(top) == 1 and f"{next(iter(top))}/pack.json" in names)


def unique(folder, name):
    base, dot, ext = name.rpartition(".")
    if not dot:
        base, ext = name, ""
    n, out = 1, name
    while os.path.exists(os.path.join(folder, out)):
        n += 1
        out = f"{base}-{n}" + (f".{ext}" if ext else "")
    return out


# Building the pack --------------------------------------------------------------------------------------------------
def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:30] or "style"


def build(src, out, name, colours, files, made_on, progress=lambda step, of, words: None):
    """Makes the pack in `out` (made empty first) from the kit's files in `src`. `files`: [{"name", "kind", "role", "origin", "link", "dur"}].
    One FFmpeg command at a time. Returns the folder. Raises KitError for what the person can change."""
    name = draw.clean_words(name, 40) or "My channel"
    c1, c2 = draw.colour(colours[0] if colours else "", "#10202C"), draw.colour(colours[1] if len(colours) > 1 else "", "#1B8A7F")
    use = [f for f in files if f.get("role") not in (None, "", "skip")]
    if not use:
        raise KitError("Every file is marked Leave it out. Mark at least one as something")
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    idents, bumpers, music = [], [], []
    doc = {"pack": 1, "name": name, "made": made_on[:40], "size": [pack.W, pack.H], "fps": pack.FPS,
           "colours": {"text": draw.text_colour(c1, c2)[0], "accent": c2}}
    todo = len(use) + 2
    done = 0

    def tick(words):
        nonlocal done
        done += 1
        progress(done, todo, words)

    for f in use:
        path = os.path.join(src, f["name"])
        role, ext = f["role"], extension(f["name"])
        tick(f"Adding {f['name']}")
        if role == "ident":
            rel = f"idents/ident{len(idents) + 1:02d}.mp4" if f["kind"] == "still" else f"idents/ident{len(idents) + 1:02d}.{ext}"
            os.makedirs(os.path.join(out, "idents"), exist_ok=True)
            _video(path, os.path.join(out, rel), f["kind"], 5)
            idents.append(os.path.basename(rel))
        elif role == "bumper":
            rel = f"bumpers/bumper{len(bumpers) + 1:02d}.mp4" if f["kind"] == "still" else f"bumpers/bumper{len(bumpers) + 1:02d}.{ext}"
            os.makedirs(os.path.join(out, "bumpers"), exist_ok=True)
            _video(path, os.path.join(out, rel), f["kind"], 2)
            bumpers.append(os.path.basename(rel))
        elif role == "logo":
            if f["kind"] != "still":
                raise KitError(f"{f['name']}: a logo is a picture with a clear background. Export a PNG")
            os.makedirs(os.path.join(out, "logo"), exist_ok=True)
            draw.ff("-i", path, "-vf", "scale='min(iw,iw*200/ih)':'min(ih,200)':flags=lanczos:force_original_aspect_ratio=decrease,format=rgba",
                    "-map_metadata", "-1", "-frames:v", "1", os.path.join(out, "logo", "dog.png"))
        elif role in ("coming_next", "promo"):
            folder = "coming-next" if role == "coming_next" else "promo"
            os.makedirs(os.path.join(out, folder), exist_ok=True)
            if f["kind"] == "still":
                rel = f"{folder}/background.{'png' if ext == 'png' else 'jpg'}"
                draw.ff("-i", path, "-map_metadata", "-1", "-frames:v", "1", os.path.join(out, rel))
            else:
                rel = f"{folder}/background.mp4" if ext == "mp4" else f"{folder}/background.{ext}"
                _video(path, os.path.join(out, rel), "video", 5)
            layout = json.loads(json.dumps(pack.DEFAULT_LAYOUT[role]))
            layout["background"] = rel
            layout.pop("music", None)
            doc[role] = layout
        elif role == "music":
            os.makedirs(os.path.join(out, "promo", "music"), exist_ok=True)
            leaf = f"{slug(f['name'].rsplit('.', 1)[0])[:40] or 'music'}.{ext}"
            draw.ff("-i", path, "-vn", "-map_metadata", "-1", "-c", "copy", os.path.join(out, "promo", "music", leaf))
            music.append(f"promo/music/{leaf}")
    tick("Making the on-screen logo" if not os.path.exists(os.path.join(out, "logo", "dog.png")) else "Finishing")
    if not os.path.exists(os.path.join(out, "logo", "dog.png")):
        os.makedirs(os.path.join(out, "logo"), exist_ok=True)
        ink, _, _ = draw.text_colour(c1, c1)
        draw.text_logo(name, ink, c1, os.path.join(out, "logo", "dog.png"), out)
    doc["logo"] = {"dog": "logo/dog.png"}
    if idents:
        doc["idents"] = idents
    if bumpers:
        doc["bumpers"] = bumpers
    if music and "promo" in doc:
        doc["promo"]["music"] = music
    elif music:
        music = []  # a promo needs a background to use them: said on the page
    write_json(os.path.join(out, "pack.json"), doc)
    with open(os.path.join(out, "LICENCE.txt"), "w", encoding="utf-8") as fh:
        fh.write(licence_text(name, use, made_on))
    with open(os.path.join(out, "kit.json"), "w", encoding="utf-8") as fh:
        fh.write(kit_json(name, [c1, c2], use))
    tick("Checking it")
    return out


def _video(src, dst, kind, seconds):
    """A video copied without its metadata (the picture and sound untouched), or a still made into a clip of `seconds`."""
    if draw.stopped():
        raise draw.Stopped("A channel started to play, so the style stopped")
    if kind == "still":
        draw.still_to_clip(src, dst, seconds)
    else:
        draw.ff("-i", src, "-map", "0:v:0", "-map", "0:a?", "-map_metadata", "-1", "-c", "copy", dst)


def write_json(path, doc):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
        f.write("\n")


def words_for_problems(got):
    """What a failed check tells the person, in one line."""
    return "; ".join(got["problems"][:4]) + (f"; and {len(got['problems']) - 4} more" if len(got["problems"]) > 4 else "")


def today():
    return f"{time.localtime().tm_mday} " + time.strftime("%B %Y")


def flash_notes(src, files):
    """For each video in the kit, the plain warning about fast brightness jumps, or nothing: {file name: words}."""
    out = {}
    for f in files:
        if f.get("kind") == "video":
            said = flash.words(flash.check(os.path.join(src, f["name"])))
            if said:
                out[f["name"]] = said
    return out
