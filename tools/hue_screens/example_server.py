#!/usr/bin/env python3
"""Starboard's example server (made-up data) with the Philips Hue plug-in added and active, its calls sent to the
plug-in's real container on this computer, which talks to the made-up bridge (tests/hue_mock_bridge.py). For the
plug-in's pictures and its accessibility check (tools/hue_screens/run.sh).

    python3 tools/hue_screens/example_server.py <starboard checkout> <data folder> <port> <plug-in port>

Nothing real is read or changed: no Hue bridge, no Jellyfin. 20 November 2026."""
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent.parent.parent
starboard, data, port, plugin_port = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
sys.path.insert(0, str(pathlib.Path(starboard) / "tools" / "screenshots"))
sys.argv = ["example_server.py", data, port]
import example_server as ex  # noqa: E402  (Starboard's example server: its set-up runs on import, main() below)
from starboard import plugin_cards, plugin_logo, plugin_watch, plugins_admin  # noqa: E402

MANIFEST = json.loads((HERE / "philips-hue" / "starboard-plugin.json").read_text())
# Installed as published: an image pinned by digest (this one is made up), on the port the test container listens on.
MANIFEST["containers"][0].update(image="ghcr.io/themightytrex/starboard-plugin-philips-hue@sha256:" + "e" * 64, port=plugin_port)


def hue(data_dir):
    if not any(p["id"] == "philips-hue" for p in plugins_admin.listing(data_dir)):
        plugins_admin.install(data_dir, json.loads(json.dumps(MANIFEST)), "/nonexistent-media")
        plugins_admin.keep_logo(data_dir, "philips-hue", plugin_logo.clean((HERE / "philips-hue" / "logo.svg").read_bytes(), "logo.svg"))
        plugins_admin.set_state(data_dir, "philips-hue", "enabled")
    real_host, real_ask = plugin_cards._host, plugin_watch._ask
    plugin_cards._host = lambda pid, main, wake=True: "127.0.0.1" if pid == "philips-hue" else real_host(pid, main, wake)
    plugin_watch._ask = lambda pid, main, path: "ok" if pid == "philips-hue" else real_ask(pid, main, path)


ex._example_library_cleanup = hue
ex.main()
