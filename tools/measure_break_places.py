#!/usr/bin/env python3
"""Measures what finding the places for breaks costs (DASH-538): python3 tools/measure_break_places.py file.mp4 [seconds]
Runs tv-station/breaks.py's own search (breaks.survey) for At silence and At the end of a scene on one programme, and
prints the processor seconds (user and system, all of FFmpeg's processes) and the time it took, and the same for each hour of
the programme. Then the arithmetic that chooses the breaks from what was kept (breaks.place), which is all that runs when
a channel is planned. Make a test programme with tools/make_break_test_file.py."""
import json
import os
import resource
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tv-station"))
import breaks  # noqa: E402

path = sys.argv[1]
length = float(sys.argv[2]) if len(sys.argv) > 2 else 1800.0
breaks.begin()
report = {}
for name, methods in (("At silence", ("silence",)), ("At the end of a scene", ("scene",))):
    before, began = resource.getrusage(resource.RUSAGE_CHILDREN), time.monotonic()
    got = breaks.survey(path, length, (), methods)
    after, wall = resource.getrusage(resource.RUSAGE_CHILDREN), time.monotonic() - began
    cpu = (after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime)
    report[name] = {"processor_seconds": round(cpu, 2), "seconds": round(wall, 2),
                    "processor_seconds_per_hour": round(cpu * 3600 / length, 2), "seconds_per_hour": round(wall * 3600 / length, 2),
                    "kept_bytes": len(json.dumps(got, separators=(",", ":"))), "kept": got}
t = time.perf_counter()
for _ in range(1000):
    breaks.place(length, 3, [(c, 0.0) for c in report["At the end of a scene"]["kept"]["scn"]])
report["choosing, once (microseconds)"] = round((time.perf_counter() - t) * 1000, 1)
print(json.dumps(report, indent=1))
