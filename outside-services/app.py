"""Outside services: Up or down for things that are not on this server: your router, a NAS, a website."""
import time
import urllib.error
from sbplugin import every, fetch, keep, remember, serve, setting


def targets():
    out = []
    for line in setting("addresses", []) or []:
        parts = str(line).split()
        if parts:
            out.append((" ".join(parts[:-1]) or parts[-1], parts[-1]))
    return out[:20]


def check():
    rows = []
    for name, url in targets():
        started = time.monotonic()
        try:
            fetch(url, timeout=8, raw=True, limit=1024)
            up = True
        except urllib.error.HTTPError as e:
            up = e.code < 500  # it answered: a sign-in page or 404 still means it is up
        except Exception:  # noqa: BLE001
            up = False
        rows.append({"name": name, "url": url, "up": up, "ms": round((time.monotonic() - started) * 1000)})
    keep("rows", rows)


def status():
    rows = remember("rows", [])
    if not rows:
        return {"state": "warning", "text": "Add addresses in the plug-in's settings" if not targets() else "Not checked yet"}
    down = [r["name"] for r in rows if not r["up"]]
    return {"state": "problem" if down else "ok", "text": f"Not answering: {', '.join(down)}" if down else f"All {len(rows)} answer"}


def card():
    return {"items": [{"title": r["name"], "detail": f"Up, {r['ms']} ms" if r["up"] else "Not answering", "link": r["url"]}
                      for r in remember("rows", [])][:10]}


every(60 * float(setting("minutes", 5)), check, first=2)
serve({"/status": status, "/card": card})
