"""Maintenance windows for a group (Uptime and status 2.0.0): while one is on, the group's checks still run and are
kept in the history, but no alert is sent, and the status page says Maintenance.

People write them on one line, several split by ";":
    Sunday 02:00 to 04:00          every week (any day name, "weekdays", "weekends" or "every day")
    every day 03:00 to 03:30       every day
    2026-11-21 02:00 to 06:00      once, on that date
    now for 2 hours                once, from now (minutes, hours or days)
A window whose end is before its start ends the next day. Times are the server's own time zone.
"""
import re
import time

DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
DAY_WORDS = ["Mondays", "Tuesdays", "Wednesdays", "Thursdays", "Fridays", "Saturdays", "Sundays"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November",
          "December"]
MAX = 10


class WindowError(ValueError):
    pass


def _minutes(hhmm):
    m = re.fullmatch(r"([01]?\d|2[0-3])[:.]([0-5]\d)", hhmm)
    if not m:
        raise WindowError(f"\"{hhmm}\" is not a time. Write it as 02:00")
    return int(m.group(1)) * 60 + int(m.group(2))


def parse(text, now=None):
    """The windows in text, as a list of dicts. An empty text is no windows."""
    now = time.time() if now is None else now
    out = []
    for part in [p.strip() for p in re.split(r"[;\n]", str(text or "")) if p.strip()]:
        low = " ".join(part.lower().split())
        m = re.fullmatch(r"now for (\d+(?:\.\d+)?) ?(minutes?|mins?|m|hours?|h|days?|d)", low)
        if m:
            n = float(m.group(1)) * {"m": 60, "h": 3600, "d": 86400}[m.group(2)[0]]
            if not 60 <= n <= 31 * 86400:
                raise WindowError("Make a window from 1 minute to 31 days long")
            out.append({"kind": "once", "start": int(now), "end": int(now + n)})
            continue
        m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2}) (\S+) to (\S+)", low)
        if m:
            start_min, end_min = _minutes(m.group(4)), _minutes(m.group(5))
            try:
                day = time.mktime((int(m.group(1)), int(m.group(2)), int(m.group(3)), 0, 0, 0, 0, 0, -1))
                time.strptime(f"{m.group(1)}-{m.group(2)}-{m.group(3)}", "%Y-%m-%d")
            except (ValueError, OverflowError):
                raise WindowError(f"{m.group(1)}-{m.group(2)}-{m.group(3)} is not a date") from None
            start = _at(day, start_min)
            end = _at(day, end_min) if end_min > start_min else _at(day + 86400 + 3600, end_min)
            out.append({"kind": "once", "start": int(start), "end": int(end)})
            continue
        m = re.fullmatch(r"(every day|daily|weekdays|weekends|(?:(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)s?"
                         r"(?:,? (?:and )?)?)+) (\S+) to (\S+)", low)
        if m:
            words = m.group(1)
            if words in ("every day", "daily"):
                days = list(range(7))
            elif words == "weekdays":
                days = [0, 1, 2, 3, 4]
            elif words == "weekends":
                days = [5, 6]
            else:
                days = sorted({DAYS.index(d.rstrip("s")) for d in re.findall(r"[a-z]+day", words)})
            out.append({"kind": "weekly", "days": days, "start": _minutes(m.group(2)), "end": _minutes(m.group(3))})
            continue
        raise WindowError(f"\"{part}\" is not a window. Write it as Sunday 02:00 to 04:00, every day 03:00 to 03:30, "
                          "2026-11-21 02:00 to 06:00 or now for 2 hours")
    if len(out) > MAX:
        raise WindowError(f"Up to {MAX} windows a group")
    return out


def _at(day_start, minutes):
    t = time.localtime(day_start)
    return time.mktime((t.tm_year, t.tm_mon, t.tm_mday, minutes // 60, minutes % 60, 0, 0, 0, -1))


def active(windows, now=None):
    """The window that is on now, or None."""
    now = time.time() if now is None else now
    t = time.localtime(now)
    minute, day = t.tm_hour * 60 + t.tm_min, t.tm_wday
    for w in windows or []:
        if w["kind"] == "once" and w["start"] <= now < w["end"]:
            return w
        if w["kind"] == "weekly":
            s, e = w["start"], w["end"]
            if s < e and day in w["days"] and s <= minute < e:
                return w
            if s >= e and ((day in w["days"] and minute >= s) or ((day - 1) % 7 in w["days"] and minute < e)):
                return w
    return None


def live(windows, now=None):
    """The windows still to come or on now: a one-off window that has ended is dropped."""
    now = time.time() if now is None else now
    return [w for w in windows or [] if w["kind"] != "once" or w["end"] > now]


def _hhmm(minutes):
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _days(days):
    if days == list(range(7)):
        return "Every day"
    if days == [0, 1, 2, 3, 4]:
        return "Weekdays"
    if days == [5, 6]:
        return "Weekends"
    names = [DAY_WORDS[d] for d in days]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def words(w):
    """A window in words, such as "Sundays 02:00 to 04:00" or "21 November 02:00 to 06:00"."""
    if w["kind"] == "weekly":
        return f"{_days(w['days'])} {_hhmm(w['start'])} to {_hhmm(w['end'])}"
    s, e = time.localtime(w["start"]), time.localtime(w["end"])
    same = (s.tm_year, s.tm_yday) == (e.tm_year, e.tm_yday)
    end = f"{e.tm_hour:02d}:{e.tm_min:02d}" if same else f"{e.tm_mday} {MONTHS[e.tm_mon - 1]} {e.tm_hour:02d}:{e.tm_min:02d}"
    return f"{s.tm_mday} {MONTHS[s.tm_mon - 1]} {s.tm_hour:02d}:{s.tm_min:02d} to {end}"


def line(windows):
    """The windows written back as one line people can change, in the form parse() reads."""
    out = []
    for w in windows or []:
        if w["kind"] == "weekly":
            days = ("every day" if w["days"] == list(range(7)) else "weekdays" if w["days"] == [0, 1, 2, 3, 4]
                    else "weekends" if w["days"] == [5, 6] else " ".join(DAYS[d].capitalize() for d in w["days"]))
            out.append(f"{days} {_hhmm(w['start'])} to {_hhmm(w['end'])}")
        else:
            s, e = time.localtime(w["start"]), time.localtime(w["end"])
            out.append(f"{s.tm_year}-{s.tm_mon:02d}-{s.tm_mday:02d} {s.tm_hour:02d}:{s.tm_min:02d} to {e.tm_hour:02d}:{e.tm_min:02d}")
    return "; ".join(out)
