"""Loads a plug-in's app.py as a module with its own settings and /data in a temporary folder, without serving."""
import importlib.util
import json
import os
import sys
import tempfile

sys.dont_write_bytecode = True  # no __pycache__ in the plug-in folders, which go into the zips as they are
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
STARBOARD_SRC = os.environ.get("STARBOARD_SRC", os.path.expanduser("~/src/starboard"))


def load(pid, values=None, jellyfin=None):
    tmp = tempfile.TemporaryDirectory()
    run, data = os.path.join(tmp.name, "run"), os.path.join(tmp.name, "data")
    os.makedirs(run)
    os.makedirs(data)
    with open(os.path.join(run, "settings.json"), "w") as f:
        json.dump(values or {}, f)
    with open(os.path.join(run, "jellyfin.json"), "w") as f:
        json.dump(jellyfin or {"url": "http://jellyfin.invalid:8096", "api_key": "jf-key"}, f)
    with open(os.path.join(run, "key"), "w") as f:
        f.write("sbk_test")
    os.environ["PLUGIN_RUN"], os.environ["PLUGIN_DATA"] = run, data
    sys.path.insert(0, os.path.join(ROOT, "_shared"))
    for name in ("sbplugin", f"app_{pid.replace('-', '_')}"):
        sys.modules.pop(name, None)
    spec = importlib.util.spec_from_file_location(f"app_{pid.replace('-', '_')}", os.path.join(ROOT, pid, "app.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sys.path.pop(0)
    mod._tmp, mod._run, mod._data = tmp, run, data

    def set_values(**more):
        with open(os.path.join(run, "settings.json")) as f:
            v = json.load(f)
        v.update(more)
        with open(os.path.join(run, "settings.json"), "w") as f:
            json.dump(v, f)
    mod._set = set_values
    return mod


def starboard_cleaners():
    """Starboard's own card and screen checks, when its source is on this computer; else None."""
    if not os.path.isdir(os.path.join(STARBOARD_SRC, "starboard")):
        return None
    sys.path.insert(0, STARBOARD_SRC)
    from starboard import plugin_cards, plugin_custom
    return plugin_cards, plugin_custom


def manifest(pid):
    with open(os.path.join(ROOT, pid, "starboard-plugin.json"), encoding="utf-8") as f:
        return json.load(f)
