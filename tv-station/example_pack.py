"""Makes the Example TV broadcast pack: a made-up channel's branding, drawn and composed in code, so anyone can try a
pack and it holds nothing of anyone else's (no pictures, footage, fonts or music from elsewhere; the font is the
plug-in's own Atkinson Hyperlegible Next, SIL Open Font License 1.1).

    python3 example_pack.py <output folder> [--zip <file>] [--small]

It makes, at 1920 by 1080 and 25 frames a second (--small: 480 by 270, for the tests):

    pack.json, README.txt
    logo/dog.png                 the Example TV logo on a transparent background
    logo/logo-with-music.mp4     the logo with a short tune baked in, 5 seconds
    idents/ident01.mp4 to 03     three idents, 5 to 6 seconds, each with its own tune
    coming-next/background.mp4   a 10 second loop, with the clip area framed and the fields left clear
    promo/background.mp4         a 15 second loop, the same
    promo/music/music01.m4a, 02  two 20 second music beds
    transitions/wipe01.webm, wipe02.webm, sting01.webm   with transparency (VP9 with alpha)
    coming-next/placement.png, promo/placement.png       where the clip and each field go

Only FFmpeg is needed, so the plug-in's own image makes it when Try the example pack is chosen. Every sound is made
at -23 LUFS. The same command makes the same pack.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dog  # noqa: E402
import pack  # noqa: E402

NAVY, TEAL, AMBER, WHITE = "0x10202c", "0x1b8a7f", "0xffd54f", "0xffffff"
FPS = 25


def _nice():
    try:
        os.nice(19)
    except OSError:
        pass


def ff(*args):
    # Two threads and two filter threads: the plug-in's container has 2 cores and a limit on its threads.
    r = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-filter_threads", "2", *args], capture_output=True, timeout=900,
                       check=False, preexec_fn=_nice)
    if r.returncode != 0:
        raise RuntimeError("FFmpeg: " + (r.stderr.decode("utf-8", "replace").strip().splitlines() or ["failed"])[-1][:300])


def h264(seconds):
    return ["-t", f"{seconds}", "-threads", "2", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(FPS),
            "-g", str(FPS * 2), "-movflags", "+faststart"]


AAC = ["-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2"]
LOUD = "loudnorm=I=-23:TP=-2:LRA=7,aresample=48000"


def notes(seq, decay=3.0, amp=0.22):
    """A tune as an aevalsrc sum: each (start, frequency) a plucked note that dies away, with a soft second harmonic."""
    return "+".join(f"{amp}*gte(t,{s})*exp(-{decay}*(t-{s}))*(sin(2*PI*{f}*t)+0.3*sin(4*PI*{f}*t))" for s, f in seq)


def pad(freqs, amp=0.05):
    return "+".join(f"{amp}*sin(2*PI*{f}*t)" for f in freqs)


TUNES = {
    # C major, rising: the logo's sting.
    "sting": notes([(0.2, 261.63), (0.45, 329.63), (0.7, 392.0), (0.95, 523.25), (1.6, 659.25)]) + "+" + pad([130.81, 196.0]),
    "ident01": notes([(0.3, 293.66), (0.6, 369.99), (0.9, 440.0), (1.5, 587.33), (2.6, 440.0), (3.2, 587.33)], 2.5) + "+" + pad([146.83, 220.0]),
    "ident02": notes([(0.2, 392.0), (0.5, 329.63), (0.8, 261.63), (1.4, 392.0), (2.0, 523.25)], 2.0) + "+" + pad([98.0, 196.0], 0.06),
    "ident03": notes([(0.3, 220.0), (0.7, 261.63), (1.1, 329.63), (1.5, 440.0), (2.4, 329.63), (2.8, 440.0)], 2.8) + "+" + pad([110.0, 164.81]),
}
BEDS = {
    # A pulse in A minor, and a lighter one in F major, each 20 seconds: music beds for the promos.
    "music01": "0.12*sin(2*PI*110*t)*(0.55+0.45*sin(2*PI*2*t))+0.06*sin(2*PI*164.81*t)+0.05*sin(2*PI*220*t)*(0.5+0.5*sin(PI*t))"
               "+0.05*sin(2*PI*261.63*t)*gt(mod(t,1),0.5)*exp(-6*mod(t,0.5))",
    "music02": "0.10*sin(2*PI*174.61*t)*(0.6+0.4*sin(2*PI*1.5*t))+0.06*sin(2*PI*261.63*t)+0.05*sin(2*PI*349.23*t)*exp(-4*mod(t,0.75))"
               "+0.04*sin(2*PI*440*t)*gt(mod(t,1.5),0.75)*exp(-5*mod(t,0.75))",
}


class Maker:
    def __init__(self, out, W=1920, H=1080):
        self.out, self.W, self.H = out, W, H
        self.sx = W / 1920
        self.tmp = tempfile.mkdtemp(prefix="example-pack-")

    def p(self, *parts):
        path = os.path.join(self.out, *parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return path

    def t(self, name):
        return os.path.join(self.tmp, name)

    def px(self, n):
        return max(2, int(round(n * self.sx)))

    def sound(self, name, expr, seconds, path):
        """A tune at -23 LUFS: made, measured, and made again with the difference, as loudnorm in one pass is near."""
        shape = f"afade=in:st=0:d=0.05,afade=out:st={seconds - 0.6}:d=0.6"
        src = ["-f", "lavfi", "-t", str(seconds), "-i", f"aevalsrc='{expr}':s=48000:c=stereo"]
        ff(*src, "-af", f"{shape},{LOUD}", *AAC, path)
        off = pack.LOUDNESS - (pack.loudness(path) or pack.LOUDNESS)
        if abs(off) > 0.3:
            ff(*src, "-af", f"{shape},{LOUD},volume={off:+.1f}dB", *AAC, path)

    # The logo: a teal disc with a white play sign, and the words Example TV, drawn four times as large and scaled.
    def logo(self):
        cw, ch = 2900, 800
        inside = "lte(hypot(X-400\\,Y-400)\\,360)"
        play = "gte(X\\,300)*gte(Y\\,220+(X-300)*0.75)*lte(Y\\,580-(X-300)*0.75)"
        # Teal inside a white ring, so the disc stands out on a teal picture too.
        teal = f"lte(hypot(X-400\\,Y-400)\\,322)*not({play})"
        rgb = {"r": 0x1b, "g": 0x8a, "b": 0x7f}
        geq = ":".join(f"{k}='if({teal}\\,{v}\\,255)'" for k, v in rgb.items())
        ff("-f", "lavfi", "-i", f"color=c=white:s={cw}x{ch},format=rgb24,geq={geq}", "-frames:v", "1", self.t("colour.png"))
        ff("-f", "lavfi", "-i", f"color=c=black:s={cw}x{ch},format=gray,geq=lum='255*{inside}'",
           "-vf", f"drawtext=fontfile={dog.FONT}:text='Example TV':fontsize=330:fontcolor=white:x=840:y=(h-th)/2-10",
           "-frames:v", "1", self.t("mask.png"))
        ff("-i", self.t("colour.png"), "-i", self.t("mask.png"), "-filter_complex", "[0:v][1:v]alphamerge,format=rgba", "-frames:v", "1",
           self.t("logo-big.png"))
        # The DOG: 200 pixels tall at 1080 (its words a little bold with a dark edge, so it reads on any picture).
        h = max(64, self.px(200))
        ff("-i", self.t("logo-big.png"), "-vf", f"scale=-1:{h}:flags=lanczos,format=rgba", "-frames:v", "1", self.p("logo", "dog.png"))
        for name, height in (("logo-360.png", self.px(360)), ("logo-120.png", self.px(110))):
            ff("-i", self.t("logo-big.png"), "-vf", f"scale=-1:{height}:flags=lanczos,format=rgba", "-frames:v", "1", self.t(name))

    def motion(self, path, seconds, background, logo_y, tune, extra=""):
        """A short film: a background, the logo rising into place and fading in, and its tune."""
        self.sound(tune, TUNES[tune], seconds, self.t(f"{tune}.m4a"))
        ff(*background, "-loop", "1", "-i", self.t("logo-360.png"), "-i", self.t(f"{tune}.m4a"),
           "-filter_complex",
           f"[0:v]fps={FPS},format=yuv420p{extra}[bg];[1:v]format=rgba,fade=t=in:st=0.6:d=0.8:alpha=1[lg];"
           f"[bg][lg]overlay=x=(W-w)/2:y='{logo_y}':shortest=1,fade=t=in:st=0:d=0.3,fade=t=out:st={seconds - 0.5}:d=0.5[v]",
           "-map", "[v]", "-map", "2:a", *h264(seconds), *AAC, path)

    def films(self):
        W, H = self.W, self.H
        size = f"{W}x{H}"
        self.motion(self.p("logo", "logo-with-music.mp4"), 5,
                    ["-f", "lavfi", "-t", "5", "-i", f"gradients=s={size}:c0={NAVY}:c1={TEAL}:x0=0:y0=0:x1={W}:y1={H}:speed=0.015:r={FPS}"],
                    f"(H-h)/2+{self.px(60)}*exp(-3*t)", "sting")
        # ident01: amber and white bars sweep across teal, then the logo.
        bars = (f"drawbox=x='-{W}+{W * 2}*min(1\\,t/1.2)':y={int(H * 0.30)}:w={W}:h={self.px(24)}:color={AMBER}:t=fill:enable='lt(t,4)',"
                f"drawbox=x='{W}-{W * 2}*min(1\\,max(0\\,t-0.3)/1.2)':y={int(H * 0.70)}:w={W}:h={self.px(24)}:color={WHITE}:t=fill:enable='lt(t,4)'")
        self.motion(self.p("idents", "ident01.mp4"), 6, ["-f", "lavfi", "-t", "6", "-i", f"color=c={TEAL}:s={size}:r={FPS}"],
                    f"(H-h)/2+{self.px(40)}*exp(-2*t)", "ident01", "," + bars)
        # ident02: a slow gradient of navy, teal and amber, the logo coming down into place.
        self.motion(self.p("idents", "ident02.mp4"), 6,
                    ["-f", "lavfi", "-t", "6", "-i", f"gradients=s={size}:n=3:c0={NAVY}:c1={TEAL}:c2=0x8a6d1b:speed=0.03:r={FPS}"],
                    f"(H-h)/2-{self.px(80)}*exp(-2.5*t)", "ident02")
        # ident03: a field of teal cells growing on navy, the logo in a dark band across the middle.
        cells = f"life=s={max(48, W // 10)}x{max(27, H // 10)}:mold=12:ratio=0.3:seed=7:r={FPS}:life_color={TEAL}:death_color={NAVY}:mold_color=0x1d5a5e"
        band = f",scale={W}:{H}:flags=neighbor,drawbox=x=0:y={int(H * 0.30)}:w={W}:h={int(H * 0.40)}:color={NAVY}@0.75:t=fill"
        self.motion(self.p("idents", "ident03.mp4"), 5, ["-f", "lavfi", "-t", "5", "-i", cells], "(H-h)/2", "ident03", band)

    def background(self, part, seconds, c0, c1, strip):
        """A looping card background: a slow gradient, the clip area framed in the accent colour, a strip and the logo
        in a corner inside the title safe area. Nothing where the words go."""
        W, H = self.W, self.H
        lay = pack.DEFAULT_LAYOUT[part]
        x0, y0, x1, y1 = [int(v * self.sx) for v in lay["clip"]]
        b = self.px(8)
        frame = (f"drawbox=x={x0 - b}:y={y0 - b}:w={x1 - x0 + 2 * b}:h={y1 - y0 + 2 * b}:color={AMBER}:t=fill,"
                 f"drawbox=x={x0}:y={y0}:w={x1 - x0}:h={y1 - y0}:color=black:t=fill,"
                 f"drawbox=x=0:y={int(H * strip)}:w={W}:h={self.px(10)}:color={AMBER}@0.8:t=fill,"
                 f"drawbox=x={self.px(96)}:y={self.px(150)}:w={self.px(12)}:h={self.px(780)}:color={TEAL}:t=fill")
        ff("-f", "lavfi", "-t", str(seconds), "-i", f"gradients=s={W}x{H}:c0={c0}:c1={c1}:x0=0:y0=0:x1={W}:y1={H}:speed=0.01:r={FPS}",
           "-loop", "1", "-i", self.t("logo-120.png"), "-filter_complex",
           f"[0:v]fps={FPS},format=yuv420p,{frame}[bg];[bg][1:v]overlay=x=W-w-{self.px(140)}:y={self.px(870)}:shortest=1[v]",
           "-map", "[v]", "-an", *h264(seconds), self.p(part.replace("_", "-"), "background.mp4"))

    def music(self):
        for name, expr in BEDS.items():
            self.sound(name, expr, 20, self.p("promo", "music", f"{name}.m4a"))

    def transitions(self):
        W, H = self.W, self.H
        size = f"{W}x{H}"
        vp9 = ["-threads", "2", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "32", "-deadline", "good", "-cpu-used", "5",
               "-auto-alt-ref", "0", "-an"]
        # wipe01: a teal panel with an amber edge sweeps across, covering the whole picture at its middle.
        bw = int(W * 1.4)
        ff("-f", "lavfi", "-i", f"color=c=black@0.0:s={size}:r={FPS}:d=1,format=rgba",
           "-f", "lavfi", "-i", f"color=c={TEAL}:s={bw}x{H}:r={FPS}:d=1,format=rgba",
           "-f", "lavfi", "-i", f"color=c={AMBER}:s={self.px(40)}x{H}:r={FPS}:d=1,format=rgba",
           "-filter_complex", f"[0:v][1:v]overlay=x='-{bw}+({W}+{bw})*t/1':y=0:format=rgb[a];"
                              f"[a][2:v]overlay=x='-{bw}+({W}+{bw})*t/1+{bw}':y=0:format=rgb,format=yuva420p[v]",
           "-map", "[v]", "-t", "1", *vp9, self.p("transitions", "wipe01.webm"))
        # wipe02: a navy circle opens from the middle to cover the picture, then closes.
        ff("-f", "lavfi", "-i", f"color=c=black:s={size}:r={FPS}:d=1,format=rgba",
           "-vf", f"geq=r=16:g=32:b=44:a='255*lte(hypot(X-W/2\\,Y-H/2)\\,sin(PI*T/1)*{int(1.2 * (W * W + H * H) ** 0.5 / 2)})',format=yuva420p",
           "-t", "1", *vp9, self.p("transitions", "wipe02.webm"))
        # sting01: a navy flash with the logo, solid from 0.4 to 0.8 seconds, for a cut between programmes.
        ff("-f", "lavfi", "-i", f"color=c={NAVY}:s={size}:r={FPS}:d=1.2,format=rgba", "-loop", "1", "-t", "1.2", "-i", self.t("logo-360.png"),
           "-filter_complex", "[0:v]fade=t=in:st=0:d=0.4:alpha=1,fade=t=out:st=0.8:d=0.4:alpha=1[bg];"
                              "[1:v]format=rgba,fade=t=in:st=0.15:d=0.3:alpha=1,fade=t=out:st=0.8:d=0.3:alpha=1[lg];"
                              "[bg][lg]overlay=x=(W-w)/2:y=(H-h)/2:format=rgb:shortest=1,format=yuva420p[v]",
           "-map", "[v]", "-t", "1.2", *vp9, self.p("transitions", "sting01.webm"))

    def describe(self):
        doc = pack.template_pack_json("Example TV")
        doc.update({"made": "Made in code by the plug-in", "author": "Create your own TV channel",
                    "colours": {"text": "#FFFFFF", "accent": "#FFD54F"},
                    "idents": ["ident01.mp4", "ident02.mp4", "ident03.mp4"],
                    "transitions": ["sting01.webm", "wipe01.webm", "wipe02.webm"]})
        doc["promo"]["music"] = ["promo/music/music01.m4a", "promo/music/music02.m4a"]
        with open(self.p("pack.json"), "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=1)
            f.write("\n")
        with open(self.p("README.txt"), "w", encoding="utf-8") as f:
            f.write("Example TV: a made-up channel's broadcast pack, made in code by Create your own TV channel.\n"
                    "Free to use and change. Every picture and sound in it was made by example_pack.py, with FFmpeg.\n\n" + pack.README)
        for part, folder in (("coming_next", "coming-next"), ("promo", "promo")):
            bg = self.t(f"{part}.png")
            ff("-ss", "2", "-i", self.p(folder, "background.mp4"), "-vf", "scale=1920:1080", "-frames:v", "1", bg)
            with open(self.p(folder, "placement.png"), "wb") as f:
                f.write(pack.placement_png(part, doc[part], dog.FONT, background=bg))

    def make(self):
        try:
            self.logo()
            self.films()
            self.background("coming_next", 10, NAVY, "0x16424a", 0.925)
            self.background("promo", 15, NAVY, "0x2b1f4a", 0.925)
            self.music()
            self.transitions()
            self.describe()
        finally:
            shutil.rmtree(self.tmp, ignore_errors=True)


def make(out, small=False):
    """Makes the pack in `out` (made empty first). Returns the folder."""
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    Maker(out, *((480, 270) if small else (1920, 1080))).make()
    return out


def main(argv):
    if not argv or argv[0].startswith("-"):
        print(__doc__)
        return 2
    out = argv[0]
    make(out, small="--small" in argv)
    if "--zip" in argv:
        z = argv[argv.index("--zip") + 1]
        with open(z, "wb") as f:
            f.write(pack.zip_folder(out, "Example-TV"))
    got = pack.check(out)
    for line in got["problems"] + got["notes"]:
        print(line)
    print("The pack is ready" if got["ok"] else "The pack has problems")
    return 0 if got["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
