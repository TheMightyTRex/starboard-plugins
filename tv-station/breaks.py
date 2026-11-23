"""Breaks inside programmes (0.4.0, owner, 19 November 2026: "Is there a way to use the video to guess where the break
would be"): where a programme made for commercial television went to its adverts.

For each episode or film: Jellyfin's media segments of the kind Commercial when it has them; else the programme's
own sound and picture. Programmes made for commercial television fade to black, with a moment of silence, where the
adverts went. FFmpeg listens to the sound alone for silences (cheap: no picture is decoded), then looks at 3 seconds
of a small picture round each of the longest silences for a black frame. Only a silence with a black frame counts.

The points kept are between 20% and 85% of the running time and at least 8 minutes apart: at most 1 for a programme
under 40 minutes, 2 under 75 and 3 above, those nearest to even spacing first. A programme with no clear fade to black
(most BBC programmes and films) gets none: a break in the middle of a scene would be worse than no break.

0.8.0 (DASH-538, owner, 23 November 2026: "a few options on how it puts ads into programs. For example when it detects
silence. At a set time (try and detect the end of a scene). Number of breaks in a 30 min segment and number of breaks in
a film"): where the breaks go is a choice, and how many. The work that costs something, listening for silences and
looking for the end of each scene, is done once for each programme in the quiet hours and kept as a short list of
candidate places in breaks.json. The choice (at silence, at set times, at the end of a scene) and the number are then
worked out from that list with a little arithmetic, at any time, so changing either never needs another search and
nothing here ever runs FFmpeg while a channel streams. A break the search found no place for goes to its set time.
Manual marks (DASH-539, later) are kept under "manual" in the same file and win over any of this.

Found in quiet hours, one programme at a time, at the lowest priority with one thread, and kept in breaks.json in the
plug-in's folder, so each programme is checked once. Chapters are not used: most files have none, and many that do
have chapters every few minutes that say nothing of the adverts.
"""
import json
import os
import re
import subprocess
import threading
import time
import urllib.error
import urllib.request

FIRST, LAST = 0.20, 0.85  # the part of a programme a break may fall in
APART = 8 * 60  # seconds between breaks, at least
CANDIDATES = 12  # silences looked at for a black frame, at most
SILENCE = "silencedetect=n=-45dB:d=0.4"
BLACK = "blackdetect=d=0.08:pix_th=0.12:pic_th=0.95"
_proc = {"p": None}
_stop = threading.Event()
_lock = threading.Lock()


def most_for(length):
    """How many breaks a programme of `length` seconds may have."""
    return 1 if length < 40 * 60 else 2 if length < 75 * 60 else 3


def choose(points, length):
    """The breaks kept from the points found: inside FIRST to LAST, APART from each other, at most most_for(length),
    those nearest to even spacing first. Pure, so it can be tested."""
    inside = sorted({round(p, 2) for p in points if FIRST * length <= p <= LAST * length})
    n = most_for(length)
    ideal = [length * (i + 1) / (n + 1) for i in range(n)]
    kept = []
    for target in ideal:
        for p in sorted(inside, key=lambda p: abs(p - target)):
            if all(abs(p - k) >= APART for k in kept):
                kept.append(p)
                break
    return sorted(kept)


METHODS = ("silence", "times", "scene")
METHOD_WORDS = {"silence": "At silence", "times": "At set times", "scene": "At the end of a scene"}
SCENE = 0.35  # how different one picture must be from the one before for the cut between them to count as a scene's end
SCENE_ARGS = ["-skip_frame", "nokey"]  # only the key frames are decoded: a cut is a key frame, and it costs a tenth of the time
KEEP_SILENCES = 40  # the longest silences kept for a programme
KEEP_SCENES = 150
SNAP = 0.5  # a set time snaps to a place within this part of the space between breaks, either side
MOST_BREAKS = 8
MOST_PROGRAMMES = 4000  # in breaks.json, the oldest go
FILE_VERSION = 2


def count_for(length, film, per_30=0, per_film=0):
    """How many breaks a programme of `length` seconds has (0.8.0): a film has per_film (0 for the automatic number
    of before: 1 under 40 minutes, 2 under 75, 3 above); anything else per_30 for each 30 minutes, at least 1."""
    if film and per_film:
        return max(1, min(MOST_BREAKS, int(per_film)))
    if not film and per_30:
        return max(1, min(MOST_BREAKS, int(float(per_30) * float(length) / 1800.0 + 0.5)))
    return most_for(length)


def set_times(length, n):
    """n set times in a programme, evenly spaced between 20% and 85% of it."""
    lo, hi = FIRST * length, LAST * length
    if n <= 3:
        return [length * (i + 1) / (n + 1) for i in range(n)]
    return [lo + (hi - lo) * i / (n - 1) for i in range(n)]


def place(length, n, found=(), manual=(), near=None):
    """The seconds into a programme where its n breaks go (0.8.0). manual: marks made by hand, which win over all of
    this. found: the candidate places the search kept: [(seconds, weight)], weight more for a better place. Each break
    takes the best place near its set time, inside the 20% to 85% and 8 minutes (or less, for many breaks) from the
    others; one with no place near goes to its set time. Pure: nothing is looked at or run."""
    manual = sorted({round(float(m), 2) for m in manual if 0 < float(m) < length})
    if manual:
        return manual
    if length <= 0 or n <= 0:
        return []
    ideal = set_times(length, n)
    spacing = (LAST - FIRST) * length / max(1, n)
    apart = min(APART, spacing * 0.6)
    reach = spacing * SNAP
    cands = sorted({(round(float(t), 2), float(w)) for t, w in found if FIRST * length <= t <= LAST * length})
    kept = []
    for target in ideal:
        best = None
        for t, w in cands:
            if abs(t - target) > reach or any(abs(t - k) < apart for k in kept):
                continue
            score = abs(t - target) - 60.0 * w
            if best is None or score < best[0]:
                best = (score, t)
        pick = best[1] if best else target
        if any(abs(pick - k) < apart for k in kept):  # a set time that would be too near another is left out
            continue
        kept.append(pick)
    return sorted(round(k, 2) for k in kept)


def silences(text):
    """(start, end) of each silence in FFmpeg's silencedetect lines."""
    out, start = [], None
    for line in text.splitlines():
        m = re.search(r"silence_start: (-?[0-9.]+)", line)
        if m:
            start = max(0.0, float(m.group(1)))
            continue
        m = re.search(r"silence_end: ([0-9.]+)", line)
        if m and start is not None:
            out.append((start, float(m.group(1))))
            start = None
    return out


def blacks(text):
    """(start, end) of each black stretch in FFmpeg's blackdetect lines."""
    return [(float(a), float(b)) for a, b in re.findall(r"black_start:([0-9.]+) black_end:([0-9.]+)", text)]


def scenes(text):
    """The seconds at which each scene begins, from FFmpeg's showinfo lines after select=gt(scene,...)."""
    return [float(x) for x in re.findall(r"pts_time:([0-9.]+)", text)]


def _nice():
    try:
        os.nice(19)
    except OSError:
        pass


def _run(argv, limit):
    """FFmpeg at the lowest priority; its messages (stderr) as text. Stopped at once by stop()."""
    if _stop.is_set():
        raise InterruptedError("Stopped: someone began watching")
    p = subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, preexec_fn=_nice)
    _proc["p"] = p
    got = []
    reader = threading.Thread(target=lambda: got.append(p.stderr.read().decode("utf-8", "replace")), daemon=True)
    reader.start()
    began = time.monotonic()
    try:
        while p.poll() is None:
            if _stop.wait(0.5) or time.monotonic() - began > limit:
                p.kill()
                p.wait()
                raise InterruptedError("Stopped: someone began watching" if _stop.is_set() else "Took too long")
        reader.join(5)
        return got[0] if got else ""
    finally:
        _proc["p"] = None
        if p.stderr:
            p.stderr.close()


def source(jf_url, item_id):
    return f"{jf_url.rstrip('/')}/Videos/{item_id}/stream?static=true"


def headers(jf_key):
    return ["-headers", f'Authorization: MediaBrowser Token="{jf_key}"\r\n']


def segments(jf_url, jf_key, item_id):
    """Jellyfin's Commercial media segments, as the seconds each starts at; [] when it has none or cannot say."""
    req = urllib.request.Request(f"{jf_url.rstrip('/')}/MediaSegments/{item_id}",
                                 headers={"Authorization": f'MediaBrowser Token="{jf_key}"', "X-Emby-Token": jf_key})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            items = json.load(r).get("Items") or []
    except (urllib.error.URLError, OSError, ValueError):
        return []
    return [float(x.get("StartTicks") or 0) / 1e7 for x in items if str(x.get("Type")) == "Commercial"]


def detect(src, length, head=(), limit=1800):
    """Break points in a programme from its sound and picture: [seconds, ...], chosen as choose() says. src is the
    file or address FFmpeg reads, head the arguments before it (Jellyfin's key)."""
    one = ["-threads", "1"]
    base = ["ffmpeg", "-nostdin", "-hide_banner", "-nostats", "-loglevel", "info", "-filter_threads", "1"]
    text = _run(base + one + list(head) + ["-i", src, "-map", "0:a:0", "-vn", "-sn", "-dn", "-af", SILENCE, "-f", "null", "-"], limit)
    quiet = [(a, b) for a, b in silences(text) if FIRST * length - 5 <= (a + b) / 2 <= LAST * length + 5]
    quiet = sorted(quiet, key=lambda ab: ab[0] - ab[1])[:CANDIDATES]  # the longest silences first
    points = []
    for a, b in quiet:
        mid = (a + b) / 2
        at = max(0.0, mid - 1.5)
        text = _run(base + one + list(head) + ["-ss", f"{at:.2f}", "-t", "3", "-i", src, "-an", "-sn", "-dn",
                                               "-vf", f"scale=160:-2,{BLACK}", "-f", "null", "-"], 120)
        found = blacks(text)
        if found:
            s, e = found[0]
            points.append(at + (s + e) / 2)
    return choose(points, length)


def survey(src, length, head=(), methods=("silence",), limit=3600):
    """What the search keeps for a programme (0.8.0): {"sil": [[seconds, length of the silence, 1 if the picture went
    black there], ...]} for At silence, {"scn": [seconds, ...]} for At the end of a scene. FFmpeg at the lowest priority,
    one thread, and never while anyone watches. This is the only place that costs: it is done once for each programme."""
    one = ["-threads", "1"]
    base = ["ffmpeg", "-nostdin", "-hide_banner", "-nostats", "-loglevel", "info", "-filter_threads", "1"]
    out = {}
    if "silence" in methods:
        text = _run(base + one + list(head) + ["-i", src, "-map", "0:a:0", "-vn", "-sn", "-dn", "-af", SILENCE, "-f", "null", "-"], limit)
        quiet = [(a, b) for a, b in silences(text) if 0.1 * length <= (a + b) / 2 <= 0.92 * length]
        quiet = sorted(quiet, key=lambda ab: ab[0] - ab[1])[:KEEP_SILENCES]  # the longest first
        got = []
        for k, (a, b) in enumerate(quiet):
            mid = (a + b) / 2
            black = 0
            if k < CANDIDATES:  # the picture is only looked at for the longest silences
                at = max(0.0, mid - 1.5)
                text = _run(base + one + list(head) + ["-ss", f"{at:.2f}", "-t", "3", "-i", src, "-an", "-sn", "-dn",
                                                       "-vf", f"scale=160:-2,{BLACK}", "-f", "null", "-"], 120)
                found = blacks(text)
                if found:
                    mid = at + (found[0][0] + found[0][1]) / 2
                    black = 1
            got.append([round(mid, 1), round(b - a, 1), black])
        out["sil"] = sorted(got)
    if "scene" in methods:
        text = _run(base + one + SCENE_ARGS + list(head) + ["-i", src, "-an", "-sn", "-dn", "-vf",
                                                           f"scale=160:-2,select=gt(scene\\,{SCENE}),showinfo", "-f", "null", "-"], limit)
        cuts = sorted({round(t, 1) for t in scenes(text) if 0.1 * length <= t <= 0.92 * length})
        out["scn"] = cuts[:KEEP_SCENES]
    return out


def find(jf_url, jf_key, entry):
    """Break points for a line-up entry, and how they were found: (points, "segments" | "picture")."""
    length = float(entry.get("dur") or 0)
    if length <= 0:
        return [], "picture"
    marked = segments(jf_url, jf_key, entry["id"])
    if marked:
        return choose(marked, length), "segments"
    return detect(source(jf_url, entry["id"]), length, headers(jf_key)), "picture"


def look(jf_url, jf_key, entry, methods=("silence",)):
    """What to keep for a programme for these methods (0.8.0), as survey() gives it. For At silence, Jellyfin's own
    Commercial media segments come first when it has them, and then nothing is listened to."""
    length = float(entry.get("dur") or 0)
    if length <= 0:
        return {"sil": []}
    got, todo = {}, [m for m in methods if m in ("silence", "scene")]
    if "silence" in todo:
        marked = segments(jf_url, jf_key, entry["id"])
        if marked:
            got["seg"] = [round(m, 1) for m in marked]
            todo.remove("silence")
    if todo:
        got.update(survey(source(jf_url, entry["id"]), length, headers(jf_key), todo))
    return got


def stop():
    """Stops a search at once: a channel is about to play."""
    _stop.set()
    p = _proc["p"]
    if p and p.poll() is None:
        p.kill()


class Found:
    """What has been found, in `path` (breaks.json): {item id: {"v": 2, "checked": time, "sil": [[seconds, length, black],
    ...], "scn": [seconds, ...], "seg": [seconds, ...], "manual": [seconds, ...]}}. A file of 0.4.0 to 0.7.0 has
    {"at": [seconds], "how"} for each programme, which still works as the places At silence found. "manual" is
    the place for marks made by hand (DASH-539): when it holds any, they are the breaks and nothing else is."""

    def __init__(self, path):
        self.path = path
        self._doc = None
        self._mtime = None

    def _load(self):
        try:
            m = os.path.getmtime(self.path)
        except OSError:
            self._doc, self._mtime = {}, None
            return self._doc
        if self._doc is None or m != self._mtime:
            try:
                with open(self.path, encoding="utf-8") as f:
                    self._doc = json.load(f)
            except (OSError, ValueError):
                self._doc = {}
            if not isinstance(self._doc, dict):
                self._doc = {}
            self._mtime = m
        return self._doc

    def _save(self, doc):
        if len(doc) > MOST_PROGRAMMES:  # the oldest go
            for k in sorted(doc, key=lambda k: doc[k].get("checked", 0))[: len(doc) - MOST_PROGRAMMES]:
                doc.pop(k, None)
        tmp = self.path + ".part"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(doc, f, separators=(",", ":"))
        os.replace(tmp, self.path)
        self._doc, self._mtime = doc, os.path.getmtime(self.path)

    def item(self, item_id):
        return self._load().get(str(item_id)) or {}

    def points(self, item_id):
        d = self.item(item_id)
        return list(d.get("manual") or d.get("at") or [])

    def known(self, item_id):
        return str(item_id) in self._load()

    def has(self, item_id, methods):
        """True when everything the methods need has been searched for already (At set times needs nothing)."""
        d = self.item(item_id)
        for m in methods:
            if m == "silence" and not ("sil" in d or "seg" in d or "at" in d):
                return False
            if m == "scene" and "scn" not in d:
                return False
        return True

    def put(self, item_id, at, how, now=None):
        """The result of a search of 0.4.0 to 0.7.0: the points chosen. Kept so older callers and files still work."""
        with _lock:
            doc = dict(self._load())
            old = doc.get(str(item_id)) or {}
            doc[str(item_id)] = {**old, "at": [round(float(p), 2) for p in at], "how": how, "checked": int(now or time.time())}
            self._save(doc)

    def put_survey(self, item_id, got, now=None):
        """What a search found, merged into what was found before: {"sil": ..., "scn": ..., "seg": ...}."""
        with _lock:
            doc = dict(self._load())
            old = dict(doc.get(str(item_id)) or {})
            old.update({k: v for k, v in got.items() if k in ("sil", "scn", "seg")})
            old.update({"v": FILE_VERSION, "checked": int(now or time.time())})
            doc[str(item_id)] = old
            self._save(doc)

    def set_manual(self, item_id, marks, now=None):
        """Marks made by hand (DASH-539, the screen for it comes later): the seconds into the programme where its breaks
        go. An empty list takes them off, so the automatic places are used again."""
        with _lock:
            doc = dict(self._load())
            old = dict(doc.get(str(item_id)) or {})
            marks = sorted({round(float(m), 2) for m in marks if float(m) > 0})
            if marks:
                old["manual"] = marks
            else:
                old.pop("manual", None)
            old.setdefault("checked", int(now or time.time()))
            doc[str(item_id)] = old
            self._save(doc)

    def places(self, entry, how="silence", per_30=0, per_film=0):
        """The seconds into the programme where its breaks go, by the channel's choice: the manual marks when there are
        any, else the places for `how` (silence, times or scene) and the number for its length. [] when the programme
        needs a search that has not been made yet, or is shorter than 15 minutes. Reads the small file only."""
        length = float(entry.get("dur") or 0)
        if length < 15 * 60:
            return []
        d = self.item(entry.get("id"))
        if d.get("manual"):
            return place(length, 0, manual=d["manual"])
        n = count_for(length, str(entry.get("kind")) == "Movie", per_30, per_film)
        if how == "times":
            return place(length, n)
        if how == "scene":
            if "scn" not in d:
                return []
            return place(length, n, [(t, 0.0) for t in d["scn"]])
        if d.get("seg"):
            return place(length, n, [(t, 2.0) for t in d["seg"]])
        if "sil" in d:
            return place(length, n, [(t, float(b) + min(float(ln), 4.0) / 8.0) for t, ln, b in d["sil"]])
        if d.get("at"):
            return place(length, n, [(t, 1.0) for t in d["at"]]) if (per_30 or per_film) else sorted(d["at"])
        return []

    def count(self):
        doc = self._load()
        return len(doc), sum(1 for v in doc.values() if v.get("at") or v.get("sil") or v.get("scn") or v.get("seg") or v.get("manual"))


def begin():
    """Before a run of searches: a stop() from the last run is forgotten."""
    _stop.clear()
