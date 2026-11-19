"""Promos: short trailers for programmes coming up, made in quiet hours from the channel's broadcast pack.

Each promo is a background loop (the pack's promo background, or one uploaded on the plug-in's pages, chosen at
random; or, from 0.2.0, the channel's colour when it has neither), a few short clips of the programme playing in its
clip area with the programme's own sound (0.3.0), a music bed chosen at random from the music uploaded on the plug-in's
pages and the pack's promo/music, at about a fifth of its level under the programme's sound, and the words in its fields: Coming soon, the title, the episode, the day and time
from the schedule ("Sunday at 21:00", true all week) and the channel's name. They are made one at a time, by one
FFmpeg at the lowest priority with one thread, and never while anyone is watching. Each channel keeps a set number;
a promo is replaced when it is older than the setting says, and dropped before its programme starts, so they never
pile up. Each is played in the breaks like a clip: on its own channel, and on the others unless that is deactivated.
"""
import os
import secrets
import subprocess
import threading
import time

import dog
import pack
import schedule
from guide import episode_words, is_new

LEAD = 2 * 3600  # never for a programme starting in under 2 hours; dropped then
HORIZON = 6 * 86400  # "Sunday at 21:00" is true for 6 days
FRACTIONS = (0.2, 0.42, 0.64)  # where the clips were taken from before 0.3.0
SPREAD = (0.12, 0.78)  # clips come from this part of a programme, clear of the opening titles and the end credits
SHORTEST, LONGEST = 10, 60  # seconds a promo may be (0.3.0: the setting Promo length; 10 to 30 before)
LEAD_IN = 1.0  # seconds of background and music before the first clip, and after the last
RAMP = 0.4  # seconds the music takes to fall under the programme's sound, and to rise again
_proc = {"p": None}
_stop = threading.Event()


def group_of(entry):
    return str(entry.get("group") or entry.get("id"))


def plan(channels, existing, keep, replace_days, now):
    """What to remove and what to make. Pure, so it can be tested.

    channels: [{"id", "sched": schedule.Channel, "can": True when its pack has a promo}]
    existing: the promos kept, each {"id", "cid", "group", "airs", "made"}
    keep:     how many each channel keeps
    Returns (remove, make): promos to remove, and [{"cid", "airing"}] to make, soonest first.
    """
    keep = max(1, int(keep))
    can = {c["id"]: c for c in channels if c.get("can")}
    remove, kept = [], {}
    for p in sorted(existing, key=lambda p: -float(p.get("made") or 0)):
        old = float(p.get("made") or 0) < now - float(replace_days) * 86400
        if p.get("cid") not in can or float(p.get("airs") or 0) < now + LEAD or old:
            remove.append(p)
            continue
        mine = kept.setdefault(p["cid"], [])
        if len(mine) >= keep:  # never more than the setting: the oldest go
            remove.append(p)
        else:
            mine.append(p)
    make = []
    for cid, c in can.items():
        need = keep - len(kept.get(cid, []))
        if need <= 0:
            continue
        have = {p.get("group") for p in kept.get(cid, [])}
        seen, options = set(), []
        for a in c["sched"].airings(now + LEAD, now + HORIZON, limit=400):
            g = group_of(a["entry"])
            if a["start"] < now + LEAD or g in have or g in seen:
                continue
            seen.add(g)
            options.append(a)
        # New episodes first, then the soonest.
        options.sort(key=lambda a: (not is_new(a["entry"], a["start"]), a["start"]))
        make += [{"cid": cid, "airing": a} for a in options[:need]]
    make.sort(key=lambda m: m["airing"]["start"])
    return remove, make


def words(airing, channel_name):
    e = airing["entry"]
    return {"Heading": "Coming soon", "Title": e.get("title") or "Programme", "Episode": episode_words(e),
            "Day and time": dog.day_time_words(airing["start"]), "Synopsis": (e.get("plot") or "")[:240], "Channel name": channel_name}


def clip_count(seconds, wanted=None):
    """How many clips a promo shows: the setting when given (2 to 6), else about one for every 5 seconds."""
    if wanted:
        return max(2, min(6, int(wanted)))
    return max(2, min(6, round((seconds - 2 * LEAD_IN) / 5)))


def clip_starts(dur, n, seed=0):
    """Where each clip starts, as seconds into a programme of `dur` seconds: n spread evenly over SPREAD, each moved a
    little either way by the seed, so two promos for one programme seldom show the same moments."""
    rng = schedule.Rng(seed)
    a, b = SPREAD
    step = (b - a) / max(1, n)
    return [dur * (a + step * (i + 0.15 + 0.7 * rng.below(1000) / 1000)) for i in range(n)]


def music_level(level):
    """The setting Music under the programme's sound, as a share of full: 0.05 to 1, 0.2 unless chosen."""
    try:
        v = float(level)
    except (TypeError, ValueError):
        return 0.2
    v = v / 100 if v > 1 else v
    return max(0.05, min(1.0, v)) if v > 0 else 0.2


def duck(level, start, end):
    """A volume expression of t: full before `start`, falling to `level` over RAMP seconds, rising again at `end`."""
    a, b = start - RAMP, end + RAMP
    return f"1-{1 - level:.3f}*clip(min((t-{a:.2f})/{RAMP},({b:.2f}-t)/{RAMP}),0,1)"


def command(p, airing, channel_name, music, W, H, jf_url, jf_key, texts, out, seed=0, seconds=None, background=None,
            level=0.2, clips=None, clip_sound=True):
    """The FFmpeg command for one promo, written to `out` (an MP4).

    seconds:    the setting Promo length (0.3.0), else the pack's own, else 15; 10 to 60
    background: an uploaded background loop to use in place of the pack's, {"file", "still"} (0.3.0)
    level:      the music's share of full while the programme's sound plays (0.3.0)
    clips:      how many clips, else one for about every 5 seconds
    clip_sound: the programme's sound under its clips (0.3.0); False for a programme with none
    """
    lay = p["promo"]
    seconds = max(SHORTEST, min(LONGEST, int(seconds or lay.get("seconds") or 15)))
    sx, sy = W / pack.W, H / pack.H
    x0, y0, x1, y1 = lay["clip"]
    cx, cy, cw, ch = int(x0 * sx), int(y0 * sy), int((x1 - x0) * sx) // 2 * 2, int((y1 - y0) * sy) // 2 * 2
    bg = os.path.join(p["folder"], lay["background"]) if lay.get("background") else None
    still = lay.get("still")
    if background and background.get("file"):
        bg, still = background["file"], bool(background.get("still"))
    # One thread everywhere, for each input's decoder and for the encoder: lowest priority, and well inside the
    # container's limit on threads (an FFmpeg left to choose starts a dozen or more for each input).
    one = ["-threads", "1"]
    args = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-filter_threads", "1", "-filter_complex_threads", "1"]
    if bg:
        args += one + (["-loop", "1", "-framerate", str(pack.FPS)] if still else ["-stream_loop", "-1"]) + ["-t", str(seconds), "-i", bg]
    else:  # a plain promo (0.2.0): the channel's colour, drawn by FFmpeg, for a channel with music but no pack promo
        args += ["-f", "lavfi", "-t", str(seconds), "-i", f"color=c={lay.get('colour') or '0x1f5f99'}:s={W}x{H}:r={pack.FPS}"]
    e = airing["entry"]
    dur = float(e.get("dur") or 1800)
    n_clips = clip_count(seconds, clips)
    each = (seconds - 2 * LEAD_IN) / n_clips
    for start in clip_starts(dur, n_clips, seed):
        args += one + ["-ss", f"{start:.2f}", "-t", f"{each + 0.5:.2f}", "-headers", f'Authorization: MediaBrowser Token="{jf_key}"\r\n',
                 "-i", f"{jf_url.rstrip('/')}/Videos/{e['id']}/stream?static=true"]
    n = 1 + n_clips
    if music:
        args += ["-stream_loop", "-1", "-t", str(seconds), "-i", music["file"]]
    else:
        args += ["-f", "lavfi", "-t", str(seconds), "-i", "anullsrc=r=48000:cl=stereo"]
    parts = [f"[0:v]scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={pack.FPS},format=yuv420p[bg]"]
    for i in range(n_clips):
        parts.append(f"[{i + 1}:v]scale={cw}:{ch}:force_original_aspect_ratio=increase,crop={cw}:{ch},setsar=1,fps={pack.FPS},"
                     f"format=yuv420p,trim=duration={each:.2f},setpts=PTS-STARTPTS[c{i}]")
    parts.append("".join(f"[c{i}]" for i in range(n_clips)) + f"concat=n={n_clips}:v=1:a=0,setpts=PTS-STARTPTS+{LEAD_IN}/TB[clips]")
    said = words(airing, channel_name)
    chain = []
    for name, style in (lay.get("fields") or {}).items():
        if said.get(name):
            chain += dog.box_text(texts, said[name], style, sx, sy)
    chain += [f"fade=t=in:st=0:d=0.4", f"fade=t=out:st={seconds - 0.5}:d=0.5"]
    parts.append(f"[bg][clips]overlay=x={cx}:y={cy}:eof_action=pass," + ",".join(chain) + "[v]")
    gain = float((music or {}).get("gain") or 0)
    stereo = "aresample=48000,aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo"
    bed = f"[{n}:a]{stereo},volume={gain:+.1f}dB"
    if clip_sound:
        # The programme's sound for each clip, faded in and out a little so the joins do not click, brought to -23 LUFS
        # like the music, and laid under the clips; the music falls to `level` while it plays (0.3.0).
        for i in range(n_clips):
            parts.append(f"[{i + 1}:a]{stereo},atrim=duration={each:.2f},asetpts=PTS-STARTPTS,"
                         f"afade=t=in:st=0:d=0.12,afade=t=out:st={max(0.0, each - 0.15):.2f}:d=0.15[s{i}]")
        delay = int(LEAD_IN * 1000)
        parts.append("".join(f"[s{i}]" for i in range(n_clips)) + f"concat=n={n_clips}:v=0:a=1,loudnorm=I=-23:TP=-2:LRA=11,aresample=48000,adelay={delay}|{delay},apad[prog]")
        lvl = music_level(level)
        parts.append(f"{bed},volume=eval=frame:volume='{duck(lvl, LEAD_IN, LEAD_IN + n_clips * each)}'[bed]")
        parts.append("[bed][prog]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,"
                     f"alimiter=limit=0.95,afade=t=in:st=0:d=0.5,afade=t=out:st={seconds - 1.5}:d=1.5[a]")
    else:
        parts.append(f"{bed},afade=t=in:st=0:d=0.5,afade=t=out:st={seconds - 1.5}:d=1.5[a]")
    args += ["-filter_complex", ";".join(parts), "-map", "[v]", "-map", "[a]", "-t", str(seconds), "-threads", "1",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", "-g", str(pack.FPS * 2),
             "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart", "-f", "mp4", out]
    return args, seconds


def pick_background(pool, seed):
    """One background loop from the pool, each {"file", "still"}: the same one for the same promo. None is the pack's."""
    return pool[schedule.Rng(seed).below(len(pool))] if pool else None


def pick_music(pool, seed):
    """One music bed from the pool, each {"file", "gain"}: the same one for the same promo."""
    return pool[schedule.Rng(seed).below(len(pool))] if pool else None


def music_pool(pack_music, folder, own, station, use="both"):
    """The music a promo chooses from (0.2.0). pack_music: the pack's beds ({"path", "gain"} in `folder`); own and
    station: music the owner uploaded for the channel and for every channel ({"file", "gain"}, files that exist).
    use: both (the uploaded music and the pack's), mine (uploaded only, the pack's when there is none) or pack (the
    pack's only, the uploaded when the pack has none). A channel's own music comes before the station's."""
    from_pack = [{"file": os.path.join(folder, m["path"]), "gain": float(m.get("gain") or 0)} for m in pack_music or []]
    mine = list(own or []) or list(station or [])
    if use == "pack":
        return from_pack or mine
    if use == "mine":
        return mine or from_pack
    return mine + from_pack


def plain_pack(colour):
    """A promo design with no broadcast pack (0.2.0): the default layout on the channel's colour, its words in white."""
    lay = pack.DEFAULT_LAYOUT["promo"]
    fields = {name: {"box": box, "colour": "#FFFFFF", "lines": pack.LINES.get(name, 1)} for name, box in lay["fields"].items()}
    return {"name": "Plain", "folder": "", "music": [],
            "promo": {"background": None, "clip": lay["clip"], "seconds": lay["seconds"], "fields": fields, "colour": colour or "0x1f5f99"}}


def _nice():
    try:
        os.nice(19)
    except OSError:
        pass


def run(argv, limit=600):
    """Runs one promo's FFmpeg at the lowest priority. False when it failed or was stopped (someone began watching)."""
    _stop.clear()
    try:
        proc = subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, preexec_fn=_nice)
    except OSError:
        return False, "FFmpeg could not start"
    _proc["p"] = proc
    began = time.monotonic()
    try:
        while proc.poll() is None:
            if _stop.wait(0.5) or time.monotonic() - began > limit:
                proc.kill()
                proc.wait()
                return False, "Stopped: someone began watching" if _stop.is_set() else "Took too long"
        err = proc.stderr.read(2000).decode("utf-8", "replace").strip() if proc.stderr else ""
        return proc.returncode == 0, (err.splitlines() or [""])[-1][:200]
    finally:
        _proc["p"] = None
        if proc.stderr:
            proc.stderr.close()


def stop():
    """Stops a promo being made, at once: a channel is about to play."""
    _stop.set()
    p = _proc["p"]
    if p and p.poll() is None:
        p.kill()


def new_id():
    return secrets.token_hex(5)
