"""Jellystat plug-in helper (DASH-411): the small part Starboard talks to, beside Jellystat and its PostgreSQL.

- Hands Jellyfin's address and key (from Starboard, permission jellyfin:key) to Jellystat once, the first time it
  starts with an empty database, so nobody types them into Jellystat's own set-up page.
- Restore a Jellystat backup: a PostgreSQL dump (pg_dump -Fc, as Jellystat's own database makes) that the person puts
  in the restore folder and names in the plug-in's settings. It is restored into a new database first; only when that
  worked is it swapped in, and the database it replaces is kept beside it (jfstat_before_<date>), never deleted.
- Tells Starboard how Jellystat is: a status card and the restore screen.

Python's standard library, plus psql and pg_restore from the PostgreSQL image it is built on (the same version as
the database container).
"""
import datetime as dt
import os
import re
import subprocess
import threading
import time

import sbplugin as sb

APP = os.environ.get("JELLYSTAT_URL", "http://plugin-jellystat-app:3000").rstrip("/")
DB = os.environ.get("PGDATABASE", "jfstat")
RESTORE_DIR = os.path.join(sb.DATA, "restore")
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,120}$")
_lock = threading.Lock()


def _now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def psql(sql, db="postgres", timeout=60):
    """One SQL statement through psql as the database's owner; returns its output, or raises with psql's words."""
    r = subprocess.run(["psql", "-X", "-q", "-t", "-A", "-v", "ON_ERROR_STOP=1", "-d", db, "-c", sql],
                       capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip()[-300:] or "psql failed")
    return r.stdout.strip()


# Jellyfin's address and key, handed over once ------------------------------------------------------------------

def connect():
    """While Jellystat has no Jellyfin yet (state 0), gives it Starboard's address and key through its own set-up
    call, which checks them against Jellyfin before saving."""
    try:
        state = sb.fetch(APP + "/auth/isConfigured", timeout=10).get("state")
    except Exception as e:  # noqa: BLE001 - Jellystat still starting
        sb.keep("connect", {"ok": False, "said": f"Jellystat is not answering yet: {e}"[:200], "at": _now()})
        return
    if state:  # 1: Jellyfin given, no Jellystat user yet; 2: ready
        sb.keep("connect", {"ok": True, "state": state, "said": "Jellystat has your Jellyfin.", "at": _now()})
        return
    jf = sb._json_file(os.path.join(sb.RUN, "jellyfin.json"), {}) or {}
    if not jf.get("url") or not jf.get("api_key"):
        sb.keep("connect", {"ok": False, "said": "Starboard has no Jellyfin key to give yet: add Jellyfin in Settings, Apps.", "at": _now()})
        return
    try:
        sb.fetch(APP + "/auth/configSetup", data={"JF_HOST": jf["url"], "JF_API_KEY": jf["api_key"]}, method="POST", timeout=30)
        sb.keep("connect", {"ok": True, "state": 1, "said": "Gave Jellystat your Jellyfin's address and key.", "at": _now()})
    except Exception as e:  # noqa: BLE001
        sb.keep("connect", {"ok": False, "said": f"Jellystat did not accept Jellyfin's address and key: {e}"[:200], "at": _now()})


# Restore ------------------------------------------------------------------------------------------------------------

def found():
    """The files in the restore folder, newest first: [{name, size, when}]."""
    os.makedirs(RESTORE_DIR, exist_ok=True)
    out = []
    for n in os.listdir(RESTORE_DIR):
        p = os.path.join(RESTORE_DIR, n)
        if os.path.isfile(p) and not n.startswith("."):
            st = os.stat(p)
            out.append({"name": n, "size": st.st_size, "when": st.st_mtime})
    return sorted(out, key=lambda f: -f["when"])


def check_dump(path):
    """True when the file is a PostgreSQL custom-format dump pg_restore can read; else the reason, in words."""
    with open(path, "rb") as f:
        if f.read(5) != b"PGDMP":
            return "It is not a PostgreSQL backup made with pg_dump -Fc (Jellystat's own JSON backups are restored in Jellystat itself)"
    r = subprocess.run(["pg_restore", "-l", path], capture_output=True, text=True, timeout=120)
    return True if r.returncode == 0 else f"pg_restore cannot read it: {r.stderr.strip()[-200:]}"


def restore(name, stamp=None):
    """Restores one dump into a new database and swaps it in. Returns what happened, in words; raises on a problem."""
    if not NAME.match(name or "") or "/" in name or name in (".", ".."):
        raise ValueError("Give the file's name only, such as jfstat.pgdump")
    path = os.path.join(RESTORE_DIR, name)
    if not os.path.isfile(path):
        raise ValueError(f"There is no {name} in the restore folder")
    ok = check_dump(path)
    if ok is not True:
        raise ValueError(ok)
    stamp = stamp or dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    work, before = f"{DB}_restore_{stamp}", f"{DB}_before_{stamp}"
    psql(f'CREATE DATABASE "{work}"')
    r = subprocess.run(["pg_restore", "--no-owner", "--no-privileges", "--exit-on-error", "-d", work, path],
                       capture_output=True, text=True, timeout=3600)
    if r.returncode != 0:
        # The half-made copy is kept, renamed so it is plain what it is; the person's database was not touched.
        psql(f'ALTER DATABASE "{work}" RENAME TO "{DB}_failed_{stamp}"')
        raise RuntimeError(f"The backup did not restore, so nothing was changed: {r.stderr.strip()[-200:]}")
    tables = psql("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'", db=work)
    # Swap: Jellystat holds connections, so they are closed just before each rename; it connects again by itself.
    for _ in range(10):
        try:
            psql(f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname IN ('{DB}', '{work}') AND pid <> pg_backend_pid();"
                 f' ALTER DATABASE "{DB}" RENAME TO "{before}";')
            break
        except RuntimeError:
            time.sleep(1)
    else:
        raise RuntimeError(f"Jellystat kept its database busy. The backup is ready in {work}; deactivate the plug-in and try again")
    psql(f'ALTER DATABASE "{work}" RENAME TO "{DB}"')
    return (f"Restored {name} ({tables} tables). Your database before it is kept as {before}. "
            "Deactivate and activate Jellystat if its pages still show the old figures.")


def restore_in_background():
    name = str(sb.setting("restore_file", "") or "").strip()
    if not name:
        return {"said": "Type the file's name in Backup file to restore first"}
    if not _lock.acquire(blocking=False):
        return {"said": "A restore is already running"}

    def run():
        try:
            sb.keep("restore", {"state": "running", "said": f"Restoring {name}…", "at": _now()})
            sb.keep("restore", {"state": "ok", "said": restore(name), "at": _now()})
        except Exception as e:  # noqa: BLE001 - said on the restore screen
            sb.keep("restore", {"state": "problem", "said": str(e)[:300], "at": _now()})
        finally:
            _lock.release()
    threading.Thread(target=run, daemon=True).start()
    return {"said": f"Restoring {name}. The Restore screen says when it is done."}


# What Starboard shows -----------------------------------------------------------------------------------------------

def status_card():
    c = sb.remember("connect", {}) or {}
    r = sb.remember("restore", {}) or {}
    if r.get("state") == "running":
        return {"state": "warning", "text": r["said"]}
    return {"state": "ok" if c.get("ok") else "warning", "text": c.get("said") or "Starting…"}


def screen():
    files = found()
    r = sb.remember("restore", {}) or {}
    items = [{"id": f["name"], "title": f["name"], "detail": f"{f['size'] / 1e6:,.1f} MB, added "
              + dt.datetime.fromtimestamp(f["when"], dt.timezone.utc).strftime("%d %B %Y %H:%M UTC"), "state": "unknown", "actions": []}
             for f in files]
    if r:
        items.insert(0, {"id": "last", "title": "Last restore", "detail": f"{r.get('said', '')} ({r.get('at', '')})",
                         "state": {"ok": "ok", "running": "warning", "problem": "problem"}.get(r.get("state"), "unknown"), "actions": []})
    return {"type": "list", "title": "Restore a Jellystat backup",
            "intro": ("Put a PostgreSQL backup of Jellystat's database (made with pg_dump -Fc) in the plug-in's restore "
                      "folder, data/plugins/jellystat/data/main/restore in Starboard's data folder. Type its name in "
                      "Backup file to restore, then choose Restore the backup. Your current figures are kept in the "
                      "database beside it, never deleted.") if not files else
                     "Files in the restore folder. Type the name of the one to restore in Backup file to restore, then choose Restore the backup.",
            "items": items}


def main():
    os.makedirs(RESTORE_DIR, exist_ok=True)
    sb.every(120, connect, first=20)
    sb.serve({"/status": status_card, "/restore": screen, ("POST", "/restore"): lambda body=None: {**screen(), "said": ""},
              ("POST", "/restore-now"): restore_in_background})


if __name__ == "__main__":
    main()
