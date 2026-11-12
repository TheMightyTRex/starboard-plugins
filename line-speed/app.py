"""Line speed: Tests your internet download speed once a night, outside download hours, and keeps a week of results."""
import time
from sbplugin import every, fetch, keep, last_error, remember, serve, setting


def test():
    size = int(setting("megabytes", 25)) * 1_000_000
    started = time.monotonic()
    got = len(fetch(f"https://speed.cloudflare.com/__down?bytes={size}", timeout=120, raw=True, limit=size + 1))
    mbps = round(got * 8 / (time.monotonic() - started) / 1_000_000, 1)
    runs = (remember("runs", []) + [{"at": time.time(), "mbps": mbps}])[-14:]
    keep("runs", runs)
    return {"said": f"{mbps} Mbps"}


def nightly():
    runs = remember("runs", [])
    today = time.strftime("%Y-%m-%d")
    if time.localtime().tm_hour == int(setting("hour", 4)) and not any(time.strftime("%Y-%m-%d", time.localtime(r["at"])) == today for r in runs):
        test()


def card():
    runs = remember("runs", [])
    if not runs:
        return {"value": 0, "label": "Mbps", "note": last_error() or "Not tested yet"}
    r = runs[-1]
    return {"value": r["mbps"], "label": "Mbps", "note": time.strftime("%a %H:%M", time.localtime(r["at"]))}


def week():
    return {"items": [{"title": f"{r['mbps']} Mbps", "detail": time.strftime("%A %d %b, %H:%M", time.localtime(r["at"]))}
                      for r in reversed(remember("runs", [])[-7:])]}


every(600, nightly)
serve({"/card": card, "/week": week, ("POST", "/test"): test})
