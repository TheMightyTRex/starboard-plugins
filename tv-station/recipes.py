"""Style recipes (0.13.1, DASH-637): a channel's branding drawn on the owner's own server from a name, two colours and an optional
logo. A recipe is data: a few numbers and words that say how each part moves, drawn by one FFmpeg command at a time through
draw.py (one thread, the lowest priority, never while a channel is watched). Nothing leaves the home and nothing is fetched.

Every recipe is built under the same rules:
  - nothing flashes: only fades of 0.5 seconds or more and slides of 1 second or more, never an on and off change of the whole picture
  - the name is at least 72 pixels tall at 1080p and inside the title safe area (5 percent in from each edge)
  - the words are black or white, and the colour they sit on is made darker (or lighter) in small steps until they reach 7 to 1
  - A still variant has no movement at all, for people who ask for it: the same words, one picture
A made style holds 4 short title clips, 2 bumpers, the background for the Coming up next card, the background for coming-up
trailers (both still pictures, which a pack allows) and the on-screen logo.
"""
import json
import os
import shutil
import time

import dog
import draw
import kit
import pack

W, H = draw.W, draw.H
SAFE_W = pack.TITLE_SAFE[2] - pack.TITLE_SAFE[0]  # 1728
MIN_TEXT = 72  # pixels tall at 1080p
# name: what the page calls it; blurb: one line for the option card; bg: flat or gradient; motion: how the name arrives; deco: what is drawn with it
STYLES = {
    "clean": {"name": "Clean", "blurb": "A band of your second colour wipes across, then the name comes up on it.", "bg": "flat", "motion": "fade", "deco": "wipe"},
    "evening": {"name": "Evening", "blurb": "A slow blend of your two colours, and the name fades in and out softly.", "bg": "gradient", "motion": "slowfade", "deco": "none"},
    "retro": {"name": "Retro", "blurb": "A thin frame in your second colour, and the name slides in from the left.", "bg": "flat", "motion": "slide", "deco": "frame"},
    "bold": {"name": "Bold", "blurb": "A big name on a bar of your second colour that rises from the bottom.", "bg": "flat", "motion": "fade", "deco": "bar"},
    "plain": {"name": "Plain", "blurb": "Just the name on your main colour, fading in and out.", "bg": "flat", "motion": "fade", "deco": "none"},
}
# The four short title clips: where the name sits, how long the clip is. y is the fraction of the picture's height for the middle of the name.
VARIANTS = [{"x": "centre", "y": 0.5, "seconds": 6}, {"x": "left", "y": 0.5, "seconds": 5}, {"x": "centre", "y": 0.62, "seconds": 6}, {"x": "left", "y": 0.38, "seconds": 5}]
BUMPER_SECONDS = 1.5
STILL_AT = 2.4  # the moment a still preview is taken, when the name is in place


class StyleError(ValueError):
    pass


def text_size(name):
    """The name's size in pixels: as large as fits the title safe area, 170 at most, 72 at least."""
    return max(MIN_TEXT, min(170, int(SAFE_W * 0.93 / (0.56 * max(1, len(name))))))


def _mix(c, toward, share):
    rgb = [int(c[i:i + 2], 16) for i in (1, 3, 5)]
    goal = 255 if toward == "white" else 0
    return "#" + "".join(f"{round(v + (goal - v) * share):02X}" for v in rgb)


def _carry(style):
    """Which of the two colours the words sit on."""
    deco = STYLES[style]["deco"]
    if deco in ("wipe", "bar"):
        return ("c2",)
    return ("c1", "c2") if STYLES[style]["bg"] == "gradient" else ("c1",)


def plan(style, name, c1, c2):
    """What a style does with a name and two colours: {"c1", "c2", "ink", "size", "ratio", "adjusted"}. The words are black or white, whichever
    needs the colours they sit on changed least, and a colour is made darker (or lighter, under black words) in small steps until the words
    reach 7 to 1 on it (WCAG 1.4.6). "adjusted" lists the colours that had to change, for the page to say so."""
    colours = {"c1": c1, "c2": c2}
    best = None
    for ink, toward in (("#FFFFFF", "black"), ("#000000", "white")):
        got, steps = dict(colours), 0
        for key in _carry(style):
            share = 0.0
            while draw.contrast(ink, got[key]) < 7.0 and share < 1.0:
                share = round(share + 0.05, 2)
                got[key] = _mix(colours[key], toward, share)
            steps += share
        if best is None or steps < best[0]:
            best = (steps, ink, got)
    _, ink, got = best
    adjusted = [k for k in _carry(style) if got[k] != colours[k]]
    ratio = round(min(draw.contrast(ink, got[k]) for k in _carry(style)), 1)
    return {"c1": got["c1"], "c2": got["c2"], "ink": ink, "size": text_size(name), "ratio": ratio, "adjusted": adjusted}


def _alpha(motion, seconds):
    """drawtext's alpha as an expression of t: faded in and out (0.5 seconds, or 1 second for slowfade), or solid for a still."""
    f = 1.0 if motion == "slowfade" else 0.5
    return f"if(lt(t\\,{f})\\,t/{f}\\,if(gt(t\\,{seconds - f})\\,({seconds}-t)/{f}\\,1))"


def title_filters(style, name_file, name, c1, c2, variant=0, seconds=None, still=False):
    """The FFmpeg filter chain that draws a short title clip on a 1920 by 1080 picture, from [0:v]. still: no movement, the same words."""
    st, v = STYLES[style], VARIANTS[variant]
    seconds = seconds or v["seconds"]
    look = plan(style, name, c1, c2)
    c1, c2 = look["c1"], look["c2"]
    size = look["size"]
    left = v["x"] == "left"
    tx = f"{pack.TITLE_SAFE[0] + 24}" if left else "(w-tw)/2"
    ty = f"{int(H * v['y'])}-th/2"
    parts = []
    if not still and st["motion"] == "slide":
        tx = f"{pack.TITLE_SAFE[0] + 24}+700*pow(max(0\\,1-t/1)\\,2)" if left else f"(w-tw)/2-700*pow(max(0\\,1-t/1)\\,2)"
    alpha = "1" if still else _alpha(st["motion"], seconds)
    deco = st["deco"]
    if deco == "wipe":
        y0, bh = int(H * v["y"]) - size, size * 2
        x = "0" if still else "-1920+1920*min(1\\,t/1)"
        parts.append(f"drawbox=x='{x}':y={y0}:w=1920:h={bh}:color={draw.ffcolour(c2)}:t=fill")
    elif deco == "frame":
        parts.append(f"drawbox=x={pack.TITLE_SAFE[0]}:y={pack.TITLE_SAFE[1]}:w={SAFE_W}:h={pack.TITLE_SAFE[3] - pack.TITLE_SAFE[1]}:color={draw.ffcolour(c2)}:t=8")
    elif deco == "bar":
        bh = int(size * 2.2)
        y0 = int(H * v["y"]) - bh // 2
        y = f"{y0}" if still else f"{y0}+{H}*pow(max(0\\,1-t/1)\\,2)"
        parts.append(f"drawbox=x=0:y='{y}':w=1920:h={bh}:color={draw.ffcolour(c2)}:t=fill")
    box = ""
    parts.append(f"drawtext=fontfile={dog.FONT}:textfile={name_file}:expansion=none:fontsize={size}:fontcolor={draw.ffcolour(look['ink'])}:"
                 f"alpha='{alpha}':x='{tx}':y='{ty}'{box}")
    return ",".join(parts)


def source(style, c1, c2, seconds):
    """The picture's source as FFmpeg input arguments: one colour, or a slow blend of two."""
    if STYLES[style]["bg"] == "gradient":
        return ["-f", "lavfi", "-i", f"gradients=s={W}x{H}:c0={draw.ffcolour(c1)}:c1={draw.ffcolour(c2)}:x0=0:y0=0:x1={W}:y1={H}:speed=0.01:r={draw.FPS}:d={seconds}"]
    return ["-f", "lavfi", "-i", f"color=c={draw.ffcolour(c1)}:s={W}x{H}:r={draw.FPS}:d={seconds}"]


def _fade_edges(seconds, f=0.5):
    return f"fade=t=in:st=0:d={f},fade=t=out:st={seconds - f}:d={f}"


def title_clip(style, name, c1, c2, dst, folder, variant=0, still=False):
    """Draws one short title clip (a video, no sound) to dst."""
    st, v = STYLES[style], VARIANTS[variant]
    words = draw.text_file(name, folder)
    look = plan(style, name, c1, c2)
    try:
        chain = title_filters(style, words, name, c1, c2, variant, still=still)
        draw.ff(*source(style, look["c1"], look["c2"], v["seconds"]), "-vf", f"{chain},format=yuv420p", "-an", "-t", str(v["seconds"]), *draw.H264, dst)
    finally:
        os.remove(words)


def title_still(style, name, c1, c2, dst, folder, variant=0, part="title", width=960):
    """One picture to look at before any video is made: the title clip at its middle, a bumper, or the Coming up next card. PNG, `width` wide."""
    if part == "title":
        words = draw.text_file(name, folder)
        look = plan(style, name, c1, c2)
        try:
            chain = title_filters(style, words, name, c1, c2, variant, still=True)
            draw.ff(*source(style, look["c1"], look["c2"], 1), "-vf", f"{chain},scale={width}:-2:flags=area", "-frames:v", "1", dst)
        finally:
            os.remove(words)
    elif part == "bumper":
        draw.ff(*source(style, c1, c2, 1), "-vf", _bumper_chain(c1, c2, still=True) + f",scale={width}:-2:flags=area", "-frames:v", "1", dst)
    elif part == "card":
        card_background(style, name, c1, c2, dst, folder, "coming_next", width=width)
    else:
        raise StyleError("That part has no picture")
    return dst


def _bumper_chain(c1, c2, still=False):
    """A bar of the second colour sweeps across in a second and a half and goes out the other side. In a still it is half way."""
    if still:
        return f"drawbox=x=400:y=0:w=1100:h={H}:color={draw.ffcolour(c2)}:t=fill"
    return f"drawbox=x='-1100+3000*min(1\\,t/{BUMPER_SECONDS})':y=0:w=1100:h={H}:color={draw.ffcolour(c2)}:t=fill"


def bumper(style, c1, c2, dst, variant=0):
    """A short silent bumper: a wide bar of the second colour sweeps across the main colour. Variant 1 sweeps the other way."""
    chain = _bumper_chain(c1, c2)
    if variant == 1:
        chain = chain + ",hflip"
    draw.ff(*source(style, c1, c2, BUMPER_SECONDS), "-vf", f"{chain},{_fade_edges(BUMPER_SECONDS, 0.3)},format=yuv420p", "-an", "-t", str(BUMPER_SECONDS), *draw.H264, dst)


def card_background(style, name, c1, c2, dst, folder, part, width=W):
    """The background of the Coming up next card or the coming-up trailers: the style's colours, the clip area framed in the second colour, the
    name small in a corner. A picture, which a pack allows. The words and the clip are put on it by the plug-in, in the places pack.json gives."""
    lay = pack.DEFAULT_LAYOUT[part]
    x0, y0, x1, y1 = lay["clip"]
    b = 8
    words = draw.text_file(name, folder)
    look = plan(style, name, c1, c2)
    c1, c2 = look["c1"], look["c2"]
    ink, _, _ = draw.text_colour(c1, c2 if STYLES[style]["bg"] == "gradient" else c1)
    try:
        frame = (f"drawbox=x={x0 - b}:y={y0 - b}:w={x1 - x0 + 2 * b}:h={y1 - y0 + 2 * b}:color={draw.ffcolour(c2)}:t=fill,"
                 f"drawbox=x={x0}:y={y0}:w={x1 - x0}:h={y1 - y0}:color=black:t=fill,"
                 f"drawbox=x={pack.TITLE_SAFE[0]}:y={int(H * 0.925)}:w={SAFE_W}:h=8:color={draw.ffcolour(c2)}:t=fill")
        label = (f"drawtext=fontfile={dog.FONT}:textfile={words}:expansion=none:fontsize={MIN_TEXT}:fontcolor={draw.ffcolour(ink)}:"
                 f"x={pack.TITLE_SAFE[2]}-tw:y={int(H * 0.925) - 100}")
        draw.ff(*source(style, c1, c2, 1), "-vf", f"{frame},{label},scale={width}:-2:flags=area", "-frames:v", "1", dst)
    finally:
        os.remove(words)


# The whole style -------------------------------------------------------------------------------------------------
def licence(name, style, made_on, logo_given):
    return (f"{name}: where this came from\n" + "=" * (len(name) + 24) + "\n\n"
            f"Made on {made_on} on the owner's own server by Create your own TV channel, from the style recipe {STYLES[style]['name']}, the channel's name and two colours.\n"
            + ("The on-screen logo is a picture the owner added.\n" if logo_given else "The on-screen logo is the channel's name drawn by the recipe.\n") +
            "\nThe recipes are the work of TheMightyTRexUK, and the files they draw are free to use under the MIT licence:\n\n"
            "MIT License\n\nCopyright (c) 2026 TheMightyTRexUK\n\n"
            "Permission is hereby granted, free of charge, to any person obtaining a copy of these files, to use, copy, modify, merge, publish, distribute, "
            "sublicense, and/or sell copies of them, and to permit persons to whom they are furnished to do so, subject to the following condition: "
            "the above copyright notice and this permission notice shall be included in all copies or substantial portions of the files.\n\n"
            "THE FILES ARE PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED. IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER "
            "LIABILITY ARISING FROM THEIR USE.\n")


def make(out, style, name, colours, made_on, logo=None, still=False, progress=lambda step, of, words: None):
    """Makes the pack for a style in `out` (made empty first), one FFmpeg command at a time. logo: the path of a PNG the owner added, or None to
    draw the name. still: the title clips and bumpers hold still (a picture for the whole clip)."""
    if style not in STYLES:
        raise StyleError("Choose one of the styles")
    name = draw.clean_words(name, 40)
    if not name:
        raise StyleError("Give the channel a name")
    c1, c2 = draw.colour(colours[0], "#10202C"), draw.colour(colours[1], "#1B8A7F")
    shutil.rmtree(out, ignore_errors=True)
    for sub in ("logo", "idents", "bumpers", "coming-next", "promo"):
        os.makedirs(os.path.join(out, sub))
    total = 1 + len(VARIANTS) + 2 + 2
    n = 0

    def tick(words):
        nonlocal n
        n += 1
        progress(n, total, words)

    look = plan(style, name, c1, c2)
    c1, c2 = look["c1"], look["c2"]
    tick("Drawing the logo")
    if logo:
        draw.ff("-i", logo, "-vf", "scale='min(iw,iw*200/ih)':'min(ih,200)':flags=lanczos:force_original_aspect_ratio=decrease,format=rgba", "-map_metadata", "-1",
                "-frames:v", "1", os.path.join(out, "logo", "dog.png"))
    else:
        draw.text_logo(name, look["ink"], look[_carry(style)[0]], os.path.join(out, "logo", "dog.png"), out)
    for i in range(len(VARIANTS)):
        tick(f"Drawing short title clip {i + 1} of {len(VARIANTS)}")
        title_clip(style, name, c1, c2, os.path.join(out, "idents", f"ident{i + 1:02d}.mp4"), out, variant=i, still=still)
    for i in range(2):
        tick(f"Drawing bumper {i + 1} of 2")
        bumper(style, c1, c2, os.path.join(out, "bumpers", f"bumper{i + 1:02d}.mp4"), variant=i)
    tick("Drawing the Coming up next card")
    card_background(style, name, c1, c2, os.path.join(out, "coming-next", "background.png"), out, "coming_next")
    tick("Drawing the trailer background")
    card_background(style, name, c1, c2, os.path.join(out, "promo", "background.png"), out, "promo")
    doc = pack.template_pack_json(name)
    doc.update({"made": made_on[:40], "author": "Create your own TV channel", "colours": {"text": draw.text_colour(look["c1"], look["c1"])[0], "accent": look["c2"]},
                "logo": {"dog": "logo/dog.png"}, "idents": [f"ident{i + 1:02d}.mp4" for i in range(len(VARIANTS))],
                "bumpers": ["bumper01.mp4", "bumper02.mp4"], "transitions": []})
    doc.pop("animation", None)
    for part, folder in (("coming_next", "coming-next"), ("promo", "promo")):
        doc[part]["background"] = f"{folder}/background.png"
        doc[part].pop("music", None)
    doc["transitions"] = []
    kit.write_json(os.path.join(out, "pack.json"), doc)
    with open(os.path.join(out, "LICENCE.txt"), "w", encoding="utf-8") as f:
        f.write(licence(name, style, made_on, bool(logo)))
    with open(os.path.join(out, "kit.json"), "w", encoding="utf-8") as f:
        json.dump({"kit": 1, "name": name, "colours": [c1, c2], "style": style, "files": {}}, f, indent=1)
        f.write("\n")
    return out
