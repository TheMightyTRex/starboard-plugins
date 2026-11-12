"""Disk forecast: When each disk fills at the rate it has been filling over the last month."""
import time
from sbplugin import every, keep, last_error, remember, serve, starboard


def sample():
    hist = remember("history", {})
    day = time.strftime("%Y-%m-%d")
    for d in (starboard("system") or {}).get("disks") or []:
        name = d.get("label") or d.get("mount") or d.get("name")
        if name and d.get("total"):
            hist.setdefault(name, {})[day] = [float(d.get("used") or 0), float(d["total"])]
    keep("history", {k: dict(sorted(v.items())[-35:]) for k, v in hist.items()})


def card():
    hist = remember("history", {})
    if not hist:
        return {"state": "warning", "text": last_error() or "Measuring: a forecast after two days"}
    worst, parts = None, []
    for name, days in hist.items():
        rows = sorted(days.items())
        (d0, (u0, _)), (d1, (u1, total)) = rows[0], rows[-1]
        span = (time.mktime(time.strptime(d1, "%Y-%m-%d")) - time.mktime(time.strptime(d0, "%Y-%m-%d"))) / 86400
        rate = (u1 - u0) / span if span >= 1 else 0
        if rate <= 0:
            parts.append(f"{name}: {round(100 * u1 / total)}% full, not growing")
            continue
        left = (total - u1) / rate
        worst = left if worst is None else min(worst, left)
        parts.append(f"{name}: full in about {round(left):,} days")
    state = "problem" if worst is not None and worst < 14 else "warning" if worst is not None and worst < 60 else "ok"
    return {"state": state, "text": ". ".join(parts)}


every(3600, sample)
serve({"/card": card})
