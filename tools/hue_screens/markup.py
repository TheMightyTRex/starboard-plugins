#!/usr/bin/env python3
"""Philips Hue's help pictures (help/images/philips-hue), marked up from the pictures tools/hue_screens/run.sh takes
(tools/hue_screens/out), in the style of Starboard's annotate.js: a red outline 5 pixels clear of what it marks and a
red step badge with the article's step number.

    python3 tools/hue_screens/markup.py

The boxes are in the pictures' own pixels, measured on the pictures of 20 November 2026: after run.sh takes them
again, check each box still sits on what it marks, then check every picture by eye before committing.
"""
import pathlib
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
SRC = ROOT / "tools" / "hue_screens" / "out"
OUT = ROOT / "help" / "images" / "philips-hue"
RED, GAP, STROKE, BADGE = "#C71F1F", 5, 3, 13
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# name: (source, crop box or None, [(box (x0, y0, x1, y1) in the source, step number or None)])
SHOTS = {
    "install-1-pair": ("1-bridge-not-paired", None, [((21, 287, 1107, 383), 2)]),
    "install-2-link-button": ("2-bridge-waiting-for-button", None, [((21, 108, 1107, 204), 3)]),
    "install-3-paired": ("3-bridge-paired", None, [((21, 108, 1107, 208), 4), ((21, 420, 1107, 490), None)]),
    "settings-1-rooms": ("4-rooms", (0, 0, 1128, 700), [((21, 195, 1107, 242), None), ((21, 615, 1107, 685), None)]),
    "settings-2-kitchen": ("5-room-kitchen", (0, 0, 1128, 830), [((21, 478, 1107, 545), None), ((21, 590, 1107, 655), None),
                                                                  ((21, 742, 1107, 806), None)]),
    "settings-3-schedules": ("16-schedules", None, [((21, 600, 1107, 756), None), ((836, 294, 914, 318), None)]),
    "settings-4-when-something-plays": ("17-when-something-plays", None, [((21, 106, 1107, 170), None), ((21, 206, 441, 388), None)]),
    "dashboard-card-1-both": ("18-dashboard-cards", (100, 698, 1268, 1075), [((120, 710, 676, 1062), None), ((692, 710, 1248, 858), None)]),
    "dashboard-card-2-rooms": ("18-dashboard-cards", (100, 698, 696, 1075), [((120, 710, 676, 1062), None)]),
    "dashboard-card-3-lights-on": ("18-dashboard-cards", (672, 698, 1268, 872), [((692, 710, 1248, 858), None)]),
}


def mark(name, source, crop, marks):
    img = Image.open(SRC / f"{source}.png").convert("RGB")
    ox, oy = (crop[0], crop[1]) if crop else (0, 0)
    if crop:
        img = img.crop(crop)
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, 14)
    w, h = img.size
    for (x0, y0, x1, y1), step in marks:
        box = (max(STROKE, x0 - ox - GAP), max(STROKE, y0 - oy - GAP), min(w - STROKE, x1 - ox + GAP), min(h - STROKE, y1 - oy + GAP))
        d.rounded_rectangle(box, radius=4, outline=RED, width=STROKE)
        if step is not None:
            spots = [(box[0], box[1]), (box[2], box[1]), (box[0], box[3]), (box[2], box[3])]
            bx, by = next(((x, y) for x, y in spots if BADGE <= x <= w - BADGE and BADGE <= y <= h - BADGE), spots[0])
            d.ellipse((bx - BADGE, by - BADGE, bx + BADGE, by + BADGE), fill=RED, outline="#fff", width=2)
            d.text((bx, by), str(step), fill="#fff", font=font, anchor="mm")
    OUT.mkdir(parents=True, exist_ok=True)
    img.save(OUT / f"{name}.png", optimize=True)


def main():
    missing = sorted({s for s, _, _ in SHOTS.values() if not (SRC / f"{s}.png").exists()})
    if missing:
        print("Take the pictures first with tools/hue_screens/run.sh; missing:", ", ".join(missing), file=sys.stderr)
        return 1
    for name, (source, crop, marks) in SHOTS.items():
        mark(name, source, crop, marks)
        print(f"help/images/philips-hue/{name}.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
