#!/usr/bin/env python3
"""Writes each example plug-in's folder from tools/examples_src.py: starboard-plugin.json, app.py, sbplugin.py (from
_shared), Dockerfile, README.md, LICENSE and install.py (the same installer as Styles). Run it after changing an
example, then tools/build_images.sh to build the images and tools/make_zips.py for the zips."""
import json
import os
import shutil
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from examples_src import COMMON, EXAMPLES, VERSION  # noqa: E402

DOCKERFILE = """# {name}: Python's standard library only, no other packages.
FROM python:3.12-alpine
WORKDIR /app
COPY sbplugin.py app.py /app/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER 10001:10001
CMD ["python3", "/app/app.py"]
"""

WORDS = {"network:vpn": "runs inside your VPN", "network:lan": "reaches your home network and the internet",
         "jellyfin:key": "uses Jellyfin's key, which Starboard keeps", "downloads:read": "sees what is downloading",
         "system:read": "sees processor, memory and disk use", "appearance:styles": "adds styles to Display",
         "media:read": "sees your library"}


def readme(pid, m):
    lines = [f"# {m['name']}", "", m["description"], "", "An example Starboard plug-in by TheMightyTRexUK, MIT licence.", "",
             "## What it may do", ""]
    lines += [f"- It {WORDS.get(p, p)}." for p in m["permissions"]] or ["- Nothing beyond its own folder."]
    if m.get("containers"):
        c = m["containers"][0]
        r = (m.get("resources") or {}).get(c["name"]) or {}
        lines += [f"- It runs one small container ({r.get('memory', 128)} MB of memory at most).", ""]
    if m.get("cards"):
        lines += ["## On the dashboard", ""] + [f"- **{c['title']}**: a {c['type']} card." for c in m["cards"]] + [""]
    if m.get("settings"):
        lines += ["## Settings", ""] + [f"- **{s['label']}**" + (f": {s['hint']}" if s.get("hint") else "") for s in m["settings"]] + [""]
    lines += ["## Add it", "", "In Starboard, open **Settings**, **Plug-ins**, **Add a plug-in**, and give this address:", "",
              f"`https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/{pid}/starboard-plugin.json`", "",
              "Or run `python3 install.py` in this folder.", ""]
    return "\n".join(lines)


def main():
    for pid, (spec, app) in EXAMPLES.items():
        out = os.path.join(ROOT, pid)
        os.makedirs(out, exist_ok=True)
        m = {**COMMON, "id": pid, "version": VERSION,
             "homepage": f"https://github.com/TheMightyTRex/starboard-plugins/tree/main/{pid}", **spec}
        order = ["manifest_version", "id", "name", "version", "description", "author", "licence", "homepage", "support_url",
                 "starboard_api", "permissions", "containers", "resources", "health", "settings", "actions", "cards", "styles"]
        m = {k: m[k] for k in order if k in m}
        with open(os.path.join(out, "starboard-plugin.json"), "w", encoding="utf-8") as f:
            json.dump(m, f, indent=1, ensure_ascii=False)
            f.write("\n")
        with open(os.path.join(out, "README.md"), "w", encoding="utf-8") as f:
            f.write(readme(pid, m))
        shutil.copy(os.path.join(ROOT, "styles", "LICENSE"), os.path.join(out, "LICENSE"))
        installer = open(os.path.join(ROOT, "styles", "install.py"), encoding="utf-8").read()
        with open(os.path.join(out, "install.py"), "w", encoding="utf-8") as f:
            f.write(installer.replace("The Styles plug-in's installer", f"The {m['name']} plug-in's installer"))
        if app:
            with open(os.path.join(out, "app.py"), "w", encoding="utf-8") as f:
                f.write(f'"""{m["name"]}: {m["description"]}"""\n' + app)
            shutil.copy(os.path.join(ROOT, "_shared", "sbplugin.py"), os.path.join(out, "sbplugin.py"))
            with open(os.path.join(out, "Dockerfile"), "w", encoding="utf-8") as f:
                f.write(DOCKERFILE.format(name=m["name"]))
        print("wrote", pid)


if __name__ == "__main__":
    main()
