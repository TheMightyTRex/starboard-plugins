"""Picture shrinker: shrinks the posters and photos of people Jellyfin keeps in its metadata folder, so they take less
space (DASH-432; owner, 14 November 2026: "Yes, shrink both", then "create a starboard plugin to allow this task to run
at a set time - every day, week or month").

The rules are those of the owner's one-off shrink (~/Documents/Claude/server/shrink-jellyfin-pictures.py):
- Posters (poster.* under library/) to at most 900 pixels tall, and photos of cast and crew (under People/) to at
  most 400 pixels wide, both settings. A picture already that small is left alone, and is only opened, never written.
- Each picture is written to a hidden file beside it, opened again and decoded in full, checked for its size and
  format, and swapped in only when it is smaller than the original, so Jellyfin never reads a half-written file.
  JPEG at quality 85, progressive; PNG and WebP keep their format.
- It works at the lowest priority: its thread runs at nice 19 and in the idle disk class.

When it runs: on the schedule the person chooses (plug-in API 1.14: every day, week or month at a time), with
Shrink now; and, when activated (deactivated by default), each hour of Starboard's quiet hours for the pictures
Jellyfin saved since the last pass.

Lightweight: nothing runs between runs. Pillow is loaded for the first run only, a JPEG is decoded at a reduced scale
(draft), and the card and page read a small state file.
"""
import calendar
import datetime as dt
import gc
import os
import shutil
import subprocess
import threading
import time

import sbplugin
from sbplugin import band, keep, plural, remember, serve, setting

ROOT = os.environ.get("PICTURE_SHRINKER_ROOT", "/metadata")
EXTS = {".jpg", ".jpeg", ".png", ".webp"}
TMP = ".picture-shrinker-tmp"  # its own unfinished copies, beside each picture: never shrunk, tidied at each run
QUALITY = 85
RUN_LIMIT = 115 * 60  # a run stops itself before the job's 120 minutes; the next run carries on where it stopped
NEW_LIMIT = 25 * 60  # the quiet-hours pass for new pictures, inside its 30 minutes
NEW_AGE = 600  # a picture saved in the last 10 minutes is left for the next pass: Jellyfin may still be writing it
PROGRESS_EVERY = 25  # pictures between notes of how far a run has gone
KEEP_RUNS = 20
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
DEFAULT_WHEN = {"every": "week", "day": "sunday", "time": "03:30"}
WHAT = {"scheduled": "On its schedule", "now": "Shrink now", "new": "New pictures"}
now = time.time  # replaced in tests

_lock = threading.Lock()
_job = {"thread": None, "kind": "", "progress": None}
_stop = threading.Event()


# Settings ------------------------------------------------------------------------------------------------------

def _num(key, default, lo, hi):
    try:
        return int(max(lo, min(float(setting(key, default)), hi)))
    except (TypeError, ValueError):
        return default


def sizes():
    """(the tallest a poster may be, the widest a photo of a person may be), in pixels."""
    return _num("poster_height", 900, 300, 3000), _num("person_width", 400, 100, 2000)


def schedule():
    w = setting("when", None)
    if isinstance(w, dict) and w.get("every") in ("day", "week", "month") and isinstance(w.get("time"), str):
        return w
    return DEFAULT_WHEN


def next_run(at=None):
    """The next time the schedule names after `at`, as a datetime: as Starboard runs it (a monthly date the month does
    not have is its last day)."""
    s, t = schedule(), dt.datetime.fromtimestamp(now() if at is None else at)
    hh, mm = (int(x) for x in s["time"].split(":"))
    for days in range(0, 400):
        d = (t + dt.timedelta(days=days)).replace(hour=hh, minute=mm, second=0, microsecond=0)
        if d <= t:
            continue
        if s["every"] == "day":
            return d
        if s["every"] == "week" and WEEKDAYS[d.weekday()] == str(s.get("day") or "sunday"):
            return d
        if s["every"] == "month":
            last = calendar.monthrange(d.year, d.month)[1]
            if d.day == min(int(s.get("date") or last), last):
                return d
    return None


def when_words(d, short=False):
    if not d:
        return "when you choose Shrink now"
    today = dt.date.fromtimestamp(now())
    day = "today" if d.date() == today else "tomorrow" if d.date() == today + dt.timedelta(days=1) else d.strftime("%a" if short else "%A %-d %B")
    return f"{day} {d:%H:%M}" if short else f"{day} at {d:%H:%M}"


# Shrinking -----------------------------------------------------------------------------------------------------

def kind_of(path):
    """poster, person or None, from where the picture is under the metadata folder (as the one-off shrink did)."""
    rel = os.path.relpath(path, ROOT).split(os.sep)
    name = rel[-1].lower()
    if os.path.splitext(name)[1] not in EXTS or name.endswith(TMP) or name.startswith("."):
        return None
    if rel[0] == "People":
        return "person"
    if rel[0] == "library" and name.startswith("poster"):
        return "poster"
    return None


def target(kind, size, poster_height, person_width):
    """The new size of a picture, or None when it is already small enough."""
    w, h = size
    if kind == "person" and w > person_width:
        return person_width, max(1, round(h * person_width / w))
    if kind == "poster" and h > poster_height:
        return max(1, round(w * poster_height / h)), poster_height
    return None


def pictures(since=None, until=None):
    """(path, kind, size in bytes) for each picture under library/ and People/, in folder order. With `since`, only
    pictures changed after it (and before `until`)."""
    for top in ("library", "People"):
        for folder, dirs, names in os.walk(os.path.join(ROOT, top)):
            dirs.sort()
            for name in sorted(names):
                path = os.path.join(folder, name)
                kind = kind_of(path)
                if not kind:
                    continue
                try:
                    st = os.stat(path)
                except OSError:
                    continue
                if since is not None and not (since < st.st_mtime <= (until or now())):
                    continue
                yield path, kind, st.st_size


def tidy(folder_root=None):
    """Removes its own unfinished copies, left if the container stopped part way. Nothing of Jellyfin's is touched."""
    gone = 0
    for folder, _, names in os.walk(folder_root or ROOT):
        for name in names:
            if name.endswith(TMP) and name.startswith("."):
                try:
                    os.remove(os.path.join(folder, name))
                    gone += 1
                except OSError:
                    pass
    return gone


def shrink_one(path, kind, poster_height, person_width):
    """Shrinks one picture in place. Returns None when it is left alone, else (bytes before, bytes after). Raises
    ValueError or OSError when it cannot be read or the new file fails its check; the original is then kept."""
    from PIL import Image  # loaded at the first run only
    before = os.path.getsize(path)
    with Image.open(path) as im:
        new = target(kind, im.size, poster_height, person_width)
        if not new:
            return None
        fmt = im.format
        if fmt not in ("JPEG", "PNG", "WEBP"):
            raise ValueError(f"{fmt} pictures are left as they are")
        if fmt == "JPEG":
            im.draft("RGB" if im.mode != "L" else "L", new)  # decoded at a reduced scale, still at least the new size
        src = im.convert("RGB") if fmt == "JPEG" and im.mode not in ("RGB", "L") else im
        out = src.resize(new, Image.LANCZOS)
    folder, name = os.path.split(path)
    tmp = os.path.join(folder, f".{name}{TMP}")
    try:
        if fmt == "JPEG":
            out.save(tmp, "JPEG", quality=QUALITY, optimize=True, progressive=True)
        elif fmt == "PNG":
            out.save(tmp, "PNG", optimize=True)
        else:
            out.save(tmp, "WEBP", quality=QUALITY)
        out.close()
        with Image.open(tmp) as check:
            check.verify()
        with Image.open(tmp) as check:  # opened again and decoded in full: verify() alone does not decode
            check.load()
            if check.size != new or check.format != fmt:
                raise ValueError(f"the new picture is {check.size[0]} by {check.size[1]} {check.format}, not {new[0]} by {new[1]} {fmt}")
        after = os.path.getsize(tmp)
        if after >= before:
            os.remove(tmp)
            return None  # already as small as it can be: the original is kept
        st = os.stat(path)
        os.chmod(tmp, st.st_mode & 0o777)
        try:
            os.chown(tmp, st.st_uid, st.st_gid)
        except OSError:
            pass  # it runs as the files' owner, so this only matters for a file someone else made
        os.replace(tmp, path)
        return before, after
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _lowest_priority():
    """This thread at nice 19 and in the idle disk class: it gives way to everything else on the server."""
    try:
        os.nice(19)  # on Linux this sets the calling thread only, so Starboard's questions still answer quickly
    except OSError:
        pass
    if shutil.which("ionice"):
        subprocess.run(["ionice", "-c", "3", "-p", str(threading.get_native_id())], capture_output=True, check=False)


def _state():
    s = remember("state", None) or {}
    return {"shrunk": 0, "before": 0, "after": 0, "runs": [], **s}


def run(kind, since=None, limit=RUN_LIMIT):
    """One run over the pictures (or those changed since `since`): returns its record, kept in the state file."""
    _lowest_priority()
    poster_height, person_width = sizes()
    started = now()
    rec = {"kind": kind, "start": started, "end": None, "seen": 0, "shrunk": 0, "left": 0, "failed": 0, "before": 0, "after": 0,
           "stopped": "", "poster_height": poster_height, "person_width": person_width}
    tidy()
    _job["progress"] = {**rec, "at": started}
    failures = []
    for i, (path, pkind, _) in enumerate(pictures(since=since, until=started - NEW_AGE if since is not None else None)):
        if _stop.is_set():
            rec["stopped"] = "Stopped by you" if not sbplugin.holding() else "Stopped for an update"
            break
        if now() - started > limit:
            rec["stopped"] = "Stopped at its time limit; the next run carries on"
            break
        rec["seen"] += 1
        try:
            got = shrink_one(path, pkind, poster_height, person_width)
        except Exception as e:  # noqa: BLE001 - a picture that cannot be read is left as it is
            rec["failed"] += 1
            if len(failures) < 20:
                failures.append({"file": os.path.relpath(path, ROOT), "why": f"{e}"[:160]})
            continue
        if got is None:
            rec["left"] += 1
        else:
            rec["shrunk"] += 1
            rec["before"] += got[0]
            rec["after"] += got[1]
        if i % PROGRESS_EVERY == 0:
            _job["progress"] = {**rec, "at": now()}
        if i % 200 == 0:
            gc.collect()
    rec["end"] = now()
    rec["failures"] = failures
    s = _state()
    s.update(shrunk=s["shrunk"] + rec["shrunk"], before=s["before"] + rec["before"], after=s["after"] + rec["after"],
             runs=(s["runs"] + [rec])[-KEEP_RUNS:])
    if kind == "new" or (kind != "new" and not rec["stopped"]):
        s["new_since"] = (started - NEW_AGE) if kind == "new" else started  # the next pass of new pictures starts here
    keep("state", s)
    _job["progress"] = None
    gc.collect()
    return rec


def summary(rec):
    if not rec:
        return "Nothing shrunk"
    words = (f"Shrank {plural(rec['shrunk'], 'picture')}, {size_words(rec['before'])} to {size_words(rec['after'])}; "
             f"left {rec['left']:,} that were small enough" + (f"; could not read {rec['failed']:,}" if rec["failed"] else ""))
    return words + (f". {rec['stopped']}" if rec["stopped"] else "")


def start(kind, since=None, limit=RUN_LIMIT):
    """Starts a run in the background. False when one is already running, or an update is about to start."""
    with _lock:
        if (_job["thread"] and _job["thread"].is_alive()) or sbplugin.holding():
            return False
        _stop.clear()
        out = {}

        def go():
            try:
                with sbplugin.working("shrinking pictures"):
                    out["rec"] = run(kind, since, limit)
                keep("_error", None)
            except Exception as e:  # noqa: BLE001 - kept for the card and page, never fatal
                keep("_error", {"at": now(), "text": f"{type(e).__name__}: {e}"[:200]})
            finally:
                _job["progress"] = None
        t = threading.Thread(target=go, daemon=True)
        _job.update(thread=t, kind=kind, result=out)
        t.start()
        return True


def running():
    t = _job["thread"]
    return bool(t and t.is_alive())


def _wait(limit):
    t = _job["thread"]
    if t:
        t.join(limit)
    return (_job.get("result") or {}).get("rec")


# What Starboard calls ------------------------------------------------------------------------------------------

def size_words(n):
    n = float(n or 0)
    for unit, by in (("GB", 1e9), ("MB", 1e6), ("KB", 1e3)):
        if abs(n) >= by:
            return f"{n / by:.1f} {unit}"
    return f"{int(n):,} bytes"


def job_shrink():
    """The scheduled job: a full run, answered when it ends (within the job's 120 minutes)."""
    if not os.path.isdir(ROOT):
        raise RuntimeError("Jellyfin's metadata folder is not there")
    if not start("scheduled"):
        return {"said": "Already shrinking" if running() else "Not started: the plug-in is about to be updated"}
    return {"said": summary(_wait(RUN_LIMIT + 60))}


def job_new():
    """Each hour of quiet hours: the pictures Jellyfin saved since the last pass, when that is activated."""
    if setting("new_pictures", False) is not True:
        return {"said": "Shrinking new pictures is deactivated"}
    if running():
        return {"said": "A run is already going"}
    since = float(_state().get("new_since") or (now() - 86400))
    if not start("new", since=since, limit=NEW_LIMIT):
        return {"said": "Not started: the plug-in is about to be updated"}
    rec = _wait(NEW_LIMIT + 60)
    return {"said": "No new pictures to shrink" if rec and not rec["seen"] else summary(rec)}


def shrink_now():
    if running():
        return {"said": "Already shrinking. The card and the Space saved page say how far it has gone"}
    if not start("now"):
        return {"said": "Not started: the plug-in is about to be updated"}
    return {"said": "Shrinking pictures at the lowest priority. The card and the Space saved page say how far it has gone"}


def stop():
    if not running():
        return {"said": "Nothing is being shrunk"}
    _stop.set()
    return {"said": "Stopping after the picture it is on"}


def before_update(body=None):
    """POST /update/before (plug-in API 1.14): no new run starts, and a run stops after the picture it is on.
    Every picture is swapped in whole, so nothing is left half done; the next run carries on."""
    sbplugin._work["hold"] = now() + sbplugin.HOLD_SECONDS
    was = running()
    _stop.set()
    t = _job["thread"]
    if t:
        t.join(30)
    if running():
        sbplugin._work["hold"] = 0.0
        return {"ok": False, "said": "A picture is still being shrunk. Try again in a minute"}
    return {"ok": True, "said": "Stopped shrinking; the next run carries on" if was else "Ready to update: nothing was being shrunk"}


def after_update(body=None):
    sbplugin._work["hold"] = 0.0
    _stop.clear()
    return {"ok": True, "said": f"Ready. The next run is {when_words(next_run())}"}


def card():
    """Space saved, with the band's status: shrinking now, or when it runs next."""
    s, p = _state(), _job["progress"]
    saved = int(s["before"] - s["after"])
    err = remember("_error")
    if p:
        return band({"value": saved + int(p["before"] - p["after"]), "label": "saved",
                     "note": f"Shrinking now: {plural(p['shrunk'], 'picture')} shrunk of {p['seen']:,} looked at"},
                    "running", p["at"], f"{p['shrunk']:,} shrunk so far", refresh=30)
    nxt = next_run()
    if isinstance(err, dict) and err.get("text"):
        return band({"value": saved, "label": "saved", "note": f"The last run did not finish: {err['text']}"[:80]}, "problem", err.get("at"),
                    "Last run failed", refresh=600)
    if not s["runs"]:
        return band({"value": 0, "label": "saved", "note": f"First run {when_words(nxt)}"}, "scheduled", None,
                    f"First run {when_words(nxt, True)}", refresh=600)
    last = s["runs"][-1]
    return band({"value": saved, "label": "saved", "note": f"{plural(s['shrunk'], 'picture')} shrunk. Next run {when_words(nxt)}"},
                "scheduled" if nxt else "done", last["end"], f"Next {when_words(nxt, True)}" if nxt else None, refresh=600)


def screen():
    """Space saved: the totals and each run, in a table to read."""
    s, p = _state(), _job["progress"]
    ph, pw = sizes()
    saved = s["before"] - s["after"]
    intro = (f"{size_words(saved)} saved by shrinking {plural(s['shrunk'], 'picture')}, from {size_words(s['before'])} to "
             f"{size_words(s['after'])}. Posters are shrunk to {ph} pixels tall and photos of people to {pw} pixels wide. "
             f"The next run is {when_words(next_run())}.")
    notices = []
    if not os.path.isdir(ROOT):
        notices.append({"id": "folder", "tone": "danger", "title": "Jellyfin's metadata folder is not there",
                        "text": "Check that Jellyfin is installed in Settings, Apps, then deactivate and activate this plug-in."})
    if p:
        notices.append({"id": "now", "tone": "info", "title": f"Shrinking now: {WHAT.get(_job['kind'], '')}",
                        "text": f"{plural(p['shrunk'], 'picture')} shrunk, {p['left']:,} left as they were, {p['seen']:,} looked at. Choose Stop shrinking in Actions to stop after the picture it is on."})
    err = remember("_error")
    if isinstance(err, dict) and err.get("text"):
        notices.append({"id": "error", "tone": "danger", "title": "The last run did not finish", "text": err["text"][:300], "dismiss": True})
    items = []
    for i, r in enumerate(reversed(s["runs"])):
        when = dt.datetime.fromtimestamp(r["start"])
        items.append({"id": f"r{i}", "title": f"{when:%a %-d %b %Y, %H:%M}", "group": "Runs", "actions": [],
                      "cells": {"when": f"{when:%a %-d %b %Y, %H:%M}", "what": WHAT.get(r["kind"], r["kind"]),
                                "shrunk": f"{r['shrunk']:,}", "left": f"{r['left']:,}", "failed": f"{r['failed']:,}",
                                "saved": size_words(r["before"] - r["after"]), "note": r.get("stopped") or "Finished"}})
        for j, f in enumerate(r.get("failures") or []):
            items.append({"id": f"r{i}f{j}", "title": f["file"], "group": "Could not read", "actions": [],
                          "cells": {"when": f"{when:%a %-d %b %Y}", "what": f["file"], "shrunk": "", "left": "", "failed": "",
                                    "saved": "", "note": f["why"]}})
    return {"type": "list", "title": "Space saved", "layout": "folds", "readonly": True, "intro": intro[:400],
            "columns": [{"key": "when", "label": "When"}, {"key": "what", "label": "What"}, {"key": "shrunk", "label": "Shrunk", "type": "number"},
                        {"key": "left", "label": "Left as they were", "type": "number"}, {"key": "failed", "label": "Could not read", "type": "number"},
                        {"key": "saved", "label": "Saved"}, {"key": "note", "label": "How it ended"}],
            "notices": notices, "items": items}


def screen_post(body=None):
    if (body or {}).get("action") == "dismiss":
        keep("_error", None)
    return screen()


def health():
    """200 only while it can do its work: the metadata folder is there to read and change, and its own folder too."""
    if not os.path.isdir(ROOT) or not os.access(ROOT, os.R_OK | os.W_OK | os.X_OK):
        raise RuntimeError("Jellyfin's metadata folder cannot be read and changed")
    if not os.access(sbplugin.DATA, os.W_OK):
        raise RuntimeError("Its own folder cannot be written")
    return {"ok": True}


ROUTES = {("GET", "/health"): health, "/card": card, "/saved": screen, ("POST", "/saved"): screen_post,
          ("POST", "/shrink-now"): shrink_now, ("POST", "/stop"): stop, ("POST", "/jobs/shrink"): job_shrink,
          ("POST", "/jobs/new"): job_new, ("POST", "/update/before"): before_update, ("POST", "/update/after"): after_update}

if __name__ == "__main__":
    serve(ROUTES)
