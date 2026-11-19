"""The stream: nothing plays until someone chooses a channel. The first viewer starts one FFmpeg for that channel, at
the point the schedule says (part way through a programme when that is what is on); everyone else watching that
channel shares the same stream; it stops shortly after the last viewer leaves.

Each piece of the schedule (a programme, an ident, a trailer, a card) is one FFmpeg run, writing MPEG-TS at real
time; their timestamps carry on from one to the next, so the player sees one stream.
"""
import os
import queue
import shutil
import subprocess
import threading
import time

import dog
from guide import episode_words, is_new

CHUNK = 188 * 348  # whole MPEG-TS packets, about 64 KB
VIEWER_QUEUE = 96  # chunks held for a slow viewer (about 6 MB) before it is let go
FPS = 25
SIZES = {"720": (1280, 720, 3000), "1080": (1920, 1080, 6000)}  # width, height, video kilobits a second
FAIL_PAUSE = 20  # a piece that fails is replaced by a slate for at most this long, then the next piece is tried
AHEAD = 8  # the stream may run this many seconds ahead of the clock (FFmpeg's first burst); never more
SHORTEST = 0.4  # what is left of a piece shorter than this is passed over, not started


def jellyfin_input(base, key, item_id):
    return ["-headers", f'Authorization: MediaBrowser Token="{key}"\r\n', "-i",
            f"{base.rstrip('/')}/Videos/{item_id}/stream?static=true"]


def output_args(W, H, kbps, ts_offset, duration, copy=False):
    if copy:
        video = ["-c:v", "copy"]
    else:
        video = ["-c:v", "libx264", "-preset", "veryfast", "-profile:v", "high", "-pix_fmt", "yuv420p", "-g", str(FPS * 2),
                 "-keyint_min", str(FPS), "-sc_threshold", "0", "-b:v", f"{kbps}k", "-maxrate", f"{int(kbps * 1.2)}k",
                 "-bufsize", f"{kbps * 2}k", "-threads", "3"]
    return video + ["-c:a", "aac", "-b:a", "160k", "-ac", "2", "-ar", "48000", "-t", f"{max(0.5, duration):.3f}",
                    "-output_ts_offset", f"{ts_offset:.3f}", "-f", "mpegts", "-pat_period", "0.5", "-mpegts_flags", "+resend_headers",
                    "pipe:1"]


def _pack_input(path, still, pace, most):
    """A pack's background, looped, and never longer than the piece: no input here is ever endless."""
    if still:
        return pace + ["-loop", "1", "-framerate", str(FPS), "-t", f"{most:.3f}", "-i", path]
    return pace + ["-stream_loop", "-1", "-t", f"{most:.3f}", "-i", path]


def _transition_input(tr, start, pace):
    """A transition's input: decoded with libvpx when it is VP9, which is what keeps its transparency."""
    dec = ["-c:v", "libvpx-vp9"] if tr.get("codec") == "vp9" else []
    return pace + (["-ss", f"{start:.3f}"] if start > 0 else []) + dec + ["-i", tr["file"]]


def piece_command(piece, now, ctx):
    """The FFmpeg command for what is left of one piece at `now`.

    A holding piece has "holding": {"file", "still", "words", "has_audio"} and "airing", the next programme.
    ctx: {"W", "H", "kbps", "opts", "names", "logo", "jf_url", "jf_key", "ts_offset", "texts", "clip_path", "art",
          "colour", "next_words", "start_words", "layout", "trans_in", "trans_out"}
    layout:    a broadcast pack's Coming up next layout, with "file" its background, for cards
    trans_in:  a pack's transition, {"file", "dur", "codec"}: its second half plays over the start of this piece
    trans_out: the same, its first half over the end; the piece then has "tail_from", where its last half starts
    """
    W, H = ctx["W"], ctx["H"]
    opts = ctx["opts"]
    still = bool(ctx.get("still"))
    into = max(0.0, now - piece["start"])
    left = piece["end"] - now
    kind = piece["kind"]
    # Two decoder threads for each input: FFmpeg left to choose starts one for each processor it can find, and the
    # container has a limit on threads (a programme, a background, a picture and a transition at once).
    pace = ([] if still else ["-re", "-readrate_initial_burst", "2"]) + ["-threads", "2"]
    # Few threads: Starboard's containers have a limit on processes and threads, and the plug-in has 2 cores.
    args = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-filter_threads", "2", "-filter_complex_threads", "2"]
    audio_from = None
    audio_gain = 0.0
    programme = None
    rel = 0.0
    layout = ctx.get("layout") if kind == "card" else None
    most = max(0.5, left) + 1.0  # every looped or made-up input stops a second after the piece
    if kind == "programme":
        e = piece["airing"]["entry"]
        rel = into
        args += pace + ["-ss", f"{into:.3f}"] + jellyfin_input(ctx["jf_url"], ctx["jf_key"], e["id"])
        if e.get("has_audio", True):
            audio_from = f"0:{e['audio']}" if e.get("audio") is not None else "0:a:0"
        label = ""
        if opts["label"] == "live":
            label = "Live"
        elif opts["label"] == "new_repeat":
            label = "New" if is_new(e, piece["start"]) else "Repeat"
        programme = {"duration": piece["airing"]["content_end"] - piece["start"], "label": label,
                     "start_words": ctx.get("start_words") or f"{e.get('title')}" + (f": {episode_words(e)}" if episode_words(e) else ""),
                     "next_words": ctx.get("next_words")}
    elif kind == "clip":
        c = piece["clip"]
        src = c["src"]
        seek = ["-ss", f"{into:.3f}"] if into > 0.05 or still else []
        if src.startswith("jf:"):
            args += pace + seek + jellyfin_input(ctx["jf_url"], ctx["jf_key"], src[3:])
        else:
            args += pace + seek + ["-i", ctx["clip_path"](src)]
        if c.get("has_audio", True):
            audio_from = f"0:{c['audio']}" if c.get("audio") is not None else "0:a:0"
            audio_gain = float(c.get("gain") or 0)
    elif kind == "holding":
        h = piece["holding"]
        args += _pack_input(h["file"], h.get("still"), pace, most)
        if h.get("has_audio") and not h.get("still"):
            audio_from = "0:a:0"
            audio_gain = float(h.get("gain") or 0)
    elif layout:
        args += _pack_input(layout["file"], layout.get("still"), pace, most)
    elif kind == "card" and ctx.get("art"):
        args += pace + ["-loop", "1", "-framerate", str(FPS), "-t", f"{most:.3f}", "-headers", f'Authorization: MediaBrowser Token="{ctx["jf_key"]}"\r\n',
                        "-i", ctx["art"]]
    else:
        args += pace + ["-f", "lavfi", "-t", f"{most:.3f}", "-i", f"color=c=0x14202e:s={W}x{H}:r={FPS}"]
    n_inputs = 1
    if audio_from is None:
        args += ([] if still else ["-re"]) + ["-f", "lavfi", "-t", f"{most:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
        audio_from = f"{n_inputs}:a"
        n_inputs += 1
    trans_in, trans_out = ctx.get("trans_in"), ctx.get("trans_out")
    copy = (kind == "programme" and ctx.get("copy_ok") and dog.needs_encoding(opts) and not still and not trans_in and not trans_out)
    if copy:
        args += ["-map", "0:v:0", "-map", audio_from]
        return args + output_args(W, H, ctx["kbps"], ctx["ts_offset"], left, copy=True)
    pre = []
    if layout:
        base = f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={FPS},format=yuv420p"
        sx, sy = W / 1920, H / 1080
        x0, y0, x1, y1 = layout["clip"]
        cw, ch = int((x1 - x0) * sx) // 2 * 2, int((y1 - y0) * sy) // 2 * 2
        if ctx.get("art"):
            args += pace + ["-loop", "1", "-framerate", str(FPS), "-t", f"{most:.3f}", "-headers",
                            f'Authorization: MediaBrowser Token="{ctx["jf_key"]}"\r\n', "-i", ctx["art"]]
            pre.append(f"[{n_inputs}:v]scale={cw}:{ch}:force_original_aspect_ratio=increase,crop={cw}:{ch},setsar=1,format=yuv420p[art]")
            base += f"[bgc];[bgc][art]overlay=x={int(x0 * sx)}:y={int(y0 * sy)}:eof_action=repeat"
            n_inputs += 1
        a = piece["airing"]["entry"]
        said = {"Heading": "Coming up next" if piece.get("card") == "next" else f"Later on {ctx['names']['channel']}",
                "Title": a.get("title") or "Programme", "Episode": episode_words(a), "Day and time": dog.when_words(piece["airing"]["start"], now),
                "Synopsis": a.get("plot") or "", "Channel name": ctx["names"]["channel"]}
        chain = []
        for name, style in (layout.get("fields") or {}).items():
            if said.get(name):
                chain += dog.box_text(ctx["texts"], said[name], style, sx, sy)
    elif kind == "card":
        base = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1,fps={FPS},format=yuv420p"
        a = piece["airing"]["entry"]
        card = {"kicker": "Coming up next" if piece.get("card") == "next" else f"Later on {ctx['names']['channel']}",
                "title": a.get("title") or "Programme", "episode": episode_words(a), "when": dog.when_words(piece["airing"]["start"], now),
                "plot": a.get("plot") or "", "footer": f"{ctx['names']['station']}  ·  {ctx['names']['channel']}"}
        chain = dog.card_chain(W, H, ctx["texts"], card, ctx.get("colour") or "0x1f5f99")
    elif kind == "holding":
        # A holding slide (0.2.0): the picture or short video looped until the next programme, with Back soon or a
        # countdown to it, worked out from what is left of the piece, so it reaches 0:00 as the programme starts.
        base = (f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black,"
                f"setsar=1,fps={FPS},format=yuv420p")
        nxt = (piece.get("airing") or {}).get("entry") or {}
        title = (nxt.get("title") or "") + (f": {episode_words(nxt)}" if episode_words(nxt) else "")
        chain = dog.holding_chain(W, H, ctx["texts"], piece["holding"].get("words") or "countdown", title, left)
    elif kind == "slate":
        base = "setsar=1,format=yuv420p"
        chain = dog.slate_chain(W, H, ctx["texts"], f"{ctx['names']['station']}  ·  {ctx['names']['channel']}")
    else:
        base = (f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black,"
                f"setsar=1,fps={FPS},format=yuv420p")
        chain = []
    extra, logo_f = dog.overlay_chain(opts, W, H, kind, ctx["texts"], ctx["names"], logo=ctx.get("logo"), rel=rel, programme=programme)
    chain = chain + extra
    graph = ";".join(pre + [f"[0:v]{base}" + ("," + ",".join(chain) if chain else "")])
    if logo_f:
        args += ["-loop", "1", "-t", f"{most:.3f}", "-i", ctx["logo"]]
        x, y = dog.logo_position(opts, W, H)
        graph += f"[b];[{n_inputs}:v]{logo_f}[lg];[b][lg]overlay=x={x}:y={y}:shortest=1:format=auto[v0]"
        n_inputs += 1
    else:
        graph += "[v0]"
    out = "v0"
    # Transitions: paced like the piece, so their few frames are never held waiting. The cut is at their middle.
    if trans_in and not still and into < trans_in["dur"] / 2:
        args += _transition_input(trans_in, trans_in["dur"] / 2 + into, pace)
        graph += (f";[{n_inputs}:v]scale={W}:{H},setsar=1,fps={FPS},format=yuva420p,setpts=PTS-STARTPTS[ti]"
                  f";[{out}][ti]overlay=eof_action=pass:format=auto[v1]")
        out, n_inputs = "v1", n_inputs + 1
    if trans_out and not still and piece.get("tail_from") is not None:
        half = trans_out["dur"] / 2
        late = max(0.0, now - piece["tail_from"])
        if late < half:
            args += _transition_input(trans_out, late, pace)
            graph += (f";[{n_inputs}:v]scale={W}:{H},setsar=1,fps={FPS},format=yuva420p,trim=duration={half - late:.3f},setpts=PTS-STARTPTS[to]"
                      f";[{out}][to]overlay=eof_action=pass:format=auto[v2]")
            out, n_inputs = "v2", n_inputs + 1
    if still:
        return args + ["-filter_complex", graph, "-map", f"[{out}]", "-frames:v", "1", "-c:v", "png", "-f", "image2", "pipe:1"]
    args += ["-filter_complex", graph, "-map", f"[{out}]", "-map", audio_from]
    if audio_gain:
        args += ["-af", f"volume={audio_gain:+.1f}dB"]
    return args + output_args(W, H, ctx["kbps"], ctx["ts_offset"], left)


class Busy(Exception):
    pass


class Hub:
    """One channel being watched: one FFmpeg at a time, its output shared by every viewer."""

    def __init__(self, cid, plan, grace, on_stop):
        self.cid = cid
        self.plan = plan  # plan(now) -> (piece, ctx) for what is on now
        self.grace = grace
        self.on_stop = on_stop
        self.viewers = set()
        self.lock = threading.Lock()
        self.alone_since = None
        self.started = time.time()
        self.proc = None
        self.stopping = False
        self.pieces_played = 0
        self.last_error = ""
        self.thread = threading.Thread(target=self._run, name=f"channel-{cid}", daemon=True)
        self.thread.start()

    def join(self):
        q = queue.Queue(VIEWER_QUEUE)
        with self.lock:
            self.viewers.add(q)
            self.alone_since = None
        return q

    def leave(self, q):
        with self.lock:
            self.viewers.discard(q)
            if not self.viewers:
                self.alone_since = time.monotonic()

    def idle_for(self):
        with self.lock:
            return 0.0 if self.viewers or self.alone_since is None else time.monotonic() - self.alone_since

    def stop(self):
        self.stopping = True
        p = self.proc
        if p and p.poll() is None:
            p.kill()

    def _broadcast(self, chunk):
        with self.lock:
            gone = []
            for q in self.viewers:
                try:
                    q.put_nowait(chunk)
                except queue.Full:
                    gone.append(q)
            for q in gone:  # a viewer too slow to keep up is let go, so it cannot hold the others back
                self.viewers.discard(q)
                try:
                    q.put_nowait(None)
                except queue.Full:
                    pass
            if gone and not self.viewers:
                self.alone_since = time.monotonic()

    def _run(self):
        try:
            cursor = 0.0  # how far through the schedule the stream has been sent, which runs a little ahead of the clock
            while not self.stopping:
                now = time.time()
                if abs(cursor - now) < AHEAD:
                    # Carry on from the end of what was sent: nothing is sent twice (FFmpeg's first burst runs ahead) and
                    # nothing is passed over (a piece that takes a moment to start runs behind). Further out, the clock wins.
                    now = cursor
                piece, ctx, cleanup = self.plan(now, self.started)
                if piece is None:
                    break
                if piece["end"] - now < SHORTEST:
                    cursor = piece["end"]
                    if cleanup:
                        cleanup()
                    if cursor > time.time() + AHEAD:
                        time.sleep(0.2)
                    continue
                argv = piece_command(piece, now, ctx)
                began = time.monotonic()
                ok = self._play(argv)
                if cleanup:
                    cleanup()
                self.pieces_played += 1
                cursor = piece["end"] if ok else time.time()
                if self.stopping:
                    break
                if not ok and time.monotonic() - began < 2 and piece["end"] - time.time() > 1:
                    # The piece would not play (a file gone, Jellyfin not answering): a slate instead, then try again.
                    slate = {"kind": "slate", "start": time.time(), "end": min(piece["end"], time.time() + FAIL_PAUSE)}
                    _, ctx2, cleanup2 = self.plan(time.time(), self.started, piece=slate)
                    self._play(piece_command(slate, time.time(), ctx2))
                    if cleanup2:
                        cleanup2()
        finally:
            with self.lock:
                for q in self.viewers:
                    try:
                        q.put_nowait(None)
                    except queue.Full:
                        pass
                self.viewers.clear()
            self.on_stop(self)

    def _play(self, argv):
        try:
            self.proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL)
        except OSError:
            return False
        fd = self.proc.stdout.fileno()
        held = b""
        try:
            while not self.stopping:
                got = os.read(fd, CHUNK)
                if not got:
                    break
                held += got
                whole = len(held) - len(held) % 188
                if whole >= CHUNK or (whole and len(got) < CHUNK):
                    self._broadcast(held[:whole])
                    held = held[whole:]
                if self.idle_for() > self.grace:
                    self.stopping = True
        finally:
            if self.proc.poll() is None:
                self.proc.kill()
            err = self.proc.stderr.read(2000) if self.proc.stderr else b""
            rc = self.proc.wait()
            self.proc.stdout.close()
            if self.proc.stderr:
                self.proc.stderr.close()
        if rc not in (0, -9) and err:
            self.last_error = err.decode("utf-8", "replace").strip().splitlines()[-1][:200]
        return rc == 0


class Streams:
    """Every channel being watched, at most `most` at once, and a watcher that stops the ones nobody watches."""

    def __init__(self):
        self.hubs = {}
        self.lock = threading.Lock()
        self._watcher = None

    def get(self, cid, plan, most, grace):
        with self.lock:
            hub = self.hubs.get(cid)
            if hub and not hub.stopping:
                return hub
            if len([h for h in self.hubs.values() if not h.stopping]) >= most:
                raise Busy(f"{most} channels are playing, the most at once")
            hub = Hub(cid, plan, grace, self._gone)
            self.hubs[cid] = hub
            if not self._watcher or not self._watcher.is_alive():
                self._watcher = threading.Thread(target=self._watch, name="watcher", daemon=True)
                self._watcher.start()
            return hub

    def _gone(self, hub):
        with self.lock:
            if self.hubs.get(hub.cid) is hub:
                del self.hubs[hub.cid]

    def _watch(self):
        """Runs only while a channel plays: stops each channel `grace` seconds after its last viewer left."""
        while True:
            time.sleep(5)
            with self.lock:
                hubs = list(self.hubs.values())
            if not hubs:
                return
            for h in hubs:
                if h.idle_for() > h.grace:
                    h.stop()

    def stop_all(self):
        with self.lock:
            hubs = list(self.hubs.values())
        for h in hubs:
            h.stop()
        return len(hubs)

    def playing(self):
        with self.lock:
            return {cid: len(h.viewers) for cid, h in self.hubs.items() if not h.stopping}


def has_ffmpeg():
    return bool(shutil.which("ffmpeg"))
