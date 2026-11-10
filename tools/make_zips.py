#!/usr/bin/env python3
"""Makes zips/<plug-in>.zip from each plug-in folder, the same bytes every time. With --check, says whether any zip
is out of date instead (run before each commit)."""
import io
import os
import sys
import zipfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def build(name):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for n in sorted(os.listdir(os.path.join(ROOT, name))):
            info = zipfile.ZipInfo(f"{name}/{n}", date_time=(2026, 1, 1, 0, 0, 0))
            info.external_attr = (0o755 if n.endswith(".py") else 0o644) << 16
            with open(os.path.join(ROOT, name, n), "rb") as f:
                z.writestr(info, f.read(), zipfile.ZIP_DEFLATED)
    return out.getvalue()


def main():
    check = "--check" in sys.argv
    stale = []
    for name in sorted(os.listdir(ROOT)):
        if not os.path.isfile(os.path.join(ROOT, name, "starboard-plugin.json")):
            continue
        path = os.path.join(ROOT, "zips", f"{name}.zip")
        data = build(name)
        old = open(path, "rb").read() if os.path.exists(path) else None
        if old != data:
            stale.append(name)
            if not check:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "wb") as f:
                    f.write(data)
    if check and stale:
        print("Out of date: " + ", ".join(stale) + ". Run python3 tools/make_zips.py")
        return 1
    print("Zips up to date" if check else f"Made {len(stale)} zip(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
