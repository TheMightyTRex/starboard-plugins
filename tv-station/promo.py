"""Promos: short trailers for programmes coming up, made in quiet hours from the channel's broadcast pack.

Each promo is the pack's promo background (or, from 0.2.0, the channel's colour when it has music but no pack promo),
a few short clips of the programme playing in its clip area, a music bed chosen at random from the music uploaded on
the plug-in's pages and the pack's promo/music, and the words in its fields: Coming soon, the title, the episode, the day and time
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
FRACTIONS = (0.2, 0.42, 0.64)  # where the clips are taken from, clear of the opening titles and the end credits
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


def command(p, airing, channel_name, music, W, H, jf_url, jf_key, texts, out, seed=0):
    """The FFmpeg command for one promo, written to `out` (an MP4)."""
    lay = p["promo"]
    seconds = max(10, min(30, int(lay.get("seconds") or 15)))
    sx, sy = W / pack.W, H / pack.H
    x0, y0, x1, y1 = lay["clip"]
    cx, cy, cw, ch = int(x0 * sx), int(y0 * sy), int((x1 - x0) * sx) // 2 * 2, int((y1 - y0) * sy) // 2 * 2
    bg = os.path.join(p["folder"], lay["background"]) if lay.get("background") else None
    # One thread everywhere, for each input's decoder and for the encoder: lowest priority, and well inside the
    # container's limit on threads (an FFmpeg left to choose starts a dozen or more for each input).
    one = ["-threads", "1"]
    args = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-filter_threads", "1", "-filter_complex_threads", "1"]
    if bg:
        args += one + (["-loop", "1", "-framerate", str(pack.FPS)] if lay.get("still") else ["-stream_loop", "-1"]) + ["-t", str(seconds), "-i", bg]
    else:  # a plain promo (0.2.0): the channel's colour, drawn by FFmpeg, for a channel with music but no pack promo
        args += ["-f", "lavfi", "-t", str(seconds), "-i", f"color=c={lay.get('colour') or '0x1f5f99'}:s={W}x{H}:r={pack.FPS}"]
    e = airing["entry"]
    dur = float(e.get("dur") or 1800)
    each = (seconds - 2.0) / len(FRACTIONS)
    for f in FRACTIONS:
        args += one + ["-ss", f"{dur * f:.2f}", "-t", f"{each + 0.5:.2f}", "-headers", f'Authorization: MediaBrowser Token="{jf_key}"\r\n',
                 "-i", f"{jf_url.rstrip('/')}/Videos/{e['id']}/stream?static=true"]
    n = 1 + len(FRACTIONS)
    if music:
        args += ["-stream_loop", "-1", "-t", str(seconds), "-i", music["file"]]
    else:
        args += ["-f", "lavfi", "-t", str(seconds), "-i", "anullsrc=r=48000:cl=stereo"]
    parts = [f"[0:v]scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={pack.FPS},format=yuv420p[bg]"]
    for i in range(len(FRACTIONS)):
        parts.append(f"[{i + 1}:v]scale={cw}:{ch}:force_original_aspect_ratio=increase,crop={cw}:{ch},setsar=1,fps={pack.FPS},"
                     f"format=yuv420p,trim=duration={each:.2f},setpts=PTS-STARTPTS[c{i}]")
    parts.append("".join(f"[c{i}]" for i in range(len(FRACTIONS))) + f"concat=n={len(FRACTIONS)}:v=1:a=0,setpts=PTS-STARTPTS+1/TB[clips]")
    said = words(airing, channel_name)
    chain = []
    for name, style in (lay.get("fields") or {}).items():
        if said.get(name):
            chain += dog.box_text(texts, said[name], style, sx, sy)
    chain += [f"fade=t=in:st=0:d=0.4", f"fade=t=out:st={seconds - 0.5}:d=0.5"]
    parts.append(f"[bg][clips]overlay=x={cx}:y={cy}:eof_action=pass," + ",".join(chain) + "[v]")
    gain = float((music or {}).get("gain") or 0)
    parts.append(f"[{n}:a]volume={gain:+.1f}dB,afade=t=in:st=0:d=0.5,afade=t=out:st={seconds - 1.5}:d=1.5,aresample=48000[a]")
    args += ["-filter_complex", ";".join(parts), "-map", "[v]", "-map", "[a]", "-t", str(seconds), "-threads", "1",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", "-g", str(pack.FPS * 2),
             "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart", "-f", "mp4", out]
    return args, seconds


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
