#!/usr/bin/env python3
"""Checks the plug-ins help (help/ and each plug-in's README.md) before it is built (DASH-426). Exits 1 on a problem.

- Every plug-in in the catalogue is in one group of help-centre.json and has its eight pages: README.md and the seven
  in help/plugins/<id>/, each starting "# <Name>: <Page>".
- No page is still a placeholder ("still to be written", TODO and the like) and no table cell is left empty.
- Every Problems page and every troubleshooting article starts with a flow chart (a flow block).
- Every link to another file goes somewhere.
- The writing rules of the design system's CONTENT-DESIGN.md: no em dashes, contractions, click, enable or disable,
  screen (page), positions or exclamation marks.
- The developers' pages describe the newest plug-in API any plug-in here needs: when a manifest asks for a newer one
  than the "<!-- plugin-api: 1.14 -->" line in help/developers/plug-in-api.md, update those pages first.

    python3 tools/check_help.py
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
HELP = ROOT / "help"
PAGES = [("install", "Install"), ("settings", "Settings"), ("dashboard-card", "Dashboard card"), ("updates", "Updates"),
         ("accessibility", "Accessibility"), ("problems", "Problems"), ("for-developers", "For developers")]
PLACEHOLDERS = [r"still to be written", r"\bto be written\b", r"\bTODO\b", r"\bTBD\b", r"\bTBC\b", r"lorem ipsum"]
RULES = [
    (r"—", "an em dash"),
    (r"\b(can't|won't|don't|doesn't|isn't|aren't|didn't|wasn't|haven't|hasn't|shouldn't|wouldn't|couldn't|you're|you'll|"
     r"you've|we're|they're|it's|that's|there's|let's|I'm)\b", "a contraction"),
    (r"\b(click|clicking|clicked|tap|tapping)\b", "click or tap (use select)"),
    (r"\b(enable|enables|enabled|disable|disables|disabled|toggle|toggles)\b", "enable, disable or toggle (use activate or deactivate)"),
    (r"\b(turn|turns|turned|turning|switch|switches|switched) (it |them |this |that )?(on|off)\b|\bon or off\b", "turn on or off (use activate or deactivate)"),
    (r"(?<!home )(?<!no )(?<!a )\bscreen\b(?! reader)(?! or keyboard)", "screen (use page)"),
    (r"\b(top right|top left|bottom right|bottom left|on the left|on the right|scroll down|scroll up)\b", "a position"),
    (r"(?<!\[)!(?!\[)", "an exclamation mark"),
    (r"\b(click here|read more)\b", "a vague link"),
]
API_LINE = re.compile(r"<!--\s*plugin-api:\s*([\d.]+)\s*-->")


def words_only(md):
    md = re.sub(r"^```.*?^```[ \t]*$", "", md, flags=re.S | re.M)
    md = re.sub(r"<!--.*?-->", "", md, flags=re.S)
    md = re.sub(r"`[^`\n]*`", "", md)
    md = re.sub(r"\]\([^)]*\)", "]", md)
    md = re.sub(r"https?://\S+", "", md)
    return md


def version(v):
    return tuple(int(x) for x in v.split("."))


def check_page(path, problems, readme=False):
    rel = path.relative_to(ROOT)
    md = path.read_text(encoding="utf-8")
    text = words_only(md)
    for pat in PLACEHOLDERS:
        m = re.search(pat, text, flags=re.I if pat.islower() else 0)
        if m:
            problems.append(f"{rel}: still a placeholder ({m.group(0)})")
    for n, line in enumerate(re.sub(r"^```.*?^```[ \t]*$", "", md, flags=re.S | re.M).splitlines(), 1):
        if line.startswith("|") and not re.match(r"^\|[\s|:-]+\|$", line):
            cells = re.split(r"(?<!\\)\|", line.strip()[1:-1])
            if any(not c.strip() for c in cells):
                problems.append(f"{rel}: a table cell is empty: {line.strip()[:60]}")
    for n, line in enumerate(text.splitlines(), 1):
        for pat, what in RULES:
            if re.search(pat, line, flags=re.I if "I'm" not in pat else 0):
                problems.append(f"{rel}:{n}: {what}: {line.strip()[:90]}")
    for target in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", re.sub(r"^```.*?^```", "", md, flags=re.S | re.M)):
        if re.match(r"^[a-z]+:", target):
            continue
        if not (path.parent / target).resolve().exists():
            problems.append(f"{rel}: the link to {target} goes nowhere")
    return md


def main():
    problems = []
    cfg = json.loads((ROOT / "help-centre.json").read_text())
    cat = {p["id"]: p for p in json.loads((ROOT / "catalogue.json").read_text())["plugins"]}
    grouped = [pid for g in cfg["plugins"]["groups"] for pid in g["ids"]]
    for pid in sorted(set(cat) - set(grouped)):
        problems.append(f"help-centre.json: {pid} is in the catalogue but in no group")
    for pid in sorted({p for p in grouped if grouped.count(p) > 1}):
        problems.append(f"help-centre.json: {pid} is in more than one group")
    for pid, entry in sorted(cat.items()):
        name = entry["name"]
        readme = ROOT / pid / "README.md"
        if not readme.exists():
            problems.append(f"{pid}: no README.md, its Overview page")
        else:
            check_page(readme, problems, readme=True)
        for key, label in PAGES:
            path = HELP / "plugins" / pid / f"{key}.md"
            if not path.exists():
                problems.append(f"{path.relative_to(ROOT)}: missing")
                continue
            md = check_page(path, problems)
            first = md.splitlines()[0] if md else ""
            if first != f"# {name}: {label}":
                problems.append(f"{path.relative_to(ROOT)}: the first line should be '# {name}: {label}'")
            if key == "problems" and "```flow" not in md:
                problems.append(f"{path.relative_to(ROOT)}: a Problems page starts with a flow chart (a flow block)")
    for path in sorted(HELP.rglob("*.md")):
        if path.is_relative_to(HELP / "plugins") or path.name == "HOW-THIS-HELP-IS-WRITTEN.md":
            continue
        md = check_page(path, problems)
        if path.name != "README.md":
            if not re.search(r"<!--\s*help:\s*[\w-]+\s*/\s*[\w-]+\s*-->", md):
                problems.append(f"{path.relative_to(ROOT)}: no <!-- help: <area> / <group> --> line under its first line")
            if md.splitlines()[0].rstrip().endswith("troubleshooting") and "```flow" not in md:
                problems.append(f"{path.relative_to(ROOT)}: a troubleshooting article starts with a flow chart (a flow block)")
    # The developers' pages describe the newest plug-in API any plug-in here asks for.
    api_page = HELP / "developers" / "plug-in-api.md"
    m = API_LINE.search(api_page.read_text()) if api_page.exists() else None
    if not m:
        problems.append("help/developers/plug-in-api.md: no <!-- plugin-api: x.y --> line saying which plug-in API it describes")
    else:
        described = version(m.group(1))
        for path in sorted(ROOT.glob("*/starboard-plugin.json")):
            want = re.search(r">=\s*([\d.]+)", json.loads(path.read_text()).get("starboard_api", ""))
            if want and version(want.group(1))[:2] > described[:2]:
                problems.append(f"{path.parent.name} needs plug-in API {want.group(1)}, newer than the {m.group(1)} the developers' "
                                "pages describe: update help/developers first, then the plugin-api line")
    for p in problems:
        print(p)
    print(f"{len(cat)} plug-ins checked, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
