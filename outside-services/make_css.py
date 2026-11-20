#!/usr/bin/env python3
"""Makes ds.css for the status page from the TRex Design System (github.com/TheMightyTRex/design-system): its
tokens.css and components.css as they are, so the page's chips, tables, cards and skip link are the library's own.
Run it after the design system changes, with the design system checked out beside it:

    python3 outside-services/make_css.py ~/src/design-system
"""
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent


def main(src):
    src = pathlib.Path(os.path.expanduser(src))
    commit = subprocess.run(["git", "-C", str(src), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    head = (f"/* The TRex Design System's tokens.css and components.css at {commit or 'an unknown commit'}, copied for the\n"
            "   Uptime and status page by make_css.py. Do not change this copy: change the design system and run it again. */\n")
    text = head + (src / "tokens.css").read_text(encoding="utf-8") + "\n" + (src / "components.css").read_text(encoding="utf-8")
    (HERE / "ds.css").write_text(text, encoding="utf-8")
    font = src / "fonts" / "atkinson-hyperlegible-next.woff2"
    (HERE / "font.woff2").write_bytes(font.read_bytes())
    print(f"wrote ds.css ({len(text):,} characters) and font.woff2 from {commit}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "~/src/design-system")
