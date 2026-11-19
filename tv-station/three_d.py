"""3D films left out of channels (0.5.5, owner, 19 November 2026: "I dont want any 3d films as it plays as 2 images").

A 3D film plays on a 2D screen as two pictures, side by side or one over the other. Some say so (Jellyfin's 3D format,
or a 3D word in the file's name); others are named like any film, as the owner's Cloudy with a Chance of Meatballs
was. So each film on a channel is also checked once, in quiet hours: two frames, at 30% and 60% of its running time,
each shrunk to 128 by 72 grey dots, and the two halves of each compared. The halves of a 3D frame are nearly the same
picture (the owner's 3D film: a mean difference of 3 to 5 out of 255; 2D films: 44 to 74); both frames must agree, and
a nearly flat frame (a fade to black) counts for neither. What was found is kept, so each film is checked once.
"""
import json
import os
import re
import subprocess
import threading
import time

W, H = 128, 72
SAME = 6.0  # the halves of a frame differ by less than this: the same picture twice
SPREAD = 40  # a frame with less between its darkest and lightest dot than this tells nothing
SHARES = (0.3, 0.6)
WORDS = re.compile(r"(?<![A-Za-z0-9])(3[Dd]|SBS|HSBS|H-SBS|Half-SBS|HOU|H-OU|Half-OU|MVC)(?![A-Za-z0-9])")  # tags in capitals, as releases write them
_lock = threading.Lock()
_proc = {"p": None}
_stop = threading.Event()


def said(item):
    """Why a Jellyfin item says it is 3D (its 3D format, or a 3D word in its file's name), or "" when it does not."""
    if item.get("Video3DFormat"):
        return f"Jellyfin marks it {item['Video3DFormat']}"
    name = os.path.basename(str(item.get("Path") or ""))
    title = str(item.get("Name") or "")
    # A 3D word in the film's own title, such as Saw 3D (the owner's copy is 2D), says nothing about the file: the title,
    # and the part of it before a colon or bracket, are taken out of the name first.
    for words in {title, re.split(r"[:(]", title)[0].strip()}:
        if words:
            name = re.sub(re.escape(words), " ", name, flags=re.I)
    if WORDS.search(name):
        return "its file name says 3D"
    return ""


def halves(px):
    """(side by side, one over the other, spread) for one frame of W by H grey dots."""
    sbs = sum(abs(px[y * W + x] - px[y * W + x + W // 2]) for y in range(H) for x in range(W // 2)) / (W // 2 * H)
    ou = sum(abs(px[y * W + x] - px[(y + H // 2) * W + x]) for y in range(H // 2) for x in range(W)) / (W * H // 2)
    return sbs, ou, max(px) - min(px)


def verdict(scores):
    """"side by side", "one over the other", or "" (2D, or not enough to tell) from the frames' scores."""
    if len(scores) < len(SHARES) or any(sp <= SPREAD for _, _, sp in scores):
        return ""
    if all(sbs < SAME for sbs, _, _ in scores):
        return "side by side"
    if all(ou < SAME for _, ou, _ in scores):
        return "one over the other"
    return ""


def _nice():
    try:
        os.nice(19)
    except OSError:
        pass


def frame(src, head, at, limit=120):
    """One frame at `at` seconds as W by H grey dots, at the lowest priority; None when it cannot be read."""
    if _stop.is_set():
        raise InterruptedError("Stopped: someone began watching")
    argv = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-threads", "1", *head, "-ss", f"{at:.0f}", "-i", src,
            "-frames:v", "1", "-vf", f"scale={W}:{H},format=gray", "-f", "rawvideo", "-"]
    p = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, preexec_fn=_nice)
    _proc["p"] = p
    got = []
    reader = threading.Thread(target=lambda: got.append(p.stdout.read()), daemon=True)
    reader.start()
    began = time.monotonic()
    try:
        while p.poll() is None:
            if _stop.wait(0.2) or time.monotonic() - began > limit:
                p.kill()
                p.wait()
                raise InterruptedError("Stopped: someone began watching" if _stop.is_set() else "Took too long")
        reader.join(5)
        data = got[0] if got else b""
        return data if len(data) == W * H else None
    finally:
        _proc["p"] = None
        if p.stdout:
            p.stdout.close()


def look(jf_url, jf_key, entry):
    """Looks at one film: "side by side", "one over the other", "" for 2D, or None when its frames could not be read."""
    dur = float(entry.get("dur") or 0)
    src = f"{jf_url.rstrip('/')}/Videos/{entry['id']}/stream?static=true"
    head = ["-headers", f'Authorization: MediaBrowser Token="{jf_key}"\r\n']
    scores = []
    for share in SHARES:
        px = frame(src, head, dur * share)
        if px is None:
            return None
        scores.append(halves(px))
    return verdict(scores)


def stop():
    """Stops a look at once: a channel is about to play."""
    _stop.set()
    p = _proc["p"]
    if p and p.poll() is None:
        p.kill()


def begin():
    _stop.clear()


class Found:
    """Films checked, in `path` (three_d.json): {item id: {"3d": "" or how, "checked"}}."""

    def __init__(self, path):
        self.path = path
        self._doc, self._mtime = None, None

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

    def known(self, item_id):
        return str(item_id) in self._load()

    def how(self, item_id):
        """How a film looked at is 3D ("side by side" or "one over the other"), or "" (2D, or not looked at)."""
        return str((self._load().get(str(item_id)) or {}).get("3d") or "")

    def put(self, item_id, how, now=None):
        with _lock:
            doc = dict(self._load())
            doc[str(item_id)] = {"3d": how or "", "checked": int(now or time.time())}
            tmp = self.path + ".part"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(doc, f)
            os.replace(tmp, self.path)
            self._doc, self._mtime = doc, os.path.getmtime(self.path)

    def count(self):
        doc = self._load()
        return len(doc), sum(1 for v in doc.values() if v.get("3d"))
