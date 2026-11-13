#!/usr/bin/env python3
"""Runs an app plug-in (DASH-411) exactly as Starboard writes it, hardened (read only, no capabilities, its own
user, its memory limit), but on closed networks with no way out and no port on the home network, then checks its web
page answers and measures it at rest. Nothing real is touched: every container, network and folder is named bench-app-.

    STARBOARD_SRC=~/src/starboard-night-app-plugins python3 tools/app_check.py jellystat [navidrome ...]

Settings: SETTLE (seconds before measuring, default 120), SAMPLES (default 36, one each 5 seconds), WORK (where the
test folders go, default /mnt/pool/build-cache/app-check), OUT (where the figures go). Each app's folders are left in
WORK for a look afterwards; nothing is deleted.
"""
import json
import os
import re
import statistics
import subprocess
import sys
import time

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.environ.get("STARBOARD_SRC", os.path.expanduser("~/src/starboard")))
from starboard import plugins  # noqa: E402

# A local disk: SQLite and PostgreSQL refuse the pool's FUSE file system ("disk I/O error"), as they would in real use.
WORK = os.environ.get("WORK", os.path.expanduser("~/.cache/starboard-app-check"))
OUT = os.environ.get("OUT", os.path.expanduser("~/Documents/Claude/starboard/app-plugins-2026-11-13"))
SETTLE = int(os.environ.get("SETTLE", "120"))
SAMPLES = int(os.environ.get("SAMPLES", "36"))
PROBE = os.environ.get("PROBE_IMAGE", "ghcr.io/themightytrex/starboard-plugin-examples:1.1.0")
STAMP = time.strftime("%Y%m%d-%H%M%S")


def sh(*args, check=False, **kw):
    return subprocess.run(list(args), capture_output=True, text=True, check=check, **kw)


def render(pid, manifest, base):
    """Starboard's own Compose file for the plug-in, renamed and closed: no ports, every network internal."""
    media = os.path.join(base, "media")
    for sub in ("movies", "tv", "music", "books", "comics", "audiobooks"):
        os.makedirs(os.path.join(media, sub), exist_ok=True)
    plugin_dir = os.path.join(base, "plugin")
    os.makedirs(os.path.join(plugin_dir, "run"), exist_ok=True)
    run = os.path.join(plugin_dir, "run")
    json.dump({}, open(os.path.join(run, "settings.json"), "w"))
    open(os.path.join(run, "key"), "w").write("sbk_test")
    json.dump({"url": "http://host.docker.internal:8096", "api_key": "0" * 32}, open(os.path.join(run, "jellyfin.json"), "w"))
    for f in os.listdir(run):
        os.chmod(os.path.join(run, f), 0o644)
    extra = {"ports": {}, "secrets": {n: os.urandom(24).hex() for n in plugins.secret_names(manifest)},
             "jellyfin": {"url": "http://host.docker.internal:8096", "api_key": "0" * 32}}
    text = plugins.compose(manifest, plugin_dir, media, None, media_user=os.environ.get("MEDIA_USER", "1000:1000"), extra=extra)
    text = text.replace(f"plugin-{pid}", f"bench-app-{pid}").replace("starboard.plugin:", "bench.plugin:")
    text = text.replace("  lan:\n    driver: bridge", "  lan:\n    internal: true")
    path = os.path.join(base, "compose.yaml")
    open(path, "w").write(text)
    json.dump(extra["secrets"], open(os.path.join(base, "secrets.json"), "w"))
    return path, plugin_dir


def prepare(manifest, plugin_dir):
    """What Starboard's helper does before a start: each data folder made and given to the container's user."""
    cmds = []
    for c in manifest["containers"]:
        vols = c.get("volumes") or []
        subs = [v.split(":", 1)[0][5:] for v in vols if re.match(plugins.DATA_AT, v) and v.startswith("data/")]
        if "data" not in vols and not any(re.match(plugins.DATA_AT, v) for v in vols):
            continue
        user = c.get("user") or "10001:10001"
        user = os.environ.get("MEDIA_USER", "1000:1000") if user == "media" else user  # plug-in API 1.12
        d = f"/w/data/{c['name']}"
        cmds.append(f"mkdir -p {d} && chown {user} {d} && chmod 700 {d}")
        made = json.load(open(os.path.join(os.path.dirname(plugin_dir), "secrets.json")))
        for fname, text in (c.get("files") or {}).items():
            import base64
            body = base64.b64encode(plugins._fill(text, {"secrets": made}).encode()).decode()
            cmds.append(f"echo {body} | base64 -d > {d}/{fname} && chown {user} {d}/{fname} && chmod 600 {d}/{fname}")
        cmds += [f"mkdir -p {d}/{s} && chown {user} {d}/{s}" for s in subs]
    if cmds:
        sh("docker", "run", "--rm", "-v", f"{plugin_dir}:/w", "alpine:3.21", "sh", "-c", " && ".join(cmds), check=True)


def probe(pid, manifest):
    """The first published container's page, asked from a container on the plug-in's own network."""
    for c in manifest["containers"]:
        if c.get("publish") and c.get("port"):
            url = f"http://bench-app-{pid}-{c['name']}:{c['port']}/"
            code = ("import urllib.request,sys\n"
                    "try:\n r=urllib.request.urlopen(sys.argv[1],timeout=10);print(r.status)\n"
                    "except Exception as e:\n print(getattr(e,'code',None) or e)")
            r = sh("docker", "run", "--rm", "--network", f"bench-app-{pid}", "--entrypoint", "python3", PROBE, "-c", code, url)
            return url, (r.stdout.strip() or r.stderr.strip()[-200:])
    return None, "no page"


def mib(text):
    found = re.match(r"([\d.]+)\s*([KMG]i?B|B)", text)
    if not found:
        return 0.0
    num, unit = found.groups()
    return float(num) * {"KiB": 1 / 1024, "MiB": 1, "GiB": 1024, "kB": 1 / 1024, "MB": 1, "GB": 1024, "B": 0}.get(unit, 1)


def measure(names):
    rows = {n: {"mem": [], "cpu": [], "pids": []} for n in names}
    for _ in range(SAMPLES):
        out = sh("docker", "stats", "--no-stream", "--format", "{{.Name}} {{.CPUPerc}} {{.MemUsage}} {{.PIDs}}", *names).stdout
        for line in out.splitlines():
            parts = line.split()
            if parts and parts[0] in rows:
                rows[parts[0]]["cpu"].append(float(parts[1].rstrip("%")))
                rows[parts[0]]["mem"].append(mib(parts[2]))
                rows[parts[0]]["pids"].append(int(parts[-1]))
        time.sleep(5)
    return {n: {"memory_median": round(statistics.median(r["mem"]), 1), "memory_peak": round(max(r["mem"]), 1),
                "cpu_median": round(statistics.median(r["cpu"]), 2), "cpu_peak": round(max(r["cpu"]), 2),
                "threads": max(r["pids"])} for n, r in rows.items() if r["mem"]}


def check(pid):
    manifest = json.load(open(os.path.join(ROOT, pid, "starboard-plugin.json")))
    if os.environ.get("APP_IMAGE"):  # a local build of a plug-in's own helper image, before it is published
        for c in manifest["containers"]:
            if "themightytrex" in c["image"]:
                c["image"] = os.environ["APP_IMAGE"]
    base = os.path.join(WORK, f"{pid}-{STAMP}")
    os.makedirs(base, exist_ok=True)
    path, plugin_dir = render(pid, manifest, base)
    prepare(manifest, plugin_dir)
    project = f"bench-app-{pid}"
    up = sh("docker", "compose", "-p", project, "-f", path, "up", "-d")
    result = {"plugin": pid, "version": manifest["version"], "up": up.returncode == 0, "up_said": (up.stderr or up.stdout)[-400:]}
    try:
        _run(pid, manifest, project, up, result)
    finally:
        sh("docker", "compose", "-p", project, "-f", path, "down")
    with open(os.path.join(OUT, "results.jsonl"), "a") as f:
        f.write(json.dumps({**result, "at": STAMP}) + "\n")
    print(json.dumps(result, indent=1))
    return result


def _run(pid, manifest, project, up, result):
    if up.returncode == 0:
        time.sleep(SETTLE)
        names = [f"{project}-{c['name']}" for c in manifest["containers"]]
        result["url"], result["answer"] = probe(pid, manifest)
        result["containers"] = measure(names)
        result["status"] = {n: sh("docker", "inspect", n, "--format", "{{.State.Status}} restarts={{.RestartCount}} exit={{.State.ExitCode}}").stdout.strip() for n in names}
        os.makedirs(os.path.join(OUT, "logs"), exist_ok=True)
        for n in names:
            log = sh("docker", "logs", "--tail", "300", n)
            open(os.path.join(OUT, "logs", f"{n}.txt"), "w").write(log.stdout + log.stderr)
        result["memory_total"] = round(sum(c["memory_median"] for c in result["containers"].values()), 1)
        result["cpu_total"] = round(sum(c["cpu_median"] for c in result["containers"].values()), 2)


if __name__ == "__main__":
    bad = 0
    for name in sys.argv[1:]:
        r = check(name)
        bad += 0 if r.get("up") and str(r.get("answer", "")).startswith(("2", "3", "401")) else 1
    sys.exit(1 if bad else 0)
