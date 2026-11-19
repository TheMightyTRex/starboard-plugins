"""Animation on and off for what is drawn over the picture (0.3.0): the on-screen logo, the clock, the label, the
straps, the Coming up next and Later cards and the words on the holding slide.

Each animated thing is drawn on a small layer of its own, with a transparent background, and laid over the picture
by FFmpeg's overlay, whose position is an expression of t, the time into the piece. Fades use the fade filter on the
layer's transparency, a wipe moves a crop window over the layer, and Grow scales it from its centre. A layer whose
words never change is drawn once and repeated, so an animation costs little processor: the overlay of a small layer
for each frame, and a few filters only while it moves.

Timing is exact: a thing animates on from its start and is off by its end, so nothing ever runs past it. When the
animation would not fit (a thing shown for less than two animations), both are shortened to fit.

None is no layer at all: the filters are what they were before 0.3.0.
"""

FPS = 25

# Each way in, and its way off: the key is kept in settings and pack.json.
MOVES = {"none": ("None", "None"),
         "fade": ("Fade in", "Fade out"),
         "left": ("Slide in from the left", "Slide off to the left"),
         "right": ("Slide in from the right", "Slide off to the right"),
         "bottom": ("Slide up from the bottom", "Slide down off the bottom"),
         "wipe": ("Wipe on from the left", "Wipe off to the right"),
         "grow": ("Grow from the centre", "Shrink to the centre")}
SPEEDS = {"quick": 0.3, "normal": 0.6, "slow": 1.0}
SPEED_WORDS = {"quick": "Quick, 0.3 seconds", "normal": "Normal, 0.6 seconds", "slow": "Slow, 1 second"}
# What can animate, in the order the pages list them.
ITEMS = {"cards": "Coming up next and Later cards", "straps": "Straps", "logo": "On-screen logo", "clock": "Clock",
         "label": "New, Repeat or Live label", "holding": "Words on the holding slide"}
PARTS = ("in", "out", "speed")


def key(item, part):
    return f"anim_{item}_{part}"


def spec(opts, item):
    """{"in", "out", "d"} for one item from resolved options (dog.resolve); None when it does not animate."""
    i, o = opts.get(key(item, "in"), "none"), opts.get(key(item, "out"), "none")
    i, o = (i if i in MOVES else "none"), (o if o in MOVES else "none")
    if i == "none" and o == "none":
        return None
    return {"in": i, "out": o, "d": SPEEDS.get(opts.get(key(item, "speed")), SPEEDS["normal"])}


def fit(sp, t0, t1):
    """The animation fitted to a thing shown from t0 to t1, in seconds of this piece (t0 may be before 0, when the
    piece joins part way through). Returns {"in", "out", "t0", "t1", "din", "dout"}, or None for no animation:
    an animation on that has already begun is left out (the thing is simply there), as is one off that has."""
    if not sp or t1 <= max(0.0, t0):
        return None
    d = min(sp["d"], (t1 - t0) / 2)
    din = d if sp["in"] != "none" and t0 >= 0 and d >= 0.04 else 0.0
    dout = d if sp["out"] != "none" and t1 - d >= 0 and d >= 0.04 else 0.0
    if not din and not dout:
        return None
    return {"in": sp["in"] if din else "none", "out": sp["out"] if dout else "none", "t0": t0, "t1": t1, "din": din, "dout": dout}


def _n(v):
    return f"{v:.3f}".rstrip("0").rstrip(".") if v != int(v) else str(int(v))


def p_in(f):
    """0 before the animation on, rising to 1 at its end."""
    return f"clip((t-{_n(f['t0'])})/{_n(f['din'])},0,1)" if f["din"] else "1"


def p_out(f):
    """0 until the animation off starts, rising to 1 at the end of the thing."""
    return f"clip((t-{_n(f['t1'] - f['dout'])})/{_n(f['dout'])},0,1)" if f["dout"] else "0"


def ease_in(f):
    """Comes in fast and settles: 1 - (1 - p)^2."""
    return f"(1-pow(1-{p_in(f)},2))"


def ease_out(f):
    """Leaves slowly then fast: p^2."""
    return f"pow({p_out(f)},2)"


def layer_filters(f, lw=None, lh=None):
    """Filters on the layer (RGBA) for its animation: fade, grow (needs the layer's size) and wipe, in that order."""
    out = []
    if f["in"] == "fade":
        out.append(f"fade=t=in:st={_n(f['t0'])}:d={_n(f['din'])}:alpha=1")
    if f["out"] == "fade":
        out.append(f"fade=t=out:st={_n(f['t1'] - f['dout'])}:d={_n(f['dout'])}:alpha=1")
    if "grow" in (f["in"], f["out"]):
        s = "*".join(([ease_in(f)] if f["in"] == "grow" else []) + ([f"(1-{ease_out(f)})"] if f["out"] == "grow" else []))
        out.append(f"scale=w='max(2,trunc({lw}*{s}/2)*2)':h='max(2,trunc({lh}*{s}/2)*2)':eval=frame")
        out.append(f"pad={lw}:{lh}:'(ow-iw)/2':'(oh-ih)/2':color=black@0:eval=frame")
    if "wipe" in (f["in"], f["out"]):
        out.append("pad=3*iw:ih:iw:0:color=black@0")
        out.append(f"crop=iw/3:ih:x='iw/3*({_wipe(f)})':y=0")
    return out


def _wipe(f):
    """How far the wipe window has moved, 0 to 2: 0 to 1 while wiping on, 1 to 2 while wiping off."""
    return ("+".join([p_in(f) if f["in"] == "wipe" else "1"] + ([p_out(f)] if f["out"] == "wipe" else [])))


def position(f, x, y):
    """The overlay's x and y as expressions of t, for a layer whose resting place is x, y (numbers or expressions in
    W, H, w and h, as overlay takes them)."""
    xs, ys = [f"({x})"], [f"({y})"]
    if f["in"] == "left":
        xs.append(f"-(({x})+w)*(1-{ease_in(f)})")
    elif f["in"] == "right":
        xs.append(f"+(W-({x}))*(1-{ease_in(f)})")
    elif f["in"] == "bottom":
        ys.append(f"+(H-({y}))*(1-{ease_in(f)})")
    if f["out"] == "left":
        xs.append(f"-(({x})+w)*{ease_out(f)}")
    elif f["out"] == "right":
        xs.append(f"+(W-({x}))*{ease_out(f)}")
    elif f["out"] == "bottom":
        ys.append(f"+(H-({y}))*{ease_out(f)}")
    if "wipe" in (f["in"], f["out"]):
        xs.append(f"-w+w*({_wipe(f)})")
    return "".join(xs), "".join(ys)


def enable(f):
    """Shown from its start to its end, and not a frame past it."""
    if f["t0"] > 0:
        return f"between(t,{_n(f['t0'])},{_n(f['t1'])})"
    return f"lt(t,{_n(f['t1'])})"


def overlay(f, x, y):
    """The overlay filter that lays an animated layer on the picture."""
    ox, oy = position(f, x, y)
    return f"overlay=x='{ox}':y='{oy}':format=auto:enable='{enable(f)}'"


def canvas(w, h):
    """A transparent layer of w by h, for words drawn on it: YUV with transparency, as the picture is, so laying it over
    needs no conversion for each frame (measured: an RGBA card layer cost a quarter more processor)."""
    return f"color=c=black@0:s={int(w)}x{int(h)}:r={FPS},format=yuva420p"


# Drawn once and repeated: for a layer whose words never change, so its words are not drawn again for every frame.
HOLD = f"trim=end_frame=1,loop=loop=-1:size=1:start=0,setpts=N/{FPS}/TB"
