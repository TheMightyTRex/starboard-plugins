"""The break grids (0.8.0, DASH-537; owner, 23 November 2026: "add two types of grid with a drag and drop ... One for
In between programs and one for Breaks ... 7 columns with a selection for Random, Sequence, Day of week, Morning,
Afternoon, Evening and the columns change based on that setting; a list of items you drag into each column").

A channel has two grids:
  between  what plays after each programme, before the next one starts
  inside   what plays in a break inside a programme

Each grid is {"mode", "count", "columns"}. The mode says how a break chooses its column:
  random    one of the first `count` columns, at random (the same airing always gets the same one)
  sequence  the first `count` columns in turn, round and round
  day       Monday to Sunday: the column of the weekday the break is on
  time      Morning (before 12:00), Afternoon (12:00 to 17:59) and Evening (from 18:00)
`columns` always holds 7 lists, so changing the mode never loses what was placed: the columns the mode does not use
are kept, not shown, and come back when the mode does. A column is a list of items, {"kind", "times"}, played in order.

Everything here is a pure function on the document, so the page, the plan and the tests share one set of rules.
Without a saved grid a channel keeps the order it always had (schedule.plan_break), and the page shows that order as
its starting grid (default_between, default_inside): nothing is saved until a change is made.
"""
import copy
import time

MODES = ("random", "sequence", "day", "time")
MODE_WORDS = {"random": "Random", "sequence": "Sequence", "day": "Day of week", "time": "Morning, afternoon and evening"}
MODE_HELP = {
    "random": "Each break picks one of its columns at random. Each column is an alternative.",
    "sequence": "The columns play in order, column 1 first, then 2, and so on, and then round again.",
    "day": "Each break plays the column for the day it is on, Monday to Sunday.",
    "time": "Each break plays the column for the time of day: morning before 12:00, afternoon from 12:00, evening from 18:00.",
}
DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
TIME_NAMES = ("Morning", "Afternoon", "Evening")
MOST_COLUMNS = 7
MOST_ITEMS = 12  # in one column
MOST_TIMES = 6  # one kind in one place
GRIDS = ("between", "inside")
GRID_WORDS = {"between": "In between programmes", "inside": "Breaks"}

# kind -> (words on the page, takes a number of times, what it is)
KINDS = {
    "bumper": ("Bumper", True, "A very short version of the ident with no music, from the broadcast pack."),
    "promo": ("Promo", True, "A promo, a trailer or one of your clips, chosen at random. Each plays once at most in a break."),
    "adverts": ("Adverts", True, "One of your extra videos, chosen at random."),
    "ident": ("Ident", True, "An ident, with its music."),
    "other_promo": ("Other channel promo", True, "A promo for a programme on one of your other channels."),
    "coming_promo": ("Coming soon promo", True, "A Coming soon promo for a programme on this channel."),
    "holding": ("Holding countdown", False, "The holding slide with the time to the programme's start. It takes the time that is left, "
                                           "and the clock counts through anything that plays after it."),
    "back_soon": ("Back soon", False, "The holding slide with Back soon. It takes the time that is left."),
}
ELASTIC = ("holding", "back_soon")  # one at most in a column: they take the time the rest leaves
ORDER = tuple(KINDS)


class GridError(ValueError):
    pass


def kinds_words():
    """For the page: each kind, its words, whether it takes a number, and what it is."""
    return [{"kind": k, "name": KINDS[k][0], "times": KINDS[k][1], "about": KINDS[k][2]} for k in ORDER]


def shown(grid):
    """How many columns the grid's mode uses."""
    mode = grid.get("mode")
    return 7 if mode == "day" else 3 if mode == "time" else max(1, min(MOST_COLUMNS, int(grid.get("count") or 1)))


def column_names(grid):
    mode = grid.get("mode")
    if mode == "day":
        return list(DAY_NAMES)
    if mode == "time":
        return list(TIME_NAMES)
    return [f"Column {i + 1}" for i in range(shown(grid))]


def new_grid(mode="random", columns=None, count=1):
    cols = [list(c) for c in (columns or [])][:MOST_COLUMNS]
    cols += [[] for _ in range(MOST_COLUMNS - len(cols))]
    return {"version": 1, "mode": mode, "count": max(1, min(MOST_COLUMNS, int(count))), "columns": cols}


def clean_item(it):
    """One item as kept, or None when it is not one."""
    if not isinstance(it, dict) or it.get("kind") not in KINDS:
        return None
    kind = it["kind"]
    if not KINDS[kind][1]:
        return {"kind": kind, "times": 1}
    try:
        times = int(it.get("times") or 1)
    except (TypeError, ValueError):
        times = 1
    return {"kind": kind, "times": max(1, min(MOST_TIMES, times))}


def clean(doc):
    """A grid read from the plug-in's own file, made safe: a mode it knows, 7 columns, only items that exist, one
    holding slide at most in a column, and not too many."""
    if not isinstance(doc, dict):
        return None
    mode = doc.get("mode") if doc.get("mode") in MODES else "random"
    cols = []
    for c in (doc.get("columns") or [])[:MOST_COLUMNS]:
        got, elastic = [], False
        for it in c if isinstance(c, list) else []:
            it = clean_item(it)
            if not it or len(got) >= MOST_ITEMS:
                continue
            if it["kind"] in ELASTIC:
                if elastic:
                    continue
                elastic = True
            got.append(it)
        cols.append(got)
    return new_grid(mode, cols, doc.get("count") or 1)


# What a channel has had all along -------------------------------------------------------------------------------------
def default_between(ch):
    """The order a channel's breaks between programmes have always had (0.5.0): a bumper, its promos, trailers and
    clips (up to the number chosen in Promos and clips in each break), one extra video, the holding slide, and an
    ident. Shown as the grid's starting point; nothing is saved until the owner changes it."""
    n = max(1, min(MOST_TIMES, int(ch.get("per_break") or 3)))
    col = [{"kind": "bumper", "times": 1}, {"kind": "promo", "times": n}, {"kind": "adverts", "times": 1},
           {"kind": "holding", "times": 1}, {"kind": "ident", "times": 1}]
    return new_grid("random", [col], 1)


def default_inside(ch):
    """A break inside a programme as it has been since 0.5.0: a bumper, promos, trailers and clips, one extra video,
    the holding slide with Back soon, and a bumper."""
    n = max(1, min(MOST_TIMES, int(ch.get("per_break") or 3)))
    col = [{"kind": "bumper", "times": 1}, {"kind": "promo", "times": n}, {"kind": "adverts", "times": 1},
           {"kind": "back_soon", "times": 1}, {"kind": "bumper", "times": 1}]
    return new_grid("random", [col], 1)


def grid_of(ch, which):
    """The grid in use for a channel: its saved one, or None when it has none (the classic order)."""
    return clean((ch.get("break_grids") or {}).get(which))


def view_of(ch, which):
    """The grid the page shows: the saved one, or the channel's classic order as a starting point."""
    return grid_of(ch, which) or (default_between(ch) if which == "between" else default_inside(ch))


# Choosing a column ---------------------------------------------------------------------------------------------------
def time_column(t):
    h = time.localtime(t).tm_hour
    return 0 if h < 12 else 1 if h < 18 else 2


def column_index(grid, t, slot_no, pick, part=0):
    """Which of the grid's columns a break at time t uses. pick: a number from the channel's own random generator,
    used by Random. slot_no and part: the programme's place in the line-up and which break inside it this is, so
    Sequence goes round and round."""
    mode = grid["mode"]
    n = shown(grid)
    if mode == "day":
        return time.localtime(t).tm_wday
    if mode == "time":
        return time_column(t)
    if mode == "sequence":
        return (int(slot_no) + int(part)) % n
    return int(pick) % n


def column_for(grid, t, slot_no, pick, part=0):
    return grid["columns"][column_index(grid, t, slot_no, pick, part)]


# Changes, each a pure function on a grid ------------------------------------------------------------------------------
def _col(grid, c):
    try:
        c = int(c)
    except (TypeError, ValueError):
        raise GridError("Choose a column")
    if not 0 <= c < shown(grid):
        raise GridError(f"There is no column {c + 1}")
    return c


def _at(col, p):
    try:
        p = int(p)
    except (TypeError, ValueError):
        raise GridError("Choose a place in the column")
    return max(0, min(len(col), p))


def _room(col, item, skip=None):
    rest = [x for i, x in enumerate(col) if i != skip]
    if len(rest) >= MOST_ITEMS:
        raise GridError(f"A column holds at most {MOST_ITEMS} items")
    if item["kind"] in ELASTIC and any(x["kind"] in ELASTIC for x in rest):
        raise GridError("A column has one holding slide at most: it takes the time that is left")


def apply(grid, op):
    """The grid after one change, which is a dict: {"op": ...}. Raises GridError with a sentence when it cannot be done.
    ops: mode (mode), count (count), add (kind, column, position), move (column, index, to_column, to_position),
    remove (column, index), times (column, index, times), clear (column)."""
    g = copy.deepcopy(grid)
    kind = op.get("op")
    if kind == "mode":
        if op.get("mode") not in MODES:
            raise GridError("Choose Random, Sequence, Day of week, or Morning, afternoon and evening")
        g["mode"] = op["mode"]
    elif kind == "count":
        try:
            n = int(op.get("count"))
        except (TypeError, ValueError):
            raise GridError("Choose how many columns")
        if g["mode"] not in ("random", "sequence"):
            raise GridError("Day of week and Morning, afternoon and evening have a set number of columns")
        if not 1 <= n <= MOST_COLUMNS:
            raise GridError(f"A grid has 1 to {MOST_COLUMNS} columns")
        g["count"] = n
    elif kind == "add":
        item = clean_item({"kind": op.get("kind"), "times": op.get("times") or 1})
        if not item:
            raise GridError("Choose what to add")
        c = _col(g, op.get("column"))
        col = g["columns"][c]
        _room(col, item)
        col.insert(_at(col, op.get("position", len(col))), item)
    elif kind == "move":
        c = _col(g, op.get("column"))
        src = g["columns"][c]
        try:
            i = int(op.get("index"))
        except (TypeError, ValueError):
            raise GridError("Choose an item")
        if not 0 <= i < len(src):
            raise GridError("That item is not there")
        dc = _col(g, op.get("to_column", c))
        item = src[i]
        dest = g["columns"][dc]
        _room(dest, item, skip=i if dc == c else None)
        src.pop(i)
        dest.insert(_at(dest, op.get("to_position", len(dest))), item)
    elif kind in ("remove", "times"):
        c = _col(g, op.get("column"))
        col = g["columns"][c]
        try:
            i = int(op.get("index"))
        except (TypeError, ValueError):
            raise GridError("Choose an item")
        if not 0 <= i < len(col):
            raise GridError("That item is not there")
        if kind == "remove":
            col.pop(i)
        else:
            if not KINDS[col[i]["kind"]][1]:
                raise GridError(f"{KINDS[col[i]['kind']][0]} has no number of times: it is shown once")
            col[i] = clean_item({"kind": col[i]["kind"], "times": op.get("times")})
    elif kind == "clear":
        g["columns"][_col(g, op.get("column"))] = []
    else:
        raise GridError("That change is not known")
    return g


def item_words(it):
    name = KINDS[it["kind"]][0]
    return f"{name}, {it['times']} times" if KINDS[it["kind"]][1] and it["times"] > 1 else name


def column_words(grid, c):
    """One column in a sentence, for the page's summary and the live region."""
    col = grid["columns"][c]
    return ", ".join(item_words(x) for x in col) if col else "empty"
