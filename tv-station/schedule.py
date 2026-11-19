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


def lineup_hash(lineup):
    return hashlib.sha256("|".join(f"{e['id']}:{round(float(e['dur']), 1)}" for e in lineup).encode()).hexdigest()[:16]


# Breaks -------------------------------------------------------------------------------------------------------------
def plan_break(airing, after, clips, options):
    """The pieces that fill the gap between a programme's end and the next slot: an ident, trailers and clips, then
    Later and Coming up next cards. The same airing always gets the same break.

    after:   the next few airings (the first is the programme after this one), for the cards
    clips:   {"idents": [...], "fillers": [...], "sting": {...} or None, "random_idents": False, "holding": {...} or None},
             each clip {"id", "dur", "title", "src"}; a promo filler also has "airs", when its programme starts
    options: {"ident_order": "in_order" | "random", "cards": True, "seed": ...}

    A broadcast pack's logo with music (the sting) opens the break when it fits; a pack's idents are always played
    in a random order (random_idents); a promo is only shown before its programme has started. With a holding slide
    (holding), the slide fills the rest of the break, looping until the next programme starts, in place of the cards.
    """
    t, end = airing["content_end"], airing["end"]
    gap = end - t
    out = []
    if gap < MIN_PIECE:
        return out
    slot_no = airing["slot_no"]
    rng = Rng(seed_of(options.get("seed", 0), "break", int(airing["start"]), slot_no))
    holding = clips.get("holding")
    cards = bool(options.get("cards", True)) and bool(after) and not holding
    reserve = min(CARD_SECONDS, gap) if cards else 0.0
    idents = [c for c in clips.get("idents") or [] if c.get("dur", 0) > 0]
    fillers = [c for c in clips.get("fillers") or [] if c.get("dur", 0) > 0 and float(c.get("airs") or end + 1) > end]
    sting = clips.get("sting")

    def add(kind, dur, **more):
        nonlocal t
        out.append({"kind": kind, "start": t, "end": t + dur, **more})
        t += dur

    if sting and 0 < float(sting.get("dur") or 0) <= end - t - reserve:
        add("clip", float(sting["dur"]), clip=sting, role="sting")
    if idents:
        in_order = options.get("ident_order", "in_order") == "in_order" and not clips.get("random_idents")
        ident = idents[slot_no % len(idents)] if in_order else idents[rng.below(len(idents))]
        if ident["dur"] <= end - t - reserve:
            add("clip", float(ident["dur"]), clip=ident, role="ident")
    last = None
    while fillers:
        room = end - t - reserve
        fits = [c for c in fillers if c["dur"] <= room and (c["id"] != last or len(fillers) == 1)]
        if not fits:
            break
        c = fits[rng.below(len(fits))]
        add("clip", float(c["dur"]), clip=c, role="filler")
        last = c["id"]
    left = end - t
    if left < MIN_PIECE:
        if out:
            out[-1]["end"] = end
        return out
    if holding:
        add("holding", left, holding=holding, airing=after[0] if after else None)
        return out
    if not cards:
        add("slate", left)
        return out
    # Later cards first, each for a programme after the next one, then Coming up next for the rest.
    later = [a for a in after[1:]]
    k = 0
    while left > CARD_MAX and later:
        d = min(CARD_MAX, left - CARD_SECONDS)
        add("card", d, card="later", airing=later[k % len(later)])
        k += 1
        left = end - t
    while left > CARD_MAX * 2:  # nothing later to show: Coming up next again, in turns
        add("card", CARD_MAX, card="next", airing=after[0])
        left = end - t
    add("card", left, card="next", airing=after[0])
    return out


def pieces_at(channel, t, clips, options, look=3):
    """Everything that plays in the slot on air at t: the programme, then its break pieces."""
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
    pieces = [{"kind": "programme", "start": a["start"], "end": a["content_end"], "airing": a}]
    pieces += plan_break(a, after, clips, options)
    return a, pieces
