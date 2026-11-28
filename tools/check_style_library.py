#!/usr/bin/env python3
"""Checks style-library/index.json: only MIT, with credits and a reviewer, packs that exist with the sha256 and size listed, each a
pack with a pack.json and a LICENCE.txt, and a preview. A link entry has a name, a maker and an https link and is never hosted."""
import hashlib
import json
import os
import re
import sys
import zipfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "style-library")
ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,40}$")
MAX = 25 * 1024 * 1024


def problems(root=ROOT):
    try:
        with open(os.path.join(root, "index.json"), encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError) as e:
        return [f"index.json cannot be read: {e}"]
    out, seen = [], set()
    for s in doc.get("styles") or []:
        sid = str(s.get("id"))
        where = f"{sid}:"
        if not ID.match(sid) or sid in seen:
            out.append(f"{where} the id is not a name of letters, numbers and hyphens, or it is listed twice")
        seen.add(sid)
        if s.get("licence") != "MIT":
            out.append(f"{where} only MIT styles are listed")
        for k in ("name", "maker", "credits"):
            if not str(s.get(k) or "").strip():
                out.append(f"{where} {k} is empty")
        if not (isinstance(s.get("reviewed"), dict) and s["reviewed"].get("by") and re.match(r"^\d{4}-\d{2}-\d{2}$", str(s["reviewed"].get("on")))):
            out.append(f"{where} it has not been read: reviewed needs by and on")
        if s.get("kind") == "link":
            if not str(s.get("link", "")).startswith("https://") or s.get("file"):
                out.append(f"{where} a link entry needs an https link and no file")
            continue
        if s.get("kind", "pack") != "pack":
            out.append(f"{where} kind is pack or link")
            continue
        path = os.path.join(root, str(s.get("file", "")))
        if not re.match(r"^packs/[a-z0-9][a-z0-9.-]{1,60}\.zip$", str(s.get("file", ""))) or not os.path.isfile(path):
            out.append(f"{where} the zip is not at packs/<name>.zip")
            continue
        data = open(path, "rb").read()
        if len(data) > MAX or len(data) != s.get("size"):
            out.append(f"{where} the size is not the file's size, or it is over 25 MB")
        if hashlib.sha256(data).hexdigest() != s.get("sha256"):
            out.append(f"{where} the sha256 is not the file's")
        try:
            with zipfile.ZipFile(path) as z:
                names = z.namelist()
            if "pack.json" not in names or not any(n in ("LICENCE.txt", "LICENSE.txt", "LICENCE.md", "LICENSE.md", "LICENSE", "LICENCE") for n in names):
                out.append(f"{where} the zip needs a pack.json and a LICENCE.txt")
            if any(n.startswith("/") or ".." in n.split("/") for n in names):
                out.append(f"{where} the zip has a path outside itself")
        except zipfile.BadZipFile:
            out.append(f"{where} the zip cannot be opened")
        if not os.path.isfile(os.path.join(root, str(s.get("preview", "")))) or not str(s.get("preview", "")).startswith("previews/"):
            out.append(f"{where} the preview is not at previews/<name>.png")
    return out


if __name__ == "__main__":
    found = problems()
    print("\n".join(found) if found else "The style library is fine")
    sys.exit(1 if found else 0)
