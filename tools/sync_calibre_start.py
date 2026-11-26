#!/usr/bin/env python3
"""Puts calibre-web/start.py into calibre-web/starboard-plugin.json, where Starboard writes it into the plug-in's data
folder (the container's `files`). Run it after changing start.py; a test fails while the two differ.

    python3 tools/sync_calibre_start.py          write it
    python3 tools/sync_calibre_start.py --check  only say whether they match
"""
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
MANIFEST = os.path.join(ROOT, "calibre-web", "starboard-plugin.json")
SCRIPT = os.path.join(ROOT, "calibre-web", "start.py")
NAME = "starboard-start-1.py"  # a new name when start.py changes, because Starboard writes a file only when it is missing


def main(argv):
    with open(SCRIPT, encoding="utf-8") as f:
        text = f.read()
    with open(MANIFEST, encoding="utf-8") as f:
        manifest = json.load(f)
    app = manifest["containers"][0]
    same = (app.get("files") or {}).get(NAME) == text
    if "--check" in argv:
        print("matches" if same else "differs")
        return 0 if same else 1
    if len(text) > 16384:
        print("start.py is over 16 KB, which is as much as a file in a manifest may hold")
        return 1
    app["files"] = {NAME: text}
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print("wrote", NAME, "into the manifest,", len(text), "characters")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
