#!/usr/bin/env python3
"""Keeps the two audio description plug-ins in step with the Jellyfin version (SYNC.md in the audio-description folder
of TheMightyTRex/jellyfin-plugins). Copies that folder's rules.json to audio-description/rules.json and audio-description-tracks/rules.json, or with --check
says which differ and exits 1.

  python3 tools/sync_audio_description_rules.py [--check] [JELLYFIN_PLUGIN_FOLDER]
The folder defaults to ~/src/jellyfin-plugins/audio-description.
"""
import filecmp
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
COPIES = [os.path.join(ROOT, pid, "rules.json") for pid in ("audio-description", "audio-description-tracks")]
DEFAULT = "~/src/jellyfin-plugins/audio-description"


def source(args):
    folder = os.path.abspath(os.path.expanduser(args[0] if args else DEFAULT))
    if not os.path.isfile(os.path.join(folder, "rules.json")):
        sys.exit(f"No rules.json in {folder}")
    return os.path.join(folder, "rules.json")


def main(argv):
    check = "--check" in argv
    src = source([a for a in argv if a != "--check"])
    diffs = [os.path.relpath(c, ROOT) for c in COPIES if not os.path.exists(c) or not filecmp.cmp(src, c, shallow=False)]
    if check:
        for d in diffs:
            print(d)
        print("In step with the Jellyfin version" if not diffs else f"{len(diffs)} differences: run tools/sync_audio_description_rules.py")
        return 1 if diffs else 0
    for c in COPIES:
        shutil.copyfile(src, c)
    print(f"Copied rules.json from {src} to {len(COPIES)} plug-ins")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
