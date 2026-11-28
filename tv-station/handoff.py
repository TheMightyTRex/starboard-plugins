"""Packs ready to use (0.13.3, DASH-635): a pack another plug-in left in the shared hand-off folder tv-pack (plug-in API 1.25: the
permission handoff:receive and the volume handoff/tv-pack:receive, mounted at /handoff/tv-pack).

The folder is writable by every plug-in that may send into it, so nothing in it is trusted:
  - the folder is read only when the page is drawn or a person presses a button: nothing watches it
  - a file is listed only when it is a regular file (never a link) ending in .zip, not starting with a dot (a sender writes
    .name.part and renames when whole), with a plain name, and at most 60 MB
  - a zip is copied out into the plug-in's own folder first, so the sender cannot change it while it is checked, and then
    checked exactly like an uploaded pack (the same size, file and zip-bomb limits, the same loudness step, the flash guard)
  - the file in the shared folder is removed only after a successful install, or when the person removes it
A pack from a hand-off may have no logo (the Online sources plug-in sends backgrounds and music only): the plug-in then draws the name as the
logo, as Import a kit does, before the check.
"""
import json
import os
import re
import shutil
import stat
import time
import zipfile

import draw
import kit
import pack

DIR = os.environ.get("TV_HANDOFF", "/handoff/tv-pack")
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._()-]{0,100}\.zip$")
MOST = 30  # files listed


class HandoffError(ValueError):
    pass


def _regular(path):
    try:
        st = os.lstat(path)
    except OSError:
        return None
    return st if stat.S_ISREG(st.st_mode) else None


def listing(folder=None):
    """The packs waiting: [{"name", "size", "at"}], newest first. Nothing else in the folder is looked at."""
    folder = folder or DIR
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    out = []
    for n in names:
        if n.startswith(".") or not NAME.match(n):
            continue
        st = _regular(os.path.join(folder, n))
        if st and 0 < st.st_size <= pack.MAX_ZIP:
            out.append({"name": n, "size": st.st_size, "at": int(st.st_mtime)})
    return sorted(out, key=lambda r: -r["at"])[:MOST]


def licence_of(folder, name, most=4000):
    """The text of LICENCE.txt inside a waiting zip, read from the zip without unpacking it, so the person can read where each file came from."""
    path = os.path.join(folder or DIR, name)
    if not NAME.match(name) or not _regular(path):
        return ""
    return _licence_in(path, most)


def _licence_in(path, most=200000):
    try:
        with zipfile.ZipFile(path) as z:
            for i in z.infolist():
                leaf = i.filename.split("/")
                if leaf[-1].upper() in ("LICENCE.TXT", "LICENSE.TXT") and len(leaf) <= 2 and 0 < i.file_size <= 200000:
                    return z.read(i)[:most].decode("utf-8", "replace")
    except (zipfile.BadZipFile, OSError, KeyError):
        return ""
    return ""


def take(name, work, folder=None):
    """Copies a waiting zip into `work` (the plug-in's own folder) and returns the copy's path. The copy is read once, to at most 60 MB."""
    folder = folder or DIR
    if not NAME.match(name or ""):
        raise HandoffError("That is not a name a pack zip has")
    src = os.path.join(folder, name)
    st = _regular(src)
    if not st:
        raise HandoffError("That pack is not in the folder any more")
    if not 0 < st.st_size <= pack.MAX_ZIP:
        raise HandoffError("That zip is over 60 MB, the most a pack may be")
    os.makedirs(work, exist_ok=True)
    dst = os.path.join(work, f"handoff-{int(time.time() * 1000)}.zip")
    left = pack.MAX_ZIP + 1
    with open(src, "rb") as a, open(dst, "wb") as b:
        while left > 0:
            chunk = a.read(min(1 << 20, left))
            if not chunk:
                break
            b.write(chunk)
            left -= len(chunk)
    if left <= 0:
        os.remove(dst)
        raise HandoffError("That zip is over 60 MB, the most a pack may be")
    return dst


def install(zip_copy, folder, work):
    """Unpacks and checks the private copy, adding a drawn logo when the pack has none, and puts it in place of the pack in `folder`.
    Returns the check's answer. Raises pack.PackError (the zip cannot be used) or HandoffError."""
    stage = os.path.join(work, f"stage-handoff-{int(time.time() * 1000)}")
    shutil.rmtree(stage, ignore_errors=True)
    try:
        pack.unpack(zip_copy, stage)
        text = _licence_in(zip_copy)  # unpack leaves LICENCE.txt behind, as the pack never uses it; this keeps it with the pack
        if text:
            with open(os.path.join(stage, "LICENCE.txt"), "w", encoding="utf-8") as f:
                f.write(text)
        try:
            with open(os.path.join(stage, "pack.json"), encoding="utf-8") as f:
                doc = json.load(f)
        except (OSError, ValueError):
            raise HandoffError("pack.json cannot be read") from None
        if not isinstance(doc, dict):
            raise HandoffError("pack.json should be an object")
        changed = False
        # A pack of backgrounds and music has no layout in its pack.json: the plug-in's own places for the clip and the words are used.
        for part, folder_name in (("coming_next", "coming-next"), ("promo", "promo")):
            found = next((f for f in sorted(os.listdir(os.path.join(stage, folder_name))) if re.fullmatch(r"background\.(png|jpg|jpeg|mp4|mov)", f)), None) \
                if os.path.isdir(os.path.join(stage, folder_name)) else None
            if found and not isinstance(doc.get(part), dict):
                lay = json.loads(json.dumps(pack.DEFAULT_LAYOUT[part]))
                lay["background"] = f"{folder_name}/{found}"
                lay.pop("music", None)
                if part == "promo":
                    music = os.path.join(stage, "promo", "music")
                    names = sorted(os.listdir(music)) if os.path.isdir(music) else []
                    if names:
                        lay["music"] = [f"promo/music/{n}" for n in names if re.fullmatch(r"[A-Za-z0-9 _.-]{1,60}\.(m4a|mp3|wav|flac|ogg|opus)", n)][:20]
                doc[part] = lay
                changed = True
        dog = os.path.join(stage, "logo", "dog.png")
        if not os.path.exists(dog):
            os.makedirs(os.path.join(stage, "logo"), exist_ok=True)
            draw.text_logo(draw.clean_words(doc.get("name")) or "TV", "#FFFFFF", "#10202C", dog, stage)
            doc["logo"] = {"dog": "logo/dog.png"}
            changed = True
        if changed:
            kit.write_json(os.path.join(stage, "pack.json"), doc)
        got = pack.install_folder(stage, folder)
        if not got["ok"]:
            raise pack.PackError(kit.words_for_problems(got))
        return got
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def remove(name, folder=None):
    folder = folder or DIR
    if not NAME.match(name or ""):
        raise HandoffError("That is not a name a pack zip has")
    path = os.path.join(folder, name)
    if _regular(path):
        os.remove(path)
