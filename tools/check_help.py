#!/usr/bin/env python3
"""Checks the plug-ins help (help/ and each plug-in's README.md) before it is built (DASH-426). Exits 1 on a problem.

- Every plug-in in the catalogue is in one group of help-centre.json and has its eight pages: README.md and the seven
  in help/plugins/<id>/, each starting "# <Name>: <Page>".
- No page is still a placeholder ("still to be written", TODO and the like) and no table cell is left empty.
- Every Problems page and every troubleshooting article starts with a flow chart (a flow block).
- Every link to another file goes somewhere.
- The writing rules of the design system's CONTENT-DESIGN.md: no em dashes, contractions, click, enable or disable,
  screen (page), positions or exclamation marks; and the banned words of HELP-WRITING.md section 9 (owner, 17 November
  2026: no "see" or "look"): see, look, above, below, please, just, simply, easy, advanced, type for entering and
  drive for a disk.
- The same banned words in the other text people read: every manifest's labels, hints, descriptions, card texts and
  newest changes, the strings in each app.py and _shared/sbplugin.py, and help-centre.json. A genuine exception, such
  as another app's label quoted exactly, goes in ALLOWED with its reason.
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
# HELP-WRITING.md section 9 and CONTENT-DESIGN.md 2.6, 2.7, 2.15 and 2.18 (design system audit, 17 November 2026).
WORDS = [
    (r"\b(see|sees|seeing|seen|look|looks|looking|looked)\b", "see or look (use find, check, read or show)"),
    (r"\b(above|below)\b", "above or below (name the place)"),
    (r"\b(please|just|simply|easy|easily|easier|advanced)\b", "a filler or difficulty word"),
    (r"\btyping\b|(?<!every )(?<!each )(?<!picture )(?<!file )(?<!card )\b(type|types|typed)\b(?= (it|them|in|into|your|the|its|a|an|this|that|his|her|their)\b)", "type (use enter)"),
    (r"\b(drive|drives)\b", "drive (use disk)"),
]
RULES += WORDS
# Genuine exceptions: (file, words on the line, reason). Keep each one short and give the reason.
RENAMED = "the old label, quoted exactly where What is new says what it was renamed to"
ALLOWED = [(f, w, RENAMED) for f, w in [
    ("audio-description/starboard-plugin.json", "**Look for described titles now** is now"),
    ("help/plugins/audio-description/updates.md", "**Look for described titles now** is now"),
    ("audio-description-tracks/starboard-plugin.json", "**Look in the folder now** is now"),
    ("help/plugins/audio-description-tracks/updates.md", "**Look in the folder now** is now"),
    ("direct-play/starboard-plugin.json", "**Look at the library now** is now"),
    ("help/plugins/direct-play/updates.md", "**Look at the library now** is now"),
    ("picture-shrinker/starboard-plugin.json", "**Just shrink, with no backup** is now"),
    ("help/plugins/picture-shrinker/updates.md", "**Just shrink, with no backup** is now"),
]]
API_LINE = re.compile(r"<!--\s*plugin-api:\s*([\d.]+)\s*-->")


def blank(m):
    """The same number of lines, empty, so line numbers in the problems stay true."""
    return "\n" * m.group(0).count("\n")


def words_only(md):
    # A flow chart's questions and answers are read by people, so a flow block is checked; other code blocks are not.
    md = re.sub(r"^```flow[ \t]*$(.*?)^```[ \t]*$", lambda m: re.sub(r"#[\w-]+", "", m.group(1)), md, flags=re.S | re.M)
    md = re.sub(r"^```.*?^```[ \t]*$", blank, md, flags=re.S | re.M)
    md = re.sub(r"<!--.*?-->", blank, md, flags=re.S)
    md = re.sub(r"`[^`\n]*`", "", md)
    md = re.sub(r"\]\([^)]*\)", "]", md)
    md = re.sub(r"https?://\S+", "", md)
    return md


def allowed(rel, line):
    return any(str(rel) == f and w in line for f, w, _ in ALLOWED)


# Manifest keys whose values are code, addresses or settings, not words people read.
NOT_WORDS = {"id", "key", "path", "image", "file", "homepage", "support_url", "starboard_api", "permissions", "needs", "env",
             "volumes", "network", "type", "health", "choices_path", "manifest", "version", "date", "status", "state", "icon",
             "unit_key", "group_key", "events", "daily", "time", "default", "colours", "fonts", "css", "font", "vars"}


def strings(node, where=""):
    """Every string in a manifest that people read, with where it is."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k in NOT_WORDS:
                continue
            if k == "changes" and isinstance(v, list):
                v = v[:1]  # the newest version's changes: the earlier ones are released history (exception 8)
            yield from strings(v, f"{where}.{k}" if where else k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from strings(v, f"{where}[{i}]")
    elif isinstance(node, str) and re.search(r"[A-Za-z]{2}", node) and not re.match(r"^[a-z0-9_:/.-]+$", node):
        yield where, node


def app_strings(path):
    """The strings in a Python file that reach people: every string of two or more words, less the docstrings."""
    import ast
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                docs.add(id(first.value))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docs and " " in node.value.strip():
            yield node.lineno, node.value


def check_words(rel, where, text, problems):
    for pat, what in WORDS + RULES[:5]:
        if re.search(pat, text, flags=re.I if "I'm" not in pat else 0) and not allowed(rel, text):
            problems.append(f"{rel}:{where}: {what}: {text.strip()[:90]}")


def check_other_text(problems):
    """The banned words in the manifests, the apps and help-centre.json."""
    for path in sorted(ROOT.glob("*/starboard-plugin.json")):
        rel = path.relative_to(ROOT)
        for where, text in strings(json.loads(path.read_text(encoding="utf-8"))):
            check_words(rel, where, text, problems)
    for path in sorted(list(ROOT.glob("*/app.py")) + [ROOT / "_shared" / "sbplugin.py"]):
        rel = path.relative_to(ROOT)
        for line, text in app_strings(path):
            check_words(rel, line, text, problems)
    for where, text in strings(json.loads((ROOT / "help-centre.json").read_text(encoding="utf-8"))):
        check_words(pathlib.Path("help-centre.json"), where, text, problems)


def released_history(path, md):
    """An Updates page with the "What is new" of released versions left out: released history stays as it was written
    (design system audit, exception 8). The newest version's section is checked."""
    manifest = ROOT / path.parent.name / "starboard-plugin.json"
    if path.name != "updates.md" or not manifest.exists():
        return md
    newest = json.loads(manifest.read_text(encoding="utf-8"))["version"]
    return re.sub(r"^## What is new in (?!" + re.escape(newest) + r"\s*$)[^\n]*\n.*?(?=^## |\Z)", blank, md, flags=re.S | re.M)


def version(v):
    return tuple(int(x) for x in v.split("."))


def check_page(path, problems, readme=False):
    rel = path.relative_to(ROOT)
    md = path.read_text(encoding="utf-8")
    text = words_only(released_history(path, md))
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
            if re.search(pat, line, flags=re.I if "I'm" not in pat else 0) and not allowed(rel, line):
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
        if (ROOT / pid / "HELP.md").exists():
            check_page(ROOT / pid / "HELP.md", problems)
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
    check_other_text(problems)
    for p in problems:
        print(p)
    print(f"{len(cat)} plug-ins checked, {len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
