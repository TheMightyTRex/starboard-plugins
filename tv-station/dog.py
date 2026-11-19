"""The on-screen logo (the DOG, or bug), the straps and the cards, as FFmpeg filters.

Everything drawn has enough contrast on any picture: text always has a dark outline, and the backing plate (on by
default) puts a dark, partly transparent box behind the logo, the clock and the labels. Cards darken their picture
to a third of its brightness, so white text on them is at least 7 to 1 whatever the picture.
"""
import os
import textwrap
import time

FONT = os.environ.get("TV_FONT", os.path.join(os.path.dirname(os.path.abspath(__file__)), "atkinson-hyperlegible-next.woff2"))

# The station's defaults: each channel may set its own, or keep these ("" on the channel).
DEFAULTS = {"kind": "channel_logo", "corner": "top_right", "size": "medium", "margin": "medium", "opacity": 80,
            "when": "always", "fade_in": 0, "clock": False, "label": "none", "plate": True,
            "strap_start": True, "strap_end": True, "strap_seconds": 30, "cards": True}
KINDS = {"channel_logo": "The channel's logo", "channel_name": "The channel's name", "station_name": "The station's name",
         "none": "No on-screen logo"}
CORNERS = {"top_right": "Top right", "top_left": "Top left", "bottom_right": "Bottom right", "bottom_left": "Bottom left"}
SIZES = {"small": 0.06, "medium": 0.085, "large": 0.12}  # of the picture's height
MARGINS = {"small": 0.025, "medium": 0.05, "large": 0.075}  # medium: inside a television's safe area
WHEN = {"always": "Always", "programmes": "Only during programmes", "programmes_cards": "Programmes and cards, not clips"}
LABELS = {"none": "No label", "new_repeat": "New or Repeat", "live": "Live"}
PLATE = "black@0.55"
OUTLINE = "black@0.8"


def resolve(settings, ch=None):
    """The options for one channel: the channel's own where it has one, else the station's setting, else the default."""
    out = {}
    own = (ch or {}).get("dog") or {}
    for k, d in DEFAULTS.items():
        v = own.get(k, "")
        if v in ("", None):
            v = settings.get(f"dog_{k}", "")
        if v in ("", None):
            v = d
        if isinstance(d, bool):
            v = v if isinstance(v, bool) else str(v).lower() in ("1", "true", "yes", "on")
        elif isinstance(d, int):
            try:
                v = int(v)
            except (TypeError, ValueError):
                v = d
        out[k] = v
    out["opacity"] = max(30, min(100, out["opacity"]))
    out["strap_seconds"] = max(5, min(120, out["strap_seconds"]))
    for k, allowed in (("kind", KINDS), ("corner", CORNERS), ("size", SIZES), ("margin", MARGINS), ("when", WHEN), ("label", LABELS)):
        if out[k] not in allowed:
            out[k] = DEFAULTS[k]
    return out


def needs_encoding(opts):
    """A programme can be copied as it is, with no converting, only when nothing is drawn on it."""
    return not (opts["kind"] != "none" or opts["clock"] or opts["label"] != "none" or opts["strap_start"] or opts["strap_end"])


def shows_on(opts, kind):
    """Whether the DOG shows on a piece of this kind: programme, clip (idents and trailers), card or slate."""
    if opts["kind"] == "none":
        return False
    if opts["when"] == "always":
        return True
    if opts["when"] == "programmes_cards":
        return kind in ("programme", "card", "slate", "holding")
    return kind == "programme"


def when_words(t, now=None):
    """The date and time a programme is shown, in words: "Today at 18:30", "Tomorrow at 06:00",
    "Saturday 22 November at 21:00"."""
    now = time.time() if now is None else now
    lt, ln = time.localtime(t), time.localtime(now)
    day = (time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1)) - time.mktime((ln.tm_year, ln.tm_mon, ln.tm_mday, 0, 0, 0, 0, 0, -1))) / 86400
    hm = time.strftime("%H:%M", lt)
    if round(day) == 0:
        return f"Today at {hm}"
    if round(day) == 1:
        return f"Tomorrow at {hm}"
    return f"{time.strftime('%A', lt)} {lt.tm_mday} {time.strftime('%B', lt)} at {hm}"


class Texts:
    """Text for drawtext goes in small files, so no title can break the filter (a colon or a quote in a title)."""

    def __init__(self, folder):
        self.folder = folder
        self.n = 0
        os.makedirs(folder, exist_ok=True)

    def file(self, words):
        self.n += 1
        path = os.path.join(self.folder, f"t{self.n}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(str(words).replace("\r", " ").replace("\n", " "))  # expansion=none: drawn as it is
        return path


def _text(path, size, x, y, colour="white", plate=False, enable=None, alpha=1.0, border=True):
    parts = [f"fontfile={FONT}", f"textfile={path}", "expansion=none", f"fontsize={int(size)}",
             f"fontcolor={colour}@{alpha:.2f}", f"x={x}", f"y={y}"]
    if border:
        parts += [f"borderw={max(1, int(size / 16))}", f"bordercolor={OUTLINE}"]
    if plate:
        parts += ["box=1", f"boxcolor={PLATE}", f"boxborderw={max(4, int(size / 3))}"]
    if enable:
        parts.append(f"enable='{enable}'")
    return "drawtext=" + ":".join(parts)


def _clock(size, x, y, plate, alpha):
    parts = [f"fontfile={FONT}", r"text='%{localtime\:%H\\\:%M}'", f"fontsize={int(size)}", f"fontcolor=white@{alpha:.2f}",
             f"x={x}", f"y={y}", f"borderw={max(1, int(size / 16))}", f"bordercolor={OUTLINE}"]
    if plate:
        parts += ["box=1", f"boxcolor={PLATE}", f"boxborderw={max(4, int(size / 3))}"]
    return "drawtext=" + ":".join(parts)


def _xy(corner, margin, w="w", h="h", tw="tw", th="th", mx=None):
    """Where a thing sits in a corner: `margin` from the top or bottom, and `mx` (the same unless given) from the side."""
    mx = margin if mx is None else mx
    x = f"{w}-{tw}-{mx}" if corner.endswith("right") else f"{mx}"
    y = f"{margin}" if corner.startswith("top") else f"{h}-{th}-{margin}"
    return x, y


def overlay_chain(opts, W, H, kind, texts, names, logo=None, rel=0.0, programme=None):
    """The filters drawn over one piece, after the picture is scaled to W x H.

    kind:      programme, clip, card or slate
    names:     {"channel": ..., "station": ...}
    logo:      the channel's logo as a PNG file, for the channel_logo kind (the channel's name is drawn without one)
    rel:       for a programme, how far into it this piece starts, in seconds (a mid-programme join)
    programme: for a programme, {"duration", "start_words", "next_words", "label"}
    Returns (filters on the picture as a list of strings, the logo input's filter or None).
    """
    chain, logo_filter = [], None
    margin = int(H * MARGINS[opts["margin"]])
    mx = int(W * MARGINS[opts["margin"]])  # the same share of the width from the side, so medium is inside the safe area
    size_h = int(H * SIZES[opts["size"]])
    alpha = opts["opacity"] / 100.0
    plate = opts["plate"]
    show = shows_on(opts, kind)
    fade_at = None
    if kind == "programme" and opts["fade_in"]:
        fade_at = max(0.0, opts["fade_in"] - rel)
    enable_dog = f"gte(t,{fade_at:.2f})" if fade_at else None
    dog_kind = opts["kind"]
    if dog_kind == "channel_logo" and not logo:
        dog_kind = "channel_name"
    if show and dog_kind == "channel_logo":
        pad = max(4, size_h // 6) if plate else 0
        f = f"scale=-1:{size_h - 2 * pad},format=rgba"
        if plate:
            f += f",pad=iw+{2 * pad}:ih+{2 * pad}:{pad}:{pad}:color={PLATE}"
        f += f",colorchannelmixer=aa={alpha:.2f}"
        if fade_at:
            f += f",fade=t=in:st={fade_at:.2f}:d=1:alpha=1"
        logo_filter = f
    elif show and dog_kind in ("channel_name", "station_name"):
        words = names["channel"] if dog_kind == "channel_name" else names["station"]
        x, y = _xy(opts["corner"], margin, mx=mx)
        chain.append(_text(texts.file(words), size_h * 0.62, x, y, plate=plate, enable=enable_dog, alpha=alpha))
    # The clock and the label sit beside the DOG, away from the edge it is on.
    below = opts["corner"].startswith("top")
    step = size_h + int(H * 0.012)
    small = H * 0.034
    row = 1
    if opts["clock"] and (show or opts["kind"] == "none"):
        x, _ = _xy(opts["corner"], margin, mx=mx)
        y = f"{margin + step}" if below else f"h-th-{margin + step}"
        chain.append(_clock(small, x, y, plate, alpha))
        row += 1
    if kind == "programme" and opts["label"] != "none" and programme and programme.get("label"):
        until = 120 - rel
        if until > 0:
            x, _ = _xy(opts["corner"], margin, mx=mx)
            off = margin + step + (int(small * 1.8) if row > 1 else 0)
            y = f"{off}" if below else f"h-th-{off}"
            chain.append(_text(texts.file(programme["label"]), small, x, y, plate=True, enable=f"lt(t,{until:.2f})"))
    # Straps: the programme's name for its first seconds, and Up next during the end credits.
    if kind == "programme" and programme:
        strap_corner = "bottom_right" if opts["corner"] == "bottom_left" else "bottom_left"
        x, y = _xy(strap_corner, margin, mx=mx)
        if opts["strap_start"] and programme.get("start_words") and rel < 8:
            chain.append(_text(texts.file(programme["start_words"]), H * 0.042, x, y, plate=True, enable=f"lt(t,{8 - rel:.2f})"))
        if opts["strap_end"] and programme.get("next_words"):
            s = programme["duration"] - opts["strap_seconds"] - rel
            e = programme["duration"] - 1 - rel
            if e > 0:
                chain.append(_text(texts.file(programme["next_words"]), H * 0.042, x, y, plate=True,
                                   enable=f"between(t,{max(0.0, s):.2f},{e:.2f})"))
    return chain, logo_filter


def logo_position(opts, W, H):
    margin = int(H * MARGINS[opts["margin"]])
    mx = int(W * MARGINS[opts["margin"]])
    x = f"W-w-{mx}" if opts["corner"].endswith("right") else f"{mx}"
    y = f"{margin}" if opts["corner"].startswith("top") else f"H-h-{margin}"
    return x, y


def card_chain(W, H, texts, card, colour="0x1f5f99"):
    """A Coming up next or Later card: the programme's picture darkened, its title, when it is shown and a short
    synopsis. card: {"kicker", "title", "episode", "when", "plot", "footer"}."""
    left = int(W * 0.08)
    out = [f"colorchannelmixer=rr=0.33:gg=0.33:bb=0.33",
           f"drawbox=x={left}:y={int(H * 0.2)}:w={int(H * 0.012)}:h={int(H * 0.06)}:color={colour}:t=fill"]
    y = int(H * 0.2)
    pad = int(H * 0.03)

    def line(words, size, colour="white"):
        nonlocal y
        out.append(_text(texts.file(words), size, left + pad, y, colour=colour))
        y += int(size * 1.35)

    line(card["kicker"], H * 0.05)
    y += int(H * 0.02)
    line(card["title"], H * 0.08)
    if card.get("episode"):
        line(card["episode"], H * 0.045)
    line(card["when"], H * 0.045)
    y += int(H * 0.02)
    for wrapped in textwrap.wrap(card.get("plot") or "", 64)[:3]:
        line(wrapped, H * 0.036)
    if card.get("footer"):
        out.append(_text(texts.file(card["footer"]), H * 0.032, left + pad, f"h-th-{int(H * 0.08)}"))
    return out


def slate_chain(W, H, texts, words):
    return [_text(texts.file(words), H * 0.06, "(w-tw)/2", "(h-th)/2")]


HOLDING_WORDS = {"countdown": "A countdown to the next programme", "back_soon": "Back soon", "none": "No words"}


def countdown_text(seconds):
    """The words of a countdown for drawtext with expansion: "Next programme in 4:32", counting down from `seconds`
    as the piece plays (t is the time into this FFmpeg run), rounded up, so it reads 0:01 in its last second."""
    left = f"max(0,{float(seconds):.3f}-t)"
    return f"Next programme in %{{eif:trunc(({left}+0.999)/60):d}}:%{{eif:mod(trunc({left}+0.999),60):d:2}}"


def holding_chain(W, H, texts, words, next_title="", seconds=0.0):
    """The words on a holding slide, low in the middle on a plate so they read on any picture: Back soon, or a
    countdown to the next programme with its name under it. words: countdown, back_soon or none."""
    if words not in ("countdown", "back_soon"):
        return []
    size = H * 0.06
    y = int(H * 0.72)
    if words == "back_soon":
        return [_text(texts.file("Back soon"), size, "(w-tw)/2", y, plate=True)]
    parts = [f"fontfile={FONT}", f"textfile={texts.file(countdown_text(seconds))}", "expansion=normal", f"fontsize={int(size)}",
             "fontcolor=white@1.00", "x=(w-tw)/2", f"y={y}", f"borderw={max(1, int(size / 16))}", f"bordercolor={OUTLINE}",
             "box=1", f"boxcolor={PLATE}", f"boxborderw={max(4, int(size / 3))}"]
    out = ["drawtext=" + ":".join(parts)]
    if next_title:
        out.append(_text(texts.file(next_title[:60]), H * 0.042, "(w-tw)/2", int(y + size * 1.9), plate=True))
    return out


# Broadcast packs: words drawn into the boxes pack.json gives ---------------------------------------------------------
CHAR_WIDTH = 0.56  # Atkinson Hyperlegible Next's average letter, as a share of its size (measured on mixed-case titles)
LINE_GAP = 1.22


def fit_lines(words, box_w, box_h, lines):
    """The largest size the words fit a box at, on up to `lines` lines: (size, [line, ...]). A short title fills the
    box on one line; a long one takes more lines, smaller. Words that cannot fit at the smallest size are cut, with
    an ellipsis."""
    words = " ".join(str(words or "").split())

    def size_for(n):
        return max(12.0, 0.85 * box_h / (n * LINE_GAP - (LINE_GAP - 1)))  # a little room for the tails of g, p and y

    one = min(size_for(1), box_w / max(1, len(words) * CHAR_WIDTH))  # on one line, as large as its width allows
    if words and (one >= size_for(2) or (lines == 1 and one >= size_for(1) * 0.45)):
        return one, [words]
    for n in range(1, max(1, lines) + 1):
        size = size_for(n)
        got = textwrap.wrap(words, max(4, int(box_w / (size * CHAR_WIDTH)))) or [""]
        if len(got) <= n:
            return size, got
    size = size_for(lines)
    floor = max(12.0, size * 0.45)
    while True:
        per = max(4, int(box_w / (size * CHAR_WIDTH)))
        got = textwrap.wrap(words, per) or [""]
        if len(got) <= lines or size <= floor:
            break
        size *= 0.92
    if len(got) > lines:
        got = got[:lines]
        got[-1] = got[-1][: max(1, per - 1)].rstrip() + "\u2026"
    return size, got


def box_text(texts, words, style, sx=1.0, sy=1.0):
    """Drawtext filters for one field: style {"box": [x0, y0, x1, y1] in 1920 by 1080, "colour", "align", "lines"};
    sx and sy scale the box to the picture's size."""
    x0, y0, x1, y1 = style["box"]
    x0, x1, y0, y1 = x0 * sx, x1 * sx, y0 * sy, y1 * sy
    size, got = fit_lines(words, x1 - x0, y1 - y0, int(style.get("lines") or 1))
    colour = "0x" + str(style.get("colour") or "#FFFFFF").lstrip("#")
    out = []
    for i, line in enumerate(got):
        if not line:
            continue
        x = {"centre": f"{int(x0)}+({int(x1 - x0)}-tw)/2", "right": f"{int(x1)}-tw"}.get(style.get("align"), f"{int(x0)}")
        out.append(_text(texts.file(line), size, x, int(y0 + i * size * LINE_GAP), colour=colour))
    return out


def day_time_words(t):
    """The day and time in words that stay true all week: "Sunday at 21:00". For promos, made days before they play."""
    lt = time.localtime(t)
    return f"{time.strftime('%A', lt)} at {time.strftime('%H:%M', lt)}"
