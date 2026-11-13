"""Audio description tracks: adds a description track the person already has, such as one from AudioVault, to the
film or episode in Jellyfin it belongs to, as an extra sound track named "English (Audio Description)".

How it works (DASH-410):
- The person puts the track (MP3, M4A and the like, or a zip of them) in the audio-description folder in the media
  folder, or uploads it on the plug-in's page (up to 60 MB, Starboard's limit for a file).
- The plug-in matches each file to a film or episode by its name, through Jellyfin's search, and checks that the
  track and the film are the same length, within a few seconds (the setting). A different length almost always means
  a different cut of the film, and the plug-in says so instead of adding it.
- mkvmerge copies the sound, without converting it, into a Matroska audio file with the track's language, its title,
  the visual impaired flag and not the default track; mkvmerge counts every frame, so the length is exact. When the
  lengths agree it goes next to the film as "<film>.Audio Description.eng.mka". Jellyfin loads it as an extra sound
  track and keeps the film file as it is.
- The original stays in the folder until the person says the track plays in step; then it moves to Confirmed. If it
  does not, the added track moves to Taken off. Nothing is ever deleted: the person deletes those folders themselves.

What it never does: download from or read any website (AudioVault included), change the film's own file, or delete.

Lightweight: the container rests when idle. It looks in the folder when its page opens, when Look in the folder now
is chosen, and once a night in quiet hours. mkvmerge runs only while a track is checked or added, a few seconds
each, copying the sound as it is. mkvtoolnix was chosen over ffmpeg: the image is 146 MB rather than 261 MB.
"""
import json
import os
import re
import shutil
import subprocess
import threading
import time
import unicodedata
import urllib.parse
import zipfile

import sbplugin
from sbplugin import fetch, keep, plural, remember, serve, setting

INBOX = os.environ.get("TRACKS_INBOX", "/media/audio-description")
MOUNTS = {"movies": os.environ.get("TRACKS_MOVIES", "/media/movies"), "tv": os.environ.get("TRACKS_TV", "/media/tv")}
CONFIRMED, TAKEN_OFF, UNZIPPED = "Confirmed", "Taken off", "Unzipped"
AUDIO = (".mp3", ".m4a", ".m4b", ".aac", ".mka", ".opus", ".ogg", ".oga", ".flac", ".wav")
LANGUAGES = {"eng": "English", "fra": "French", "deu": "German", "spa": "Spanish", "ita": "Italian", "nld": "Dutch",
             "por": "Portuguese", "pol": "Polish", "swe": "Swedish", "dan": "Danish", "nor": "Norwegian", "fin": "Finnish"}
UPLOAD_MAX = 60 * 1024 * 1024  # Starboard streams files up to 60 MB
ZIP_MAX = 4 * 1024 * 1024 * 1024  # what one zip may unpack to, at most
# Track names that are audio description, as the Audio description plug-in reads them (a commentary never counts).
TRACK_AD = re.compile(r"(?i)(?:\baudio[ ._-]?descri(?:ption|bed)\b|\bdescriptive[ ._-]?(?:audio|video)\b|\bdescribed\b"
                      r"|\bDVS\b|(?:^|[\s\[(._-])AD(?:$|[\s\])._-]))")
COMMENTARY = re.compile(r"(?i)comment(?:ary)?")
# Words in a track's file name that are not the title.
NOISE = re.compile(r"(?i)\b(?:audio\s?descri(?:ption|bed)|described|descriptive(?:\s(?:audio|video))?|dvs|ad|audiovault|"
                   r"eng(?:lish)?|track|mp3|m4a|aac)\b")
EPISODE = re.compile(r"(?i)\bS(\d{1,2})\s?E(\d{1,3})\b|\b(\d{1,2})x(\d{2,3})\b")
YEAR = re.compile(r"(?:^|[\s(\[])((?:19|20)\d\d)(?:$|[\s)\]])")
AUDIOVAULT = {"film": "https://audiovault.net/movies?search=", "episode": "https://audiovault.net/shows?search="}
run = subprocess.run  # replaced in tests
_lock = threading.Lock()
_pass = {"running": False, "done": 0, "total": 0}


# Words -----------------------------------------------------------------------------------------------------------

def lang():
    code = str(setting("language", "eng"))
    return code if code in LANGUAGES else "eng"


def track_title(code=None):
    return f"{LANGUAGES[code or lang()]} (Audio Description)"


def tolerance():
    try:
        return max(1, min(int(setting("tolerance", 5)), 30))
    except (TypeError, ValueError):
        return 5


def length_words(seconds):
    """A length in words, such as "1 hour 58 minutes 2 seconds"."""
    s = int(round(abs(seconds)))
    h, m, sec = s // 3600, s % 3600 // 60, s % 60
    parts = [plural(h, "hour")] if h else []
    parts += [plural(m, "minute")] if m else []
    parts += [plural(sec, "second")] if sec or not parts else []
    return " ".join(parts)


def norm(text):
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode().lower().replace("&", " and ")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


# Names -----------------------------------------------------------------------------------------------------------

def parse_name(filename):
    """What a track's file name says: a film's name and year, or a series' name with its series and episode."""
    stem = os.path.splitext(os.path.basename(filename))[0]
    text = re.sub(r"[._]+", " ", stem)
    text = re.sub(r"\[[^\]]*\]", " ", text)  # [AD], [AudioVault] and the like
    ep = EPISODE.search(text)
    if ep:
        season, episode = (int(ep.group(1)), int(ep.group(2))) if ep.group(1) else (int(ep.group(3)), int(ep.group(4)))
        name = NOISE.sub(" ", text[:ep.start()])
        name = re.sub(r"[\s()\-]+$", "", " ".join(name.split()))
        name = YEAR.sub(" ", name).strip(" -") or name
        return {"kind": "episode", "name": " ".join(name.split()), "season": season, "episode": episode}
    years = list(YEAR.finditer(text))
    year = int(years[-1].group(1)) if years else 0
    name = text[:years[-1].start()] if years and text[:years[-1].start()].strip() else text
    name = " ".join(NOISE.sub(" ", name).replace("(", " ").replace(")", " ").split()).strip(" -")
    return {"kind": "film", "name": name or str(year), "year": year}


# Jellyfin --------------------------------------------------------------------------------------------------------

def _run_file(name):
    try:
        with open(os.path.join(sbplugin.RUN, name), encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        return {}


def jellyfin(path, data=None, method=None):
    jf = _run_file("jellyfin.json")
    if not jf.get("url") or not jf.get("api_key"):
        raise LookupError("Starboard has no Jellyfin key to give yet: add Jellyfin in Settings, Apps")
    return fetch(jf["url"].rstrip("/") + path, {"X-Emby-Token": jf["api_key"]}, data=data, method=method, timeout=30)


def _q(**kw):
    return urllib.parse.urlencode({"EnableImages": "false", "EnableUserData": "false", **kw})


def _title(it):
    if it.get("Type") == "Episode":
        return f"{it.get('SeriesName') or 'A series'}, series {it.get('ParentIndexNumber') or 0} episode {it.get('IndexNumber') or 0}"
    year = it.get("ProductionYear")
    return f"{it.get('Name') or 'A film'}" + (f" ({year})" if year else "")


def _entry(it):
    return {"id": str(it.get("Id") or ""), "title": _title(it)[:120], "kind": "episode" if it.get("Type") == "Episode" else "film",
            "path": str(it.get("Path") or ""), "ticks": int(it.get("RunTimeTicks") or 0), "described": described(it.get("MediaStreams")),
            "search": str(it.get("SeriesName") or it.get("Name") or "")}


def described(streams):
    for s in streams or []:
        if isinstance(s, dict) and s.get("Type") == "Audio":
            words = " ".join(str(s.get(k) or "") for k in ("Title", "DisplayTitle", "Comment"))
            if TRACK_AD.search(words) and not COMMENTARY.search(words):
                return True
    return False


def find(parsed):
    """(the title it surely is or None, up to 11 titles it may be, words when nothing matched)."""
    if parsed["kind"] == "episode":
        shows = (jellyfin("/Items?" + _q(Recursive="true", IncludeItemTypes="Series", searchTerm=parsed["name"], Limit=5)) or {}).get("Items") or []
        same = [s for s in shows if norm(s.get("Name")) == norm(parsed["name"])] or shows[:1]
        if not same:
            return None, [], f"No series called {parsed['name']} is in Jellyfin"
        show = same[0]
        eps = (jellyfin(f"/Shows/{urllib.parse.quote(str(show['Id']))}/Episodes?" + _q(season=parsed["season"], Fields="Path,MediaStreams")) or {}).get("Items") or []
        hit = [e for e in eps if int(e.get("IndexNumber") or -1) == parsed["episode"]]
        if not hit:
            return None, [], f"{show.get('Name')} is in Jellyfin, but not series {parsed['season']} episode {parsed['episode']}"
        return _entry({**hit[0], "SeriesName": hit[0].get("SeriesName") or show.get("Name")}), [], ""
    films = (jellyfin("/Items?" + _q(Recursive="true", IncludeItemTypes="Movie", searchTerm=parsed["name"], Fields="Path,MediaStreams", Limit=11)) or {}).get("Items") or []
    maybe = [_entry(f) for f in films if f.get("Id")]
    same = [f for f in films if norm(f.get("Name")) == norm(parsed["name"]) and (not parsed["year"] or int(f.get("ProductionYear") or 0) == parsed["year"])]
    if len(same) == 1:
        return _entry(same[0]), maybe, ""
    if not maybe:
        return None, [], f"No film called {parsed['name']} is in Jellyfin"
    return None, maybe, ""


def by_id(item_id):
    items = (jellyfin("/Items?" + _q(Ids=item_id, Fields="Path,MediaStreams")) or {}).get("Items") or []
    if not items:
        raise ValueError("That title is not in Jellyfin any more. Reload the page")
    return _entry(items[0])


def refresh(item_id):
    """Asks Jellyfin to read the title again, so it finds the new sound track. Nothing else changes."""
    jellyfin(f"/Items/{urllib.parse.quote(item_id)}/Refresh?MetadataRefreshMode=Default&ImageRefreshMode=None"
             "&ReplaceAllMetadata=false&ReplaceAllImages=false", data=b"", method="POST")


# Files -----------------------------------------------------------------------------------------------------------

def local_path(jf_path):
    """Where a file Jellyfin knows is in this container: under /media/movies or /media/tv, or None. Jellyfin may see
    the media folder somewhere else (Starboard's apps see it as /data/media), so the part after movies/ or tv/ is used,
    and the file must really be inside the folder (no way out through a link)."""
    p = str(jf_path or "").replace("\\", "/")
    for name, mount in MOUNTS.items():
        for m in re.finditer(rf"/{re.escape(name)}/", p):
            here = os.path.join(mount, p[m.end():])
            real, root = os.path.realpath(here), os.path.realpath(mount)
            if real.startswith(root + os.sep) and os.path.isfile(real):
                return real
    return None


def identify(path):
    """What mkvmerge reads in a file: (its length in seconds or None, the first sound track's number or None)."""
    try:
        r = run(["mkvmerge", "-J", path], capture_output=True, text=True, timeout=120)
        info = json.loads(r.stdout or "{}") if r.returncode in (0, 1) else {}
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None, None
    ns = ((info.get("container") or {}).get("properties") or {}).get("duration")
    audio = next((t.get("id") for t in info.get("tracks") or [] if t.get("type") == "audio"), None)
    return (int(ns) / 1e9 if ns else None), audio


def target_for(video, code):
    """The new sound track's file: next to the film, with its name, so Jellyfin loads it as an extra track."""
    return os.path.splitext(video)[0] + f".Audio Description.{code}.mka"


def mux(src, track, code, out):
    """Copies one sound track, as it is (nothing converted), into a Matroska audio file with its language, its title,
    the visual impaired flag and not the default track, so nobody gets it unless they choose it."""
    t = str(int(track))
    r = run(["mkvmerge", "-q", "-o", out, "--no-global-tags", "--no-chapters", "--no-attachments", "-a", t,
             "--language", f"{t}:{code}", "--track-name", f"{t}:{track_title(code)}", "--visual-impaired-flag", f"{t}:1",
             "--default-track-flag", f"{t}:0", src], capture_output=True, text=True, timeout=900)
    if r.returncode not in (0, 1):  # 1 is warnings only
        raise RuntimeError(((r.stdout or "") + (r.stderr or "") or "mkvmerge stopped").strip().splitlines()[-1][:150])


def _free_name(folder, name):
    base, ext = os.path.splitext(name)
    n, out = 1, name
    while os.path.exists(os.path.join(folder, out)):
        n += 1
        out = f"{base} ({n}){ext}"
    return out


def move_aside(path, sub):
    """Moves a file into a folder in the inbox (Confirmed, Taken off, Unzipped). Never deletes."""
    where = os.path.join(INBOX, sub)
    os.makedirs(where, exist_ok=True)
    to = os.path.join(where, _free_name(where, os.path.basename(path)))
    shutil.move(path, to)
    return to


def unzip(path):
    """Takes the sound files out of a zip (AudioVault zips its series), by their names only, then moves the zip to
    Unzipped. Returns how many came out."""
    out = 0
    with zipfile.ZipFile(path) as z:
        members = [m for m in z.infolist() if not m.is_dir() and m.filename.lower().endswith(AUDIO)]
        if sum(m.file_size for m in members) > ZIP_MAX or len(members) > 500:
            raise ValueError("This zip is too large to unpack here. Unzip it yourself into the folder")
        for m in members:
            name = _free_name(INBOX, os.path.basename(m.filename.replace("\\", "/")))
            if not name or name.startswith("."):
                continue
            with z.open(m) as src, open(os.path.join(INBOX, name), "xb") as dst:
                shutil.copyfileobj(src, dst, 1 << 20)
            out += 1
    move_aside(path, UNZIPPED)
    return out


def inbox_files():
    """The sound files and zips at the top of the folder: no hidden files, no links, nothing in its sub folders."""
    try:
        names = sorted(os.listdir(INBOX))
    except OSError:
        return []
    return [n for n in names if not n.startswith(".") and n.lower().endswith(AUDIO + (".zip",))
            and os.path.isfile(os.path.join(INBOX, n)) and not os.path.islink(os.path.join(INBOX, n))]


# Checking and adding ---------------------------------------------------------------------------------------------

def _records():
    return remember("files", {}) or {}


def check(name, rec, item):
    """Checks one track against one title, and adds it when the lengths agree. Returns the record."""
    src = os.path.join(INBOX, name)
    rec = {**rec, "item": item, "said": ""}
    if item["described"]:
        return {**rec, "status": "described"}
    video = local_path(item["path"])
    if not video:
        return {**rec, "status": "out_of_reach"}
    out = target_for(video, lang())
    if os.path.exists(out):
        return {**rec, "status": "exists"}
    _, track_id = identify(src)
    if track_id is None:
        return {**rec, "status": "unreadable"}
    film = identify(video)[0] or (item["ticks"] / 10_000_000 if item["ticks"] else None)
    if not film:
        return {**rec, "status": "unreadable_film"}
    # The track is copied into Matroska in the folder first: mkvmerge counts every frame, so its length is exact even
    # for an MP3 with no length in its header. Only a copy that fits goes next to the film.
    part = os.path.join(INBOX, "." + os.path.splitext(name)[0][:150] + ".check.mka")
    try:
        mux(src, track_id, lang(), part)
        track = identify(part)[0]
        if not track:
            return {**rec, "status": "unreadable"}
        rec.update(track_seconds=round(track, 1), film_seconds=round(film, 1))
        if abs(track - film) > tolerance():
            return {**rec, "status": "lengths"}
        hidden = os.path.join(os.path.dirname(out), "." + os.path.basename(out) + ".part")
        shutil.move(part, hidden)  # another disk, perhaps: copied under a hidden name, so Jellyfin never sees half a file
        if os.path.exists(out):
            return {**rec, "status": "exists"}
        os.replace(hidden, out)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as e:
        return {**rec, "status": "problem", "said": str(e)[:150]}
    finally:
        for ours in (part, os.path.join(os.path.dirname(out), "." + os.path.basename(out) + ".part")):
            if os.path.exists(ours):  # only the plug-in's own working copies, never the person's files
                os.remove(ours)
    try:
        refresh(item["id"])
    except Exception:  # noqa: BLE001 - the track is there; Jellyfin finds it at its next library scan
        rec["said"] = "Jellyfin did not answer, so the track shows after its next library scan"
    return {**rec, "status": "added", "added": out, "added_at": time.time()}


def look_once(name, rec):
    parsed = parse_name(name)
    sure, maybe, why = find(parsed)
    rec = {**rec, "parsed": parsed, "maybe": [{"id": m["id"], "title": m["title"]} for m in maybe][:11], "why": why}
    if not sure:
        return {**rec, "status": "choose" if maybe else "no_match", "item": None}
    return check(name, rec, sure)


def look():
    """One pass over the folder: unzips, then matches and checks each new file. One pass at a time."""
    with _lock:
        if _pass["running"]:
            return {"said": "Already looking in the folder"}
        _pass.update(running=True, done=0, total=0)
    try:
        os.makedirs(INBOX, exist_ok=True)
        for z in [n for n in inbox_files() if n.lower().endswith(".zip")]:
            try:
                unzip(os.path.join(INBOX, z))
            except (OSError, ValueError, zipfile.BadZipFile) as e:
                recs = _records()
                recs[z] = {"status": "problem", "said": str(e)[:150], "size": 0}
                keep("files", recs)
        names = [n for n in inbox_files() if not n.lower().endswith(".zip")]
        recs = _records()
        present = set(inbox_files())
        done = sorted((n for n, r in recs.items() if r.get("status") == "confirmed" and n not in present),
                      key=lambda n: -float(recs[n].get("added_at") or 0))[:50]  # the newest 50 confirmed stay listed
        recs = {n: r for n, r in recs.items() if n in present or n in done}
        todo = []
        for n in names:
            st = os.stat(os.path.join(INBOX, n))
            sig = f"{st.st_size}:{int(st.st_mtime)}"
            if n not in recs or (recs[n].get("sig") != sig and recs[n].get("status") not in ("added",)):
                recs[n] = {"sig": sig, "status": "new"}
                todo.append(n)
        keep("files", recs)
        _pass["total"] = len(todo)
        added = 0
        for n in todo:
            try:
                recs[n] = look_once(n, recs[n])
            except (LookupError, OSError, ValueError) as e:
                recs[n] = {**recs[n], "status": "problem", "said": str(e)[:150]}
            added += recs[n].get("status") == "added"
            _pass["done"] += 1
            keep("files", recs)
        keep("last", {"at": time.time(), "checked": len(todo), "added": added})
        return {"said": f"Checked {plural(len(todo), 'new file')}, added {plural(added, 'track')}" if todo else "No new files in the folder"}
    finally:
        _pass["running"] = False


def look_soon():
    if not _pass["running"]:
        threading.Thread(target=_guarded_look, daemon=True).start()


def _guarded_look():
    try:
        look()
        keep("_error", None)
    except Exception as e:  # noqa: BLE001 - kept for the page, never fatal
        keep("_error", {"at": time.time(), "text": f"{type(e).__name__}: {e}"[:200]})
        _pass["running"] = False


def _changed():
    """Whether the folder has files the last pass did not see: one listing, no reading."""
    recs = _records()
    return any(n not in recs for n in inbox_files())


# The page --------------------------------------------------------------------------------------------------------

GROUPS = {"check": "To check", "added": "Added: check each plays in step", "done": "Done"}
OUTCOME = {"right": "Yes: put the original away", "undo": "No: take the track off", "wait": "Not checked yet"}


def _row(name, rec):
    st, item = rec.get("status"), rec.get("item") or {}
    t = item.get("title", "")
    row = {"id": name, "title": name[:120], "actions": [], "group": GROUPS["check"]}
    search = item.get("search") or (rec.get("parsed") or {}).get("name") or ""
    kind = item.get("kind") or (rec.get("parsed") or {}).get("kind") or "film"
    link = {"url": AUDIOVAULT["episode" if kind == "episode" else "film"] + urllib.parse.quote(search),
            "label": f"Search AudioVault for {search}"[:80]} if search else None
    if st == "added":
        row.update(group=GROUPS["added"], state="ok", state_label="Added",
                   detail=(f"Added to {t} as {track_title()}. Play it in Jellyfin, then say whether it plays in step. "
                           + (rec.get("said") or ""))[:200],
                   choice={"label": "Plays in step?", "value": "wait", "options": [[k, v] for k, v in (("wait", OUTCOME["wait"]), ("right", OUTCOME["right"]), ("undo", OUTCOME["undo"]))]})
        return row
    if st == "confirmed":
        row.update(group=GROUPS["done"], state="ok", state_label="Confirmed",
                   detail=f"In {t}. The original is in the {CONFIRMED} folder: delete it there when you like.")
        return row
    if st == "taken_off":
        row.update(state="off", state_label="Taken off",
                   detail=f"The added track is in the {TAKEN_OFF} folder, and the original is still here. Choose a title to try again.")
    elif st == "lengths":
        diff = rec["track_seconds"] - rec["film_seconds"]
        row.update(state="warning", state_label="Lengths differ", link=link,
                   detail=(f"{t}: the track is {length_words(diff)} {'longer' if diff > 0 else 'shorter'} than the film, so it is "
                           "probably for another cut, such as an extended one. Look for one for this cut.")[:200])
    elif st == "choose":
        row.update(state="warning", state_label="Choose the title", detail="More than one title could match. Choose the right one.")
    elif st == "no_match":
        row.update(state="warning", state_label="No match", link=link,
                   detail=(f"{rec.get('why') or 'Nothing in Jellyfin matches this name'}. Rename the file as the film and year, such as "
                           "Dune (2021).mp3, or a series as Slow Horses S01E03.mp3.")[:200])
    elif st == "described":
        row.update(state="ok", state_label="Already described",
                   detail=f"{t} already has a described sound track in Jellyfin, so nothing was added. Choose another title if this is wrong.")
    elif st == "exists":
        row.update(state="ok", state_label="Already added",
                   detail=f"{t} already has a description track file next to it, so nothing was added or replaced.")
    elif st == "out_of_reach":
        row.update(state="problem", state_label="Out of reach",
                   detail=f"{t} is not in the movies or tv folder of Starboard's media folder, so this plug-in cannot reach it to add a track.")
    elif st == "unreadable":
        row.update(state="problem", state_label="Cannot read", detail="This file could not be read as sound. Check that it plays, then put it here again.")
    elif st == "unreadable_film":
        row.update(state="problem", state_label="Cannot read film", detail=f"The length of {t} could not be read, so the track was not added.")
    elif st == "new":
        row.update(state="unknown", state_label="Waiting", detail="Waiting to be checked.")
    else:
        row.update(state="problem", state_label="Not added", detail=(rec.get("said") or "Something went wrong")[:200])
    options = [[m["id"], m["title"][:40]] for m in rec.get("maybe") or []][:11]
    if item.get("id") and item["id"] not in [o[0] for o in options]:
        options = [[item["id"], t[:40]]] + options[:10]
    if options:
        row["choice"] = {"label": "Film or episode", "value": item.get("id") or "",
                         "options": ([] if item.get("id") else [["", "Choose one"]]) + options}
    return row


def _notices():
    out = []
    if _pass["running"]:
        total = max(_pass["total"], 1)
        out.append({"id": "looking", "tone": "info", "title": "Looking in the folder",
                    "text": f"{_pass['done']} of {plural(_pass['total'], 'file')} checked", "progress": int(100 * _pass["done"] / total)})
    err = remember("_error")
    if isinstance(err, dict) and err.get("text"):
        out.append({"id": "error", "tone": "danger", "title": "The last look did not finish", "text": err["text"][:300], "dismiss": True})
    if not os.path.isdir(INBOX):
        out.append({"id": "nofolder", "tone": "warning", "title": "No audio-description folder yet",
                    "text": "Starboard makes it when the plug-in is activated. Activate it again in State if it is missing."})
    return out


def inbox_screen(said=""):
    recs = _records()
    rows = [_row(n, r) for n, r in sorted(recs.items(), key=lambda kv: kv[0].lower())]
    order = list(GROUPS.values())
    rows.sort(key=lambda r: order.index(r["group"]))
    out = {"type": "list", "title": "Description tracks to add",
           "intro": ("Put a description track you already have, such as one from AudioVault, in the audio-description folder in your media "
                     f"folder, or upload one here. It is matched by its name, its length is checked against the film (within {plural(tolerance(), 'second')}), "
                     f"and it is added next to the film as {track_title()}. Nothing is ever deleted.")[:400],
           "add": {"label": "Upload a description track", "file_only": True,
                   "file": {"label": "Choose a description track", "accept": ",".join(AUDIO + (".zip",)),
                            "hint": "MP3, M4A or a zip of them, up to 60 MB. Put larger files in the audio-description folder instead."}},
           "items": rows}
    if _notices():
        out["notices"] = _notices()
    return {**out, "said": said} if said else out


def inbox(body=None):
    if not body:
        if _changed():
            look_soon()
        return inbox_screen()
    action, name, value = body.get("action"), str(body.get("id") or ""), str(body.get("value") or "")
    if action == "dismiss":
        keep("_error", None)
        return inbox_screen()
    recs = _records()
    if action != "choose" or name not in recs:
        raise ValueError("Choose a file from the list. Reload the page if it has gone")
    rec = recs[name]
    if rec.get("status") == "added":
        return inbox_screen(_outcome(name, rec, value, recs))
    if rec.get("status") == "confirmed":
        raise ValueError("This track is confirmed already")
    if not value:
        raise ValueError("Choose a film or episode")
    if not os.path.isfile(os.path.join(INBOX, name)):
        raise ValueError("The file is not in the folder any more. Reload the page")
    recs[name] = check(name, rec, by_id(value))
    keep("files", recs)
    st = recs[name]["status"]
    t = recs[name]["item"]["title"]
    said = {"added": f"Added to {t}. Play it in Jellyfin to check it", "lengths": f"Not added: the lengths of the track and {t} differ",
            "described": f"Not added: {t} already has a described sound track"}.get(st, f"Not added to {t}")
    return inbox_screen(said)


def _outcome(name, rec, value, recs):
    t = (rec.get("item") or {}).get("title", "the title")
    if value == "right":
        if os.path.isfile(os.path.join(INBOX, name)):
            move_aside(os.path.join(INBOX, name), CONFIRMED)
        recs[name] = {**rec, "status": "confirmed"}
        keep("files", recs)
        return f"Confirmed for {t}. The original is in the {CONFIRMED} folder"
    if value == "undo":
        added = rec.get("added") or ""
        if added and os.path.isfile(added) and os.path.realpath(added).startswith(tuple(os.path.realpath(m) + os.sep for m in MOUNTS.values())):
            move_aside(added, TAKEN_OFF)
        try:
            refresh(rec["item"]["id"])
        except Exception:  # noqa: BLE001
            pass
        recs[name] = {**rec, "status": "taken_off", "added": ""}
        keep("files", recs)
        return f"Taken off {t}. The track is in the {TAKEN_OFF} folder"
    return f"{t}: not checked yet"


def upload(name, item, length, stream):
    """A file chosen on the page, streamed into the folder a piece at a time, then checked with the rest."""
    base = os.path.basename(str(name).replace("\\", "/")).strip()
    if not base or base.startswith(".") or not base.lower().endswith(AUDIO + (".zip",)):
        raise ValueError("Choose a sound file, such as an MP3 or M4A, or a zip of them")
    if not 0 < length <= UPLOAD_MAX:
        raise ValueError("Choose a file up to 60 MB, or put it in the audio-description folder")
    os.makedirs(INBOX, exist_ok=True)
    final = os.path.join(INBOX, _free_name(INBOX, base))
    part = os.path.join(INBOX, "." + os.path.basename(final) + ".part")
    left = length
    try:
        with open(part, "xb") as f:
            while left:
                chunk = stream.read(min(1 << 20, left))
                if not chunk:
                    raise ValueError("The upload stopped before the end")
                f.write(chunk)
                left -= len(chunk)
        os.replace(part, final)
    finally:
        if os.path.exists(part):  # our own unfinished copy
            os.remove(part)
    look_soon()
    return inbox_screen(f"Uploaded {os.path.basename(final)}. It is being checked")


def look_now():
    look_soon()
    return {"said": "Looking in the folder. The list updates in a minute"}


def job():
    out = look()
    keep("_error", None)
    return out


def count():
    recs = _records()
    waiting = sum(1 for r in recs.values() if r.get("status") == "added")
    check_ = sum(1 for r in recs.values() if r.get("status") not in ("added", "confirmed", "described", "exists"))
    return {"value": waiting, "label": "to check" if waiting != 1 else "track to check",
            "note": f"{plural(check_, 'file')} {'needs' if check_ == 1 else 'need'} a look" if check_ else "Nothing else waiting"}


ROUTES = {"/inbox": inbox, ("POST", "/inbox"): inbox, ("FILE", "/inbox/file"): upload,
          ("POST", "/look"): look_now, ("POST", "/jobs/look"): job, "/count": count}

if __name__ == "__main__":
    serve(ROUTES)
