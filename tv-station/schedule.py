"""The schedule: what each channel shows at any moment, worked out from time, never stored or streamed.

The idea comes from Clickarr (github.com/thegregstengel/clickarr, MIT): a channel is a function from time to
programme. Its inputs are small and kept: a frozen line-up (each programme and how long it runs), the time the
line-up started, and a seed. With the same inputs, every question about the same moment gets the same answer, so
the guide, the dashboard card and the stream always agree, and nothing runs between viewings. No code is copied.

A channel has eras. An era is one line-up from a moment on. When the line-up changes (new episodes, or the owner
changes what the channel shows), a new era starts at the end of the programme on air then, carrying on from the
programme that would have come next, so the channel never jumps part way through a programme.

Times are seconds since 1970 (UTC). Local time is used only for words people read.
"""
import bisect
import hashlib
import math

import breakgrid

SCHEDULER_VERSION = 1
MASK = (1 << 64) - 1
CARD_SECONDS = 10  # one Coming up next or Later card
CARD_MAX = 20  # the longest one card stays on screen
MIN_PIECE = 1.0  # a gap shorter than this is left as a short pause at the end of the programme


# A small random number generator of our own (SplitMix64), so a shuffle is the same on every computer and every
# Python version, which random.Random does not promise.
class Rng:
    def __init__(self, seed):
        self.state = int(seed) & MASK

    def next(self):
        self.state = (self.state + 0x9E3779B97F4A7C15) & MASK
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK
        return z ^ (z >> 31)

    def below(self, n):
        return self.next() % n if n > 0 else 0


def seed_of(*parts):
    """A 64-bit number from any values, the same everywhere."""
    h = hashlib.sha256("\x1f".join(str(p) for p in parts).encode()).digest()
    return int.from_bytes(h[:8], "big")


def shuffled(items, seed):
    out = list(items)
    rng = Rng(seed)
    for i in range(len(out) - 1, 0, -1):
        j = rng.below(i + 1)
        out[i], out[j] = out[j], out[i]
    return out


def group_runs(entries, run):
    """Each series' episodes in their order, cut into runs of `run` in a row. A film is a run of its own."""
    groups, order = {}, []
    for i, e in enumerate(entries):
        g = e.get("group") or e["id"]
        if g not in groups:
            groups[g] = []
            order.append(g)
        groups[g].append(i)
    n = max(1, int(run or 1))
    return [[groups[g][k:k + n] for k in range(0, len(groups[g]), n)] for g in order]


def cycle_order(entries, order, run, seed, cycle):
    """The order of the line-up's programmes in one cycle, as positions in `entries`.
    In order: each series' runs in turn (A1 A2, B1 B2, A3 A4 ...). Shuffled: the runs in a new order each cycle."""
    groups = group_runs(entries, run)
    if order == "shuffle":
        runs = [r for g in groups for r in g]
        return [i for r in shuffled(runs, seed_of(seed, cycle)) for i in r]
    out, k = [], 0
    while True:
        took = False
        for g in groups:
            if k < len(g):
                out.extend(g[k])
                took = True
        if not took:
            return out
        k += 1


def slot_length(duration, start_on, break_seconds=0):
    """How long a programme's slot is. Back to back (start_on 0): the programme and the break after it. On the
    quarter, half or whole hour (15, 30 or 60): rounded up to the next one, and the break fills the rest."""
    need = max(1.0, float(duration)) + max(0, int(break_seconds or 0))
    if not start_on:
        return need
    grid = int(start_on) * 60
    return float(math.ceil(need / grid - 1e-9) * grid)


def floor_to(t, start_on):
    if not start_on:
        return float(int(t))
    grid = int(start_on) * 60
    return float(int(t // grid) * grid)


class Era:
    """One line-up from `start` on. `skip` is how many programmes of the first cycle are passed over, so a new era
    carries on where the one before it was."""

    def __init__(self, spec):
        self.start = float(spec["from"])
        self.entries = spec.get("lineup") or []
        self.seed = spec.get("seed", 0)
        self.order = spec.get("order", "in_order")
        self.run = int(spec.get("run") or 1)
        self.start_on = int(spec.get("start_on") or 0)
        self.break_seconds = int(spec.get("break_seconds") or 0)
        self.skip = int(spec.get("skip") or 0)
        self.slots = [slot_length(e["dur"], self.start_on, self.break_seconds) for e in self.entries]
        self.length = sum(self.slots)
        self._cache = {}

    def _cycle(self, cycle):
        got = self._cache.get(cycle)
        if got is None:
            order = cycle_order(self.entries, self.order, self.run, self.seed, cycle)
            sums, t = [], 0.0
            for i in order:
                sums.append(t)
                t += self.slots[i]
            got = (order, sums)
            if len(self._cache) > 8:
                self._cache.clear()
            self._cache[cycle] = got
        return got

    def offset0(self):
        if not self.entries:
            return 0.0
        order, sums = self._cycle(0)
        return sums[self.skip % len(order)] if order else 0.0

    def airing(self, t):
        """The programme in its slot at time t: a dict, or None before the era or with an empty line-up."""
        if not self.entries or self.length <= 0 or t < self.start:
            return None
        e = (t - self.start) + self.offset0()
        cycle = int(e // self.length)
        within = e - cycle * self.length
        order, sums = self._cycle(cycle)
        pos = bisect.bisect_right(sums, within) - 1
        slot_start = t - (within - sums[pos])
        idx = order[pos]
        entry = self.entries[idx]
        dur = float(entry["dur"])
        end = slot_start + self.slots[idx]
        return {"entry": entry, "start": slot_start, "content_end": min(slot_start + dur, end), "end": end,
                "cycle": cycle, "pos": pos, "slot_no": cycle * len(order) + pos}

    def next_entry_id(self, t):
        """The programme that follows the one on air at t."""
        a = self.airing(t)
        if not a:
            return None
        nxt = self.airing(a["end"])
        return nxt["entry"]["id"] if nxt else None


class Channel:
    """A channel's eras, from its kept settings: {"eras": [...], ...}."""

    def __init__(self, spec):
        self.spec = spec
        self.eras = sorted((Era(e) for e in spec.get("eras") or []), key=lambda e: e.start)
        self._starts = [e.start for e in self.eras]

    def era_at(self, t):
        i = bisect.bisect_right(self._starts, t) - 1
        return self.eras[i] if i >= 0 else None

    def airing(self, t):
        era = self.era_at(t)
        a = era.airing(t) if era else None
        if a is None:
            return None
        # A later era cuts this slot short only if it starts inside it (it never does when made by new_era).
        i = self.eras.index(era)
        if i + 1 < len(self.eras) and self.eras[i + 1].start < a["end"]:
            a["end"] = self.eras[i + 1].start
            a["content_end"] = min(a["content_end"], a["end"])
        return a

    def airings(self, start, stop, limit=2000):
        """Every slot that overlaps [start, stop), in order."""
        out, t = [], float(start)
        while t < stop and len(out) < limit:
            a = self.airing(t)
            if a is None:
                era = next((e for e in self.eras if e.start > t), None)
                if not era:
                    break
                t = era.start
                continue
            out.append(a)
            t = a["end"] if a["end"] > t else t + 1
        return out


def new_era(spec, lineup, now, settings_changed=False):
    """The channel's eras with a new line-up starting at the end of the programme on air at `now` (or at once, on the
    next boundary, when nothing is on). Carries on from the programme that would have come next when it is still in
    the new line-up. Returns the new list of eras; drops the ones that ended over a day ago."""
    ch = Channel(spec)
    a = ch.airing(now)
    order = spec.get("order", "in_order")
    start_on = int(spec.get("start_on") or 0)
    if a:
        start = a["end"]
        era = ch.era_at(now)
        nxt = era.airing(a["end"]) if era else None
        follow = nxt["entry"]["id"] if nxt else None
    else:
        start = floor_to(now, start_on) if start_on else float(int(now))
        follow = None
    era = {"from": start, "lineup": lineup, "seed": spec.get("seed", 0), "order": order, "run": int(spec.get("run") or 1),
           "start_on": start_on, "break_seconds": int(spec.get("break_seconds") or 0), "skip": 0}
    if follow and lineup:
        first = cycle_order(lineup, order, era["run"], era["seed"], 0)
        where = {lineup[i]["id"]: k for k, i in enumerate(first)}
        era["skip"] = where.get(follow, 0)
    keep = [e for e in spec.get("eras") or [] if float(e["from"]) < start]
    # Drop eras that a later one replaced over a day ago: they can never be asked about again.
    while len(keep) > 1 and float(keep[1]["from"]) < now - 86400:
        keep.pop(0)
    return keep + [era]


# What a refresh may change in a programme already in a line-up (0.5.5): its details, never what the timing rests on
# (its id, length, series or kind), so the schedule stays exactly as it was.
DETAIL_KEYS = ("audio_n", "audio_langs", "has_audio", "title", "ep", "s", "e", "plot", "year", "premiere", "genres", "art", "backdrop")


def refresh_details(eras, entries):
    """Brings the programmes in every era up to date from a fresh read of Jellyfin, by id: the DETAIL_KEYS change, and
    the sound field from before 0.5.4 ("audio", Jellyfin's Index) goes. Returns how many programmes changed."""
    fresh = {e["id"]: e for e in entries}
    changed = 0
    for era in eras or []:
        for e in era.get("lineup") or []:
            f = fresh.get(e.get("id"))
            if not f:
                continue
            new = {k: f[k] for k in DETAIL_KEYS if k in f}
            gone = "audio_langs" in e and "audio_langs" not in f  # 0.6.0: kept only for a file with several sound tracks
            if any(e.get(k) != v for k, v in new.items()) or "audio" in e or gone:
                e.update(new)
                e.pop("audio", None)
                if gone:
                    e.pop("audio_langs")
                changed += 1
    return changed


def lineup_hash(lineup):
    return hashlib.sha256("|".join(f"{e['id']}:{round(float(e['dur']), 1)}" for e in lineup).encode()).hexdigest()[:16]


# Breaks -------------------------------------------------------------------------------------------------------------
MID_LEAST = 20.0  # a break inside a programme shorter than this (bumpers and clips) is left out (0.4.0)
END_ROOM = 15.0  # the end break keeps at least this, past its bumpers and ident, when breaks inside take their time


def _pick(items, rng, last=None):
    choice = [c for c in items if c.get("id") != last] or items
    return choice[rng.below(len(choice))]


def _fill(fillers, extras, room, rng, most):
    """The promos, trailers and clips for a break (0.5.0): up to `most` of them, each once, in a random order, then one
    extra video at random. Only those that fit in `room` seconds. most None: as many as fit, repeating (before 0.5.0)."""
    picked, used = [], 0.0
    if most is None:
        last = None
        while fillers:
            fits = [c for c in fillers if c["dur"] <= room - used and (c["id"] != last or len(fillers) == 1)]
            if not fits:
                break
            c = fits[rng.below(len(fits))]
            picked.append((c, "filler"))
            used += float(c["dur"])
            last = c["id"]
    else:
        pool = list(fillers)
        while pool and len(picked) < int(most):
            fits = [c for c in pool if c["dur"] <= room - used]
            if not fits:
                break
            c = fits[rng.below(len(fits))]
            pool = [x for x in pool if x["id"] != c["id"]]
            picked.append((c, "filler"))
            used += float(c["dur"])
    fits = [c for c in extras or [] if c.get("dur", 0) > 0 and c["dur"] <= room - used]
    if fits:
        c = fits[rng.below(len(fits))]
        picked.append((c, "extra"))
        used += float(c["dur"])
    return picked


def plan_break(airing, after, clips, options):
    """The pieces that fill the gap between a programme's end and the next programme. The same airing always gets
    the same break.

    after:   the next few airings (the first is the programme after this one), for the cards
    clips:   {"idents": [...], "fillers": [...], "extras": [...], "bumpers": [...], "sting": {...} or None,
             "random_idents": False, "holding": {...} or None}, each clip {"id", "dur", "title", "src"}; a promo filler
             also has "airs", when its programme starts
    options: {"ident_order": "in_order" | "random", "cards": True, "seed": ..., "fill_most": 3}

    The order (owner, 19 November 2026, 0.5.0): a bumper; promos, trailers and clips, up to fill_most of them, each
    once; one of the owner's extra videos at random; the holding slide to the end (or Later and Coming up next cards,
    or a slate); and one ident with its music immediately before the new programme. The ident comes from the idents (a
    pack's in a random order), else the pack's logo with music. When the gap is short the ident comes first, then the
    bumper. A promo is only shown before its programme has started.
    """
    t, end = airing["content_end"], airing["end"]
    gap = end - t
    out = []
    if gap < MIN_PIECE:
        return out
    slot_no = airing["slot_no"]
    rng = Rng(seed_of(options.get("seed", 0), "break", int(airing["start"]), slot_no))
    holding = clips.get("holding")
    idents = [c for c in clips.get("idents") or [] if c.get("dur", 0) > 0]
    fillers = [c for c in clips.get("fillers") or [] if c.get("dur", 0) > 0 and float(c.get("airs") or end + 1) > end]
    bumpers = [c for c in clips.get("bumpers") or [] if c.get("dur", 0) > 0]
    sting = clips.get("sting") if clips.get("sting") and float(clips["sting"].get("dur") or 0) > 0 else None

    ident = None
    if idents:
        in_order = options.get("ident_order", "in_order") == "in_order" and not clips.get("random_idents")
        ident = idents[slot_no % len(idents)] if in_order else idents[rng.below(len(idents))]
    elif sting:
        ident = sting
    if ident and float(ident["dur"]) > gap:
        ident = None
    stop = end - (float(ident["dur"]) if ident else 0.0)  # where the middle of the break ends
    opening = _pick(bumpers, rng) if bumpers else None
    if opening and float(opening["dur"]) > stop - t:
        opening = None
    cards = bool(options.get("cards", True)) and bool(after) and not holding

    def add(kind, dur, **more):
        nonlocal t
        out.append({"kind": kind, "start": t, "end": t + dur, **more})
        t += dur

    if opening:
        add("clip", float(opening["dur"]), clip=opening, role="bumper")
    reserve = min(CARD_SECONDS, max(0.0, stop - t)) if cards else 0.0
    for c, role in _fill(fillers, clips.get("extras"), stop - t - reserve, rng, options.get("fill_most")):
        add("clip", float(c["dur"]), clip=c, role=role)
    left = stop - t
    if left >= MIN_PIECE:
        if holding:
            add("holding", left, holding=holding, airing=after[0] if after else None)
        elif not cards:
            add("slate", left)
        else:
            # Later cards first, each for a programme after the next one, then Coming up next for the rest.
            later = list(after[1:])
            k = 0
            while left > CARD_MAX and later:
                add("card", min(CARD_MAX, left - CARD_SECONDS), card="later", airing=later[k % len(later)])
                k += 1
                left = stop - t
            while left > CARD_MAX * 2:  # nothing later to show: Coming up next again, in turns
                add("card", CARD_MAX, card="next", airing=after[0])
                left = stop - t
            add("card", left, card="next", airing=after[0])
    elif out and left > 0:
        out[-1]["end"] = stop
        t = stop
    elif left > 0:
        t = stop  # under a second before the ident: a short pause at the end of the programme
    if ident:
        add("clip", float(ident["dur"]), clip=ident, role="ident")
    if out:
        out[-1]["end"] = end
    return out


def plan_mid_break(t, most, clips, seed, fill_most=None):
    """A break inside a programme (0.4.0; 0.5.0 order): from t for at most `most` seconds, a bumper, promos, trailers
    and clips (up to fill_most, each once), one extra video, the holding slide with Back soon for the rest, and a
    bumper; no ident. Without a holding slide it is as long as what plays. Empty when no promo, clip or extra video
    fits, so the programme carries on."""
    rng = Rng(seed)
    end = t + most
    fillers = [c for c in clips.get("fillers") or [] if c.get("dur", 0) > 0 and float(c.get("airs") or end + 1) > end]
    bumpers = [c for c in clips.get("bumpers") or [] if c.get("dur", 0) > 0]
    opening = _pick(bumpers, rng) if bumpers else None
    closing = _pick(bumpers, rng, opening["id"]) if bumpers else None
    ends = (float(opening["dur"]) + float(closing["dur"])) if bumpers else 0.0
    picked = _fill(fillers, clips.get("extras"), most - ends, rng, fill_most)
    if not picked:
        return []
    out = []
    seq = ([{"kind": "clip", "clip": opening, "role": "bumper", "dur": float(opening["dur"])}] if opening else [])
    seq += [{"kind": "clip", "clip": c, "role": role, "dur": float(c["dur"])} for c, role in picked]
    used = sum(x["dur"] for x in seq) + (float(closing["dur"]) if closing else 0.0)
    holding = clips.get("holding")
    if holding and most - used >= MIN_PIECE:
        seq.append({"kind": "holding", "holding": {**holding, "words": "back_soon" if holding.get("words") != "none" else "none"},
                    "airing": None, "dur": most - used})
    if closing:
        seq.append({"kind": "clip", "clip": closing, "role": "bumper", "dur": float(closing["dur"])})
    for x in seq:
        d = x.pop("dur")
        out.append({**x, "start": t, "end": t + d, "mid": True})
        t += d
    return out


# Breaks from a grid (0.8.0, DASH-537) ----------------------------------------------------------------------------------
PRIORITY = {"ident": 0, "bumper": 1, "adverts": 2, "promo": 3, "other_promo": 3, "coming_promo": 3}  # 0 is the last to go
CLIP_ROLES = {"bumper": "bumper", "ident": "ident", "adverts": "extra"}


def resolve_column(column, clips, options, rng, end, slot_no, longest):
    """A grid column's items as what plays: [(kind, clip)], in order; a holding item gives (kind, None). Each promo,
    clip or extra video plays once at most in a break, and a bumper or ident is not the same twice running when there
    is another. An item with nothing to draw from is left out, and so is a clip longer than `longest`."""
    cid = options.get("cid")
    fillers = [c for c in clips.get("fillers") or [] if c.get("dur", 0) > 0 and float(c.get("airs") or end + 1) > end]
    made = [c for c in fillers if c.get("role") == "promo"]
    idents = [c for c in clips.get("idents") or [] if c.get("dur", 0) > 0]
    sting = clips.get("sting") if clips.get("sting") and float(clips["sting"].get("dur") or 0) > 0 else None
    pools = {"bumper": [c for c in clips.get("bumpers") or [] if c.get("dur", 0) > 0], "ident": idents or ([sting] if sting else []),
             "adverts": [c for c in clips.get("extras") or [] if c.get("dur", 0) > 0], "promo": fillers,
             "other_promo": [c for c in made if c.get("cid") != cid], "coming_promo": [c for c in made if c.get("cid") == cid]}
    in_order = options.get("ident_order", "in_order") == "in_order" and not clips.get("random_idents") and bool(idents)
    used, last, played, out = set(), {}, 0, []
    for it in column:
        kind = it["kind"]
        if kind in breakgrid.ELASTIC:
            out.append((kind, None))
            continue
        for _ in range(int(it.get("times") or 1)):
            pool = [c for c in pools[kind] if float(c["dur"]) <= longest]
            if kind in ("bumper", "ident"):
                pool = [c for c in pool if c["id"] != last.get(kind)] or pool
            else:
                pool = [c for c in pool if c["id"] not in used]
            if not pool:
                break
            if kind == "ident" and in_order:
                c = idents[(slot_no + played) % len(idents)]
                if float(c["dur"]) > longest:
                    break
            else:
                c = pool[rng.below(len(pool))]
            used.add(c["id"])
            last[kind] = c["id"]
            played += kind == "ident"
            out.append((kind, c))
    return out


def trim(seq, room, soft=0.0):
    """The sequence with its clips fitting in `room` seconds: while they do not, the last of the least wanted goes
    (promos, then extra videos, then bumpers; an ident is the last to go). `soft` more seconds are kept free (for cards)
    by taking away anything but an ident."""
    seq = list(seq)
    for limit, only in ((room, False), (room - soft, True)):
        while sum(float(c["dur"]) for _, c in seq if c) > limit:
            cands = [(PRIORITY.get(k, 3), j) for j, (k, c) in enumerate(seq) if c and not (only and k == "ident")]
            if not cands:
                break
            seq.pop(max(cands)[1])
    return seq


def lay_out(start, seq, fill, left):
    """Pieces from `start`: each clip for its own length and, where the sequence has (kind, None), whatever fill(t, left,
    kind) gives for the `left` seconds, which the clips do not take."""
    out, t = [], start
    for kind, c in seq:
        if c:
            out.append({"kind": "clip", "start": t, "end": t + float(c["dur"]), "clip": c, "role": CLIP_ROLES.get(kind, "filler")})
        elif left >= MIN_PIECE:
            for piece in fill(t, left, kind) or []:
                out.append(piece)
            t = out[-1]["end"] if out else t
            continue
        t = out[-1]["end"] if out else t
    return out


def _cards_fill(after):
    """Later and Coming up next cards for `left` seconds (the classic break's fill)."""
    def fill(t, left, kind):
        out, stop, k = [], t + left, 0
        later = list(after[1:])
        while stop - t > CARD_MAX and later:
            d = min(CARD_MAX, stop - t - CARD_SECONDS)
            out.append({"kind": "card", "start": t, "end": t + d, "card": "later", "airing": later[k % len(later)]})
            t += d
            k += 1
        while stop - t > CARD_MAX * 2:
            out.append({"kind": "card", "start": t, "end": t + CARD_MAX, "card": "next", "airing": after[0]})
            t += CARD_MAX
        out.append({"kind": "card", "start": t, "end": stop, "card": "next", "airing": after[0]})
        return out
    return fill


def plan_break_grid(airing, after, clips, options, column):
    """A break between programmes from a column of the grid (0.8.0): its items in the order given, each for its number
    of times. A holding item takes the time the clips leave, with the countdown to the next programme's start (it
    counts through anything that plays after it); with none in the column, or no holding slide, Later and Coming up
    next cards or a slate fill the time just before the idents that end the break. The same airing always gets the
    same break. A short gap is handled as the classic break does: the last piece is stretched to the start."""
    t, end = airing["content_end"], airing["end"]
    gap = end - t
    if gap < MIN_PIECE:
        return []
    rng = Rng(seed_of(options.get("seed", 0), "break", int(airing["start"]), airing["slot_no"]))
    holding = clips.get("holding")
    cards = bool(options.get("cards", True)) and bool(after)
    seq = resolve_column(column, clips, options, rng, end, airing["slot_no"], gap)
    elastic = next((k for k, c in seq if c is None), None)
    if elastic is None:
        j = len(seq)
        while j > 0 and seq[j - 1][0] == "ident":
            j -= 1
        seq.insert(j, ("fill", None))
    seq = trim(seq, gap, min(CARD_SECONDS, gap) if cards and not (elastic and holding) else 0.0)
    left = gap - sum(float(c["dur"]) for _, c in seq if c)
    cards_fill = _cards_fill(after) if cards else None

    def fill(at, room, kind):
        if holding and kind in breakgrid.ELASTIC:
            words = "back_soon" if kind == "back_soon" else "countdown"
            return [{"kind": "holding", "start": at, "end": at + room, "holding": {**holding, "words": words},
                     "airing": after[0] if after else None, "until": end}]
        if cards_fill:
            return cards_fill(at, room, kind)
        return [{"kind": "slate", "start": at, "end": at + room}]
    out = lay_out(t, seq, fill, left)
    if out:
        out[-1]["end"] = end
    return out


def plan_mid_grid(t, most, clips, seed, column, options, airing):
    """A break inside a programme from a column of the grid (0.8.0), from t for at most `most` seconds: the items in
    order, then a holding item taking what is left (the break is as long as what plays when it has none). Empty
    when nothing plays, so the programme carries on. The countdown counts to the programme's return."""
    rng = Rng(seed)
    end = t + most
    holding = clips.get("holding")
    seq = resolve_column(column, clips, options, rng, end, 0, most)
    seq = [(k, c) for k, c in seq if c or holding]
    seq = trim(seq, most)
    if not seq:
        return []
    left = most - sum(float(c["dur"]) for _, c in seq if c)

    def fill(at, room, kind):
        words = "back_soon" if kind == "back_soon" else "countdown"
        return [{"kind": "holding", "start": at, "end": at + room, "holding": {**holding, "words": words}, "airing": airing, "until": end}]
    out = lay_out(t, seq, fill, left)
    if not out:
        return []
    stop = out[-1]["end"]
    for x in out:
        x["mid"] = True
        if x["kind"] == "holding":
            x["until"] = stop
    return out


def pieces_at(channel, t, clips, options, look=3):
    """Everything that plays in the slot on air at t: the programme, then its break pieces.

    options may also have (0.4.0) "breaks_in": a function of an entry giving the seconds into it where a break may go,
    and "mid_seconds": how long each break inside a programme may be (0, none). The programme is then played in
    parts, {"kind": "programme", "offset": seconds into it, "length": its running time}, with a break between; their
    time comes from the end break, so the slot, and the schedule, never move."""
    a = channel.airing(t)
    if not a:
        return None, []
    after, s = [], a["end"]
    for _ in range(look):
        n = channel.airing(s)
        if not n:
            break
        after.append(n)
        s = n["end"]
    length = a["content_end"] - a["start"]
    parts, mids = split_programme(a, clips, options)
    pieces = []
    t0 = a["start"]
    for (o0, o1), mid in zip(parts, mids + [[]]):
        pieces.append({"kind": "programme", "start": t0, "end": t0 + (o1 - o0), "airing": a, "offset": o0, "length": length})
        t0 += o1 - o0
        pieces += mid
        if mid:
            t0 = mid[-1]["end"]
    between = (options.get("grids") or {}).get("between")
    if between:
        pick = Rng(seed_of(options.get("seed", 0), "column", int(a["start"]), a["slot_no"])).below(breakgrid.MOST_COLUMNS)
        pieces += plan_break_grid({**a, "content_end": t0}, after, clips, options, breakgrid.column_for(between, t0, a["slot_no"], pick))
    else:
        pieces += plan_break({**a, "content_end": t0}, after, clips, options)
    return a, pieces


def split_programme(a, clips, options):
    """Where a programme is played in parts (0.4.0): ([(from, to) seconds into it, ...], [the break after each part
    but the last]). One part, the whole programme, unless breaks inside programmes are chosen, points are known, and
    the end break has the time."""
    length = a["content_end"] - a["start"]
    whole = ([(0.0, length)], [])
    most = float(options.get("mid_seconds") or 0)
    find = options.get("breaks_in")
    if most <= 0 or not find or length <= 0:
        return whole
    points = sorted(p for p in (find(a["entry"]) or []) if 60 < p < length - 60)
    if not points:
        return whole
    # The end break keeps room for its bumper, its ident and a little more; the rest may go inside.
    bumper = max([float(c.get("dur") or 0) for c in clips.get("bumpers") or []] or [0.0])
    ident = max([float(c.get("dur") or 0) for c in clips.get("idents") or []] or [float((clips.get("sting") or {}).get("dur") or 0)])
    spare = (a["end"] - a["content_end"]) - (bumper + ident + END_ROOM)
    parts, mids, at, taken = [], [], 0.0, 0.0
    inside = (options.get("grids") or {}).get("inside")
    for n, p in enumerate(points):
        give = min(most, spare)
        if give < MID_LEAST:
            break
        when = a["start"] + p + taken
        mid_seed = seed_of(options.get("seed", 0), "mid", int(a["start"]), int(p))
        if inside:
            pick = Rng(seed_of(mid_seed, "column")).below(breakgrid.MOST_COLUMNS)
            mid = plan_mid_grid(when, give, clips, mid_seed, breakgrid.column_for(inside, when, a["slot_no"], pick, n), options, a)
        else:
            mid = plan_mid_break(when, give, clips, mid_seed, options.get("fill_most"))
        if not mid:
            continue
        parts.append((at, p))
        mids.append(mid)
        took = mid[-1]["end"] - mid[0]["start"]
        spare -= took
        taken += took
        at = p
    if not mids:
        return whole
    parts.append((at, length))
    return parts, mids
