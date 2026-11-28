"""A guard against flashing (0.13.0, DASH-633; owner, 28 November 2026): a plain warning when a clip made, added or
imported has fast brightness jumps, in the way WCAG 2.3.1 (Three flashes or below threshold) describes them.

It is a guard, not the full Harding test that broadcasters run. It reads the picture small (16 by 9 grey squares, 25 a
second, one thread, lowest priority), so a clip of a minute costs a few seconds of one processor and a few
megabytes. It never stops a file being used: it says what it found and the person decides.

What counts:
  a jump      the brightness (relative luminance, 0 to 1) of the whole picture, or of one quarter of it, changes
              by 0.10 or more from one frame to the next, and the darker of the two frames is below 0.80
  a flash     a jump followed by a jump the other way
  a warning   more than 3 flashes in any one second, in the whole picture or in any quarter (a quarter is 25 percent
              of the picture, the area WCAG counts)
A fade, however quick, is not a flash: its jumps all go the same way.
"""
import subprocess

FPS = 25
GRID = (16, 9)
STEP = 0.10  # the change in relative luminance that counts
DARK = 0.80  # a change between two frames both lighter than this does not count (WCAG's general flash threshold)
MOST_FLASHES = 3  # in any one second
SECONDS = 90  # how much of a clip is read: more than a minute and a half is not read
ENABLED = True
_REGIONS = {"all": (0, 16, 0, 9), "left top": (0, 8, 0, 4), "right top": (8, 16, 0, 4), "left bottom": (0, 8, 5, 9),
            "right bottom": (8, 16, 5, 9)}


def _nice():
    try:
        import os
        os.nice(19)
    except OSError:
        pass


def _linear(v):
    """An 8 bit grey value as relative luminance (0 to 1), by the sRGB curve."""
    c = v / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


_TABLE = [_linear(i) for i in range(256)]


def frame_series(data, grid=GRID):
    """The brightness of every frame, as {region: [luminance per frame]}, from raw grey frames (grid[0] by grid[1] bytes each)."""
    w, h = grid
    size = w * h
    out = {k: [] for k in _REGIONS}
    for off in range(0, len(data) - size + 1, size):
        frame = data[off:off + size]
        for key, (x0, x1, y0, y1) in _REGIONS.items():
            total = n = 0
            for y in range(y0, y1):
                row = frame[y * w + x0:y * w + x1]
                total += sum(_TABLE[b] for b in row)
                n += len(row)
            out[key].append(total / n if n else 0.0)
    return out


def jumps(series):
    """Where the brightness jumps: [(frame number, +1 for brighter or -1 for darker)]."""
    found = []
    for i in range(1, len(series)):
        a, b = series[i - 1], series[i]
        if abs(b - a) >= STEP and min(a, b) < DARK:
            found.append((i, 1 if b > a else -1))
    return found


def flashes(series, fps=FPS):
    """The most flashes in any one second of one series, and the second it starts at: (count, seconds from the start).
    A flash is a pair of jumps the opposite way round, so n turns of direction within the second make (n + 1) // 2."""
    marks = []  # the frame at which a jump went the other way from the one before
    last = 0
    for frame, sign in jumps(series):
        if last and sign != last:
            marks.append(frame)
        last = sign
    best, at, lo = 0, 0.0, 0
    for hi in range(len(marks)):
        while marks[hi] - marks[lo] >= fps:
            lo += 1
        count = (hi - lo + 2) // 2
        if count > best:
            best, at = count, marks[lo] / fps
    return best, at


def judge(all_series, fps=FPS):
    """The answer for a clip: {"flashes": most in one second, "at": seconds, "where": which part, "warn": bool}."""
    best = {"flashes": 0, "at": 0.0, "where": "all", "warn": False}
    for key, series in all_series.items():
        n, at = flashes(series, fps)
        if n > best["flashes"]:
            best.update({"flashes": n, "at": round(at, 1), "where": key})
    best["warn"] = best["flashes"] > MOST_FLASHES
    return best


def read_frames(path, seconds=SECONDS):
    """The raw grey frames of the first `seconds` of a clip, 16 by 9 at 25 a second, or None when FFmpeg cannot read it."""
    w, h = GRID
    try:
        r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-threads", "1", "-t", str(seconds), "-i", path, "-an", "-sn",
                            "-vf", f"fps={FPS},scale={w}:{h}:flags=area,format=gray", "-f", "rawvideo", "-"],
                           capture_output=True, timeout=240, check=False, preexec_fn=_nice)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 and r.stdout else None


def check(path, seconds=SECONDS):
    """Reads a clip and judges it. None when it cannot be read or the guard is off (so nothing is said about it)."""
    if not ENABLED:
        return None
    data = read_frames(path, seconds)
    if not data:
        return None
    return judge(frame_series(data))


def clock(seconds):
    s = int(round(seconds))
    return f"{s // 60}:{s % 60:02d}"


def words(res):
    """What to tell the person, or "" when the clip is fine."""
    if not res or not res.get("warn"):
        return ""
    part = "" if res.get("where") == "all" else f" in the {res['where']} of the picture"
    return (f"it flashes {res['flashes']} times in one second{part}, from {clock(res['at'])}. Fast flashing can make some people ill. "
            "Choose another clip, or keep it if you are sure")
