#!/usr/bin/env python3
"""Writes each example plug-in's folder from tools/examples_src.py: starboard-plugin.json, app.py, sbplugin.py (from
_shared), Dockerfile, README.md, LICENSE and install.py (the same installer as Styles). Run it after changing an
example, then tools/build_images.sh to build the images and tools/make_zips.py for the zips."""
import datetime as dt
import json
import os
import shutil
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from examples_src import COMMON, EXAMPLES, IMAGE_VERSION, NEW_IN_IMAGE, VERSION  # noqa: E402

DIGEST_FILE = os.path.join(ROOT, "tools", "examples-digest.txt")
_digest = open(DIGEST_FILE).read().strip() if os.path.isfile(DIGEST_FILE) else ""
EXAMPLES_IMAGE = (f"ghcr.io/themightytrex/starboard-plugin-examples@{_digest}" if _digest.startswith("sha256:")
                  else f"ghcr.io/themightytrex/starboard-plugin-examples:{VERSION}")
# The plug-ins added since that digest name the image's next tag until it is built and pinned again (13 November 2026).
NEXT_IMAGE = f"ghcr.io/themightytrex/starboard-plugin-examples:{IMAGE_VERSION}"

DOCKERFILE = """# {name}: Python's standard library only, no other packages.
FROM python:3.12-alpine
# Every package of the base image takes Alpine's fixed version at build (as Starboard does), so a fix such as
# zlib's CVE-2026-4738 or krb5's 1.22.3 reaches the next build with no change here.
RUN apk upgrade --no-cache
WORKDIR /app
COPY sbplugin.py app.py /app/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER 10001:10001
CMD ["python3", "/app/app.py"]
"""

WORDS = {"network:vpn": "runs inside your VPN", "network:lan": "reaches your home network and the internet",
         "jellyfin:key": "uses Jellyfin's key, which Starboard keeps", "downloads:read": "sees what is downloading",
         "system:read": "sees processor, memory and disk use", "appearance:styles": "adds styles to Display",
         "media:read": "sees your library", "apps:read": "sees your apps and whether they answer"}


def readme(pid, m, extra=""):
    lines = [f"# {m['name']}", "", m["description"], "", "An example Starboard plug-in by TheMightyTRexUK, MIT licence.", "",
             "## What it may do", ""]
    lines += [f"- It {WORDS.get(p, p)}." for p in m["permissions"]] or ["- Nothing beyond its own folder."]
    if m.get("containers"):
        c = m["containers"][0]
        r = (m.get("resources") or {}).get(c["name"]) or {}
        lines += [f"- It runs one small container ({r.get('memory', 128)} MB of memory at most).", ""]
    if m.get("cards"):
        lines += ["## On the dashboard", ""] + [f"- **{c['title']}**: a {c['type']} card." for c in m["cards"]] + [""]
    if m.get("events"):
        lines += ["## What wakes it", "", "Starboard sends it these events: " + ", ".join(f"`{e}`" for e in m["events"]) + "."]
        lines += [f"Starboard runs its job **{j['label']}** daily at {j['daily']}." for j in m.get("jobs") or [] if "daily" in j] + [""]
    screens = [s for s in m.get("settings") or [] if s["type"] == "custom"]
    if screens:
        lines += ["## In its section of Settings, Plug-ins", ""] + [f"- **{s['label']}**: a table to read." for s in screens] + [""]
    plain = [s for s in m.get("settings") or [] if s["type"] != "custom"]
    if plain:
        groups = []
        for s in plain:
            if s.get("group", "Settings") not in groups:
                groups.append(s.get("group", "Settings"))
        lines += ["## Settings", ""]
        for g in groups:
            if len(groups) > 1:
                lines += [f"### {g}", ""]
            lines += [f"- **{s['label']}**" + (f": {s['hint']}" if s.get("hint") else "") for s in plain if s.get("group", "Settings") == g] + [""]
    if extra:
        lines += [extra.strip(), ""]
    lines += ["## Add it", "", "In Starboard, open **Settings**, **Plug-ins**, **Add a plug-in**, and give this address:", "",
              f"`https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/{pid}/starboard-plugin.json`", "",
              "Or run `python3 install.py` in this folder.", ""]
    return "\n".join(lines)


def changelog(m):
    """CHANGELOG.md from the manifest's changes (plug-in API 1.10), so the two always say the same."""
    out = ["# Changelog", ""]
    for c in m["changes"]:
        d = dt.date.fromisoformat(c["date"])
        out += [f"## {c['version']} ({d.day} {d:%B %Y})", ""]
        for kind in ("added", "changed", "deprecated", "removed", "fixed", "security"):
            if c.get(kind):
                out += [f"### {kind.capitalize()}"] + [f"- {line.replace('**', '')}" for line in c[kind]] + [""]
    return "\n".join(out)


def main():
    for pid, (spec, app) in EXAMPLES.items():
        out = os.path.join(ROOT, pid)
        os.makedirs(out, exist_ok=True)
        m = {**COMMON, "id": pid, "version": VERSION,
             "homepage": f"https://github.com/TheMightyTRex/starboard-plugins/tree/main/{pid}", **spec}
        order = ["manifest_version", "id", "name", "version", "description", "author", "licence", "homepage", "support_url",
                 "starboard_api", "permissions", "needs", "containers", "resources", "health", "settings", "actions", "cards",
                 "events", "jobs", "styles", "changes"]
        m = {k: m[k] for k in order if k in m}
        # One shared image for every example (12 November 2026): pinned by digest once GitHub has built it.
        for c in m.get("containers") or []:
            c["image"] = NEXT_IMAGE if pid in NEW_IN_IMAGE else EXAMPLES_IMAGE
            c["env"] = {**(c.get("env") or {}), "EXAMPLE": pid}  # the shared image runs /app/<EXAMPLE>/app.py
        with open(os.path.join(out, "starboard-plugin.json"), "w", encoding="utf-8") as f:
            json.dump(m, f, indent=1, ensure_ascii=False)
            f.write("\n")
        with open(os.path.join(out, "README.md"), "w", encoding="utf-8") as f:
            f.write(readme(pid, m, spec.get("_readme", "")))
        if m.get("changes"):
            with open(os.path.join(out, "CHANGELOG.md"), "w", encoding="utf-8") as f:
                f.write(changelog(m))
        shutil.copy(os.path.join(ROOT, "styles", "LICENSE"), os.path.join(out, "LICENSE"))
        installer = open(os.path.join(ROOT, "styles", "install.py"), encoding="utf-8").read()
        with open(os.path.join(out, "install.py"), "w", encoding="utf-8") as f:
            f.write(installer.replace("The Styles plug-in's installer", f"The {m['name']} plug-in's installer"))
        if app:
            if app != "file":  # "file": app.py is kept in the plug-in's own folder, with its tests in tests/
                with open(os.path.join(out, "app.py"), "w", encoding="utf-8") as f:
                    f.write(f'"""{m["name"]}: {m["description"]}"""\n' + app)
            shutil.copy(os.path.join(ROOT, "_shared", "sbplugin.py"), os.path.join(out, "sbplugin.py"))
            with open(os.path.join(out, "Dockerfile"), "w", encoding="utf-8") as f:
                f.write(DOCKERFILE.format(name=m["name"]))
        print("wrote", pid)
    write_catalogue()


# The collection's catalogue (DASH-318): every plug-in here, which Starboard's Catalogue page lists. "published" is
# true once its manifest and image are on GitHub (Styles now; the examples after DASH-331).
KINDS = {"vpn-check": "Downloads", "line-speed": "Network", "watching-now": "Jellyfin", "most-watched": "Jellyfin",
         "library-health": "Jellyfin", "dns-blocking": "Network", "home-assistant": "Home", "outside-services": "Network",
         "download-summary": "Downloads", "disk-forecast": "System", "remote-access": "Network", "seasonal-styles": "Look", "styles": "Look",
         "notifications": "System", "watch-stats": "Jellyfin"}
KINDS["audio-description"] = "Accessibility"  # hand-made, not from examples_src (DASH-399)
KINDS["audio-description-tracks"] = "Accessibility"  # hand-made, its own image with ffmpeg (DASH-410)
# The plug-ins new in the image are published once it is built with them and its digest pinned (NEW_IN_IMAGE emptied).
PUBLISHED = {"styles"} | ({pid for pid in EXAMPLES if pid not in NEW_IN_IMAGE} if _digest.startswith("sha256:") else set())


def write_catalogue():
    rows = []
    for pid in sorted(os.listdir(ROOT)):
        mf = os.path.join(ROOT, pid, "starboard-plugin.json")
        if not os.path.isfile(mf):
            continue
        m = json.load(open(mf, encoding="utf-8"))
        rows.append({"id": m["id"], "name": m["name"], "description": m["description"], "kind": KINDS.get(pid, "Other"),
                     "author": m["author"], "permissions": m["permissions"], "version": m["version"], "starboard_api": m["starboard_api"],
                     "manifest": f"https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/{pid}/starboard-plugin.json",
                     "published": pid in PUBLISHED})
    with open(os.path.join(ROOT, "catalogue.json"), "w", encoding="utf-8") as f:
        json.dump({"catalogue_version": 1, "name": "Starboard plug-ins", "plugins": rows}, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print("wrote catalogue.json,", len(rows), "plug-ins")


if __name__ == "__main__":
    main()
