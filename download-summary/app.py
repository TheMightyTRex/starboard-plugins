"""Download summary: How much has downloaded today and this week, from what Starboard sees in the queue."""
import time
from sbplugin import every, keep, remember, serve, starboard


def sample():
    seen = remember("seen", {})
    days = remember("days", {})
    today = time.strftime("%Y-%m-%d")
    now = {}
    for it in (starboard("downloads") or {}).get("items") or []:
        key = f"{it.get('client', '')}:{it.get('id', it.get('name', ''))}"
        size = float(it.get("size") or 0)
        done = size * float(it.get("progress") or 0) / (100 if float(it.get("progress") or 0) > 1 else 1)
        now[key] = done
        days[today] = days.get(today, 0) + max(0.0, done - seen.get(key, done))
    keep("seen", now)
    keep("days", dict(sorted(days.items())[-14:]))


def card():
    days = remember("days", {})
    week = sum(v for k, v in days.items() if k >= time.strftime("%Y-%m-%d", time.localtime(time.time() - 6 * 86400)))
    return {"value": int(days.get(time.strftime("%Y-%m-%d"), 0)), "label": "today", "note": f"{week / 1e9:.1f} GB this week"}


every(60, sample)
serve({"/card": card})
