#!/usr/bin/env python3
"""Starboard's example server (made-up data, nothing real is read) with this collection's own catalogue.json and
Library clean-up's real manifest, for the plug-ins help pictures (tools/help-screenshots.sh).

    python3 tools/help_screenshots/example_server.py <starboard checkout> <data folder> <port> [absent]

With "absent", Library clean-up is not added, so the Catalogue offers it and Install... shows what it may do. Without
it, Library clean-up is added and active, with made-up Preview, Holding folder, Libraries and card answers.
Nothing is read, moved or put back: Put back takes the row off the list here. 15 November 2026."""
import json
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent.parent.parent
starboard, data, port = sys.argv[1], sys.argv[2], sys.argv[3]
absent = len(sys.argv) > 4 and sys.argv[4] == "absent"
sys.path.insert(0, str(pathlib.Path(starboard) / "tools" / "screenshots"))
sys.argv = ["example_server.py", data, port]
import example_server as ex  # noqa: E402  (Starboard's example server: its set-up runs on import, main() below)
from starboard import plugin_cards, plugin_custom, plugin_logo, plugin_watch, plugins_admin  # noqa: E402

CATALOGUE = json.loads((HERE / "catalogue.json").read_text())
MANIFEST = json.loads((HERE / "library-cleanup" / "starboard-plugin.json").read_text())
_real_catalogue, _real_manifest = plugins_admin.fetch_catalogue, plugins_admin.fetch_manifest


def catalogue(address, opener=None):
    """The collection's own catalogue, as Starboard reads it from GitHub."""
    if address == plugins_admin.CATALOGUE_URL:
        return {"name": CATALOGUE.get("name") or "Starboard plug-ins",
                "items": [x for x in map(plugins_admin._clean_entry, CATALOGUE["plugins"]) if x]}
    return _real_catalogue(address, opener)


def manifest(address, opener=None, sha256=""):
    if "library-cleanup" in str(address):
        return json.loads(json.dumps(MANIFEST))
    return _real_manifest(address, opener) if not sha256 else _real_manifest(address, opener, sha256)


plugins_admin.fetch_catalogue = catalogue
plugins_admin.fetch_manifest = manifest

PREVIEW = [("A quiet harbour (2004)", "Films", "Watched by everyone, last 120 days ago", "3.9 GB", "/media/movies/A quiet harbour (2004)"),
           ("North road (2011)", "Films", "Not watched for 12 months", "2.2 GB", "/media/movies/North road (2011)"),
           ("Salt and stone (2016)", "Series", "Ended, and every episode watched", "18.4 GB", "/media/tv/Salt and stone (2016)")]
HELD = [{"id": "h1", "title": "A made-up film (2001)", "group": "Films",
         "detail": "Films. Moved Saturday 15 November, 4.2 GB. Watched by everyone, last 120 days ago"},
        {"id": "h2", "title": "Harbour lights (2019)", "group": "Series",
         "detail": "Series. Moved Saturday 15 November, 31.8 GB. Ended, and every episode watched"},
        {"id": "h3", "title": "The long field (1998)", "group": "Films",
         "detail": "Films. Moved Friday 14 November, 2.7 GB. Not watched for 12 months"}]
COLUMNS = [{"key": "title", "label": "Title"}, {"key": "library", "label": "Library"}, {"key": "why", "label": "Why it would move"},
           {"key": "size", "label": "Space"}, {"key": "where", "label": "Folder"}]


def screen(key, held, off):
    """The screens as library-cleanup/app.py draws them (preview_screen, held_screen, libraries_screen)."""
    if key == "preview":
        return {"type": "list", "title": "Preview", "layout": "folds", "readonly": True, "columns": COLUMNS,
                "filters": [{"key": "why", "label": "Why"}],
                "intro": "3 items would move to the holding folder, freeing 24.5 GB. 2 items the rules found are always kept. "
                         "Worked out Sun 15 Nov at 09:12 for 3 people in 2 libraries. Nothing moves until you activate Move items each day.",
                "items": [{"id": f"p{i}", "title": t, "group": lib, "actions": [],
                           "cells": {"title": t, "library": lib, "why": r, "size": z, "where": w}}
                          for i, (t, lib, r, z, w) in enumerate(PREVIEW)]}
    if key == "libraries":
        libs = [("films", "Films", "films", "/media/movies"), ("series", "Series", "series", "/media/tv"),
                ("children", "Children's films", "films", "/media/children")]
        return {"type": "list", "title": "Libraries",
                "intro": "The rules look only at the libraries activated here. A library you add to Jellyfin is looked at until you deactivate it.",
                "items": [{"id": i, "title": t, "detail": ("Films" if k == "films" else "Series") + ": " + where,
                           "group": "Films" if k == "films" else "Series", "on": i not in off,
                           "state": "ok" if i not in off else "off", "state_label": "Looked at" if i not in off else "Left alone",
                           "actions": ["toggle"]} for i, t, k, where in libs]}
    return {"type": "list", "title": "Holding folder",
            "intro": f"{len(held)} items in media/.holding/library-cleanup, 38.7 GB. Put back returns each to where it was, and Reelix "
                     "follows it again. Nothing here is deleted; to free the space for good, delete them yourself.",
            "items": [{**h, "state": "off", "state_label": "In holding", "actions": ["restore"]} for h in held]}


def cleanup(data_dir):
    if absent:
        return
    if not any(p["id"] == "library-cleanup" for p in plugins_admin.listing(data_dir)):
        plugins_admin.install(data_dir, json.loads(json.dumps(MANIFEST)), "/nonexistent-media")
        plugins_admin.keep_logo(data_dir, "library-cleanup", plugin_logo.clean((HERE / "library-cleanup" / "logo.svg").read_bytes(), "logo.svg"))
        plugins_admin.set_state(data_dir, "library-cleanup", "enabled")
    real_call, real_ask, real_answer = plugin_custom.call, plugin_watch._ask, plugin_cards.answer
    held, off = list(HELD), {"children"}

    def call(data_dir_, pid, key, body=None, opener=None):
        if pid != "library-cleanup":
            return real_call(data_dir_, pid, key, body, opener)
        said = None
        if body is not None and body.get("action") == "restore":
            gone = next((h for h in held if h["id"] == body.get("id")), None)
            if gone:
                held.remove(gone)
                said = f"Put back {gone['title']}. This is example data, so nothing moved"
        if body is not None and body.get("action") == "toggle":
            lid = str(body.get("id") or "")
            said = "The rules look at this library again" if lid in off else "The rules leave this library alone"
            off.symmetric_difference_update({lid})
        out = plugin_custom.clean(screen(key, held, off))
        if body is not None:
            out["said"] = said or "This is example data, so nothing changed"
        return out

    def answer(d, pid, cid, opener=None):
        if pid != "library-cleanup":
            return real_answer(d, pid, cid, opener)
        active = any(x["key"] == "active" and x["value"] for x in plugins_admin.public_settings(d, "library-cleanup"))
        card = ({"value": 41553759436, "label": "in the holding folder", "note": "3 items held. Next look in quiet hours",
                 "status": "scheduled", "status_label": "Next in quiet hours"} if active else
                {"value": 41553759436, "label": "in the holding folder", "note": "Deactivated. Preview: 3 items, 24.5 GB",
                 "status": "inactive", "status_label": "Deactivated"})
        return {"type": "stat", "format": "bytes", "asked": int(time.time()),
                "data": plugin_cards.clean("stat", {**card, "updated": int(time.time()) - 300})}

    plugin_custom.call = call
    plugin_cards.answer = answer
    plugin_watch._ask = lambda pid, main, path: "ok" if pid == "library-cleanup" else real_ask(pid, main, path)


ex._example_library_cleanup = cleanup
ex.main()
