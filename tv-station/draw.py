"""FFmpeg for the style pages (0.10.0): one command at a time, one thread, the lowest priority, and a stop that kills the
command at once when a channel starts to play.

Measured on this server on 28 November 2026: a 6 second 1920 by 1080 title clip took 3.4 seconds and 205 MB with one
thread and a short look-ahead, and 1.8 seconds and 570 MB with two, against the container's 768 MB. So every command
here is told to use one thread, and the jobs that use it (styles.py, kit.py) run one at a time.
"""
import os
import re
import subprocess
import tempfile
import threading

import dog

W, H, FPS = 1920, 1080, 25
_proc = {"p": None}
_stop = threading.Event()
_run = threading.Lock()  # one FFmpeg command at a time, from anywhere in this module


class Stopped(RuntimeError):
    pass


def _nice():
    try:
        os.nice(19)
    except OSError:
        pass


def stop():
    """A channel is about to play: whatever is being drawn stops now."""
    _stop.set()
    p = _proc["p"]
    if p and p.poll() is None:
        p.kill()


def clear():
    _stop.clear()


def stopped():
    return _stop.is_set()


# One thread, a short look-ahead, no second encoder: what the measurement above used.
H264 = ["-threads", "1", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-x264-params", "threads=1:lookahead-threads=1:rc-lookahead=10:sliced-threads=0", "-g", str(FPS * 2), "-movflags", "+faststart"]


def ff(*args, timeout=300):
    """Runs FFmpeg once. Raises Stopped when stop() was called, RuntimeError with FFmpeg's last line when it fails."""
    if _stop.is_set():
        raise Stopped("A channel started to play, so the style stopped")
    with _run:
        p = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-y", "-filter_threads", "1", "-filter_complex_threads", "1", *args],
                             stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, preexec_fn=_nice)
        _proc["p"] = p
        try:
            err = p.communicate(timeout=timeout)[1]
        except subprocess.TimeoutExpired:
            p.kill()
            p.communicate()
            raise RuntimeError("FFmpeg took too long") from None
        finally:
            _proc["p"] = None
    if _stop.is_set():
        raise Stopped("A channel started to play, so the style stopped")
    if p.returncode != 0:
        raise RuntimeError("FFmpeg: " + (err.decode("utf-8", "replace").strip().splitlines() or ["failed"])[-1][:300])


def text_file(words, folder):
    """Words in a file for drawtext's textfile, so nothing in them is read as part of a command."""
    fd, path = tempfile.mkstemp(prefix="words-", suffix=".txt", dir=folder)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(words)
    return path


def clean_words(raw, most=40):
    """A name cut to 40 characters, with nothing a person could not read on a television: control characters go."""
    return re.sub(r"\s+", " ", "".join(c for c in str(raw or "") if c.isprintable())).strip()[:most]


def colour(raw, default="#1B8A7F"):
    """#RRGGBB in capitals, or the default."""
    return str(raw).upper() if re.fullmatch(r"#[0-9A-Fa-f]{6}", str(raw or "")) else default


def luminance(hexcolour):
    c = [int(hexcolour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def text_colour(c1, c2):
    """Black or white, whichever reads best on both colours, and whether it reaches 7 to 1 (WCAG 1.4.6) on both."""
    white = min(contrast("#FFFFFF", c1), contrast("#FFFFFF", c2))
    black = min(contrast("#000000", c1), contrast("#000000", c2))
    ink, ratio = ("#FFFFFF", white) if white >= black else ("#000000", black)
    return ink, ratio >= 7.0, round(ratio, 1)


def ffcolour(c):
    return "0x" + c[1:]


def still_to_clip(src, dst, seconds=5, fade=0.5):
    """A still picture as a short title clip: fitted inside 1920 by 1080, faded in and out. No sound."""
    ff("-loop", "1", "-framerate", str(FPS), "-t", str(seconds), "-i", src, "-vf",
       f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,format=yuv420p,"
       f"fade=t=in:st=0:d={fade},fade=t=out:st={seconds - fade}:d={fade}", "-an", "-t", str(seconds), *H264, dst)


def text_logo(name, ink, plate, dst, folder):
    """The on-screen logo made from the channel's name: the words on a plate of the colour, the rest clear. 120 pixels tall."""
    name = clean_words(name) or "TV"
    words = text_file(name, folder)
    size = 64
    width = min(1800, int(0.62 * size * len(name)) + 96)
    try:
        ff("-f", "lavfi", "-i", f"color=c=black@0.0:s={width}x120:r=1,format=rgba", "-vf",
           f"drawtext=fontfile={dog.FONT}:textfile={words}:expansion=none:fontsize={size}:fontcolor={ffcolour(ink)}:x=24:y=(h-th)/2:"
           f"box=1:boxcolor={ffcolour(plate)}@0.92:boxborderw=24,format=rgba", "-frames:v", "1", dst)
    finally:
        os.remove(words)
    return dst
