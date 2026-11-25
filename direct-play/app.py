"""Direct play: makes films and series play directly on the devices people choose, so Jellyfin does not have to
convert them while they play (DASH-425). The rules and checks are those of the owner's mediafix script, which
converted 1,173 files and saved 1.03 TB.

How it works:
- Survey: it walks the movies and tv folders and probes each video with ffprobe. Only new or changed files are
  probed (same size and modified time: the cached facts are kept), so a second survey reads almost nothing.
- Rules: from the facts and the devices chosen in its settings, each file needs one of these, cheapest first:
    remux     the wrong container (AVI, M2TS, TS and the like): repackaged as MKV, streams copied
    audio     no sound track every chosen device plays (DTS, TrueHD, FLAC...): a playable track is added beside the
              original, which is kept (AC3 5.1, or AAC stereo when a chosen device lacks AC3)
    shrink    H.264 at remux bitrates: H.264 CRF 20 with a bitrate cap
    reencode  an old format (DivX, Xvid, MPEG-2, WMV, VC-1), 10-bit H.264, larger than a chosen device shows, or HEVC
              when the setting asks and no chosen device plays it: H.264 CRF 20
  HEVC is left alone unless that setting is activated: it costs space, and Jellyfin converts it live.
- One file at a time, at the lowest processor and disk priority, only when the schedule allows (weekends, Starboard's
  quiet hours, or any time). The file being converted always finishes; the schedule is checked between files.
- Each output is checked (length, video, the first sound track, where sound and picture start) before it replaces
  the original. Then Reelix rescans the film or series, and Jellyfin is told the file changed.
- Pause stops the current file at once: its unfinished copy is removed and the file is done again later.

Lightweight: the worker wakes once a minute and does nothing outside its hours. The card reads a small status file
the worker writes while converting, at most as often as Card updates every says (30 seconds unless changed): no probing for the card.
"""
import contextlib
import errno
import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

import sbplugin
from sbplugin import fetch, keep, plural, remember, serve

ROOTS = {"movies": os.environ.get("DIRECT_PLAY_MOVIES", "/media/movies"), "tv": os.environ.get("DIRECT_PLAY_TV", "/media/tv")}
VIDEO = re.compile(r"\.(mkv|mp4|avi|m4v|mov|wmv|ts|m2ts|mpg|mpeg|divx|flv|webm)$", re.I)
OURS = (".direct-play.", ".mediafix.")  # unfinished copies, ours or mediafix's: never surveyed
GOOD_CONTAINERS = ("mkv", "mp4", "m4v")
LOSSLESS_KEEP = {"dts", "truehd", "flac", "opus", "vorbis", "aac", "ac3", "eac3", "mp3"}  # worth keeping beside a new track
ORDER = ["remux", "audio", "shrink", "reencode"]
WORDS = {"remux": "Repackage as MKV", "audio": "Add a playable sound track", "shrink": "Shrink", "reencode": "Convert to H.264"}
KEPT = ".direct-play-originals"  # where originals go when Keep the originals is activated, in the same folder tree
SURVEY_HOURS = 6  # a new survey at most this often while working
TICK = 60  # the worker wakes once a minute
CARD_SECONDS = (10, 30, 60, 300)  # Card updates every (owner, 14 November 2026): 30 seconds unless changed
run = subprocess.run  # replaced in tests
popen = subprocess.Popen  # replaced in tests
now = time.time  # replaced in tests
localtime = time.localtime  # replaced in tests

# Devices -------------------------------------------------------------------------------------------------------
# What each plays directly: video codecs, the tallest picture, and sound codecs. 10-bit H.264 plays on none of them.
# Kept on the safe side: a device that plays a format only on some models, or only through a receiver, is not
# counted for it.
DEVICES = {
    "roku_express": {"label": "Roku Express and older Rokus", "video": {"h264"}, "height": 1080,
                     "audio": {"aac", "ac3", "eac3", "mp3"}},
    "roku_4k": {"label": "Roku 4K", "video": {"h264", "hevc", "vp9"}, "height": 2160, "audio": {"aac", "ac3", "eac3", "mp3"}},
    "fire_tv": {"label": "Fire TV Sticks", "video": {"h264", "hevc", "vp9"}, "height": 1080, "audio": {"aac", "ac3", "eac3", "mp3"}},
    "chromecast": {"label": "Chromecast", "video": {"h264"}, "height": 1080, "audio": {"aac", "mp3", "opus", "flac", "vorbis"}},
    "smart_tv": {"label": "Smart TV apps", "video": {"h264", "hevc", "vp9"}, "height": 2160, "audio": {"aac", "ac3", "eac3", "mp3"}},
    "browser": {"label": "Web browsers", "video": {"h264", "vp9", "av1"}, "height": 2160, "audio": {"aac", "mp3", "opus", "flac", "vorbis"}},
    "apple_tv": {"label": "Apple TV", "video": {"h264", "hevc"}, "height": 2160, "audio": {"aac", "ac3", "eac3", "mp3", "flac", "alac"}},
    "shield": {"label": "Nvidia Shield", "video": {"h264", "hevc", "vp9", "mpeg2video", "vc1", "mpeg4"}, "height": 2160,
               "audio": {"aac", "ac3", "eac3", "mp3", "dts", "truehd", "flac", "opus", "vorbis"}},
}
DEFAULT_DEVICES = {"roku_express"}  # the owner's mediafix rules
CODEC_WORDS = {"hevc": "HEVC", "h264": "H.264", "mpeg4": "MPEG-4 (DivX or Xvid)", "msmpeg4v3": "DivX 3", "mpeg2video": "MPEG-2",
               "vc1": "VC-1", "wmv3": "WMV", "wmv2": "WMV", "mpeg1video": "MPEG-1", "vp9": "VP9", "av1": "AV1", "vp8": "VP8",
               "dts": "DTS", "truehd": "Dolby TrueHD", "flac": "FLAC", "pcm_s16le": "PCM", "mp2": "MP2", "wmav2": "WMA",
               "ac3": "Dolby Digital", "eac3": "Dolby Digital Plus", "aac": "AAC", "mp3": "MP3", "opus": "Opus", "vorbis": "Vorbis"}

_lock = threading.Lock()
_pass = threading.local()  # the settings the worker read once for its pass (see setting)
_current = {"proc": None, "path": None}
_wake = threading.Event()
_survey_now = threading.Event()


def words(codec):
    return CODEC_WORDS.get(codec or "", (codec or "unknown").upper())


# Settings ------------------------------------------------------------------------------------------------------

def setting(key, default=None):
    """One setting. The worker reads settings.json once for each pass and once after each file, not each time it
    asks: a pass with nothing to do asked about ninety times, and each read woke the worker about six times, so it
    woke about 570 times a minute at rest (measured 16 November 2026). Anything else, the card included, and the
    worker while it converts a file, read the file each time, as before."""
    held = getattr(_pass, "settings", None)
    if held is None:
        return sbplugin.setting(key, default)
    v = held.get(key)
    return default if v in (None, "") else v


@contextlib.contextmanager
def _as_they_change():
    """While a file is converted, settings are read as they change (Card updates every, Pause); afterwards the pass
    reads them once again."""
    held, _pass.settings = getattr(_pass, "settings", None), None
    try:
        yield
    finally:
        if held is not None:
            _pass.settings = sbplugin.settings()


def chosen():
    """The devices chosen in settings: their keys, in the table's order."""
    out = [k for k in DEVICES if bool(setting(f"device_{k}", k in DEFAULT_DEVICES)) is True]
    return out


def profile(devices=None):
    """What every chosen device plays: the video codecs, the tallest picture and the sound codecs, or None."""
    devices = chosen() if devices is None else devices
    if not devices:
        return None
    video = set.intersection(*(DEVICES[d]["video"] for d in devices))
    audio = set.intersection(*(DEVICES[d]["audio"] for d in devices))
    return {"devices": list(devices), "video": video, "audio": audio or {"aac"}, "height": min(DEVICES[d]["height"] for d in devices)}


def _num(key, default, lo, hi):
    try:
        return max(lo, min(float(setting(key, default)), hi))
    except (TypeError, ValueError):
        return default


def card_seconds():
    """How often the card updates, and the worker writes its status file while converting: 30 seconds unless changed."""
    try:
        v = int(setting("card_seconds", 30))
    except (TypeError, ValueError):
        return 30
    return v if v in CARD_SECONDS else 30


def options():
    return {"hevc_to_h264": bool(setting("hevc_to_h264", False)) is True,
            "shrink": bool(setting("shrink", True)) is True,
            "caps": {1080: _num("shrink_1080", 15, 4, 80), 720: _num("shrink_720", 8, 2, 40), 0: _num("shrink_sd", 5, 1, 20)},
            "keep_originals": bool(setting("keep_originals", False)) is True,
            "when": str(setting("when", "weekends")) if str(setting("when", "weekends")) in ("weekends", "quiet", "any") else "weekends"}


# Survey --------------------------------------------------------------------------------------------------------

def _low():
    """The prefix that runs a program at the lowest processor and disk priority."""
    pre = ["nice", "-n", "19"] if shutil.which("nice") else []
    return (["ionice", "-c", "3"] if shutil.which("ionice") else []) + pre


def ffprobe(path):
    r = run(_low() + ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path],
            capture_output=True, text=True, timeout=600)
    if r.returncode:
        raise RuntimeError((r.stderr or "ffprobe failed").strip()[-200:])
    return json.loads(r.stdout or "{}")


def video_stream(streams):
    return next((s for s in streams if s.get("codec_type") == "video" and not (s.get("disposition") or {}).get("attached_pic")), None)


def facts(path):
    """What the survey keeps about one file: its size, time, container, video and sound. No rule is applied here, so
    changing the devices needs no new probe."""
    st = os.stat(path)
    rec = {"path": path, "size": st.st_size, "mtime": int(st.st_mtime), "container": os.path.splitext(path)[1].lower().lstrip(".")}
    try:
        d = ffprobe(path)
    except Exception as e:  # noqa: BLE001 - a file that cannot be read is listed with why
        return {**rec, "error": str(e)[:200]}
    streams, fmt = d.get("streams") or [], d.get("format") or {}
    v = video_stream(streams)
    dur = float(fmt.get("duration") or 0)
    if not v:
        return {**rec, "error": "no video stream", "dur": round(dur)}
    return {**rec, "dur": round(dur), "vcodec": v.get("codec_name"), "h": v.get("height") or 0, "w": v.get("width") or 0,
            "tenbit": "10" in (v.get("pix_fmt") or "") or "10" in (v.get("profile") or ""),
            "mbps": round(st.st_size * 8 / dur / 1e6, 1) if dur else None,
            "audio": sorted({s.get("codec_name") for s in streams if s.get("codec_type") == "audio" and s.get("codec_name")})}


def files():
    out = []
    for root in ROOTS.values():
        for d, dirs, fs in os.walk(root):
            dirs[:] = [x for x in dirs if not x.startswith(".")]  # hidden folders, our kept originals among them
            out += [os.path.join(d, f) for f in fs if VIDEO.search(f) and not f.startswith(".") and not any(o in f for o in OURS)]
    return sorted(out)


def survey():
    """Probes only new or changed files; keeps the facts of the rest. Two probes at a time, at the lowest priority."""
    old = {r["path"]: r for r in remember("survey", []) or []}
    keep_, todo = [], []
    for p in files():
        try:
            st = os.stat(p)
        except OSError:
            continue
        r = old.get(p)
        if r and r.get("size") == st.st_size and r.get("mtime") == int(st.st_mtime):
            keep_.append(r)
        else:
            todo.append(p)
    with ThreadPoolExecutor(2) as ex:
        new = list(ex.map(facts, todo))
    out = keep_ + new
    if not save("survey", out):
        raise NoRoom()
    state = _state()
    state.update(surveyed=now(), probed=len(new))
    save("state", state, hold=True)
    return out


# Rules ---------------------------------------------------------------------------------------------------------

def tier(height):
    return 1080 if (height or 0) > 800 else 720 if (height or 0) > 600 else 0


def too_big(rec, prof):
    cap_h = prof["height"]
    cap_w = 1920 if cap_h <= 1080 else 3840
    return (rec.get("h") or 0) > cap_h + 8 or (rec.get("w") or 0) > cap_w


_UNSET = object()


def classify(rec, prof=_UNSET, opts=None):
    """(what the file needs, why): one of remux, audio, shrink, reencode, or ok, hevc (left alone), error."""
    prof = profile() if prof is _UNSET else prof
    opts = options() if opts is None else opts
    if rec.get("error"):
        return "error", rec["error"]
    if not prof:
        return "ok", "no devices chosen"
    v = rec.get("vcodec")
    if v == "h264" and rec.get("tenbit"):
        return "reencode", "10-bit H.264, which no device plays"
    if v not in prof["video"]:
        if v == "hevc":
            if opts["hevc_to_h264"]:
                return "reencode", "HEVC, which none of your devices plays"
            return "hevc", "HEVC: left alone, Jellyfin converts it as it plays"
        return "reencode", f"video is {words(v)}"
    if v == "h264" and too_big(rec, prof):
        return "reencode", f"{rec.get('w')} by {rec.get('h')}, larger than your devices show"
    audio = set(rec.get("audio") or [])
    if audio and not audio & prof["audio"]:
        return "audio", "sound is " + ", ".join(words(a) for a in sorted(audio))
    if rec.get("container") not in GOOD_CONTAINERS:
        return "remux", f"container is {str(rec.get('container')).upper()}"
    if opts["shrink"] and v == "h264" and rec.get("mbps") and rec["mbps"] > opts["caps"][tier(rec.get("h"))]:
        return "shrink", f"{rec['mbps']} Mbps"
    return "ok", ""


# Converting ----------------------------------------------------------------------------------------------------

def new_track(channels, prof):
    """The added sound track: AC3 5.1 when there are more than two channels and every device plays AC3, else AAC stereo."""
    if channels > 2 and "ac3" in prof["audio"]:
        return "ac3", ["ac3", "640k", str(min(channels, 6))], "Dolby Digital 5.1"
    return "aac", ["aac", "192k", "2"], "AAC Stereo"


def build_cmd(src, bucket, info, tmp, prof):
    """mediafix's ffmpeg command, with the chosen devices' sound and picture size in place of the Roku's."""
    streams = info.get("streams") or []
    v = video_stream(streams)
    auds = [s for s in streams if s.get("codec_type") == "audio"]
    subs = [s for s in streams if s.get("codec_type") == "subtitle"]
    ext = os.path.splitext(src)[1].lower()
    good = ext in (".mkv", ".mp4", ".m4v")
    playable = prof["audio"]

    cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-y", "-loglevel", "error", "-nostats", "-progress", "pipe:1", "-threads", "2"]
    if not good:
        cmd += ["-fflags", "+genpts"]  # rebuild timestamps from AVI and TS: avoids sound drifting from the picture
    cmd += ["-i", src, "-map_metadata", "0", "-map_chapters", "0", "-max_muxing_queue_size", "4096", "-filter_threads", "1"]

    cmd += ["-map", f"0:{v['index']}"]
    if bucket in ("remux", "audio"):
        cmd += ["-c:v", "copy"]
    else:
        vf = []
        if v.get("field_order") not in (None, "progressive", "unknown"):
            vf.append("bwdif=mode=send_frame")  # deinterlace DVD and TV sources
        cap_h = prof["height"] if prof["height"] <= 1080 else 2160
        cap_w = 1920 if cap_h <= 1080 else 3840
        if (v.get("width") or 0) > cap_w or (v.get("height") or 0) > cap_h + 8:
            vf.append(f"scale=w={cap_w}:h={cap_h}:force_original_aspect_ratio=decrease:force_divisible_by=2")
        cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-profile:v", "high", "-level:v", "4.1" if cap_h <= 1080 else "5.1",
                "-pix_fmt", "yuv420p", "-fps_mode", "passthrough", "-threads", "2"]
        if bucket == "shrink" or (v.get("height") or 0) > 800:
            cmd += ["-maxrate", "10M", "-bufsize", "20M"] if cap_h <= 1080 else ["-maxrate", "20M", "-bufsize", "40M"]
        if vf:
            cmd += ["-vf", ",".join(vf)]

    # Sound: the first (default) track is one every chosen device plays. AVI and TS sound is always converted, with
    # resync: copying variable bitrate MP3 out of an AVI is a classic cause of drift.
    has_ok = good and any(a.get("codec_name") in playable for a in auds)
    out_a = 0
    if auds and not has_ok:
        a0 = next((a for a in auds if (a.get("disposition") or {}).get("default")), auds[0])
        ch = a0.get("channels") or 2
        _, (codec, rate, chans), title = new_track(ch, prof)
        cmd += ["-map", f"0:{a0['index']}", f"-c:a:{out_a}", codec, f"-b:a:{out_a}", rate, f"-ac:a:{out_a}", chans]
        if not good:
            cmd += [f"-filter:a:{out_a}", "aresample=async=1:first_pts=0"]  # keeps converted AVI sound locked to the picture
        lang = (a0.get("tags") or {}).get("language")
        if lang:
            cmd += [f"-metadata:s:a:{out_a}", f"language={lang}"]
        cmd += [f"-metadata:s:a:{out_a}", f"title={title}", f"-disposition:a:{out_a}", "default"]
        out_a += 1
    if has_ok:  # a playable track first and default, such as a remux with TrueHD listed before its AC3 track
        first = next(a for a in auds if a.get("codec_name") in playable)
        auds = [first] + [a for a in auds if a is not first]
    keep_ = LOSSLESS_KEEP if good else {"dts", "truehd", "flac"}  # AVI and the like: no lossy duplicate
    for a in auds:
        if not has_ok and a.get("codec_name") not in keep_:
            continue  # MP2, WMA, PCM, or the AVI track just converted
        cmd += ["-map", f"0:{a['index']}", f"-c:a:{out_a}", "copy", f"-disposition:a:{out_a}", "default" if has_ok and out_a == 0 else "0"]
        out_a += 1

    out_s = 0
    for s in subs:
        c = s.get("codec_name")
        if c in ("eia_608", "bin_data") or c is None:
            continue
        cmd += ["-map", f"0:{s['index']}", f"-c:s:{out_s}", "srt" if c == "mov_text" else "copy"]
        out_s += 1
    if any(s.get("codec_type") == "attachment" for s in streams):
        cmd += ["-map", "0:t", "-c:t", "copy"]
    return cmd + ["-f", "matroska", tmp]


def wanted_subs(info):
    return sum(1 for s in info.get("streams") or [] if s.get("codec_type") == "subtitle" and s.get("codec_name") not in ("eia_608", "bin_data", None))


def check(src_info, out, bucket, prof):
    """mediafix's check of a new file before it replaces the original: None when it is right, else what is wrong."""
    sd = float((src_info.get("format") or {}).get("duration") or 0)
    od = float((out.get("format") or {}).get("duration") or 0)
    if sd and abs(od - sd) > max(2.0, sd * 0.005):
        return f"length {od:.0f} seconds, the original {sd:.0f}"
    v = video_stream(out.get("streams") or [])
    if not v:
        return "no picture in the new file"
    want = "h264" if bucket in ("shrink", "reencode") else (video_stream(src_info.get("streams") or []) or {}).get("codec_name")
    if v.get("codec_name") != want:
        return f"the new picture is {words(v.get('codec_name'))}, not {words(want)}"
    a = [s for s in out.get("streams") or [] if s.get("codec_type") == "audio"]
    if any(s.get("codec_type") == "audio" for s in src_info.get("streams") or []):
        if not a or a[0].get("codec_name") not in prof["audio"]:
            return "the first sound track is not one your devices play"
        vs, as_ = float(v.get("start_time") or 0), float(a[0].get("start_time") or 0)
        if abs(vs - as_) > 0.5:
            return f"sound starts {as_ - vs:+.2f} seconds from the picture"
    subs = sum(1 for s in out.get("streams") or [] if s.get("codec_type") == "subtitle")
    if subs < wanted_subs(src_info):
        return f"{subs} of {wanted_subs(src_info)} subtitle tracks"
    return None


def _rm(p):
    """Removes one of the plug-in's own unfinished copies, never a person's file."""
    if p and any(o in os.path.basename(p) for o in OURS[:1]):
        try:
            os.remove(p)
        except OSError:
            pass


_unsaved = {"state": None, "n": 0}  # progress the disk had no room for: kept here and written as soon as there is room


class NoRoom(Exception):
    """The plug-in's own folder is full: nothing more is converted until its progress can be written down again."""


def _no_room(e):
    return isinstance(e, OSError) and e.errno in (errno.ENOSPC, errno.EDQUOT)


def save(name, value, hold=False):
    """keep(), safe on a full disk. keep() writes a new file and swaps it in, so a failed write leaves the last good one
    as it was; here the half-written new file is also removed (it only takes up the room that is missing) and False comes
    back instead of an error. A value the plug-in cannot do without (hold=True: the progress) is kept in memory and
    written as soon as there is room, by flush_unsaved()."""
    try:
        keep(name, value)
    except OSError as e:
        with contextlib.suppress(OSError):
            os.remove(os.path.join(sbplugin.DATA, f"{name}.json.tmp"))
        if not _no_room(e):
            raise
        if hold:
            _unsaved[name] = value
            _unsaved["n"] += 1
        return False
    if hold and _unsaved.get(name) is not None:
        _unsaved[name] = None
        _unsaved["n"] += 1
    return True


def flush_unsaved():
    """Writes down the progress that had no room before. False while the disk is still full."""
    value = _unsaved.get("state")
    return value is None or save("state", value, hold=True)


def free_enough(folder, size):
    """mediafix asked for the file's size and a fifth, plus 50 GB. On a smaller disk the margin is a tenth of it."""
    st = os.statvfs(folder)
    margin = min(50e9, st.f_blocks * st.f_frsize * 0.1)
    return st.f_bavail * st.f_frsize >= size * 1.2 + margin


def _encode(cmd, dur, rec, bucket):
    """Runs ffmpeg at the lowest priority, reading its progress for the card. Returns (return code, last error line)."""
    log = os.path.join(sbplugin.DATA, "ffmpeg.log")
    with open(log, "w", encoding="utf-8") as err:
        p = popen(_low() + cmd, stdout=subprocess.PIPE, stderr=err, text=True)
        with _lock:
            _current.update(proc=p, path=rec["path"])
        last, speed, done_s = 0.0, 0.0, 0.0
        status(rec, bucket, 0, None, force=True)
        for line in p.stdout:
            k, _, v = line.strip().partition("=")
            if k == "out_time_us" and v.lstrip("-").isdigit():
                done_s = max(0.0, int(v) / 1e6)
            elif k == "speed":
                try:
                    speed = float(v.rstrip("x"))
                except ValueError:
                    pass
            elif k == "progress" and now() - last >= card_seconds():
                last = now()
                pct = int(min(99, 100 * done_s / dur)) if dur else None
                left = (dur - done_s) / speed if dur and speed > 0 else None
                status(rec, bucket, pct, left)
        code = p.wait()
        p.stdout.close()
        with _lock:
            _current.update(proc=None, path=None)
    try:
        with open(log, encoding="utf-8") as f:
            lines = [x for x in f.read().strip().splitlines() if x.strip()]
    except OSError:
        lines = []
    return code, (lines[-1] if lines else "")[:200]


class Stopped(Exception):
    """Pause stopped the file: its unfinished copy is gone and it is done again later."""


def fix(rec, bucket, prof, opts):
    """Fixes one file. None when done, else why not."""
    src = rec["path"]
    d, base = os.path.split(src)
    stem = os.path.splitext(base)[0]
    tmp, dst = os.path.join(d, f".{stem}.direct-play.mkv"), os.path.join(d, stem + ".mkv")
    info = ffprobe(src)
    if not free_enough(d, rec["size"]):
        return "not enough free space"
    code, err = 1, ""
    try:
        code, err = _encode(build_cmd(src, bucket, info, tmp, prof), float((info.get("format") or {}).get("duration") or 0), rec, bucket)
    finally:
        if code:
            _rm(tmp)
    if _state().get("paused") or sbplugin.holding():  # paused, or stopped for an update (plug-in API 1.14)
        _rm(tmp)
        raise Stopped()
    if code or not os.path.exists(tmp):
        _rm(tmp)
        return "ffmpeg: " + (err or "stopped")
    try:
        problem = check(info, ffprobe(tmp), bucket, prof)
    except Exception as e:  # noqa: BLE001
        problem = f"the new file could not be read: {e}"
    if problem:
        _rm(tmp)
        return "check failed: " + problem
    new_size = os.path.getsize(tmp)
    if bucket == "shrink" and new_size > rec["size"] * 0.9:
        _rm(tmp)
        return f"not worth it ({new_size / 1e9:.1f} GB against {rec['size'] / 1e9:.1f} GB), so the original was kept"
    if opts["keep_originals"]:
        put_aside(src)
    os.replace(tmp, dst)
    if dst != src and os.path.exists(src):
        os.remove(src)  # the original, replaced by the checked new file, as mediafix does
    rescan(src, dst)
    return None


def put_aside(src):
    """Keep the originals: the original moves to .direct-play-originals in its own top folder, same disk, never deleted."""
    for root in ROOTS.values():
        r = os.path.realpath(root)
        if os.path.realpath(src).startswith(r + os.sep):
            to = os.path.join(r, KEPT, os.path.relpath(os.path.realpath(src), r))
            os.makedirs(os.path.dirname(to), exist_ok=True)
            shutil.move(src, to)
            return to
    return None


# Telling Reelix and Jellyfin -----------------------------------------------------------------------------------

def _run_file(name):
    try:
        with open(os.path.join(sbplugin.RUN, name), encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        return {}


def reelix(path, data=None, method=None):
    rx = _run_file("reelix.json")
    if not rx.get("url") or not rx.get("api_key"):
        raise LookupError("no Reelix")
    return fetch(rx["url"].rstrip("/") + "/api/v1" + path, {"X-Api-Key": rx["api_key"]}, data=data, method=method, timeout=30)


def jellyfin(path, data=None, method=None):
    jf = _run_file("jellyfin.json")
    if not jf.get("url") or not jf.get("api_key"):
        raise LookupError("no Jellyfin")
    return fetch(jf["url"].rstrip("/") + path, sbplugin.jellyfin_headers(jf["api_key"]), data=data, method=method, timeout=30)


_library = {"at": 0, "movies": [], "series": []}


def library():
    """Reelix's films and series (id, title, year, folder), read at most once an hour."""
    if now() - _library["at"] > 3600:
        for kind, path in (("movies", "/movies?page_size=0"), ("series", "/series?page_size=0")):
            try:
                got = reelix(path)
                _library[kind] = [{"id": x.get("id"), "title": x.get("title"), "year": x.get("year"), "folder": os.path.basename(str(x.get("path") or "").rstrip("/"))}
                                  for x in (got.get("items") if isinstance(got, dict) else got) or [] if isinstance(x, dict)]
            except Exception:  # noqa: BLE001 - no Reelix: the folder names are used
                _library[kind] = []
        _library["at"] = now()
    return _library


def where(path):
    """(movies or tv, the top folder's name, the path inside the root) for a file, or (None, None, None)."""
    for kind, root in ROOTS.items():
        rel = os.path.relpath(path, root)
        if not rel.startswith(".."):
            return kind, rel.split(os.sep)[0], rel
    return None, None, None


def rescan(old, new):
    """Reelix rescans the film or series (its file may have a new name), and Jellyfin is told the file changed. Either
    may be missing; the new file is there whatever they say."""
    kind, top, rel = where(new)
    lib = library()
    hit = next((x for x in lib["movies" if kind == "movies" else "series"] if x["folder"] == top), None)
    if hit and hit.get("id") is not None:
        try:
            reelix(f"/{'movies' if kind == 'movies' else 'series'}/{hit['id']}/rescan", data=b"", method="POST")
        except Exception:  # noqa: BLE001
            pass
    try:
        folders = jellyfin("/Library/VirtualFolders") or []
        locs = [loc for f in folders for loc in (f.get("Locations") or []) if os.path.basename(loc.rstrip("/")) == os.path.basename(ROOTS[kind].rstrip("/"))]
        if locs:
            base = locs[0].rstrip("/")
            ups = [{"Path": f"{base}/{rel}", "UpdateType": "Modified" if old == new else "Created"}]
            if old != new:
                ups.append({"Path": f"{base}/{os.path.relpath(old, ROOTS[kind])}", "UpdateType": "Deleted"})
            jellyfin("/Library/Media/Updated", data={"Updates": ups}, method="POST")
    except Exception:  # noqa: BLE001 - Jellyfin finds it at its next scan
        pass


# Titles --------------------------------------------------------------------------------------------------------

EPISODE = re.compile(r"(?i)\bS(\d{1,2})\s?E(\d{1,3})\b|\b(\d{1,2})x(\d{2,3})\b")


def title(path):
    """A title people know: Reelix's name for the film or series when it is known, else the folder's name, with the
    series and episode from the file's name."""
    kind, top, rel = where(path)
    if not kind:
        return os.path.basename(path)
    lib = _library  # only what is already read: the card never asks Reelix
    hit = next((x for x in lib["movies" if kind == "movies" else "series"] if x["folder"] == top), None)
    name = (f"{hit['title']}" + (f" ({hit['year']})" if kind == "movies" and hit.get("year") else "")) if hit and hit.get("title") else top
    if kind == "tv":
        m = EPISODE.search(os.path.basename(path))
        if m:
            s, e = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
            return f"{name}, series {int(s)} episode {int(e)}"
        if os.sep in rel:
            return f"{name}, {os.path.splitext(os.path.basename(path))[0]}"
    return name


# Schedule ------------------------------------------------------------------------------------------------------

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def in_hours(when=None):
    when = when or options()["when"]
    if when == "any":
        return True
    if when == "weekends":
        return localtime(now()).tm_wday >= 5
    q = remember("quiet", {}) or {}
    return now() - float(q.get("at") or 0) < 65 * 60  # Starboard's quiet-hours job wakes it each hour in quiet hours


def next_run(when=None):
    when = when or options()["when"]
    if when == "any":
        return "now"
    if when == "weekends":
        return "on Saturday from midnight"
    q = remember("quiet", {}) or {}
    return f"in quiet hours, from about {int(q['from']):02d}:00" if q.get("from") is not None else "in Starboard's quiet hours"


def quiet_job():
    """Starboard runs this each hour in its quiet hours (the download hours when they are set, else 01:00 to 06:00)."""
    q = remember("quiet", {}) or {}
    t = now()
    if t - float(q.get("at") or 0) > 3 * 3600:  # a new night: remember when it starts, for the card
        q["from"] = localtime(t).tm_hour
    q["at"] = t
    save("quiet", q)
    _wake.set()
    return {"said": "Quiet hours: working on the files that need it" if options()["when"] == "quiet" else "Quiet hours noted"}


# State and the worker ------------------------------------------------------------------------------------------

def surveyed():
    """The survey's facts, read from its file each time: they are not kept in memory between asks (a library of 50,000
    files is about 48 MB of them), as the cards use todo_head() instead."""
    return remember("survey", []) or []


def _stamp(name):
    try:
        st = os.stat(os.path.join(sbplugin.DATA, f"{name}.json"))
        return st.st_ino, st.st_mtime_ns, st.st_size
    except OSError:
        return None


_head = {"key": None, "count": 0, "head": []}
HEAD = 5  # the card shows the next four, and one more in case the first is the file being converted


def todo_head():
    """(how many files are still to do, the first few in order): what the cards and the idle reason need. Worked out
    again only when the survey, the state or the devices and options changed, so the card asked every 30 seconds costs
    a look at two files' times, not a read of the whole survey."""
    prof, opts = profile(), options()
    key = (_stamp("survey"), _stamp("state"), _unsaved["n"], tuple(sorted(prof["devices"])) if prof else None, json.dumps(opts, sort_keys=True))
    if _head["key"] != key:
        todo = todo_list(prof=prof, opts=opts)
        _head.update(key=key, count=len(todo), head=todo[:HEAD])
    return _head["count"], _head["head"]


def _state():
    s = _unsaved["state"] or remember("state", None) or {}
    return {"done": 0, "saved_bytes": 0, "failed": {}, "paused": False, **s}


def todo_list(recs=None, prof=None, opts=None, state=None):
    recs = surveyed() if recs is None else recs
    prof = profile() if prof is None else prof
    opts = options() if opts is None else opts
    failed = (state or _state())["failed"]
    out = []
    for r in recs:
        f = failed.get(r["path"])
        if f and f.get("size") == r.get("size") and f.get("mtime") == r.get("mtime"):
            continue  # failed before and not changed since
        b, why = classify(r, prof, opts)
        if b in ORDER:
            out.append({**r, "bucket": b, "why": why})
    return sorted(out, key=lambda r: (ORDER.index(r["bucket"]), r["path"]))


def status(rec=None, bucket=None, pct=None, left=None, force=False, reason=None):
    """The small file the card reads: what is being converted, how far, and why nothing is when nothing is."""
    st = (remember("now", {}) or {}) if rec else {}  # only a file being converted needs what it said before
    if not force and rec and st.get("path") == rec["path"] and now() - float(st.get("at") or 0) < card_seconds():
        return
    out = {"at": now()}
    if rec:
        out.update(path=rec["path"], title=title(rec["path"]), action=WORDS.get(bucket, bucket), percent=pct,
                   left=round(left) if left is not None else None, started=st.get("started") if st.get("path") == rec["path"] else now())
    else:
        out["reason"] = reason or ""
    save("now", out)  # only the card: not worth stopping for when the disk is full


def why_idle():
    s = _state()
    if s.get("paused"):
        return "Paused"
    if sbplugin.holding():
        return "Waiting for an update"
    if not profile():
        return "No devices chosen"
    if not in_hours():
        return {"weekends": "Waiting for the weekend", "quiet": "Waiting for quiet hours"}.get(options()["when"], "Waiting")
    if not s.get("surveyed"):
        return "Checking the library"
    return "Nothing left to do" if not todo_head()[0] else "Starting the next file"


def work_once():
    """One pass: survey when it is due, then fix files one at a time while the hours allow. Returns files fixed."""
    _pass.settings = sbplugin.settings()  # read once for the pass (see setting)
    try:
        if not flush_unsaved():
            raise NoRoom()
        return _work()
    finally:
        _pass.settings = None


def _work():
    if _survey_now.is_set():  # Look at the library now: at any hour, even while paused
        _survey_now.clear()
        status(reason="Checking the library")
        survey()
        library()
    s = _state()
    if s.get("paused") or not profile():
        status(reason=why_idle())
        return 0
    if not in_hours():
        status(reason=why_idle())
        return 0
    if now() - float(s.get("surveyed") or 0) > SURVEY_HOURS * 3600:
        status(reason="Checking the library")
        survey()
        library()
    fixed = 0
    while True:
        s = _state()
        if s.get("paused") or not in_hours() or sbplugin.holding():
            break
        prof, opts = profile(), options()
        left, head = todo_head()  # read again only when the survey, the state or the settings changed
        if not left:
            break
        rec = head[0]
        if not os.path.exists(rec["path"]):
            survey()
            continue
        with _as_they_change():
            try:
                err = fix(rec, rec["bucket"], prof, opts)
            except Stopped:
                break
            except Exception as e:  # noqa: BLE001
                if _no_room(e):  # not this file's fault: it is not marked as failed, and it is tried again when there is room
                    _rm(os.path.join(os.path.dirname(rec["path"]), f".{os.path.splitext(os.path.basename(rec['path']))[0]}.direct-play.mkv"))
                    raise NoRoom() from e
                err = f"error: {e}"[:200]
        s = _state()
        if err:
            s["failed"][rec["path"]] = {"why": err, "size": rec["size"], "mtime": rec["mtime"], "title": title(rec["path"]), "at": now()}
        else:
            dst = os.path.splitext(rec["path"])[0] + ".mkv"
            new = os.path.getsize(dst) if os.path.exists(dst) else rec["size"]
            s["done"] += 1
            s["saved_bytes"] += rec["size"] - new
            s["last"] = {"title": title(rec["path"]), "action": WORDS[rec["bucket"]], "before": rec["size"], "after": new, "at": now()}
            fixed += 1
            _refresh_one(rec["path"], dst)
        if not save("state", s, hold=True):
            raise NoRoom()  # the result is kept in memory; the next pass writes it down first, and no file is started before
    status(reason=why_idle())
    return fixed


def _refresh_one(old, new):
    """The survey's record of a fixed file is replaced by the new file's facts, so it is not done twice."""
    recs = [r for r in remember("survey", []) or [] if r["path"] not in (old, new)]
    if os.path.exists(new):
        recs.append(facts(new))
    save("survey", recs)  # the survey is worked out again from the files if this cannot be written


def note_error(e):
    """Keeps what went wrong for the page. On a full disk it cannot, and the worker must still be alive for when there is
    room again (it once ended here, and nothing was converted until the plug-in was restarted)."""
    if isinstance(e, NoRoom) or _no_room(e):
        text = "The disk is full, so it stopped before the next file. Free some space and it carries on by itself"
    else:
        text = f"{type(e).__name__}: {e}"[:200]
    save("_error", {"at": now(), "text": text})


def worker():
    time.sleep(float(os.environ.get("DIRECT_PLAY_FIRST", "20")))  # the smoke test starts it at once
    while True:
        try:
            work_once()
            sbplugin.clear_error()
        except Exception as e:  # noqa: BLE001 - kept for the page, never fatal
            note_error(e)
        _wake.wait(TICK)
        _wake.clear()


# What Starboard calls ------------------------------------------------------------------------------------------

def size_words(n):
    n = float(n or 0)
    for unit, by in (("TB", 1e12), ("GB", 1e9), ("MB", 1e6)):
        if abs(n) >= by:
            return f"{n / by:.2f} {unit}" if unit == "TB" else f"{n / by:.1f} {unit}"
    return f"{int(n):,} bytes"


def time_words(seconds):
    m = max(1, int(round(seconds / 60)))
    h, m = divmod(m, 60)
    return " ".join(([plural(h, "hour")] if h else []) + ([plural(m, "minute")] if m else []))


def totals():
    s = _state()
    return f"{plural(s['done'], 'file')} fixed, {size_words(s['saved_bytes'])} saved, {plural(todo_head()[0], 'file')} still to do"


def card():
    """The dashboard card: converting now, the next few, and the totals. It reads the status file and the survey's
    cached facts only: nothing is probed or asked for it."""
    st = remember("now", {}) or {}
    items = []
    converting = st.get("path") and _current["path"] == st.get("path")
    if converting:
        bits = [st.get("action") or ""]
        if st.get("percent") is not None:
            bits.append(f"{st['percent']}% done")
        if st.get("left"):
            bits.append(f"about {time_words(st['left'])} left")
        items.append({"title": f"Converting now: {st.get('title')}", "detail": ", ".join(b for b in bits if b)})
    else:
        reason = why_idle()
        items.append({"title": reason, "detail": "" if reason in ("Nothing left to do", "No devices chosen") and reason != "Paused" else
                      ("Resume it on the plug-in's page in Settings, Plug-ins" if reason == "Paused" else f"Next runs {next_run()}")})
        if reason == "No devices chosen":
            items[-1]["detail"] = "Choose your devices on the plug-in's page in Settings, Plug-ins"
        elif reason == "Nothing left to do":
            items[-1]["detail"] = "New films and series are checked " + ("when it next runs" if not in_hours() else "every few hours")
    nxt = [r for r in todo_head()[1] if r["path"] != st.get("path") or not converting][:4]
    items += [{"title": f"Next: {title(r['path'])}", "detail": WORDS[r["bucket"]]} for r in nxt]
    items.append({"title": "Totals", "detail": totals()})
    state = "converting" if converting else {"Paused": "paused", "Nothing left to do": "done", "No devices chosen": "needs_setup"}.get(items[0]["title"], "waiting")
    # The card band (plug-in API 1.14, DASH-428): the status chip and when the card last changed.
    return {"items": items, "refresh_seconds": card_seconds(), "status": state, "updated": int(min(float(st.get("at") or now()), now()))}


def summary_card():
    s = _state()
    left = todo_head()[0]
    answer = {"value": int(s["saved_bytes"]), "label": "saved", "note": f"{plural(s['done'], 'file')} fixed, {plural(left, 'file')} to do"}
    at = (s.get("last") or {}).get("at")
    if _current["path"]:
        return sbplugin.band(answer, "converting", at)
    if s.get("paused"):
        return sbplugin.band(answer, "paused", at)
    return sbplugin.band(answer, "done" if not left and s.get("surveyed") else "waiting", at)


GROUPS = {"now": "Converting now", "todo": "Still to do", "failed": "Not fixed", "done": "Fixed", "alone": "Left alone"}


def screen():
    """Files: the work in tables, read only, with the progress and the state as notices."""
    s, st = _state(), remember("now", {}) or {}
    prof, opts = profile(), options()
    todo = todo_list(prof=prof, opts=opts, state=s)
    items = []
    for i, r in enumerate(todo[:3000]):
        g = GROUPS["now"] if _current["path"] == r["path"] else GROUPS["todo"]
        items.append({"id": f"t{i}", "title": title(r["path"]), "group": g, "actions": [],
                      "cells": {"title": title(r["path"]), "file": os.path.basename(r["path"]), "needs": WORDS[r["bucket"]], "why": r["why"], "size": size_words(r["size"])}})
    for i, (p, f) in enumerate(sorted(s["failed"].items(), key=lambda kv: -float(kv[1].get("at") or 0))[:500]):
        items.append({"id": f"f{i}", "title": f.get("title") or os.path.basename(p), "group": GROUPS["failed"], "actions": [],
                      "cells": {"title": f.get("title") or "", "file": os.path.basename(p), "needs": "Not fixed", "why": f.get("why") or "", "size": size_words(f.get("size"))}})
    alone = [r for r in surveyed() if classify(r, prof, opts)[0] in ("hevc", "error")][:500]
    for i, r in enumerate(alone):
        b, why = classify(r, prof, opts)
        items.append({"id": f"a{i}", "title": title(r["path"]), "group": GROUPS["alone"], "actions": [],
                      "cells": {"title": title(r["path"]), "file": os.path.basename(r["path"]), "needs": "Left alone" if b == "hevc" else "Cannot read", "why": why, "size": size_words(r.get("size"))}})
    notices = []
    if _current["path"] and st.get("path") == _current["path"]:
        t = f"{st.get('action')}" + (f", about {time_words(st['left'])} left" if st.get("left") else "")
        notices.append({"id": "now", "tone": "info", "title": f"Converting {st.get('title')}", "text": t, "progress": int(st.get("percent") or 0)})
    else:
        reason = why_idle()
        notices.append({"id": "idle", "tone": "warning" if reason in ("Paused", "No devices chosen") else "info", "title": reason,
                        "text": ("Choose 'Resume fixing' in 'Actions' to carry on." if reason == "Paused" else
                                 "Choose your devices in 'Devices'." if reason == "No devices chosen" else f"Next runs {next_run()}.")})
    err = remember("_error")
    if isinstance(err, dict) and err.get("text"):
        notices.append({"id": "error", "tone": "danger", "title": "The last pass did not finish", "text": err["text"][:300], "dismiss": True})
    last = s.get("last")
    intro = totals() + "." + (f" Last file: {last['title']}, {last['action'].lower()}, {size_words(last['before'])} to {size_words(last['after'])}." if last else "")
    return {"type": "list", "title": "Files", "layout": "folds", "readonly": True, "intro": intro[:400],
            "columns": [{"key": "title", "label": "Title"}, {"key": "needs", "label": "What it needs"}, {"key": "why", "label": "Why"},
                        {"key": "size", "label": "Size"}, {"key": "file", "label": "File"}],
            "filters": [{"key": "needs", "label": "What it needs"}], "notices": notices, "items": items}


def screen_post(body=None):
    if (body or {}).get("action") == "dismiss":
        save("_error", None)
    return screen()


def pause():
    s = _state()
    s["paused"] = True
    save("state", s, hold=True)
    with _lock:
        p = _current["proc"]
    if p:
        p.terminate()  # its unfinished copy is removed, and the file is done again later
    status(reason="Paused")
    return {"said": "Paused. The file being converted was stopped and is done again later"}


def resume():
    s = _state()
    s["paused"] = False
    save("state", s, hold=True)
    _wake.set()
    return {"said": "Resumed. It carries on " + ("now" if in_hours() else next_run())}


def before_update(body=None):
    """POST /update/before (plug-in API 1.14): no new file starts, and the file being converted is stopped; its
    unfinished copy is removed and it is converted again after the update, as Pause does."""
    sbplugin._work["hold"] = now() + sbplugin.HOLD_SECONDS
    with _lock:
        p, name = _current["proc"], _current["path"]
    if p:
        p.terminate()
    for _ in range(60):  # up to 30 seconds for the worker to tidy up
        if not _current["path"]:
            break
        time.sleep(0.5)
    if _current["path"]:
        sbplugin._work["hold"] = 0.0
        return {"ok": False, "said": "A file is still being converted. Try again in a minute"}
    status(reason="Waiting for an update")
    return {"ok": True, "said": f"Stopped converting {title(name)}; it is converted again after the update" if name else "Ready to update: nothing was being converted"}


def after_update(body=None):
    """POST /update/after: carries on, after the update or a Roll back."""
    sbplugin._work["hold"] = 0.0
    _wake.set()
    return {"ok": True, "said": "Carrying on " + ("now" if in_hours() else next_run())}


def survey_now():
    _survey_now.set()
    _wake.set()
    return {"said": "Checking the library. Only new or changed files are read"}


ROUTES = {"/card": card, "/summary": summary_card, "/files": screen, ("POST", "/files"): screen_post,
          ("POST", "/pause"): pause, ("POST", "/resume"): resume, ("POST", "/survey"): survey_now, ("POST", "/jobs/quiet"): quiet_job,
          ("POST", "/update/before"): before_update, ("POST", "/update/after"): after_update}

if __name__ == "__main__":
    threading.Thread(target=worker, daemon=True).start()
    serve(ROUTES)
