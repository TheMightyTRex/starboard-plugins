#!/usr/bin/env python3
"""Draws every plug-in's logo (DASH-428, plug-in API 1.14; owner, 14 November 2026: "create a logo for each
plugin"): <plug-in>/logo.svg, and "logo": {"file": "logo.svg", "alt": ...} in each hand-made manifest
(tools/make_examples.py adds it to the examples it writes, from the same table).

The alt text is the plug-in's name and "logo", such as "Direct play logo" (design system ALT-TEXT.md section 6, audit
of 17 November 2026): Starboard uses it only where the logo stands for the plug-in on its own, and hides the logo
from screen readers beside the plug-in's name. The words for the symbol, such as "a play symbol on a screen", are
for the help's Accessibility pages and this table.

Each logo is original and simple, so it reads from 22 to 48 pixels: a rounded tile in one colour with a white symbol
of thick strokes or solid shapes. No brand marks: the plug-ins for other apps (Jellyfin, Home Assistant, Seerr,
Calibre-Web and the rest) have neutral symbols of what they do, not those projects' logos. Every colour has at least
4.5 to 1 contrast with white, so the symbol reads in light and dark. Only the shapes Starboard allows are used (no
style, script, picture or outside link), with a viewBox, well under 16 KB.

    python3 tools/make_logos.py           # writes the files; STARBOARD_SRC: checks each with Starboard's cleaner
    python3 tools/make_logos.py --check   # says whether any logo or manifest is out of date
"""
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
W = "#ffffff"


def s(width=3.5):
    """A white line of the given width, with round ends and corners."""
    return f'fill="none" stroke="{W}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"'


S = s()

# id: (colour, the symbol in plain words for the help, the symbol on a 48 by 48 grid)
LOGOS = {
    "audio-description": ("#0b6670", "A loudspeaker with sound waves",
                          f'<path d="M10 20h6l8-7v22l-8-7h-6z" fill="{W}"/><path d="M30 18.5a7.5 7.5 0 0 1 0 11M34.5 14a14 14 0 0 1 0 20" {S}/>'),
    "audio-description-tracks": ("#2d5a87", "A loudspeaker with a plus sign",
                                 f'<path d="M8 20h6l8-7v22l-8-7H8z" fill="{W}"/><path d="M33 18v12M27 24h12" {S}/>'),
    "calibre-web": ("#6b3b1d", "A book in a browser window",
                    f'<rect x="9" y="11" width="30" height="26" rx="3" {S}/><path d="M9 17.5h30" {S}/>'
                    f'<path d="M24 23.5c-2.2-1.5-5.2-1.8-8-1.2v9.6c2.8-.6 5.8-.3 8 1.2 2.2-1.5 5.2-1.8 8-1.2v-9.6c-2.8-.6-5.8-.3-8 1.2z" fill="{W}"/>'),
    "direct-play": ("#1f5f99", "A play symbol on a screen",
                    f'<rect x="8" y="11" width="32" height="22" rx="3" {S}/><path d="M21 16.5v11l9-5.5z" fill="{W}"/><path d="M17 38h14" {S}/>'),
    "disk-forecast": ("#3d4f63", "A partly full disk",
                      f'<rect x="9" y="13" width="30" height="22" rx="3" {S}/><path d="M9 28h30" {S}/>'
                      f'<rect x="14" y="18" width="13" height="5" rx="1" fill="{W}"/><circle cx="33" cy="31.5" r="1.8" fill="{W}"/>'),
    "dns-blocking": ("#a3302b", "A circle with a line through it",
                     f'<circle cx="24" cy="24" r="13" {s(4)}/><path d="M15 33l18-18" {s(4)}/>'),
    "download-summary": ("#2e6b30", "An arrow down into a tray",
                         f'<path d="M24 9v18M16 20l8 8 8-8" {S}/><path d="M11 29v7h26v-7" {S}/>'),
    "home-assistant": ("#0f6857", "A house with lines of writing",
                       f'<path d="M9 24L24 11l15 13" {S}/><path d="M14 21v16h20V21" {S}/><path d="M19 28h10M19 32.5h7" {s(3)}/>'),
    "jellystat": ("#8a3b12", "A pie chart",
                  f'<circle cx="24" cy="24" r="13" {S}/><path d="M24 24V11a13 13 0 0 1 12.4 16.9z" fill="{W}"/>'),
    "kavita": ("#1d6363", "An open book",
               f'<path d="M24 15c-3-2.6-8-3.2-13-2.2v21.5c5-1 10-.4 13 2.2 3-2.6 8-3.2 13-2.2V12.8c-5-1-10-.4-13 2.2z" {S}/><path d="M24 15v21" {S}/>'),
    "library-cleanup": ("#4d5b16", "A storage box with an arrow going into it",
                        f'<rect x="8.5" y="11" width="31" height="7.5" rx="2" fill="{W}"/><path d="M11.5 18.5v17a2.5 2.5 0 0 0 2.5 2.5h20a2.5 2.5 0 0 0 2.5-2.5v-17" {S}/>'
                        f'<path d="M24 23v9.5M19.5 28.5l4.5 4.5 4.5-4.5" {S}/>'),
    "library-health": ("#6b4f1d", "A clipboard with a tick",
                       f'<rect x="12" y="12" width="24" height="27" rx="3" {S}/><rect x="18.5" y="8.5" width="11" height="6.5" rx="2" fill="{W}"/>'
                       f'<path d="M18 26.5l4 4 8-9" {S}/>'),
    "line-speed": ("#984a00", "A speed gauge",
                   f'<path d="M10.5 32a13.5 13.5 0 1 1 27 0" {s(4)}/><path d="M24 32l7.5-8.5" {S}/><circle cx="24" cy="32" r="3" fill="{W}"/>'),
    "maintainerr": ("#5a4687", "A broom",
                    f'<path d="M34.5 8.5L25 24" {S}/><path d="M19 22.5l10.5 6-4.5 11.5-14-8z" fill="{W}"/>'),
    "most-watched": ("#8e2a6b", "A star",
                     f'<path d="M24 9.5l4.4 9.3 10.1 1.2-7.5 7 2 10.1L24 32.1l-9 5 2-10.1-7.5-7 10.1-1.2z" fill="{W}"/>'),
    "navidrome": ("#a3243f", "A music note",
                  f'<path d="M28 31V11.5l8 3v5.5l-8-3" {S}/><ellipse cx="22" cy="31" rx="6.5" ry="5" fill="{W}"/>'),
    "notifications": ("#a33c17", "A bell",
                      f'<path d="M24 10.5a8.5 8.5 0 0 0-8.5 8.5v6.5l-3.5 5.5h24l-3.5-5.5V19a8.5 8.5 0 0 0-8.5-8.5z" fill="{W}"/>'
                      f'<circle cx="24" cy="35" r="3.2" fill="{W}"/>'),
    "outside-services": ("#33449e", "A globe",
                         f'<circle cx="24" cy="24" r="13" {S}/><ellipse cx="24" cy="24" rx="6" ry="13" {s(3)}/><path d="M11 24h26" {s(3)}/>'),
    "picture-shrinker": ("#8a4a0b", "A picture with an arrow pointing into its corner",
                         f'<rect x="8" y="16" width="24" height="22" rx="3" fill="{W}"/>'
                         f'<path d="M11.5 34.5l6.5-8 4.5 5 2.5-3 4 6z" fill="#8a4a0b"/><circle cx="25" cy="22" r="2.5" fill="#8a4a0b"/>'
                         f'<path d="M40 8l-8 8M32 10.5V16h5.5" {S}/>'),
    "remote-access": ("#0b5c86", "A phone with signal waves",
                      f'<rect x="10" y="16" width="15" height="24" rx="3" {S}/><path d="M16 34.5h3" {S}/>'
                      f'<path d="M30 14a7 7 0 0 1 5 5M30 8a13 13 0 0 1 11 11" {S}/>'),
    "seerr": ("#8a2f5c", "A speech bubble with a plus sign",
              f'<path d="M12 11h24a3 3 0 0 1 3 3v14a3 3 0 0 1-3 3H23l-8 6.5V31h-3a3 3 0 0 1-3-3V14a3 3 0 0 1 3-3z" {S}/>'
              f'<path d="M24 16v10M19 21h10" {S}/>'),
    "styles": ("#6236a8", "A painter's palette",
               f'<path d="M24 10a14 14 0 1 0 0 28c2.3 0 3.2-1.7 2.3-3.4-.9-1.8.3-3.9 2.4-3.9H32a6 6 0 0 0 6-6c0-8.2-6.3-14.7-14-14.7z" fill="{W}"/>'
               '<circle cx="16.5" cy="23" r="2.6" fill="#6236a8"/><circle cx="21.5" cy="16.5" r="2.6" fill="#6236a8"/>'
               '<circle cx="29.5" cy="17" r="2.6" fill="#6236a8"/>'),
    "tdarr": ("#2a6585", "Two arrows in a circle",
              f'<path d="M13.5 21a11 11 0 0 1 19.5-4.5M34.5 27A11 11 0 0 1 15 31.5" {S}/>'
              f'<path d="M34.5 10.5v7h-7M13.5 37.5v-7h7" {S}/>'),
    "uptime-kuma": ("#1d6b45", "A heartbeat line",
                    f'<path d="M7 26h8l3.5-9 5.5 16 4-12 2.5 5H41" {S}/>'),
    "vpn-check": ("#2c4f7c", "A shield with a tick",
                  f'<path d="M24 9.5l12.5 4.5v9.5c0 8-5.3 13.2-12.5 15.5-7.2-2.3-12.5-7.5-12.5-15.5V14z" fill="{W}"/>'
                  '<path d="M18.5 24.5l4 4 7.5-8.5" fill="none" stroke="#2c4f7c" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>'),
    "watch-stats": ("#4a3a8c", "A bar chart",
                    f'<rect x="12.5" y="25" width="5.5" height="11" rx="1" fill="{W}"/><rect x="21.25" y="18" width="5.5" height="18" rx="1" fill="{W}"/>'
                    f'<rect x="30" y="12" width="5.5" height="24" rx="1" fill="{W}"/><path d="M10 39h28" {s(3)}/>'),
    "watching-now": ("#7a2f8f", "An eye",
                     f'<path d="M7.5 24c4-7 10-10.5 16.5-10.5S36.5 17 40.5 24c-4 7-10 10.5-16.5 10.5S11.5 31 7.5 24z" {S}/>'
                     f'<circle cx="24" cy="24" r="5" fill="{W}"/>'),
    "wizarr": ("#3b5aa0", "An envelope",
               f'<rect x="9" y="13" width="30" height="22" rx="2.5" {S}/><path d="M10 15.5l14 10.5 14-10.5" {S}/>'),
}


def name_of(pid):
    """The plug-in's name, from its manifest, or from tools/examples_src.py before an example's manifest is written."""
    mf = os.path.join(ROOT, pid, "starboard-plugin.json")
    if os.path.isfile(mf):
        return json.load(open(mf, encoding="utf-8"))["name"]
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    from examples_src import EXAMPLES  # noqa: E402
    return EXAMPLES[pid][0]["name"]


def alt(pid, name=None):
    """The logo's alt text: the plug-in's name and "logo", for where the name is not beside it."""
    return f"{name or name_of(pid)} logo"


def svg(pid, name=None):
    colour, _, body = LOGOS[pid]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="48" height="48" role="img">'
            f'<title>{alt(pid, name)}</title><rect width="48" height="48" rx="11" fill="{colour}"/>{body}</svg>\n')


def entry(pid, name=None):
    return {"file": "logo.svg", "alt": alt(pid, name)}


def contrast(hex_a, hex_b=W):
    """WCAG contrast ratio between two colours."""
    def lum(h):
        rgb = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        rgb = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
        return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
    a, b = sorted((lum(hex_a), lum(hex_b)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def with_logo(m, pid):
    """The manifest with its logo field, placed before changes so the file reads in the reference's order."""
    out = {k: v for k, v in m.items() if k not in ("logo", "changes")}
    out["logo"] = entry(pid)
    if "changes" in m:
        out["changes"] = m["changes"]
    return out


def plugins():
    return sorted(d for d in os.listdir(ROOT) if os.path.isfile(os.path.join(ROOT, d, "starboard-plugin.json")))


def main():
    check = "--check" in sys.argv
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    from examples_src import EXAMPLES  # noqa: E402  (make_examples.py writes those manifests)
    cleaner = None
    src = os.environ.get("STARBOARD_SRC", os.path.expanduser("~/src/starboard"))
    if os.path.isfile(os.path.join(src, "starboard", "plugin_logo.py")):
        sys.path.insert(0, src)
        from starboard import plugin_logo as cleaner  # noqa: E402
    stale, problems = [], []
    for pid in plugins():
        if pid not in LOGOS:
            problems.append(f"{pid}: no logo in tools/make_logos.py")
            continue
        colour = LOGOS[pid][0]
        if contrast(colour) < 4.5:
            problems.append(f"{pid}: {colour} has {contrast(colour):.2f} to 1 contrast with white; 4.5 at least")
        data = svg(pid).encode()
        if cleaner:
            try:
                cleaner.clean_svg(data)
            except ValueError as e:
                problems.append(f"{pid}: {e}")
            problems += [f"{pid}: {p}" for p in cleaner.check_entry(entry(pid))]
        path = os.path.join(ROOT, pid, "logo.svg")
        if not os.path.isfile(path) or open(path, "rb").read() != data:
            stale.append(f"{pid}/logo.svg")
            if not check:
                with open(path, "wb") as f:
                    f.write(data)
        if pid in EXAMPLES:
            continue
        mf = os.path.join(ROOT, pid, "starboard-plugin.json")
        m = json.load(open(mf, encoding="utf-8"))
        new = with_logo(m, pid)
        if json.dumps(new) != json.dumps(m):
            stale.append(f"{pid}/starboard-plugin.json")
            if not check:
                with open(mf, "w", encoding="utf-8") as f:
                    json.dump(new, f, indent=1, ensure_ascii=False)
                    f.write("\n")
    for p in problems:
        print(p)
    if check:
        print("Out of date: " + ", ".join(stale) + ". Run python3 tools/make_logos.py" if stale else "Logos up to date")
        return 1 if stale or problems else 0
    print(f"Wrote {len(stale)} file(s); {len(problems)} problem(s)" + ("" if cleaner else "; Starboard's cleaner not found, set STARBOARD_SRC"))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
