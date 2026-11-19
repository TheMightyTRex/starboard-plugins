"""What each channel has played to someone watching (0.3.0, owner, 19 November 2026: "the live tv needs to remember on
its own what its actually played so if I create a schedule with from last watched it knows what I have seen").

A channel streams only while someone is tuned in, so what its stream sends is what was watched. For each episode or
film it records when it was on and how many seconds of it were streamed to at least one viewer; once SEEN_SHARE of
it has been, it counts as seen on that channel. "From the next episode not watched" then passes over an episode
that Jellyfin says was played or that the channel's record says was seen.

Nothing is ever sent to Jellyfin: its played marks are never changed. Each channel's record is one small file in
the plug-in's folder, holding the newest MOST entries, written at most once every WRITE_EVERY seconds while a
channel plays and once when it stops, never for every frame.
"""
import json
import os
import threading
import time

SEEN_SHARE = 0.7  # of a programme streamed to a viewer, for it to count as seen on the channel
MOST = 5000  # entries kept for each channel, the newest
WRITE_EVERY = 60  # seconds between writes of a channel's record while it plays


class Record:
    """Every channel's record, in `folder`/<channel>.json: [{"id", "series", "title", "ep", "at", "seconds",
    "length", "seen"}], oldest first."""

    def __init__(self, folder):
        self.folder = folder
        self.lock = threading.Lock()
        self.cache = {}
        self.dirty = set()
        self.written = {}

    def path(self, cid):
        return os.path.join(self.folder, f"{cid}.json")

    def _load(self, cid):
        if cid not in self.cache:
            try:
                with open(self.path(cid), encoding="utf-8") as f:
                    got = json.load(f)
                self.cache[cid] = [e for e in got if isinstance(e, dict) and e.get("id")] if isinstance(got, list) else []
            except (OSError, ValueError):
                self.cache[cid] = []
        return self.cache[cid]

    def note(self, cid, entry, at, length, seconds, now=None):
        """`seconds` more of a programme (entry: its line-up entry; at: when its airing started; length: its length in
        seconds) streamed to a viewer. Added to what was noted for the same airing, so a programme joined, left and
        joined again counts once."""
        now = time.time() if now is None else now
        if seconds <= 0 or length <= 0 or not entry.get("id"):
            return None
        with self.lock:
            rows = self._load(cid)
            row = next((r for r in reversed(rows[-50:]) if r["id"] == entry["id"] and abs(r["at"] - at) < 1), None)
            if row is None:
                row = {"id": entry["id"], "series": entry.get("group") if entry.get("kind") == "Episode" else None,
                       "title": str(entry.get("title") or "")[:120], "ep": _ep(entry), "at": int(at), "seconds": 0.0,
                       "length": round(float(length), 1), "seen": False}
                rows.append(row)
                if len(rows) > MOST:
                    del rows[:len(rows) - MOST]
            row["seconds"] = round(min(float(length), row["seconds"] + float(seconds)), 1)
            row["seen"] = row["seconds"] >= SEEN_SHARE * float(length)
            row["last"] = int(now)
            self.dirty.add(cid)
        self.flush(cid)
        return row

    def flush(self, cid=None, force=False, now=None):
        """Writes a channel's record when it has changed and WRITE_EVERY seconds have passed (or when forced)."""
        now = time.monotonic() if now is None else now
        with self.lock:
            for c in [cid] if cid else list(self.dirty):
                if c not in self.dirty or (not force and now - self.written.get(c, -1e12) < WRITE_EVERY):
                    continue
                os.makedirs(self.folder, exist_ok=True)
                tmp = self.path(c) + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(self.cache.get(c, []), f, separators=(",", ":"))
                os.replace(tmp, self.path(c))
                self.dirty.discard(c)
                self.written[c] = now

    def seen_ids(self, cid):
        """The episodes and films seen on a channel."""
        with self.lock:
            return {r["id"] for r in self._load(cid) if r.get("seen")}

    def latest(self, cid, n=5):
        """The newest n entries, newest first."""
        with self.lock:
            return list(reversed(self._load(cid)[-n:]))

    def count(self, cid):
        with self.lock:
            return len(self._load(cid))

    def forget(self, cid):
        """Forgets everything a channel has played (Forget what this channel has played)."""
        with self.lock:
            self.cache[cid] = []
            self.dirty.discard(cid)
            try:
                os.remove(self.path(cid))
            except FileNotFoundError:
                pass


def _ep(e):
    if e.get("kind") != "Episode":
        return ""
    bits = (f"Series {e['s']}, episode {e['e']}" if e.get("s") is not None and e.get("e") is not None else "")
    return (bits + (f": {e['ep']}" if e.get("ep") else ""))[:120]


def streamed(piece, now, ok, watched, burst=2.5):
    """How many seconds of a programme piece were streamed to a viewer: the time viewers were there while it played,
    and, when it played to its end, the few seconds FFmpeg sends at once as it starts."""
    left = max(0.0, piece["end"] - now)
    return min(left, watched + (burst if ok else 0.0))
