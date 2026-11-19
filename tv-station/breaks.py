"""Breaks inside programmes (0.4.0, owner, 19 November 2026: "Is there a way to use the video to guess where the break
would be"): where a programme made for commercial television went to its adverts.

For each episode or film: Jellyfin's media segments of the kind Commercial when it has them; else the programme's
own sound and picture. Programmes made for commercial television fade to black, with a moment of silence, where the
adverts went. FFmpeg listens to the sound alone for silences (cheap: no picture is decoded), then looks at 3 seconds
of a small picture round each of the longest silences for a black frame. Only a silence with a black frame counts.

The points kept are between 20% and 85% of the running time and at least 8 minutes apart: at most 1 for a programme
under 40 minutes, 2 under 75 and 3 above, those nearest to even spacing first. A programme with no clear fade to black
(most BBC programmes and films) gets none: a break in the middle of a scene would be worse than no break.

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


def find(jf_url, jf_key, entry):
    """Break points for a line-up entry, and how they were found: (points, "segments" | "picture")."""
    length = float(entry.get("dur") or 0)
    if length <= 0:
        return [], "picture"
    marked = segments(jf_url, jf_key, entry["id"])
    if marked:
        return choose(marked, length), "segments"
    return detect(source(jf_url, entry["id"]), length, headers(jf_key)), "picture"


def stop():
    """Stops a search at once: a channel is about to play."""
    _stop.set()
    p = _proc["p"]
    if p and p.poll() is None:
        p.kill()


class Found:
    """What has been found, in `path` (breaks.json): {item id: {"at": [seconds], "how", "checked"}}."""

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
            self._mtime = m
        return self._doc

    def points(self, item_id):
        return list((self._load().get(str(item_id)) or {}).get("at") or [])

    def known(self, item_id):
        return str(item_id) in self._load()

    def put(self, item_id, at, how, now=None):
        with _lock:
            doc = dict(self._load())
            doc[str(item_id)] = {"at": [round(float(p), 2) for p in at], "how": how, "checked": int(now or time.time())}
            if len(doc) > 20000:  # the oldest go
                for k in sorted(doc, key=lambda k: doc[k].get("checked", 0))[: len(doc) - 20000]:
                    doc.pop(k, None)
            tmp = self.path + ".part"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(doc, f)
            os.replace(tmp, self.path)
            self._doc, self._mtime = doc, os.path.getmtime(self.path)

    def count(self):
        doc = self._load()
        return len(doc), sum(1 for v in doc.values() if v.get("at"))


def begin():
    """Before a run of searches: a stop() from the last run is forgotten."""
    _stop.clear()
