"""The schedule grid: a repeating week of fixed slots for a channel, in 15 minute steps, Monday to Sunday.

A slot is a film or a series at a day and a time. A series slot plays the next episode of that series on that
channel: every slot of the series in the week, in order, takes the next one, from the start point chosen (the first
episode, a series and episode, or the next one not watched), and the next week carries on. Each slot takes the time
of its longest programme, rounded up to 15 minutes, so slots never run into each other whatever the episode.

Fixed slots win. The time between them keeps the channel's automatic line-up: each automatic programme that fits
whole in the gap plays at its usual time, and what is left is the break after the programme before it, with its
idents, promos and cards, as before.

Stored as one small JSON file per channel, worked out when asked: nothing runs in the background. Every change is a
pure function on the document here, so the page, the tests and the suggester share one set of rules.
"""
import bisect
import copy
import hashlib
import json
import math
import os
import secrets
import time

import schedule

STEP = 15  # minutes
DAY = 24 * 60
WEEK = 7 * DAY
DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
SHORT = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
MAX_SLOTS = 400
MAX_EPISODES = 2000


class GridError(ValueError):
    pass


def empty():
    return {"version": 1, "slots": [], "series": {}, "films": {}}


def hm(minutes):
    m = int(minutes) % DAY
    return f"{m // 60:02d}:{m % 60:02d}"


def where(day, start):
    return f"{DAYS[int(day) % 7]} {hm(start)}"


# Local weeks ---------------------------------------------------------------------------------------------------------
def week_start(t):
    """Monday 00:00, local time, of the week holding t."""
    lt = time.localtime(t)
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday - lt.tm_wday, 0, 0, 0, 0, 0, -1))


def at(monday, day, minutes):
    """The moment of a slot in the week starting `monday` (local, so a clock change keeps 20:00 at 20:00)."""
    lt = time.localtime(monday + 3600 * 12)
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday + int(day), 0, int(minutes), 0, 0, 0, -1))


def weeks_between(a, b):
    return int(round((week_start(b) - week_start(a)) / (7 * 86400)))


# The document --------------------------------------------------------------------------------------------------------
def length(doc, ref):
    """How long a slot of this film or series takes, in minutes: its longest programme, rounded up to 15."""
    kind, _, rid = ref.partition(":")
    if kind == "s":
        eps = (doc["series"].get(rid) or {}).get("episodes") or []
        longest = max((float(e.get("dur") or 0) for e in eps), default=1800)
    else:
        longest = float((doc["films"].get(rid) or {}).get("dur") or 5400)
    return max(STEP, int(math.ceil(longest / 60 / STEP - 1e-9)) * STEP)


def name_of(doc, ref):
    kind, _, rid = ref.partition(":")
    item = doc["series"].get(rid) if kind == "s" else doc["films"].get(rid)
    return (item or {}).get("name") or (item or {}).get("title") or "Programme"


def span(doc, slot):
    """(start, end) in minutes from Monday 00:00; the end may pass Sunday midnight."""
    s = int(slot["day"]) * DAY + int(slot["start"])
    return s, s + length(doc, slot["ref"])


def clash(doc, day, start, ref, ignore=()):
    """The slot that a programme at this day and time would run into, or None. The week wraps round."""
    s, e = int(day) * DAY + int(start), int(day) * DAY + int(start) + length(doc, ref)
    for other in doc["slots"]:
        if other["id"] in ignore:
            continue
        os_, oe = span(doc, other)
        for shift in (-WEEK, 0, WEEK):
            if s < oe + shift and os_ + shift < e:
                return other
    return None


def ordered(doc):
    return sorted(doc["slots"], key=lambda x: (int(x["day"]), int(x["start"])))


def check_place(day, start):
    if not (isinstance(day, int) and 0 <= day < 7):
        raise GridError("Choose a day from Monday to Sunday")
    if not (isinstance(start, int) and 0 <= start < DAY and start % STEP == 0):
        raise GridError("Choose a time on the quarter hour")


def _place(doc, day, start, ref, ignore=()):
    check_place(day, start)
    other = clash(doc, day, start, ref, ignore)
    if other:
        raise GridError(f"{name_of(doc, ref)} at {where(day, start)} would run into {name_of(doc, other['ref'])} at "
                        f"{where(other['day'], other['start'])}. Move that first, or choose another time")


def tidy(doc):
    """Leaves out films and series no slot uses any more."""
    used = {s["ref"] for s in doc["slots"]}
    doc["series"] = {k: v for k, v in doc["series"].items() if f"s:{k}" in used}
    doc["films"] = {k: v for k, v in doc["films"].items() if f"f:{k}" in used}
    return doc


def clean(raw):
    """A document read from a file or a draft, with anything out of shape left out."""
    doc = empty()
    if not isinstance(raw, dict):
        return doc
    for sid, s in (raw.get("series") or {}).items():
        if isinstance(s, dict) and isinstance(s.get("episodes"), list):
            doc["series"][str(sid)] = {"name": str(s.get("name") or "Series")[:120], "episodes": s["episodes"][:MAX_EPISODES],
                                       "first": int(s.get("first") or 0), "anchor": float(s.get("anchor") or 0),
                                       "start": s.get("start") if isinstance(s.get("start"), dict) else {"mode": "first"}}
    for fid, f in (raw.get("films") or {}).items():
        if isinstance(f, dict) and f.get("id"):
            doc["films"][str(fid)] = f
    for s in (raw.get("slots") or [])[:MAX_SLOTS]:
        try:
            slot = {"id": str(s["id"])[:16], "day": int(s["day"]), "start": int(s["start"]), "ref": str(s["ref"])}
        except (KeyError, TypeError, ValueError):
            continue
        kind, _, rid = slot["ref"].partition(":")
        if 0 <= slot["day"] < 7 and 0 <= slot["start"] < DAY and slot["start"] % STEP == 0 and (
                (kind == "s" and rid in doc["series"]) or (kind == "f" and rid in doc["films"])):
            doc["slots"].append(slot)
    for k in ("saved", "suggested", "note"):
        if k in raw:
            doc[k] = raw[k]
    return doc


# Series: which episode plays ------------------------------------------------------------------------------------------
def occurrences(doc, sid):
    """The slots of a series in the week, in order: the nth of them plays the nth next episode."""
    return [s for s in ordered(doc) if s["ref"] == f"s:{sid}"]


def episode_index(doc, sid, slot_id, monday):
    """Which episode (a position in the series' list) the slot plays in the week starting `monday`."""
    s = doc["series"][sid]
    eps = s["episodes"]
    if not eps:
        return None
    occ = [x["id"] for x in occurrences(doc, sid)]
    k = occ.index(slot_id) if slot_id in occ else 0
    w = weeks_between(s.get("anchor") or monday, monday)
    return (int(s.get("first") or 0) + w * len(occ) + k) % len(eps)


def reanchor(doc, sid, now):
    """Before the slots of a series change, the series carries on from the episode due at the start of this week,
    so adding or removing a slot never jumps back to the first episode."""
    s = doc["series"].get(sid)
    if not s or not s["episodes"]:
        return
    monday = week_start(now)
    occ = occurrences(doc, sid)
    if occ and s.get("anchor"):
        s["first"] = episode_index(doc, sid, occ[0]["id"], monday)
    s["anchor"] = monday


def start_words(s):
    st = s.get("start") or {}
    if st.get("mode") == "episode":
        return f"From series {st.get('s')}, episode {st.get('e')}"
    if st.get("mode") == "unwatched":
        return "From the next episode not watched"
    return "From the first episode"


def set_start(doc, sid, mode, now, s=None, e=None, unwatched_index=None):
    """Where a series starts: the first episode, a series and episode, or the next not watched (found in Jellyfin
    by the page, and given here as its position)."""
    doc = copy.deepcopy(doc)
    item = doc["series"].get(sid)
    if not item:
        raise GridError("That series is not on this channel's grid")
    eps = item["episodes"]
    if mode == "first":
        first = 0
    elif mode == "episode":
        first = next((i for i, x in enumerate(eps) if x.get("s") == s and x.get("e") == e), None)
        if first is None:
            raise GridError(f"{item['name']} has no series {s}, episode {e}")
    elif mode == "unwatched":
        first = int(unwatched_index or 0) % max(1, len(eps))
    else:
        raise GridError("Choose where the series starts")
    item["first"], item["anchor"] = first, week_start(now)
    item["start"] = {"mode": mode, **({"s": s, "e": e} if mode == "episode" else {})}
    return doc, f"{item['name']}: {start_words(item)[0].lower()}{start_words(item)[1:]}, this week"


# Changes --------------------------------------------------------------------------------------------------------------
def add(doc, day, start, kind, item, now, episodes=None, start_mode=None):
    """Adds a film (item: its programme) or a series (item: {"id", "name"}, episodes: in order) at a day and time."""
    doc = copy.deepcopy(doc)
    if len(doc["slots"]) >= MAX_SLOTS:
        raise GridError(f"A grid holds up to {MAX_SLOTS} slots")
    if kind == "series":
        sid = str(item["id"])
        if sid not in doc["series"]:
            if not episodes:
                raise GridError(f"{item.get('name') or 'That series'} has no episodes Jellyfin can play")
            doc["series"][sid] = {"name": str(item.get("name") or "Series")[:120], "episodes": episodes[:MAX_EPISODES], "first": 0,
                                  "anchor": week_start(now), "start": {"mode": "first"}}
        ref = f"s:{sid}"
        reanchor(doc, sid, now)
    elif kind == "film":
        fid = str(item["id"])
        doc["films"][fid] = item
        ref = f"f:{fid}"
    else:
        raise GridError("Choose a film or a series")
    _place(doc, day, start, ref)
    slot = {"id": secrets.token_hex(4), "day": day, "start": start, "ref": ref}
    doc["slots"].append(slot)
    if start_mode and kind == "series":
        doc, _ = set_start(doc, ref[2:], now=now, **start_mode)
    return doc, slot["id"], f"Added {name_of(doc, ref)} at {where(day, start)}"


def find(doc, slot_id):
    s = next((x for x in doc["slots"] if x["id"] == slot_id), None)
    if not s:
        raise GridError("That slot has gone. The grid may have changed in another tab")
    return s


def move(doc, slot_id, day, start, now):
    """Moves a slot: what a drag does, and what Move to, Move earlier and Move later do without one."""
    doc = copy.deepcopy(doc)
    s = find(doc, slot_id)
    _place(doc, day, start, s["ref"], ignore={slot_id})
    if s["ref"].startswith("s:"):
        reanchor(doc, s["ref"][2:], now)
    s["day"], s["start"] = day, start
    return doc, f"Moved {name_of(doc, s['ref'])} to {where(day, start)}"


def nudge(doc, slot_id, minutes, now):
    """Moves a slot earlier or later by 15 minutes or more, across midnight into the day before or after."""
    s = find(doc, slot_id)
    t = (int(s["day"]) * DAY + int(s["start"]) + int(minutes)) % WEEK
    return move(doc, slot_id, t // DAY, t % DAY, now)


def remove(doc, slot_id, now):
    doc = copy.deepcopy(doc)
    s = find(doc, slot_id)
    if s["ref"].startswith("s:"):
        reanchor(doc, s["ref"][2:], now)
    doc["slots"] = [x for x in doc["slots"] if x["id"] != slot_id]
    return tidy(doc), f"Removed {name_of(doc, s['ref'])} from {where(s['day'], s['start'])}"


def copy_day(doc, from_day, to_days, now):
    """Copies one day's slots to other days, in place of what was on them (as rota planners do). Series keep
    playing their next episodes in order."""
    doc = copy.deepcopy(doc)
    to_days = sorted({int(d) for d in to_days if 0 <= int(d) < 7 and int(d) != int(from_day)})
    if not to_days:
        raise GridError("Choose at least one other day to copy to")
    source = [s for s in ordered(doc) if s["day"] == from_day]
    if not source:
        raise GridError(f"{DAYS[from_day]} has nothing to copy")
    replaced = [s for s in doc["slots"] if s["day"] in to_days]
    for sid in {s["ref"][2:] for s in source + replaced if s["ref"].startswith("s:")}:
        reanchor(doc, sid, now)
    doc["slots"] = [s for s in doc["slots"] if s["day"] not in to_days]
    for d in to_days:
        for s in source:
            _place(doc, d, s["start"], s["ref"])
            doc["slots"].append({"id": secrets.token_hex(4), "day": d, "start": s["start"], "ref": s["ref"]})
    days = ", ".join(DAYS[d] for d in to_days)
    said = f"Copied {DAYS[from_day]} to {days}"
    if replaced:
        said += f", in place of {len(replaced)} slot{'s' if len(replaced) != 1 else ''} there"
    return tidy(doc), said


def stripe(doc, slot_id, weekdays, per_day, weekends, now):
    """Strips a series: the same time on each chosen weekday (and Saturday and Sunday when weekends is on), with
    `per_day` episodes one after another, each the next episode in order. Refuses all of it if any would clash."""
    doc = copy.deepcopy(doc)
    s = find(doc, slot_id)
    days = sorted({int(d) for d in weekdays if 0 <= int(d) < 5} | ({5, 6} if weekends else set()) | {int(s["day"])})
    per_day = max(1, min(6, int(per_day)))
    if not days:
        raise GridError("Choose at least one day")
    ref, start, L = s["ref"], int(s["start"]), length(doc, s["ref"])
    if ref.startswith("s:"):
        reanchor(doc, ref[2:], now)  # the series carries on from the episode due now
    if start + per_day * L > DAY + L:
        raise GridError(f"{per_day} episodes from {hm(start)} would run past the end of the day. Choose fewer, or an earlier time")
    keep = [x for x in doc["slots"] if not (x["ref"] == ref and x["start"] in [start + k * L for k in range(per_day)] and x["day"] in days)]
    keep = [x for x in keep if x["id"] != slot_id]
    trial = {**doc, "slots": keep}
    added = 0
    for d in days:
        for k in range(per_day):
            t = start + k * L
            day, minute = d + t // DAY, t % DAY
            _place(trial, day % 7, minute, ref)
            trial["slots"].append({"id": slot_id if (d == s["day"] and k == 0) else secrets.token_hex(4), "day": day % 7, "start": minute,
                                   "ref": ref})
            added += 1
    doc = trial
    names = ", ".join(SHORT[d] for d in days)
    return doc, (f"Striped {name_of(doc, ref)} at {hm(start)} on {names}: {per_day} episode{'s' if per_day != 1 else ''} a day, "
                 f"{added} slots, each the next episode")


# Rules: Shows at set times (0.15.0, DASH-649) ------------------------------------------------------------------------
# A rule is how a person says it: "Harbour lights, Monday to Friday at 19:00, 2 episodes". It is read from the slots,
# never stored, so every grid already made shows as rules and a rule is only slots: nothing to migrate or keep in step.
def days_words(days):
    days = sorted(set(days))
    if days == list(range(7)):
        return "every day"
    if days == list(range(5)):
        return "Monday to Friday"
    if days == [5, 6]:
        return "Saturday and Sunday"
    if len(days) == 1:
        return DAYS[days[0]]
    return ", ".join(SHORT[d] for d in days)


def rules(doc):
    """The slots as rules: one for each film or series, start time and number of programmes in a row, with its days."""
    out = []
    by_ref = {}
    for s in ordered(doc):
        by_ref.setdefault(s["ref"], []).append(s)
    for ref, slots in by_ref.items():
        step = length(doc, ref)
        runs, per_day = [], {}
        for s in slots:
            per_day.setdefault(int(s["day"]), []).append(s)
        for day, ss in per_day.items():
            cur = [ss[0]]
            for x in ss[1:]:
                if int(x["start"]) == int(cur[-1]["start"]) + step:
                    cur.append(x)
                else:
                    runs.append((day, cur))
                    cur = [x]
            runs.append((day, cur))
        groups = {}
        for day, cur in runs:
            groups.setdefault((int(cur[0]["start"]), len(cur)), []).append((day, cur))
        for (start, n), found in groups.items():
            ids = [x["id"] for _, cur in found for x in cur]
            days = sorted(d for d, _ in found)
            name = name_of(doc, ref)
            out.append({"id": "r" + hashlib.sha1(",".join(sorted(ids)).encode()).hexdigest()[:8], "ref": ref, "name": name, "days": days,
                        "start": start, "n": n, "slots": ids,
                        "words": f"{name}, {days_words(days)} at {hm(start)}, {n} episode{'s' if n != 1 else ''}"
                                 if ref.startswith("s:") else f"{name}, {days_words(days)} at {hm(start)}"})
    return sorted(out, key=lambda r: (r["start"], r["name"], r["days"]))


def add_rule(doc, days, start, kind, item, n, now, episodes=None, start_mode=None):
    """A film or series at a time on chosen days, with n episodes one after another. All of it or none: a clash with
    anything on the grid refuses the whole rule and says which."""
    days = sorted({int(d) for d in days})
    if not days or any(not 0 <= d < 7 for d in days):
        raise GridError("Choose at least one day")
    n = max(1, min(6, int(n))) if kind == "series" else 1
    check_place(days[0], int(start))
    doc, _, _ = add(doc, days[0], int(start), kind, item, now, episodes, start_mode)
    ref = doc["slots"][-1]["ref"]
    step = length(doc, ref)
    if int(start) + n * step > DAY:
        raise GridError(f"{n} episodes from {hm(start)} would run past midnight. Choose fewer, or an earlier time")
    if len(doc["slots"]) + (len(days) * n - 1) > MAX_SLOTS:
        raise GridError(f"A grid holds up to {MAX_SLOTS} slots")
    first = doc["slots"].pop()
    for d in days:
        for k in range(n):
            t = int(start) + k * step
            _place(doc, d, t, ref)
            doc["slots"].append({"id": first["id"] if (d == days[0] and k == 0) else secrets.token_hex(4), "day": d, "start": t, "ref": ref})
    return doc, f"Added {name_of(doc, ref)} at {hm(start)}, {days_words(days)}" + (f", {n} episode{'s' if n != 1 else ''}" if kind == "series" else "")


def remove_rule(doc, rule_id, now):
    doc = copy.deepcopy(doc)
    found = next((r for r in rules(doc) if r["id"] == rule_id), None)
    if not found:
        raise GridError("That time has gone. The grid may have changed in another tab")
    if found["ref"].startswith("s:"):
        reanchor(doc, found["ref"][2:], now)  # the series carries on from the episode due now
    gone = set(found["slots"])
    doc["slots"] = [x for x in doc["slots"] if x["id"] not in gone]
    return tidy(doc), f"Removed {found['words']}"


# The week, worked out --------------------------------------------------------------------------------------------------
def week(doc, monday):
    """Every slot in the week starting `monday`, as airings: {"slot", "start", "end", "content_end", "entry"}."""
    out = []
    for s in ordered(doc):
        kind, _, rid = s["ref"].partition(":")
        if kind == "s":
            i = episode_index(doc, rid, s["id"], monday)
            if i is None:
                continue
            entry = doc["series"][rid]["episodes"][i]
        else:
            entry = doc["films"].get(rid)
            if not entry:
                continue
        start = at(monday, s["day"], s["start"])
        out.append({"slot": s["id"], "start": start, "end": start + length(doc, s["ref"]) * 60,
                    "content_end": start + float(entry.get("dur") or 0), "entry": entry})
    return out


class GridChannel:
    """A channel with a grid: its fixed slots, and its automatic line-up in the time between them. Answers the same
    questions as schedule.Channel (airing and airings), so the guide, the card, the stream and the breaks follow it."""

    def __init__(self, base, doc):
        self.base = base
        self.doc = doc
        self._days = {}

    def _fixed(self, t0, t1):
        out = []
        m = week_start(t0) - 7 * 86400
        while m < t1:
            out += [a for a in week(self.doc, m) if a["end"] > t0 and a["start"] < t1]
            m = week_start(m + 8 * 86400)
        return sorted(out, key=lambda a: a["start"])

    def _things(self, day0):
        """Every airing from a day before `day0` to two days after it, with the gaps filled and the breaks set."""
        got = self._days.get(day0)
        if got is not None:
            return got
        t0, t1 = day0 - 86400, day0 + 2 * 86400
        wide = self._fixed(t0 - 8 * 86400, t1 + 8 * 86400)
        # The slots in the window, and the one before and after it, so time with nothing fixed or fitting for days
        # is the break of the slot before (a channel with a weekly film and nothing else still always has something).
        inside = [a for a in wide if a["end"] > t0 and a["start"] < t1]
        before = [a for a in wide if a["end"] <= t0][-1:]
        after = [a for a in wide if a["start"] >= t1][:1]
        fixed = before + inside + after
        if before:
            t0 = before[0]["start"]
        if after:
            t1 = after[0]["end"]
        things = []
        edges = [t0] + [x for a in fixed for x in (a["start"], a["end"])] + [t1]
        gaps = [(edges[i], edges[i + 1]) for i in range(0, len(edges), 2)]
        for g0, g1 in gaps:
            for a in self.base.airings(g0, g1, limit=400):
                if a["start"] >= g0 and a["content_end"] <= g1:
                    things.append({**a, "fill": True})
        for a in fixed:
            e = a["entry"]
            things.append({"entry": e, "start": a["start"], "content_end": min(a["content_end"], a["end"]), "end": a["end"],
                           "cycle": 0, "pos": 0, "slot_no": int(a["start"]), "grid": a["slot"]})
        things.sort(key=lambda a: a["start"])
        for i, a in enumerate(things[:-1]):  # the time to the next one is this one's break
            a["end"] = max(a["content_end"], things[i + 1]["start"])
        if len(self._days) > 6:
            self._days.clear()
        self._days[day0] = things
        return things

    def airing(self, t):
        lt = time.localtime(t)
        day0 = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))
        things = self._things(day0)
        starts = [a["start"] for a in things]
        i = bisect.bisect_right(starts, t) - 1
        if 0 <= i < len(things) - 1:  # the last one's end is not known inside this window
            a = things[i]
            if a["start"] <= t < a["end"]:
                return dict(a)
        return self.base.airing(t)  # nothing fixed or fitting for over a day: the automatic line-up as it is

    def airings(self, start, stop, limit=2000):
        out, t = [], float(start)
        while t < stop and len(out) < limit:
            a = self.airing(t)
            if a is None:
                break
            out.append(a)
            t = a["end"] if a["end"] > t else t + 1
        return out


def channel_of(ch, doc=None):
    """The schedule a channel follows: its grid, when it has slots, over its automatic line-up."""
    base = schedule.Channel(ch)
    doc = doc if doc is not None else ch.get("_grid")
    if doc and doc.get("slots"):
        return GridChannel(base, doc)
    return base


# Files ------------------------------------------------------------------------------------------------------------------
def path(folder, cid, kind=""):
    return os.path.join(folder, f"{cid}{('.' + kind) if kind else ''}.json")


def load(folder, cid, kind=""):
    try:
        with open(path(folder, cid, kind), encoding="utf-8") as f:
            return clean(json.load(f))
    except (OSError, ValueError):
        return None


def store(folder, cid, doc, kind=""):
    os.makedirs(folder, exist_ok=True)
    p = path(folder, cid, kind)
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump(doc, f, separators=(",", ":"))
    os.replace(p + ".tmp", p)


def drop(folder, cid, kind):
    try:
        os.remove(path(folder, cid, kind))
    except OSError:
        pass


def view(doc, monday):
    """What the page draws for the week: each slot with its words."""
    out = []
    for a in week(doc, monday):
        s = next(x for x in doc["slots"] if x["id"] == a["slot"])
        e = a["entry"]
        kind = "series" if s["ref"].startswith("s:") else "film"
        detail = ""
        if kind == "series":
            detail = f"Series {e.get('s')}, episode {e.get('e')}" + (f": {e.get('ep')}" if e.get("ep") else "")
        elif e.get("year"):
            detail = str(e["year"])
        out.append({"id": s["id"], "day": s["day"], "start": s["start"], "length": length(doc, s["ref"]), "kind": kind,
                    "ref": s["ref"], "title": name_of(doc, s["ref"]), "detail": detail,
                    "minutes": int(round(float(e.get("dur") or 0) / 60))})
    series = {sid: {"name": v["name"], "start": start_words(v), "episodes": len(v["episodes"])} for sid, v in doc["series"].items()}
    return {"slots": out, "series": series}
