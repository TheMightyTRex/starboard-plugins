#!/usr/bin/env python3
"""Keeps the Picture shrinker in step with the Jellyfin version (DASH-433; SYNC.md in
the picture-shrinker folder of TheMightyTRex/jellyfin-plugins). Copies that folder's rules.json to picture-shrinker/rules.json and
its shared test pictures (tests/pictures) to tests/picture-shrinker-shared, or with --check says what differs and
exits 1.

  python3 tools/sync_picture_rules.py [--check] [JELLYFIN_PICTURE_SHRINKER_FOLDER]
The folder defaults to ~/src/jellyfin-plugins/picture-shrinker.
"""
import filecmp
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
RULES = os.path.join(ROOT, "picture-shrinker", "rules.json")
SHARED = os.path.join(ROOT, "tests", "picture-shrinker-shared")


def files(top):
    out = set()
    for folder, _, names in os.walk(top):
        for n in names:
            out.add(os.path.relpath(os.path.join(folder, n), top))
    return out


def differences(src):
    diffs = []
    if not filecmp.cmp(os.path.join(src, "rules.json"), RULES, shallow=False) if os.path.exists(RULES) else True:
        diffs.append("picture-shrinker/rules.json")
    theirs, ours = os.path.join(src, "tests", "pictures"), SHARED
    a, b = files(theirs), files(ours) if os.path.isdir(ours) else set()
    diffs += [f"missing: {f}" for f in sorted(a - b)] + [f"extra: {f}" for f in sorted(b - a)]
    diffs += [f"differs: {f}" for f in sorted(a & b) if not filecmp.cmp(os.path.join(theirs, f), os.path.join(ours, f), shallow=False)]
    return diffs


def main(argv):
    check = "--check" in argv
    args = [a for a in argv if a != "--check"]
    src = os.path.abspath(os.path.expanduser(args[0] if args else "~/src/jellyfin-plugins/picture-shrinker"))
    if not os.path.isfile(os.path.join(src, "rules.json")):
        sys.exit(f"No rules.json in {src}")
    diffs = differences(src)
    if check:
        for d in diffs:
            print(d)
        print("In step with the Jellyfin version" if not diffs else f"{len(diffs)} differences: run tools/sync_picture_rules.py")
        return 1 if diffs else 0
    shutil.copyfile(os.path.join(src, "rules.json"), RULES)
    if os.path.isdir(SHARED):
        shutil.rmtree(SHARED)
    shutil.copytree(os.path.join(src, "tests", "pictures"), SHARED)
    print(f"Copied rules.json and {len(files(SHARED))} shared test files from {src}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
