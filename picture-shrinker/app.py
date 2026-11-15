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

Rules 1.1 (DASH-433): the rules are in rules.json, the same file as the Jellyfin plug-in's
(TheMightyTRex/jellyfin-plugin-picture-shrinker, SYNC.md there); tools/sync_picture_rules.py copies it in. Each original
is backed up before its first shrink (activated by default), and Restore original pictures puts them back. When the
Jellyfin plug-in is installed, this one stays idle, so the two never shrink the same pictures. A finished run sends no
notification: its only result is the figures on the card and the Space saved page.

Lightweight: nothing runs between runs. Pillow is loaded for the first run only, a JPEG is decoded at a reduced scale
(draft), and the card and page read a small state file.
"""
import calendar
import datetime as dt
import gc
import json
import os
import shutil
import subprocess
import threading
import time

import sbplugin
from sbplugin import band, keep, plural, remember, serve, setting

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "rules.json"), encoding="utf-8") as _f:
    RULES = json.load(_f)  # the rules both picture shrinkers follow (SYNC.md in the Jellyfin plug-in's repository)
ROOT = os.environ.get("PICTURE_SHRINKER_ROOT", "/metadata")
BACKUP = os.environ.get("PICTURE_SHRINKER_BACKUP", os.path.join(os.environ.get("PLUGIN_DATA", "/data"), "originals"))
POSTER, PERSON = RULES["kinds"]["poster"], RULES["kinds"]["person"]
EXTS = set(RULES["extensions"])
FORMATS = tuple(RULES["formats"])
TMP = RULES["temp_suffix"]  # its own unfinished copies, beside each picture: never shrunk, tidied at each run
QUALITY = RULES["quality"]["default"]
KEEP_FREE = RULES["backup"]["keep_free_bytes"]  # the backup disk keeps this much free, or the picture is not shrunk
RUN_LIMIT = RULES["run_limit_minutes"] * 60  # a run stops itself before the job's 120 minutes; the next carries on
NEW_LIMIT = 25 * 60  # the quiet-hours pass for new pictures, inside its 30 minutes
NEW_AGE = RULES["new_pictures"]["min_age_seconds"]  # a picture this new is left for the next pass: Jellyfin may still be writing it
PROGRESS_EVERY = 25  # pictures between notes of how far a run has gone
KEEP_RUNS = RULES["keep_runs"]
KEEP_FAILURES = RULES["keep_failures_per_run"]
JELLYFIN_PLUGIN = "80bf9325d2994e24ac74c087aeec3011"  # the Jellyfin version's id (DASH-433)
JELLYFIN_CHECK_EVERY = 600  # seconds between asks of Jellyfin's plug-in list
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
DEFAULT_WHEN = {"every": "week", "day": "sunday", "time": "03:30"}
WHAT = {"scheduled": "On its schedule", "now": "Shrink now", "new": "New pictures", "restore": "Restore original pictures"}
now = time.time  # replaced in tests

_lock = threading.Lock()
_job = {"thread": None, "kind": "", "progress": None}
_jf = {"at": 0.0, "installed": False}
_stop = threading.Event()


# Settings ------------------------------------------------------------------------------------------------------

def _num(key, default, lo, hi):
    try:
        return int(max(lo, min(float(setting(key, default)), hi)))
    except (TypeError, ValueError):
        return default


def sizes():
    """(the tallest a poster may be, the widest a photo of a person may be), in pixels."""
    return (_num("poster_height", POSTER["default"], POSTER["min"], POSTER["max"]),
            _num("person_width", PERSON["default"], PERSON["min"], PERSON["max"]))


def quality():
    q = RULES["quality"]
    return _num("quality", q["default"], q["min"], q["max"])


def backup_on():
    return setting("backup", RULES["backup"]["default"]) is not False


def included():
    """The kinds of picture to shrink: posters, photos of people, or both (the default)."""
    return {k for k, key in (("poster", "posters"), ("person", "people")) if setting(key, True) is not False}


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
    if len(rel) < 2 or rel[0] == "..":
        return None
    if rel[0] == PERSON["folder"] and name.startswith(PERSON["name_starts_with"]):
        return "person"
    if rel[0] == POSTER["folder"] and name.startswith(POSTER["name_starts_with"]):
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
    for top in (POSTER["folder"], PERSON["folder"]):
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
    for top in [folder_root] if folder_root else [ROOT, BACKUP]:
        for folder, _, names in os.walk(top):
            for name in names:
                if name.endswith(TMP):
                    try:
                        os.remove(os.path.join(folder, name))
                        gone += 1
                    except OSError:
                        pass
    return gone


class BackupError(Exception):
    """The original could not be backed up, so the picture is not shrunk."""


def backup_path(path):
    return os.path.join(BACKUP, os.path.relpath(path, ROOT))


def back_up(path, size):
    """Copies the original to the backup folder unless a backup of it is already there (never overwritten: the one
    there is the original, this one may be shrunk already). Returns the bytes copied. Raises BackupError."""
    copy = backup_path(path)
    if os.path.exists(copy):
        return 0
    tmp = copy + TMP
    try:
        os.makedirs(os.path.dirname(copy), exist_ok=True)
        free = shutil.disk_usage(os.path.dirname(copy)).free
        if free < size + KEEP_FREE:
            raise BackupError(f"not shrunk: the backup disk has only {size_words(free)} free")
        shutil.copyfile(path, tmp)
        if os.path.getsize(tmp) != size:
            raise BackupError("not shrunk: the backup copy is not the same size as the original")
        st = os.stat(path)
        os.utime(tmp, ns=(st.st_atime_ns, st.st_mtime_ns))
        os.replace(tmp, copy)
        return size
    except OSError as e:
        raise BackupError(f"not shrunk: the original could not be backed up ({e.strerror or e})") from None
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def shrink_one(path, kind, poster_height, person_width, q=None, backup=None):
    """Shrinks one picture in place. Returns None when it is left alone, else (bytes before, bytes after, bytes backed
    up). Raises ValueError or OSError when it cannot be read or the new file fails its check, and BackupError when its
    original cannot be backed up; the original is then kept."""
    q = QUALITY if q is None else q
    backup = backup_on() if backup is None else backup
    from PIL import Image  # loaded at the first run only
    before = os.path.getsize(path)
    with Image.open(path) as im:
        new = target(kind, im.size, poster_height, person_width)
        if not new:
            return None
        fmt = im.format
        if fmt not in FORMATS:
            raise ValueError(f"{fmt} pictures are left as they are")
        if fmt == "JPEG":
            im.draft("RGB" if im.mode != "L" else "L", new)  # decoded at a reduced scale, still at least the new size
        src = im.convert("RGB") if fmt == "JPEG" and im.mode not in ("RGB", "L") else im
        out = src.resize(new, Image.LANCZOS)
    folder, name = os.path.split(path)
    tmp = os.path.join(folder, f".{name}{TMP}")
    try:
        if fmt == "JPEG":
            out.save(tmp, "JPEG", quality=q, optimize=True, progressive=True)
        elif fmt == "PNG":
            out.save(tmp, "PNG", optimize=True)
        else:
            out.save(tmp, "WEBP", quality=q)
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
        copied = back_up(path, before) if backup else 0
        st = os.stat(path)
        os.chmod(tmp, st.st_mode & 0o777)
        try:
            os.chown(tmp, st.st_uid, st.st_gid)
        except OSError:
            pass  # it runs as the files' owner, so this only matters for a file someone else made
        os.replace(tmp, path)
        return before, after, copied
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
    q, backup, kinds = quality(), backup_on(), included()
    started = now()
    rec = {"kind": kind, "start": started, "end": None, "seen": 0, "shrunk": 0, "left": 0, "failed": 0, "not_backed_up": 0,
           "before": 0, "after": 0, "backed_up": 0, "backed_up_bytes": 0, "stopped": "", "poster_height": poster_height,
           "person_width": person_width}
    tidy()
    _job["progress"] = {**rec, "at": started}
    failures = []
    for i, (path, pkind, _) in enumerate(p for p in pictures(since=since, until=started - NEW_AGE if since is not None else None) if p[1] in kinds):
        if _stop.is_set():
            rec["stopped"] = "Stopped by you" if not sbplugin.holding() else "Stopped for an update"
            break
        if now() - started > limit:
            rec["stopped"] = "Stopped at its time limit; the next run carries on"
            break
        rec["seen"] += 1
        try:
            got = shrink_one(path, pkind, poster_height, person_width, q, backup)
        except Exception as e:  # noqa: BLE001 - a picture that cannot be read, or backed up, is left as it is
            rec["not_backed_up" if isinstance(e, BackupError) else "failed"] += 1
            if len(failures) < KEEP_FAILURES:
                failures.append({"file": os.path.relpath(path, ROOT), "why": f"{e}"[:160]})
            continue
        if got is None:
            rec["left"] += 1
        else:
            rec["shrunk"] += 1
            rec["before"] += got[0]
            rec["after"] += got[1]
            if got[2]:
                rec["backed_up"] += 1
                rec["backed_up_bytes"] += got[2]
        if i % PROGRESS_EVERY == 0:
            _job["progress"] = {**rec, "at": now()}
        if i % 200 == 0:
            gc.collect()
    rec["end"] = now()
    rec["failures"] = failures
    if rec["not_backed_up"] and not rec["stopped"]:
        rec["stopped"] = f"{rec['not_backed_up']:,} not shrunk because their originals could not be backed up"
    s = _state()
    s.update(shrunk=s["shrunk"] + rec["shrunk"], before=s["before"] + rec["before"], after=s["after"] + rec["after"],
             runs=(s["runs"] + [rec])[-KEEP_RUNS:])
    if kind == "new" or (kind != "new" and not rec["stopped"]):
        s["new_since"] = (started - NEW_AGE) if kind == "new" else started  # the next pass of new pictures starts here
    keep("state", s)
    keep("space", measure())  # the figures the card shows, measured after each run, never on a timer
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
    """Starts a run (or a restore) in the background. False when one is already running, or an update is about to
    start."""
    with _lock:
        if (_job["thread"] and _job["thread"].is_alive()) or sbplugin.holding():
            return False
        _stop.clear()
        out = {}

        def go():
            try:
                with sbplugin.working("restoring pictures" if kind == "restore" else "shrinking pictures"):
                    out["rec"] = restore() if kind == "restore" else run(kind, since, limit)
                keep("_error", None)
            except Exception as e:  # noqa: BLE001 - kept for the page as the last run's result, never fatal
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


# Backup: restore, measure and delete ---------------------------------------------------------------------------

def _same(a, b):
    if os.path.getsize(a) != os.path.getsize(b):
        return False
    with open(a, "rb") as fa, open(b, "rb") as fb:
        while True:
            x, y = fa.read(1 << 16), fb.read(1 << 16)
            if x != y:
                return False
            if not x:
                return True


def _backups():
    """Each file in the backup folder that the shrinker put there: pictures under library and People."""
    for top in (POSTER["folder"], PERSON["folder"]):
        for folder, dirs, names in os.walk(os.path.join(BACKUP, top)):  # os.walk never follows a link to a folder
            dirs.sort()
            for name in sorted(names):
                if not name.endswith(TMP):
                    yield os.path.join(folder, name)


def restore():
    """Puts every backed-up original back where it came from. The backup is kept, so it can be done again; a picture
    whose film, series or person is no longer in Jellyfin stays in the backup."""
    _lowest_priority()
    rec = {"kind": "restore", "start": now(), "end": None, "restored": 0, "bytes": 0, "shrunk_bytes": 0, "already": 0, "gone": 0,
           "failed": 0, "stopped": ""}
    for copy in _backups():
        if _stop.is_set():
            rec["stopped"] = "Stopped by you" if not sbplugin.holding() else "Stopped for an update"
            break
        live = os.path.join(ROOT, os.path.relpath(copy, BACKUP))
        if not kind_of(live) or not os.path.isdir(os.path.dirname(live)):
            rec["gone"] += 1
            continue
        tmp = os.path.join(os.path.dirname(live), f".{os.path.basename(live)}{TMP}")
        try:
            if os.path.exists(live) and _same(copy, live):
                rec["already"] += 1
                continue
            shrunk_size = os.path.getsize(live) if os.path.exists(live) else 0
            shutil.copyfile(copy, tmp)
            if os.path.exists(live):
                st = os.stat(live)
                os.chmod(tmp, st.st_mode & 0o777)
                try:
                    os.chown(tmp, st.st_uid, st.st_gid)
                except OSError:
                    pass
            os.replace(tmp, live)
            rec["restored"] += 1
            rec["bytes"] += os.path.getsize(live)
            rec["shrunk_bytes"] += shrunk_size
        except OSError:
            rec["failed"] += 1
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
    rec["end"] = now()
    s = _state()
    s["last_restore"] = rec
    # The space saved is what is saved now: a restored picture no longer counts.
    s.update(shrunk=max(0, s["shrunk"] - rec["restored"]), before=max(0, s["before"] - rec["bytes"]),
             after=max(0, s["after"] - rec["shrunk_bytes"]))
    keep("state", s)
    keep("space", measure())
    return rec


def measure():
    """The live pictures, the backup and the space saved, measured now: when the page opens and after each run or
    action, never on a timer."""
    live = [0, 0]
    for _, _, size in pictures():
        live[0] += 1
        live[1] += size
    backup = [0, 0]
    for path in _backups():
        try:
            backup[1] += os.path.getsize(path)
            backup[0] += 1
        except OSError:
            pass
    s = _state()
    return {"live_count": live[0], "live_bytes": live[1], "backup_count": backup[0], "backup_bytes": backup[1],
            "saved": s["before"] - s["after"], "shrunk": s["shrunk"], "measured": now()}


def delete_backup():
    """Deletes the backup for good: only pictures the shrinker put in the backup folder (no link is followed out of
    it), then its empty folders. Refused while a run or a restore is going."""
    root = os.path.realpath(BACKUP)
    if not os.path.isdir(root):
        return {"said": "There is no backup to delete"}
    if running():
        return {"said": "Not deleted: the shrinker is running. Try again when it has finished"}
    with _lock:
        files = size = 0
        for path in list(_backups()):
            real = os.path.realpath(path) if not os.path.islink(path) else os.path.join(os.path.realpath(os.path.dirname(path)), os.path.basename(path))
            if not real.startswith(root + os.sep) or os.path.splitext(path)[1].lower() not in EXTS:
                continue
            try:
                n = 0 if os.path.islink(path) else os.path.getsize(path)
                os.remove(path)  # a link is removed itself, never what it points at
                files += 1
                size += n
            except OSError:
                pass
        for top in (POSTER["folder"], PERSON["folder"]):
            for folder, _, _ in sorted(os.walk(os.path.join(root, top), topdown=False), key=lambda w: -len(w[0])):
                try:
                    if os.path.realpath(folder).startswith(root + os.sep) and not os.listdir(folder):
                        os.rmdir(folder)
                except OSError:
                    pass
        print(f"Deleted the backup: {files} original pictures, {size} bytes, from {root}", flush=True)
        s = _state()
        s["last_delete"] = {"at": now(), "files": files, "bytes": size}
        keep("state", s)
    if not files:
        return {"said": "There is no backup to delete"}
    keep("space", measure())
    return {"said": f"Deleted the backup: {plural(files, 'original picture')}, {size_words(size)} freed. The shrunk pictures stay"}


# The Jellyfin version ------------------------------------------------------------------------------------------

def jellyfin_version_installed(force=False):
    """True when Jellyfin's own Picture shrinker plug-in is installed and not deactivated (asked of Jellyfin's
    /Plugins at most every 10 minutes). Then this one stays idle, so the two never shrink the same pictures. When
    Jellyfin cannot be asked, it carries on as before."""
    if not force and now() - _jf["at"] < JELLYFIN_CHECK_EVERY:
        return _jf["installed"]
    try:
        plugins = sbplugin.jellyfin("/Plugins") or []
        _jf["installed"] = any(str(p.get("Id") or "").replace("-", "").lower() == JELLYFIN_PLUGIN
                               and str(p.get("Status") or "") not in ("Disabled", "Deleted", "Superseded", "NotSupported")
                               for p in plugins if isinstance(p, dict))
    except Exception:  # noqa: BLE001 - no key yet, or Jellyfin is restarting: keep the last answer
        pass
    _jf["at"] = now()
    return _jf["installed"]


IDLE = ("Idle: Jellyfin's own Picture shrinker plug-in is installed, so this one does nothing and the two never shrink "
        "the same pictures. Remove one of them")


# What Starboard calls ------------------------------------------------------------------------------------------

def size_words(n):
    n = float(n or 0)
    for unit, by in (("GB", 1e9), ("MB", 1e6), ("KB", 1e3)):
        if abs(n) >= by:
            return f"{n / by:.1f} {unit}"
    return f"{int(n):,} bytes"


def job_shrink():
    """The scheduled job: a full run, answered when it ends (within the job's 120 minutes). Its answer goes only to
    Starboard's own job history: no notification is sent."""
    if not os.path.isdir(ROOT):
        raise RuntimeError("Jellyfin's metadata folder is not there")
    if jellyfin_version_installed():
        return {"said": IDLE}
    if not start("scheduled"):
        return {"said": "Already shrinking" if running() else "Not started: the plug-in is about to be updated"}
    return {"said": summary(_wait(RUN_LIMIT + 60))}


def job_new():
    """Each hour of quiet hours: the pictures Jellyfin saved since the last pass, when that is activated."""
    if setting("new_pictures", RULES["new_pictures"]["default"]) is not True:
        return {"said": "Shrinking new pictures is deactivated"}
    if jellyfin_version_installed():
        return {"said": IDLE}
    if running():
        return {"said": "A run is already going"}
    since = float(_state().get("new_since") or (now() - 86400))
    if not start("new", since=since, limit=NEW_LIMIT):
        return {"said": "Not started: the plug-in is about to be updated"}
    rec = _wait(NEW_LIMIT + 60)
    return {"said": "No new pictures to shrink" if rec and not rec["seen"] else summary(rec)}


def shrink_now():
    if jellyfin_version_installed(force=True):
        return {"said": IDLE}
    if running():
        return {"said": "Already shrinking. The Space saved page says how far it has gone"}
    if not start("now"):
        return {"said": "Not started: the plug-in is about to be updated"}
    return {"said": "Shrinking pictures at the lowest priority. The Space saved page says how far it has gone"}


def restore_now():
    if running():
        return {"said": "Not started: a run is going. Choose Stop shrinking first, or try again when it has finished"}
    if not any(True for _ in _backups()):
        return {"said": "There is no backup to restore"}
    if not start("restore"):
        return {"said": "Not started: the plug-in is about to be updated"}
    return {"said": "Putting the original pictures back. The Space saved page says when it has finished. Change When to shrink, or the next run shrinks them again"}


def delete_backup_now():
    return delete_backup()


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
    """Space saved and the backup, from the figures kept after the last run or action. The band always says when it
    runs next (or that it is idle): a finished run, or a failed one, changes only the figures, never the status, so
    nothing on the dashboard asks for attention."""
    s, p = _state(), _job["progress"]
    sp = remember("space", None) or {}
    saved = int(s["before"] - s["after"])
    backup = f"; backup {size_words(sp.get('backup_bytes', 0))}" if sp.get("backup_count") else ""
    if jellyfin_version_installed():
        return band({"value": saved, "label": "saved", "note": "Idle: Jellyfin's own Picture shrinker is installed"}, "idle", None,
                    "Idle", refresh=600)
    nxt = next_run()
    label = f"Next {when_words(nxt, True)}" if nxt else None
    if p:
        return band({"value": saved + int(p["before"] - p["after"]), "label": "saved",
                     "note": f"{plural(p['shrunk'], 'picture')} shrunk of {p['seen']:,} looked at so far"},
                    "scheduled", None, label, refresh=60)
    if not s["runs"]:
        return band({"value": 0, "label": "saved", "note": f"First run {when_words(nxt)}"}, "scheduled", None,
                    f"First run {when_words(nxt, True)}", refresh=600)
    last = s["runs"][-1]
    return band({"value": saved, "label": "saved", "note": f"{plural(s['shrunk'], 'picture')} shrunk{backup}. Next run {when_words(nxt)}"[:120]},
                "scheduled" if nxt else "done", last["end"], label, refresh=600)


def screen():
    """Space saved: the pictures now, the backup and the space saved (measured as the page opens), and each run."""
    s, p = _state(), _job["progress"]
    ph, pw = sizes()
    sp = measure()
    keep("space", sp)
    intro = (f"Pictures now: {size_words(sp['live_bytes'])} in {plural(sp['live_count'], 'poster or photo', 'posters and photos')}. "
             f"Backup of the originals: {size_words(sp['backup_bytes'])} in {plural(sp['backup_count'], 'picture')}. "
             f"Space saved: {size_words(sp['saved'])} by shrinking {plural(sp['shrunk'], 'picture')}. "
             f"Posters to {ph} pixels tall, photos of people to {pw} wide. The next run is {when_words(next_run())}.")
    notices = []
    if jellyfin_version_installed(force=True):
        notices.append({"id": "jellyfin", "tone": "info", "title": "Idle: Jellyfin's own Picture shrinker is installed",
                        "text": "This plug-in does nothing while Jellyfin's own version is installed, so the two never shrink the same pictures. Remove one of them."})
    if not os.path.isdir(ROOT):
        notices.append({"id": "folder", "tone": "danger", "title": "Jellyfin's metadata folder is not there",
                        "text": "Check that Jellyfin is installed in Settings, Apps, then deactivate and activate this plug-in."})
    if not backup_on():
        notices.append({"id": "nobackup", "tone": "warning", "title": "Backup is deactivated",
                        "text": "Pictures shrunk from now on cannot be put back. Jellyfin can download them again with Refresh metadata, but pictures you chose yourself are lost."})
    if p:
        notices.append({"id": "now", "tone": "info", "title": f"Running now: {WHAT.get(_job['kind'], '')}",
                        "text": f"{plural(p['shrunk'], 'picture')} shrunk, {p['left']:,} left as they were, {p['seen']:,} looked at. Choose Stop shrinking in Actions to stop after the picture it is on."})
    err = remember("_error")
    if isinstance(err, dict) and err.get("text"):
        notices.append({"id": "error", "tone": "danger", "title": "The last run did not finish", "text": err["text"][:300], "dismiss": True})
    if s.get("last_restore"):
        r = s["last_restore"]
        notices.append({"id": "restore", "tone": "info", "title": "Last restore",
                        "text": f"Put back {plural(r['restored'], 'original picture')}; {r['already']:,} were already the original; {r['gone']:,} are no longer in Jellyfin. {r.get('stopped') or ''}".strip(), "dismiss": True})
    items = []
    for i, r in enumerate(reversed(s["runs"])):
        when = dt.datetime.fromtimestamp(r["start"])
        items.append({"id": f"r{i}", "title": f"{when:%a %-d %b %Y, %H:%M}", "group": "Runs", "actions": [],
                      "cells": {"when": f"{when:%a %-d %b %Y, %H:%M}", "what": WHAT.get(r["kind"], r["kind"]),
                                "shrunk": f"{r['shrunk']:,}", "left": f"{r['left']:,}", "failed": f"{r['failed'] + r.get('not_backed_up', 0):,}",
                                "saved": size_words(r["before"] - r["after"]), "note": r.get("stopped") or "Finished"}})
        for j, f in enumerate(r.get("failures") or []):
            items.append({"id": f"r{i}f{j}", "title": f["file"], "group": "Not shrunk", "actions": [],
                          "cells": {"when": f"{when:%a %-d %b %Y}", "what": f["file"], "shrunk": "", "left": "", "failed": "",
                                    "saved": "", "note": f["why"]}})
    return {"type": "list", "title": "Space saved", "layout": "folds", "readonly": True, "intro": intro[:400],
            "columns": [{"key": "when", "label": "When"}, {"key": "what", "label": "What"}, {"key": "shrunk", "label": "Shrunk", "type": "number"},
                        {"key": "left", "label": "Left as they were", "type": "number"}, {"key": "failed", "label": "Not shrunk", "type": "number"},
                        {"key": "saved", "label": "Saved"}, {"key": "note", "label": "How it ended"}],
            "notices": notices, "items": items}


def screen_post(body=None):
    if (body or {}).get("action") == "dismiss":
        if (body or {}).get("id") == "restore":
            s = _state()
            s.pop("last_restore", None)
            keep("state", s)
        else:
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
          ("POST", "/shrink-now"): shrink_now, ("POST", "/stop"): stop, ("POST", "/restore"): restore_now,
          ("POST", "/delete-backup"): delete_backup_now, ("POST", "/jobs/shrink"): job_shrink,
          ("POST", "/jobs/new"): job_new, ("POST", "/update/before"): before_update, ("POST", "/update/after"): after_update}

if __name__ == "__main__":
    serve(ROUTES)
