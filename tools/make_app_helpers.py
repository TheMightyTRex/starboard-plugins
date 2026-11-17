#!/usr/bin/env python3
"""Copies the app plug-ins' helper files into their manifests (17 November 2026: Themearr and checkrr).

An app plug-in that needs a small helper beside the app, for its card or to set the app up, can run it in the
official Python image instead of an image of ours: the helper's code goes in the manifest's `files` (plug-in API
1.13), which Starboard writes once into the container's own folder before its first start, and `command` runs it.
No image of ours is built or published, and the code people approve is in the manifest they read.

Starboard never writes a file over one that is there, so a helper's file name carries the plug-in's version
(app-1.0.0.py): an update writes the new one beside the old, and `command` runs the new one. A settings file the
person may change, such as checkrr.yaml, keeps one name, so their change stays.

    python3 tools/make_app_helpers.py           # writes the files into the manifests
    python3 tools/make_app_helpers.py --check   # says whether any manifest is out of date (the tests run this)
"""
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
# plug-in id: {container: {file name in the container's folder (with {version}): source file in the plug-in's folder}}
HELPERS = {
    "themearr": {"main": {"app-{version}.py": "helper.py"}},
    "checkrr": {"main": {"app-{version}.py": "helper.py"}, "app": {"checkrr.yaml": "checkrr.yaml"}},
}
LIMIT = 16384  # Starboard's limit for each file's text


def wanted(pid):
    path = os.path.join(ROOT, pid, "starboard-plugin.json")
    with open(path, encoding="utf-8") as f:
        m = json.load(f)
    for c in m["containers"]:
        spec = HELPERS[pid].get(c["name"])
        if not spec:
            continue
        files = {}
        for name, src in spec.items():
            with open(os.path.join(ROOT, pid, src), encoding="utf-8") as f:
                text = f.read()
            if len(text) > LIMIT:
                raise SystemExit(f"{pid}/{src} is {len(text):,} characters; Starboard takes up to {LIMIT:,}")
            files[name.format(version=m["version"])] = text
            if name.endswith(".py"):
                folder = next(v.split(":", 1)[1] for v in c["volumes"] if v.startswith("data:"))
                c["command"] = ["python3", f"{folder}/{name.format(version=m['version'])}"]
        c["files"] = files
    return path, m


def main():
    check = "--check" in sys.argv
    stale = []
    for pid in HELPERS:
        path, m = wanted(pid)
        text = json.dumps(m, indent=1, ensure_ascii=False) + "\n"
        with open(path, encoding="utf-8") as f:
            now = f.read()
        if now != text:
            stale.append(pid)
            if not check:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
                print("wrote", path)
    if check and stale:
        print("Out of date, run tools/make_app_helpers.py:", ", ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
