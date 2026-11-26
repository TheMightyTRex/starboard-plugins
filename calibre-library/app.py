"""Calibre library maker (DASH-590): makes a new Calibre library from the books in your books folder, so Calibre-Web has
something to open.

- Reads your books folder (read only) and never changes, moves or deletes a book there. Each book is copied into a NEW
  library in its own folder, books-library, by calibredb, Calibre's own command, in batches.
- Safe to run again: books it has already handled are remembered, and Calibre skips a book that is already in the
  library, so only books that arrived since are added.
- Says what it will do first (how many books, how much space, how long), shows progress in words, and lists each file
  it could not read or could read nothing from.
- Rests when not used: Starboard stops it after a few idle minutes, and nothing runs in it between runs.
"""
import datetime as dt
import json
import os
import re
import shutil
import sqlite3
import subprocess
import threading
import time
import zipfile

import sbplugin as sb

SOURCE = os.environ.get("BOOKS", "/media/books")
LIBRARY = os.environ.get("LIBRARY", "/media/books-library")
FORMATS = {"epub", "kepub", "mobi", "azw", "azw3", "pdf", "fb2", "txt", "rtf", "docx", "odt", "cbz", "cbr", "djvu", "lit"}
BATCH = 20
SECONDS_A_BOOK = 3.0  # measured: 2.5 seconds a book and 5 or 6 seconds to start
SECONDS_TO_START = 6.0
SPACE_MARGIN = 1.1  # a library holds a copy of each book, a cover and a small file of details
_lock = threading.Lock()
_stop = threading.Event()


def now():
    return dt.datetime.now(dt.timezone.utc).strftime("%d %B %Y %H:%M UTC")


def size_words(n):
    if n < 5e5:
        return "under 1 MB"
    if n >= 1e12:
        return f"{n / 1e12:,.1f} TB"
    return f"{n / 1e9:,.1f} GB" if n >= 1e9 else f"{n / 1e6:,.0f} MB"


def time_words(seconds):
    minutes = round(seconds / 60)
    if minutes < 1:
        return "under a minute"
    if minutes < 90:
        return "about " + sb.plural(minutes, "minute")
    return f"about {seconds / 3600:,.1f} hours"


# What is in the books folder ---------------------------------------------------------------------------------------

def scan(root=None):
    """[(path, size)] of every book file under the books folder, in a fixed order. Hidden folders and files are left out."""
    root = root or SOURCE
    out = []
    for folder, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for name in sorted(files):
            if name.startswith(".") or name.rsplit(".", 1)[-1].lower() not in FORMATS:
                continue
            path = os.path.join(folder, name)
            try:
                out.append((path, os.path.getsize(path)))
            except OSError:
                continue
    return out


def unreadable(path, size):
    """Why this file cannot be a book, in words, or "" when it looks fine. Calibre adds a damaged file with no details
    instead of refusing it, so Starboard looks first and says which ones it is leaving out."""
    ext = path.rsplit(".", 1)[-1].lower()
    if size == 0:
        return "the file is empty"
    try:
        if ext in ("epub", "kepub", "cbz", "docx", "odt"):
            if not zipfile.is_zipfile(path):
                return "it is not a complete book file (damaged or cut short)"
            with zipfile.ZipFile(path) as z:
                if not z.namelist():
                    return "the book file has nothing in it"
        elif ext == "pdf":
            with open(path, "rb") as f:
                if b"%PDF" not in f.read(1024):
                    return "it is not a PDF file"
        elif ext in ("mobi", "azw", "azw3"):
            with open(path, "rb") as f:
                head = f.read(68)
            if head[60:68] not in (b"BOOKMOBI", b"TEXtREAd") and len(head) < 68:
                return "it is not a complete book file (damaged or cut short)"
    except (OSError, zipfile.BadZipFile) as e:
        return f"it could not be opened ({type(e).__name__})"
    return ""


def key(path, size):
    return f"{os.path.relpath(path, SOURCE)}|{size}"


def library_count():
    """How many books the library holds, or None when there is no library yet."""
    db = os.path.join(LIBRARY, "metadata.db")
    if not os.path.isfile(db):
        return None
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5)
        try:
            return con.execute("select count(*) from books").fetchone()[0]
        finally:
            con.close()
    except sqlite3.Error:
        return None


def free_space():
    try:
        return shutil.disk_usage(LIBRARY if os.path.isdir(LIBRARY) else os.path.dirname(LIBRARY.rstrip("/")) or "/").free
    except OSError:
        return 0


def plan():
    """What a run would do now: the new books, their size, the space needed and the time, and whether it can start."""
    done = set(sb.remember("done", []) or [])
    found = scan()
    new = [(p, s) for p, s in found if key(p, s) not in done]
    total = sum(s for _p, s in new)
    need = int(total * SPACE_MARGIN)
    free = free_space()
    return {"found": len(found), "new": new, "new_count": len(new), "bytes": total, "need": need, "free": free,
            "seconds": SECONDS_TO_START + len(new) * SECONDS_A_BOOK + (len(new) / BATCH) * SECONDS_TO_START,
            "enough": free >= need, "library": library_count()}


# The run ------------------------------------------------------------------------------------------------------------

def calibredb(files):
    """Adds these files to the library with calibredb. Returns (added ids, skipped as already there, output)."""
    env = {**os.environ, "HOME": "/tmp", "QT_QPA_PLATFORM": "offscreen", "CALIBRE_CONFIG_DIRECTORY": "/tmp/calibre"}
    r = subprocess.run(["calibredb", "add", "--with-library", LIBRARY, "--", *files], capture_output=True, text=True,
                       timeout=60 + 60 * len(files), env=env)
    out = (r.stdout or "") + (r.stderr or "")
    if r.returncode != 0:
        raise RuntimeError("Calibre stopped: " + " ".join(out.strip().splitlines()[-1:])[:200])
    ids = [int(i) for i in re.findall(r"\d+", (re.search(r"Added book ids?: ([\d, ]+)", out) or [None, ""])[1])]
    skipped = [line.strip() for line in out.splitlines() if line.startswith("    /")]
    return ids, skipped


def nameless(ids):
    """The titles of added books Calibre found no author in: it names them from the file, which is worth a look."""
    db = os.path.join(LIBRARY, "metadata.db")
    if not ids or not os.path.isfile(db):
        return []
    marks = ",".join("?" * len(ids))
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=10)
        try:
            return [r[0] for r in con.execute(
                f"select b.title from books b join books_authors_link l on l.book = b.id join authors a on a.id = l.author "
                f"where b.id in ({marks}) and a.name = 'Unknown'", ids)]
        finally:
            con.close()
    except sqlite3.Error:
        return []


def run_all(new):
    state = {"state": "running", "total": len(new), "done": 0, "added": 0, "already": 0, "left_out": [], "no_details": [],
             "started": now(), "said": ""}
    sb.keep("run", state)
    done = set(sb.remember("done", []) or [])
    todo = []
    for path, size in new:
        why = unreadable(path, size)
        if why:
            state["left_out"].append({"file": os.path.relpath(path, SOURCE), "why": why})
            state["done"] += 1
        else:
            todo.append((path, size))
    sb.keep("run", state)
    os.makedirs(LIBRARY, exist_ok=True)
    try:
        for i in range(0, len(todo), BATCH):
            if _stop.is_set():
                state.update(state="stopped", said=f"Stopped by you after {sb.plural(state['done'], 'book')}. Run it again to carry on.", finished=now())
                break
            chunk = todo[i:i + BATCH]
            try:
                ids, skipped = calibredb([p for p, _s in chunk])
            except (RuntimeError, subprocess.TimeoutExpired, OSError) as e:
                for path, _s in chunk:
                    state["left_out"].append({"file": os.path.relpath(path, SOURCE), "why": str(e) if isinstance(e, RuntimeError) else "Calibre took too long over this group of books"})
                state["done"] += len(chunk)
                sb.keep("run", state)
                continue
            state["added"] += len(ids)
            state["already"] += len(skipped)
            state["done"] += len(chunk)
            state["no_details"] += nameless(ids)
            done |= {key(p, s) for p, s in chunk}
            sb.keep("done", sorted(done))
            sb.keep("run", state)
        else:
            state.update(state="ok", finished=now(), said=summary(state))
    except Exception as e:  # noqa: BLE001 - said on the page
        state.update(state="problem", said=f"It stopped: {e}"[:300], finished=now())
    sb.keep("run", state)


def summary(state):
    parts = [f"Added {sb.plural(state['added'], 'book')} to your library"]
    if state["already"]:
        parts.append(f"{sb.plural(state['already'], 'book')} {'was' if state['already'] == 1 else 'were'} already there")
    if state["left_out"]:
        parts.append(f"{sb.plural(len(state['left_out']), 'file')} could not be read and {'was' if len(state['left_out']) == 1 else 'were'} left out")
    return ". ".join(parts) + "."


def start():
    if not _lock.acquire(blocking=False):
        return {"said": "It is already making the library"}
    p = plan()
    if not p["new_count"]:
        _lock.release()
        return {"said": "There is nothing new to add. Every book in your books folder is already handled"}
    if not p["enough"]:
        _lock.release()
        return {"said": f"There is not enough room. The library needs about {size_words(p['need'])} and {size_words(p['free'])} is free"}
    _stop.clear()

    def go():
        try:
            with sb.working("making the library"):  # an update waits for it, or is refused
                run_all(p["new"])
        finally:
            _lock.release()
    threading.Thread(target=go, daemon=True).start()
    return {"said": f"Making your library from {sb.plural(p['new_count'], 'book')}. The page shows how far it has got"}


def stop():
    if not _lock.locked():
        return {"said": "Nothing is running"}
    _stop.set()
    return {"said": "Stopping after the books it is adding now"}


# What Starboard shows ----------------------------------------------------------------------------------------------

def screen():
    run = sb.remember("run", {}) or {}
    running = _lock.locked()
    if run.get("state") == "running" and not running:  # the container was restarted in the middle
        run = {**run, "state": "stopped", "said": "It was interrupted. Run it again to carry on: books already added are kept."}
        sb.keep("run", run)
    p = plan()
    items = []
    if running and run.get("state") == "running":
        items.append({"id": "progress", "title": f"Making your library: {run['done']:,} of {run['total']:,} books", "state": "warning",
                      "state_label": "Working",
                      "detail": f"Added {run['added']:,}. {len(run['left_out'])} left out. Started {run['started']}. It takes "
                                f"{time_words(max(0, run['total'] - run['done']) * SECONDS_A_BOOK)} more.", "actions": []})
    elif run.get("said"):
        items.append({"id": "last", "title": "Last run", "detail": f"{run['said']} ({run.get('finished', run.get('started', ''))})",
                      "state": {"ok": "ok", "stopped": "warning", "problem": "problem"}.get(run.get("state"), "unknown"),
                      "state_label": {"ok": "Done", "stopped": "Stopped", "problem": "Problem"}.get(run.get("state"), ""), "actions": []})
    have = p["library"]
    items.append({"id": "books", "title": "Your books folder", "state": "ok" if p["found"] else "warning",
                  "state_label": "Found" if p["found"] else "Empty",
                  "detail": (f"{sb.plural(p['found'], 'book file')}, {p['new_count']:,} not yet in the library"
                             f" ({size_words(p['bytes'])}). Starboard never changes this folder.") if p["found"]
                  else "No book files were found in your books folder.", "actions": []})
    items.append({"id": "library", "title": "Your Calibre library", "state": "ok" if have else "unknown",
                  "state_label": "Made" if have else "Not made yet",
                  "detail": (f"{sb.plural(have, 'book')} in the books-library folder. Calibre-Web opens it when it next starts." if have
                             else "The books-library folder has no Calibre library yet."), "actions": []})
    if p["new_count"] and not running:
        items.append({"id": "plan", "title": "What Make the library will do", "state": "ok" if p["enough"] else "problem",
                      "state_label": "Ready" if p["enough"] else "Not enough room",
                      "detail": (f"It copies {sb.plural(p['new_count'], 'book')} ({size_words(p['bytes'])}) into the books-library folder, which needs "
                                 f"about {size_words(p['need'])}; {size_words(p['free'])} is free. It takes {time_words(p['seconds'])}. "
                                 "Your own files are not touched."), "actions": []})
    for n, f in enumerate(run.get("left_out") or []):
        items.append({"id": f"out{n}", "title": f["file"], "state": "problem", "state_label": "Left out",
                      "detail": f"Could not be read: {f['why']}.", "actions": []})
    for n, title in enumerate(run.get("no_details") or []):
        items.append({"id": f"nod{n}", "title": title, "state": "warning", "state_label": "Added, no author",
                      "detail": "Calibre found no title or author inside this file, so it named the book from the file.", "actions": []})
    return {"type": "list", "title": "Make a Calibre library from your books",
            "intro": "Calibre-Web needs a Calibre library, which is a folder with a file called metadata.db. Your books folder is not one, "
                     "so this makes a new one beside it, in books-library, by copying each book with Calibre's own tool. Your books folder is "
                     "read only here and is never changed. Run it again later to add books that arrived since. Then deactivate and activate "
                     "Calibre-Web, so it opens the library.",
            "items": items}


def main():
    os.makedirs(sb.DATA, exist_ok=True)
    sb.serve({"/library": screen, ("POST", "/library"): lambda body=None: {**screen(), "said": ""},
              ("POST", "/make"): start, ("POST", "/stop"): stop})


if __name__ == "__main__":
    main()
