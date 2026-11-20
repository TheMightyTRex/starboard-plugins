"""The status page (Uptime and status 2.0.0): one read-only page on the home network, written as plain HTML after each
round of checks into the container's memory (/tmp), so it costs no disk writes and nothing runs when someone opens it.

It uses the TRex Design System: its tokens and the parts of its components the page needs (ds.css, made by
make_css.py from the design system's own files), the status chip with words, shape and colour together, and tables with
a caption and row headers. It shows names, never addresses or heartbeat links, because anyone on the home network can
open it. It does not refresh by itself, which would move a screen reader's place; it says when it was written.
"""
import html
import time

TONES = {"up": ("success", "Up"), "down": ("danger", "Down"), "maintenance": ("muted", "Maintenance"),
         "waiting": ("", "Not checked yet"), "retry": ("warning", "Trying again"), "off": ("muted", "Paused")}
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November",
          "December"]


def chip(state):
    tone, words = TONES[state]
    attr = f' data-tone="{tone}"' if tone else ""
    return f'<span class="chip"{attr}><span class="visually-hidden">Status: </span>{words}</span>'


def percent(p):
    if p is None:
        return "No checks yet"
    return f"{p:.2f}%" if p < 100 else "100%"


def when(t):
    lt = time.localtime(t)
    return f"{lt.tm_mday} {MONTHS[lt.tm_mon - 1]} {lt.tm_year} at {lt.tm_hour:02d}:{lt.tm_min:02d}"


def build(title, groups, now=None):
    """groups: [{"name", "state", "up", "total", "maintenance": words or "", "checks": [{"name", "kind", "state",
    "ms", "day", "month", "quarter", "cert": words or ""}]}]."""
    now = time.time() if now is None else now
    e = html.escape
    total = sum(g["total"] for g in groups)
    down = sum(1 for g in groups for c in g["checks"] if c["state"] == "down")
    up = sum(1 for g in groups for c in g["checks"] if c["state"] == "up")
    if not total:
        summary = "Nothing is checked yet."
    elif down:
        summary = f"{down} of {total} {'check is' if total == 1 else 'checks are'} down."
    elif up == total:
        summary = f"All {total} {'check is' if total == 1 else 'checks are'} up."
    else:
        summary = f"{up} of {total} checks are up. The others are not checked yet or are being tried again."
    out = [f"""<!doctype html>
<html lang="en-GB" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>{e(title)}</title>
<link rel="stylesheet" href="ds.css">
<link rel="stylesheet" href="status.css">
<script src="theme.js"></script>
</head>
<body>
<a class="skip-link" href="#main">Skip to the checks</a>
<header class="status-head">
<h1>{e(title)}</h1>
<p class="status-summary">{e(summary)}</p>
<p class="status-when">Written {e(when(now))}. Reload the page for the latest.</p>
</header>
<main id="main" class="status-main" tabindex="-1">"""]
    if not groups:
        out.append("<p>No checks have been added yet.</p>")
    for i, g in enumerate(groups):
        gid = f"g{i}"
        note = f'<p class="status-note">Maintenance: {e(g["maintenance"])}. Alerts are paused.</p>' if g["maintenance"] else ""
        out.append(f"""<section class="card status-group" aria-labelledby="{gid}">
<div class="status-group__head"><h2 id="{gid}">{e(g['name'])}</h2>{chip(g['state'])}<p class="status-count">{g['up']} of {g['total']} up</p></div>
{note}<div class="table-wrap" role="region" aria-labelledby="{gid}-cap" tabindex="0">
<table class="table">
<caption id="{gid}-cap" class="visually-hidden">{e(g['name'])}: each check, its status, response time and uptime</caption>
<thead><tr><th scope="col">Check</th><th scope="col">Status</th><th scope="col">Response time</th><th scope="col">Last 24 hours</th><th scope="col">Last 30 days</th><th scope="col">Last 90 days</th><th scope="col">Certificate</th></tr></thead>
<tbody>""")
        for c in g["checks"]:
            ms = "None" if c.get("ms") is None else "Under 1 ms" if c["ms"] < 1 else f"{c['ms']:,.0f} ms"
            out.append(f"<tr><th scope=\"row\">{e(c['name'])}<span class=\"status-kind\">{e(c['kind'])}</span></th>"
                       f"<td>{chip(c['state'])}</td><td>{e(ms)}</td><td>{percent(c['day'])}</td><td>{percent(c['month'])}</td>"
                       f"<td>{percent(c['quarter'])}</td><td>{e(c['cert'] or 'None')}</td></tr>")
        out.append("</tbody></table></div></section>")
    out.append("""</main>
<footer class="status-foot"><p>Made by Starboard's Uptime and status plug-in. This page only shows: nothing on it can change anything.</p></footer>
</body>
</html>
""")
    return "\n".join(out)
