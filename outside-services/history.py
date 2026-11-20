"""Response times and uptime for 90 days, in kilobytes (Uptime and status 2.0.0).

Each check has one small file, /data/history/<id>.bin: 2,160 hourly slots (90 days) of five whole numbers, the hour it
holds, how many checks ran, how many were up, the sum of their times and the slowest, in milliseconds. That is 43 KB a
check whatever happens, with no database. The hours roll up into days when asked (daily()). Each slot is reused 90 days
later, so nothing grows and nothing needs tidying.

It is written once an hour (when the hour changes), before an update and when the container stops, never after each
check: an hour of history at most is lost if the computer loses power.
"""
import array
import os
import threading
import time

HOURS = 90 * 24
FIELDS = 5  # hour number, count, up, sum of ms, slowest ms
_lock = threading.Lock()


class History:
    def __init__(self, folder):
        self.folder = folder
        self.series = {}  # check id -> array('I')
        self.dirty = set()
        self.hour = int(time.time() // 3600)

    def _path(self, cid):
        return os.path.join(self.folder, f"{cid}.bin")

    def _get(self, cid):
        a = self.series.get(cid)
        if a is None:
            a = array.array("I")
            try:
                with open(self._path(cid), "rb") as f:
                    a.frombytes(f.read(HOURS * FIELDS * a.itemsize))
            except OSError:
                pass
            if len(a) != HOURS * FIELDS:
                a = array.array("I", bytes(HOURS * FIELDS * a.itemsize))
            self.series[cid] = a
        return a

    def add(self, cid, up, ms, now=None):
        """One check's result. ms is None for a heartbeat or a check with no time."""
        now = time.time() if now is None else now
        hour = int(now // 3600)
        with _lock:
            a = self._get(cid)
            i = (hour % HOURS) * FIELDS
            if a[i] != hour:
                a[i:i + FIELDS] = array.array("I", [hour, 0, 0, 0, 0])
            a[i + 1] += 1
            if up:
                a[i + 2] += 1
                if ms is not None:
                    v = min(int(round(ms)), 0xFFFFFFFF // 4096)
                    a[i + 3] = min(a[i + 3] + v, 0xFFFFFFFF)
                    a[i + 4] = max(a[i + 4], v)
            self.dirty.add(cid)
        if hour != self.hour:
            self.hour = hour
            self.save()

    def save(self):
        """Writes what changed, each file whole and in one step."""
        with _lock:
            todo, self.dirty = self.dirty, set()
            os.makedirs(self.folder, exist_ok=True)
            for cid in todo:
                a = self.series.get(cid)
                if a is None:
                    continue
                path = self._path(cid)
                with open(path + ".tmp", "wb") as f:
                    f.write(a.tobytes())
                os.replace(path + ".tmp", path)

    def forget(self, cid):
        with _lock:
            self.series.pop(cid, None)
            self.dirty.discard(cid)
            try:
                os.remove(self._path(cid))
            except OSError:
                pass

    def hours(self, cid, count, now=None):
        """The last `count` hours, oldest first: (hour number, checks, up, sum of ms, slowest)."""
        now = time.time() if now is None else now
        last = int(now // 3600)
        with _lock:
            a = self._get(cid)
            out = []
            for h in range(last - count + 1, last + 1):
                i = (h % HOURS) * FIELDS
                out.append(tuple(a[i:i + FIELDS]) if a[i] == h else (h, 0, 0, 0, 0))
        return out

    def hourly_ms(self, cid, count=24, now=None):
        """The average time of each of the last `count` hours, None where nothing was up."""
        return [round(s / u, 1) if u else None for _, _, u, s, _ in self.hours(cid, count, now)]

    def daily(self, cid, days=90, now=None):
        """The hours rolled up into days, oldest first: {"day": seconds at its start (local), "checks", "up", "ms"}."""
        now = time.time() if now is None else now
        out = {}
        for h, n, u, s, worst in self.hours(cid, days * 24, now):
            if not n:
                continue
            t = time.localtime(h * 3600)
            day = int(time.mktime((t.tm_year, t.tm_mon, t.tm_mday, 0, 0, 0, 0, 0, -1)))
            d = out.setdefault(day, {"day": day, "checks": 0, "up": 0, "sum": 0, "slowest": 0})
            d["checks"] += n
            d["up"] += u
            d["sum"] += s
            d["slowest"] = max(d["slowest"], worst)
        rows = [out[k] for k in sorted(out)]
        for d in rows:
            d["ms"] = round(d.pop("sum") / d["up"], 1) if d["up"] else None
        return rows[-days:]

    def uptime(self, cid, hours, now=None):
        """The share of checks that were up in the last `hours`, from 0 to 100, or None with no checks."""
        rows = self.hours(cid, hours, now)
        n = sum(r[1] for r in rows)
        return round(100 * sum(r[2] for r in rows) / n, 2) if n else None
