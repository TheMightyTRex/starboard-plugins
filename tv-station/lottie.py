"""Lottie import (0.13.3, DASH-639): a Lottie animation (the JSON that After Effects, LottieFiles and other tools export) used as a short
title clip or a bumper. The JSON is data, never run: it is checked first (size, no expressions, no links, no images or text,
a size and length that fit), its colours are swapped for the channel's two colours, and rlottie draws the frames, which FFmpeg
encodes with the name drawn over them. Nothing leaves the home.

Measured on this server on 28 November 2026 in the plug-in's image with the container's limits (768 MB, 2 processors, 128
processes): a 6 second 1920 by 1080 25 frame animation took 12 seconds and peaked at 222 MB (FFmpeg, one thread) and 41 MB (Python)
over a colour, and 20 seconds and 402 MB with transparency kept (VP9 with alpha). The container's own peak stayed under 540 MB
with the install of the library counted. The explicit size argument of rlottie-python crashed in that build, so every frame is
drawn at the animation's own size, which a file may not make larger than 1920 by 1080.
"""
import json
import re

import draw

MAX_BYTES = 1024 * 1024
MAX_W, MAX_H = 1920, 1080
MAX_SECONDS = 10.0
MAX_FPS = 60
MAX_LAYERS = 60
MAX_DEPTH = 40
ALLOWED_LAYERS = {0: "a pre-composition", 1: "a solid", 3: "a null object", 4: "a shape"}
LINK = re.compile(r"(?i)\b(https?|ftp|file|data|javascript):")


class LottieError(ValueError):
    pass


def available():
    """Whether rlottie is in this image."""
    try:
        import rlottie_python  # noqa: F401
        return True
    except ImportError:
        return False


def _walk(node, depth=0):
    """Every (key, value) pair in a JSON document, without recursion past MAX_DEPTH. Raises LottieError when it is deeper."""
    stack = [(node, 0)]
    while stack:
        cur, d = stack.pop()
        if d > MAX_DEPTH:
            raise LottieError("the animation nests more than 40 levels deep")
        if isinstance(cur, dict):
            for k, v in cur.items():
                yield k, v
                stack.append((v, d + 1))
        elif isinstance(cur, list):
            for v in cur:
                stack.append((v, d + 1))


def check(raw):
    """Reads and checks a Lottie file's bytes. Returns (doc, info): info = {"w", "h", "dur", "fps"}. Raises LottieError with one sentence."""
    if len(raw) > MAX_BYTES:
        raise LottieError("it is over 1 MB. A title animation is much smaller than that")
    try:
        doc = json.loads(raw.decode("utf-8-sig"))
    except (ValueError, UnicodeDecodeError):
        raise LottieError("it is not a Lottie file. Export it again as JSON, not as a dotLottie (.lottie) file") from None
    if not isinstance(doc, dict) or not isinstance(doc.get("layers"), list) or not all(k in doc for k in ("fr", "ip", "op", "w", "h")):
        raise LottieError("it is not a Lottie file: it has no frame rate, size or layers")
    try:
        w, h, fps = int(doc["w"]), int(doc["h"]), float(doc["fr"])
        frames = float(doc["op"]) - float(doc["ip"])
    except (TypeError, ValueError):
        raise LottieError("its size or frame rate is not a number") from None
    if not (16 <= w <= MAX_W and 9 <= h <= MAX_H):
        raise LottieError(f"it is {w} by {h} pixels. The most is {MAX_W} by {MAX_H}")
    if not 1 <= fps <= MAX_FPS:
        raise LottieError(f"it runs at {fps:g} frames a second. Use 1 to {MAX_FPS}")
    dur = frames / fps
    if not 0.5 <= dur <= MAX_SECONDS:
        raise LottieError(f"it is {dur:.1f} seconds long. Use 0.5 to {MAX_SECONDS:g} seconds")
    for key, value in _walk(doc):
        if key == "x" and isinstance(value, str):
            raise LottieError("it uses expressions (scripts) to move things. Export it again with the expressions baked into keyframes")
        if isinstance(value, str) and LINK.search(value):
            raise LottieError("it holds a link or an embedded file")
    for asset in doc.get("assets") or []:
        if isinstance(asset, dict) and ("p" in asset or "u" in asset or "e" in asset):
            raise LottieError("it holds pictures, which are not used. Use an animation made of shapes")
    layers = list(doc["layers"]) + [lay for a in (doc.get("assets") or []) if isinstance(a, dict) for lay in (a.get("layers") or [])]
    if len(layers) > MAX_LAYERS:
        raise LottieError(f"it has {len(layers)} layers. The most is {MAX_LAYERS}")
    for lay in layers:
        ty = lay.get("ty") if isinstance(lay, dict) else None
        if ty not in ALLOWED_LAYERS:
            word = {2: "a picture", 5: "text (which needs fonts this server does not have)", 6: "sound"}.get(ty, f"a layer of kind {ty}")
            raise LottieError(f"it has {word}. Use shapes only; the plug-in draws the name itself")
    return doc, {"w": w, "h": h, "dur": round(dur, 2), "fps": fps}


def _rgb(c):
    return [round(float(v), 4) for v in c[:3]]


def _hex_to_rgb(h):
    return [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]


def colours_of(doc):
    """The distinct colours the animation fills and strokes, as [r, g, b] with 0 to 1 values, most used first."""
    count = {}
    for node in _colour_nodes(doc):
        for rgb in _values(node):
            key = tuple(rgb)
            count[key] = count.get(key, 0) + 1
    return [list(k) for k, _ in sorted(count.items(), key=lambda kv: -kv[1])]


def _colour_nodes(doc):
    """The "c" objects of every fill (fl), stroke (st) and gradient-less solid: each {"a": 0, "k": [r, g, b, a]} or {"a": 1, "k": [{"s": [...]}, ...]}."""
    stack = [doc]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            if cur.get("ty") in ("fl", "st") and isinstance(cur.get("c"), dict):
                yield cur["c"]
            for v in cur.values():
                if isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(cur, list):
            stack.extend(v for v in cur if isinstance(v, (dict, list)))


def _values(node):
    k = node.get("k")
    if node.get("a") == 0 and isinstance(k, list) and len(k) >= 3 and all(isinstance(v, (int, float)) for v in k[:3]):
        yield _rgb(k)
    elif node.get("a") == 1 and isinstance(k, list):
        for kf in k:
            s = kf.get("s") if isinstance(kf, dict) else None
            if isinstance(s, list) and len(s) >= 3 and all(isinstance(v, (int, float)) for v in s[:3]):
                yield _rgb(s)


def recolour(doc, c1, c2):
    """The animation with its most used colour changed to c1 and every other colour to c2 (#RRGGBB each). Alpha is kept. Returns a new document."""
    out = json.loads(json.dumps(doc))
    ranked = colours_of(out)
    if not ranked:
        return out
    main = tuple(ranked[0])
    a, b = _hex_to_rgb(c1), _hex_to_rgb(c2)

    def swap(rgb, alpha):
        return [*(a if tuple(_rgb(rgb)) == main else b), alpha]

    for node in _colour_nodes(out):
        k = node.get("k")
        if node.get("a") == 0 and isinstance(k, list) and len(k) >= 3:
            node["k"] = swap(k, k[3] if len(k) > 3 else 1)
        elif node.get("a") == 1 and isinstance(k, list):
            for kf in k:
                s = kf.get("s") if isinstance(kf, dict) else None
                if isinstance(s, list) and len(s) >= 3:
                    kf["s"] = swap(s, s[3] if len(s) > 3 else 1)
    return out


def render(doc, info, dst, folder, name, ink, background, keep_alpha=False, seconds=None):
    """Draws the animation over a colour (or with its clear parts kept, as VP9 with alpha, for dst ending .webm), with `name` drawn over it, and
    encodes it with one FFmpeg thread. Needs rlottie. Raises LottieError when it is not in the image or the animation will not draw."""
    if not available():
        raise LottieError("Lottie files need rlottie, which this plug-in's image does not have yet")
    import subprocess

    from rlottie_python import LottieAnimation
    anim = LottieAnimation.from_data(json.dumps(doc))
    w, h = anim.lottie_animation_get_size()
    total = int(anim.lottie_animation_get_totalframe())
    fps = float(anim.lottie_animation_get_framerate()) or info["fps"]
    if (w, h) != (info["w"], info["h"]) or total < 1 or w > MAX_W or h > MAX_H:
        raise LottieError("rlottie cannot draw this animation")
    words = draw.text_file(name, folder) if name else None
    try:
        vf = [f"scale={draw.W}:{draw.H}:force_original_aspect_ratio=decrease:flags=bicubic,pad={draw.W}:{draw.H}:(ow-iw)/2:(oh-ih)/2:color=black@0"]
        if keep_alpha:
            enc = ["-threads", "1", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "32", "-deadline", "good", "-cpu-used", "5",
                   "-auto-alt-ref", "0", "-lag-in-frames", "0", "-an"]
            graph = f"[0:v]{vf[0]},format=rgba[v]"
        else:
            enc = [*draw.H264, "-an"]
            graph = (f"color=c={draw.ffcolour(background)}:s={draw.W}x{draw.H}:r={draw.FPS}[bg];[0:v]{vf[0]},format=rgba[an];[bg][an]overlay=shortest=1:format=auto[o];"
                     "[o]format=yuv420p[v]")
        if words:
            size = max(72, min(120, int(1500 / (0.56 * max(1, len(name))))))
            graph = graph.rsplit("[v]", 1)[0] + (f",drawtext=fontfile={draw.dog.FONT}:textfile={words}:expansion=none:fontsize={size}:fontcolor={draw.ffcolour(ink)}:"
                                                 f"x=(w-tw)/2:y={int(draw.H * 0.8)}:alpha='min(1,t/0.5)'[v]")
        if draw.stopped():
            raise draw.Stopped("A channel started to play, so the style stopped")
        cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-filter_complex_threads", "1", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{w}x{h}", "-r", f"{fps:g}", "-i", "-",
               "-filter_complex", graph, "-map", "[v]", "-r", str(draw.FPS), *[e for e in enc if e != "-r" and e != str(draw.FPS)], dst]
        with draw._run:
            p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=draw._nice)
            draw._proc["p"] = p
            try:
                for i in range(total):
                    if draw.stopped():
                        p.kill()
                        raise draw.Stopped("A channel started to play, so the style stopped")
                    frame = anim.render_pillow_frame(i).convert("RGBA")
                    try:
                        p.stdin.write(frame.tobytes())
                    except BrokenPipeError:
                        break
                try:
                    p.stdin.close()
                except OSError:
                    pass
                p.wait(timeout=300)
                err = p.stderr.read()
            finally:
                draw._proc["p"] = None
                if p.poll() is None:
                    p.kill()
        if p.returncode != 0:
            raise LottieError("FFmpeg: " + (err.decode("utf-8", "replace").strip().splitlines() or ["failed"])[-1][:200])
    finally:
        if words:
            import os
            os.remove(words)
    return dst
