#!/usr/bin/env python3
"""Writes each example plug-in's folder from tools/examples_src.py: starboard-plugin.json, app.py, sbplugin.py (from
_shared), Dockerfile, README.md, LICENSE and install.py (the same installer as Styles). Run it after changing an
example, then tools/build_images.sh to build the images and tools/make_zips.py for the zips."""
import base64
import datetime as dt
import json
import os
import re
import shutil
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from examples_src import (COMMON, EXAMPLES, IMAGE_VERSION, NEW_IN_IMAGE, TEXT_PATCH, TEXT_PATCH_CHANGE, TEXT_PATCH_DATE,  # noqa: E402
                          UPDATE_STEPS, VERSION, changes_for)
import make_logos  # noqa: E402

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
# The Python modules the app imports, compiled once here: the container's file system is read only, so otherwise
# every start compiles them again (measured 16 November 2026: start 0.71 to 0.15 processor seconds, first answer
# 0.9 to 0.4 seconds, 0.6 MB less memory at rest, for about 3 MB more image).
RUN python3 -c "import modulefinder, py_compile, sys; f = modulefinder.ModuleFinder(path=['/app'] + sys.path); [f.run_script(p) for p in sys.argv[1:]]; [py_compile.compile(m.__file__, doraise=True) for m in f.modules.values() if (m.__file__ or '').endswith('.py')]" /app/app.py
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER 10001:10001
CMD ["python3", "/app/app.py"]
"""

WORDS = {"network:vpn": "runs inside your VPN", "network:lan": "reaches your home network and the internet",
         "jellyfin:key": "uses Jellyfin's key, which Starboard keeps", "downloads:read": "reads what is downloading",
         "system:read": "reads processor, memory and disk use", "appearance:styles": "adds styles to Display",
         "media:read": "reads your library", "apps:read": "reads your apps and whether they answer",
         "power:hold": "asks Starboard to hold its heavy jobs and downloads while the computer runs on battery"}


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
    if (m.get("update") or {}).get("before"):
        lines += ["## Updating", "", "Before an update, it finishes any check or message it is part way through and starts no new one. "
                  "So the update never cuts one short (plug-in API 1.14). What changed in each version is in "
                  "[CHANGELOG.md](CHANGELOG.md), and Starboard shows it before you update.", ""]
    api = m["starboard_api"].split()[0].lstrip(">=")
    needs = "".join(f", and {n.capitalize()} added in **Settings**, then **Apps**" for n in m.get("needs") or [])
    lines += ["## Add it", "", f"Needs Starboard with plug-in API {api} or later{needs}. A Starboard with an older plug-in API is offered "
              "the version before. In Starboard, go to **Settings**, then **Plug-ins**, then **Catalogue**, and find it under "
              f"**{KINDS.get(pid, 'its kind')}**. Or, under **Add one from elsewhere**, give this address:", "",
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
        # Plug-in API 1.14 (15 November 2026): a logo, What is new for every version, and update steps for those that
        # work in the background (tools/examples_src.py UPDATE_STEPS).
        m["logo"] = make_logos.entry(pid, m["name"])
        m["changes"] = changes_for(pid, m)
        if pid in TEXT_PATCH:  # the next patch version of this plug-in, with its own entry; the image digest stays
            major, minor, patch = (int(x) for x in m["version"].split("."))
            m["version"] = f"{major}.{minor}.{patch + 1}"
            m["changes"] = [{"version": m["version"], "date": TEXT_PATCH_DATE, "changed": [TEXT_PATCH_CHANGE]}] + m["changes"]
        if pid in UPDATE_STEPS:
            m["update"] = UPDATE_STEPS[pid]
        order = ["manifest_version", "id", "name", "version", "description", "author", "licence", "homepage", "support_url",
                 "starboard_api", "permissions", "needs", "containers", "resources", "health", "settings", "setup_required",
                 "actions", "cards", "events", "jobs", "styles", "notices", "update", "switch", "logo", "changes"]
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
# worked out from each manifest by published() below.
KINDS = {"vpn-check": "Downloads", "line-speed": "Network", "watching-now": "Jellyfin", "most-watched": "Jellyfin",
         "library-health": "Jellyfin", "dns-blocking": "Network", "home-assistant": "Home", "outside-services": "Network",
         "download-summary": "Downloads", "disk-forecast": "System", "remote-access": "Network", "seasonal-styles": "Appearance", "styles": "Appearance",
         "notifications": "System", "watch-stats": "Jellyfin", "backups-watch": "System", "ups-power": "System", "immich": "Photos", "single-sign-on": "System"}
KINDS["audio-description"] = "Accessibility"  # hand-made, not from examples_src (DASH-399)
KINDS["audio-description-tracks"] = "Accessibility"  # hand-made, its own image with ffmpeg (DASH-410)
KINDS["direct-play"] = "Jellyfin"  # hand-made, its own image with ffmpeg (DASH-425)
KINDS["picture-shrinker"] = "Jellyfin"  # hand-made, its own image with Pillow (DASH-432); not recommended, never added by itself
KINDS["library-cleanup"] = "Jellyfin"  # hand-made, its own image (DASH-406, plug-in API 1.15); not recommended, never added by itself
KINDS["philips-hue"] = "Home"  # hand-made, its own image (20 November 2026, plug-in API 1.16); not recommended, never added by itself
KINDS["calibre-library"] = "Books"  # hand-made, its own image with Calibre (DASH-590); not recommended, never added by itself
KINDS["tv-station"] = "Jellyfin"  # hand-made, its own image with FFmpeg (DASH-477); not recommended, never added by itself
# Recommended (DASH-425, owner 14 November 2026: "its recommended in the catalogue"): a few plug-ins that suit most
# servers, shown first in Starboard's Catalogue (plug-in API 1.14). Never installed by default: adding stays a choice.
RECOMMENDED = {"direct-play", "notifications", "disk-forecast"}
# Apps you can add (DASH-411), each with its memory and processor at rest: the 13 November 2026 benchmark where it
# measured the app, else measured with tools/app_check.py.
REST = {"calibre-web": (172, 0.01), "jellystat": (117, 0.22), "kavita": (337, 0.99), "maintainerr": (127, 0.0),
        "navidrome": (16, 0.01), "seerr": (127, 0.0), "tdarr": (59, 0.11), "uptime-kuma": (116, 0.0), "wizarr": (124, 0.02),
        "themearr": (48, 0.64), "checkrr": (19, 0.01)}  # 17 November 2026, tools/app_check.py, as Starboard runs them
KINDS.update({pid: "Apps you can add" for pid in REST})
PINNED = re.compile(r"@sha256:[0-9a-f]{64}$")


def published(m):
    """A plug-in is published when every container image it runs is pinned by digest, so what Starboard downloads is
    exactly what was built and tested; one with no containers, such as Styles, is published as it stands. A tag (an
    image not yet built, or one that could change under it) keeps it coming soon (14 November 2026)."""
    return all(PINNED.search(c.get("image") or "") for c in m.get("containers") or [])


def logo_fields(pid, m):
    """The catalogue's logo (plug-in API 1.14): the plug-in's own logo file as a data address, and its words, so
    Starboard's Catalogue shows it before anything is added and never loads it from GitHub."""
    logo = m.get("logo") or {}
    path = os.path.join(ROOT, pid, logo.get("file") or "")
    if not logo.get("file") or not os.path.isfile(path):
        return {}
    kind = "image/svg+xml" if path.endswith(".svg") else "image/png"
    uri = f"data:{kind};base64,{base64.b64encode(open(path, 'rb').read()).decode()}"
    if len(uri) > LOGO_DATA_MAX:
        raise ValueError(f"{pid}: the logo is too large for the catalogue ({len(uri):,} of {LOGO_DATA_MAX:,} characters)")
    return {"logo": uri, "logo_alt": logo["alt"]}


LOGO_DATA_MAX = 24 * 1024  # Starboard's limit for a catalogue's data address (plugin_logo.DATA_MAX)
PREVIOUS = json.load(open(os.path.join(ROOT, "tools", "previous-versions.json"), encoding="utf-8"))


def whole(text, limit):
    """Text cut to at most `limit` characters at its last whole sentence, or else its last whole word with an
    ellipsis, never mid-word (Starboard issue #169: a summary ended "a described track an")."""
    text = " ".join(str(text).split())
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    if end >= limit // 2:
        return cut[:end + 1]
    return cut[:limit - 1].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def versions(pid, m):
    """A plug-in whose new version needs a newer plug-in API keeps its last version in the catalogue (15 November
    2026), pinned to the commit it was published at with its SHA-256, so a Starboard with an older plug-in API (such as
    0.17.0, with 1.13) still installs that one, and a newer Starboard is offered the new one."""
    old = PREVIOUS["plugins"].get(pid)
    if not old or old["version"] == m["version"]:
        return {}
    first = (m.get("changes") or [{}])[0]
    words = " ".join(line.replace("**", "") for kind in ("added", "changed", "fixed") for line in first.get(kind) or [])
    return {"versions": [
        {"version": m["version"], "starboard_api": m["starboard_api"], "released": first.get("date", ""),
         "manifest": f"https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/{pid}/starboard-plugin.json",
         "changelog": whole(words, 600)},
        # Later versions kept the same way (19 November 2026): each pinned to its own commit, newest first, so a
        # Starboard on plug-in API 1.14 or 1.15 keeps Notifications 1.1.3 when 1.2.0 needs 1.16.
        *[{"version": x["version"], "starboard_api": x["starboard_api"],
           "manifest": f"https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/{x['commit']}/{pid}/starboard-plugin.json",
           "manifest_sha256": x["sha256"]} for x in (PREVIOUS.get("more") or {}).get(pid) or []],
        {"version": old["version"], "starboard_api": old["starboard_api"],
         "manifest": f"https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/{PREVIOUS['commit']}/{pid}/starboard-plugin.json",
         "manifest_sha256": old["sha256"]}]}


# What each plug-in replaces or adds to (DASH-585, plug-in API 1.23): one plain line, up to 140 characters, shown on Starboard's
# Catalogue card and in the warning before install. A manifest may carry the same line in `replaces_or_adds`; the manifest's is used
# when it has one, so a plug-in moves the line into its manifest the next time it changes. Each line says what the plug-in really does.
NOTES = {
    "audio-description": "Adds to Jellyfin and Reelix: finds described sound tracks, plays them for people who choose it, and prefers releases that have one.",
    "audio-description-tracks": "Adds to Jellyfin: attaches a description track you already have to its film or episode.",
    "backups-watch": "Adds to Starboard: a dashboard card and an alert for your Backrest or Kopia backups. Replaces nothing.",
    "calibre-library": "Adds to Calibre-Web: makes the Calibre library it opens, from your books folder. Your books are never changed.",
    "calibre-web": "Stands alone: a separate book reader app. It reads your books folder and never changes it.",
    "checkrr": "Adds to Reelix and Jellyfin: reports damaged files each Sunday night. It never deletes, moves or replaces one.",
    "direct-play": "Adds to Jellyfin: stops it converting files as they play, one file at a time.",
    "disk-forecast": "Adds to Starboard: a dashboard card that says when each disk will fill. Replaces nothing.",
    "dns-blocking": "Adds to Starboard: a dashboard card from Pi-hole or AdGuard Home. Replaces nothing.",
    "download-summary": "Adds to Starboard: a dashboard card with what you downloaded, from the queue it already sees.",
    "home-assistant": "Adds to Starboard: a dashboard sentence from the Home Assistant things you choose.",
    "immich": "Adds to Starboard: dashboard cards from your Immich server. Immich itself stays as it is.",
    "jellystat": "Adds to Jellyfin: a separate watch statistics app with its own database. Replaces nothing.",
    "kavita": "Stands alone: a separate reader for comics, manga and books. It never changes your folders.",
    "library-cleanup": "Adds to Jellyfin and Reelix: moves watched or unwatched films and series to the holding folder. It never deletes.",
    "library-health": "Adds to Jellyfin: lists films and series with no poster, description or year.",
    "line-speed": "Adds to Starboard: a nightly internet speed test, outside download hours.",
    "maintainerr": "Adds to Jellyfin: a separate app with clean-up rules. It changes nothing until you give it a rule.",
    "most-watched": "Adds to Jellyfin: a dashboard card with what most people watched this week.",
    "navidrome": "Stands alone: a separate music server for Subsonic apps. It never changes your music folder.",
    "notifications": "Adds to Starboard: sends its events to email, Telegram, Discord and more. Starboard's own alerts stay.",
    "outside-services": "Adds to Starboard: checks things outside this server. Starboard's own app checks stay.",
    "philips-hue": "Adds to Starboard: controls your Hue lights through the Hue bridge on your home network. Nothing goes to the Hue cloud.",
    "picture-shrinker": "Adds to Jellyfin: shrinks the posters and photos of people it keeps, with or without a backup of each original.",
    "remote-access": "Adds to Starboard, Jellyfin and Audiobookshelf: reach them away from home through Tailscale or Cloudflare Tunnel.",
    "seerr": "Adds to Jellyfin: a requests page. Reelix already has requests, so most people do not need it.",
    "single-sign-on": "Adds to Starboard: one sign-in for your apps. This first version holds only the switch and the Tailscale name.",
    "styles": "Adds to Starboard: more styles in Display. The styles that come with Starboard stay.",
    "tdarr": "Adds to your library: a separate app that converts files to save space in quiet hours.",
    "themearr": "Adds to Jellyfin and Reelix: a theme tune in each film's folder. It needs a RapidAPI key.",
    "tv-station": "Adds to Jellyfin: your own TV channels in Live TV, made from your films and series.",
    "ups-power": "Adds to Starboard: a dashboard card and an alert for your UPS, read from NUT or PeaNUT.",
    "uptime-kuma": "Adds to Starboard: a separate app for more status checks. Starboard's own checks stay.",
    "vpn-check": "Adds to Starboard: shows the address and country your VPN gives. Replaces nothing.",
    "watch-stats": "Adds to Jellyfin: what was watched, by whom and when, from Playback Reporting. No second database.",
    "watching-now": "Adds to Jellyfin: a dashboard card of who is watching now.",
    "wizarr": "Adds to Jellyfin: a separate app that makes invitation links for new Jellyfin users."
}


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
                     "published": published(m), "recommended": pid in RECOMMENDED})
        note = m.get("replaces_or_adds") or NOTES.get(pid)
        if not note:
            raise ValueError(f"{pid}: add a line to NOTES in tools/make_examples.py saying what it replaces or adds to")
        rows[-1]["replaces_or_adds"] = note
        rows[-1].update(logo_fields(pid, m))
        rows[-1].update(versions(pid, m))
        if pid in REST:
            rows[-1]["rest"] = {"memory_mb": REST[pid][0], "cpu_percent": REST[pid][1]}
    with open(os.path.join(ROOT, "catalogue.json"), "w", encoding="utf-8") as f:
        json.dump({"catalogue_version": 1, "name": "Starboard plug-ins", "plugins": rows}, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print("wrote catalogue.json,", len(rows), "plug-ins")


if __name__ == "__main__":
    main()
