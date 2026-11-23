#!/usr/bin/env python3
"""Makes a 30 minute test programme with FFmpeg for measuring how breaks are placed (DASH-538):
    python3 tools/make_break_test_file.py out.mp4 [seconds] [WIDTHxHEIGHT]
Nine different pictures one after another (so each cut is a scene change that the key frames show), a sound track of a
tone, and silences in it: four at scene cuts (three of them with a black picture around them, like a fade to black for
adverts), and two in the middle of a scene (a pause in talking). Nothing real is read. The cuts and silences are
printed, so the search can be checked against them."""
import subprocess
import sys

out = sys.argv[1]
total = int(sys.argv[2]) if len(sys.argv) > 2 else 1800
size = sys.argv[3] if len(sys.argv) > 3 else "640x360"
scale = total / 1800.0
lengths = [round(x * scale) for x in (240, 180, 220, 200, 150, 250, 170, 190, 200)]
lengths[-1] += total - sum(lengths)
sources = [f"testsrc2=r=25:s={size}", f"rgbtestsrc=r=25:s={size}", f"smptehdbars=r=25:s={size}", f"gradients=r=25:s={size}:speed=0.02",
           f"testsrc=r=25:s={size}", f"colorspectrum=r=25:s={size}", f"mandelbrot=r=25:s={size}:end_scale=0.5",
           f"life=s={size}:r=25:ratio=0.3:mold=10:life_color=#00ff00:death_color=#aa0000", f"sierpinski=r=25:s={size}"]
cuts, t = [], 0
for n in lengths[:-1]:
    t += n
    cuts.append(t)
silent_cuts = [cuts[1], cuts[3], cuts[5], cuts[7]]  # silence at these cuts
black_cuts = silent_cuts[:3]
middle = [round(total * 0.39), round(total * 0.556)]  # a pause in the middle of a scene
gaps = [(c - 0.6, c + 0.6) for c in silent_cuts] + [(m, m + 1.2) for m in middle]
args = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
for src, n in zip(sources, lengths):
    args += ["-f", "lavfi", "-t", str(n), "-i", src]
graph = "".join(f"[{i}:v]format=yuv420p,setsar=1[v{i}];" for i in range(len(sources)))
graph += "".join(f"[v{i}]" for i in range(len(sources))) + f"concat=n={len(sources)}:v=1:a=0[cat];"
black = "+".join(f"between(t,{c - 0.3},{c + 0.3})" for c in black_cuts)
graph += f"[cat]drawbox=color=black:t=fill:w=iw:h=ih:enable='{black}'[v]"
mute = "+".join(f"between(t,{a:.2f},{b:.2f})" for a, b in gaps)
args += ["-f", "lavfi", "-t", str(total), "-i", "sine=f=220:r=48000", "-filter_complex", graph, "-map", "[v]", "-map", f"{len(sources)}:a",
         "-af", f"volume=0:enable='{mute}'", "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-g", "250", "-c:a", "aac", "-b:a", "96k", out]
print("scene cuts at", cuts)
print("silences at", [(round(a, 1), round(b, 1)) for a, b in gaps], "black at", black_cuts)
subprocess.run(args, check=True)
