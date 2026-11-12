"""Starts the example named by the EXAMPLE environment setting: /app/<EXAMPLE>/app.py."""
import os
import re
import runpy
import sys

name = os.environ.get("EXAMPLE", "")
path = f"/app/{name}/app.py"
if not re.match(r"^[a-z0-9-]{1,40}$", name) or not os.path.isfile(path):
    sys.exit(f"No example called {name!r}: set EXAMPLE to one of " + ", ".join(sorted(d for d in os.listdir("/app") if os.path.isfile(f"/app/{d}/app.py"))))
runpy.run_path(path, run_name="__main__")
