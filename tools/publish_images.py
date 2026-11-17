"""Pins each plug-in image that GitHub has built to its digest, so the catalogue can offer it (owner, 17 November 2026:
"Yes, automate it").

For every image this repository builds (the examples' shared image and each app plug-in's own), it asks the registry
for the image under the tag the build used, reads the commit the image was built from (the
org.opencontainers.image.revision label) and pins the digest only when the files that go into the image are the same
at that commit and now. An image built from older files, or with no revision label, is left as it is and said.

Then tools/make_examples.py and tools/make_zips.py remake the catalogue and the zips (the workflow
.github/workflows/publish.yml runs them, the tests and the checks, and opens a pull request).

    python3 tools/publish_images.py            pin what can be pinned, and say what was done
    python3 tools/publish_images.py --check    say what would be pinned; change nothing
"""
import glob
import json
import os
import re
import subprocess
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOWS = os.path.join(ROOT, ".github", "workflows")
OWNER = "themightytrex"
ACCEPT = ", ".join(["application/vnd.oci.image.index.v1+json", "application/vnd.docker.distribution.manifest.list.v2+json",
                    "application/vnd.oci.image.manifest.v1+json", "application/vnd.docker.distribution.manifest.v2+json"])
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


def _paths(workflow_text):
    """The files that go into the image: the push paths the workflow builds on, less the workflow file itself."""
    m = re.search(r"paths:\s*(\[[^\]]*\])", workflow_text)
    if not m:
        return []
    return [p for p in json.loads(m.group(1)) if not p.startswith(".github/")]


def targets():
    """[{name, repo, tag, paths, pin}] for every image a workflow here builds. `pin` is where its digest is kept:
    ("file", path) for the examples, or ("manifest", path) for an app plug-in."""
    out = []
    for wf in sorted(glob.glob(os.path.join(WORKFLOWS, "*.yml"))):
        text = open(wf, encoding="utf-8").read()
        m = re.search(r"ghcr\.io/themightytrex/(starboard-plugin-[a-z0-9-]+):\$\{\{", text)
        if not m:
            continue
        repo = m.group(1)
        ctx = re.search(r"context:\s*(\S+)", text)
        context = ctx.group(1) if ctx else "."
        if context == ".":  # the examples' shared image, tagged with IMAGE_VERSION
            sys.path.insert(0, os.path.join(ROOT, "tools"))
            import examples_src  # noqa: E402
            out.append({"name": "Example plug-ins", "repo": repo, "tag": examples_src.IMAGE_VERSION, "paths": _paths(text),
                        "pin": ("file", os.path.join(ROOT, "tools", "examples-digest.txt"))})
        else:
            manifest = os.path.join(ROOT, context, "starboard-plugin.json")
            data = json.load(open(manifest, encoding="utf-8"))
            out.append({"name": data.get("name", context), "repo": repo, "tag": data["version"], "paths": _paths(text),
                        "pin": ("manifest", manifest)})
    return out


def _get(url, token, accept=ACCEPT, head=False):
    req = urllib.request.Request(url, method="HEAD" if head else "GET",
                                 headers={"Authorization": f"Bearer {token}", "Accept": accept})
    with urllib.request.urlopen(req, timeout=30) as r:  # nosec B310: ghcr.io only
        return r.headers, (b"" if head else r.read())


def registry(repo, tag):
    """(digest, revision) of ghcr.io/themightytrex/<repo>:<tag>, or (None, None) when there is no such tag."""
    with urllib.request.urlopen(f"https://ghcr.io/token?scope=repository:{OWNER}/{repo}:pull", timeout=30) as r:  # nosec B310
        token = json.load(r)["token"]
    base = f"https://ghcr.io/v2/{OWNER}/{repo}"
    try:
        headers, body = _get(f"{base}/manifests/{tag}", token)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None, None
        raise
    digest = headers.get("Docker-Content-Digest")
    doc = json.loads(body)
    if "manifests" in doc:  # an index: read the first real platform's manifest for the labels
        first = next(m for m in doc["manifests"] if (m.get("platform") or {}).get("os") != "unknown")
        _, body = _get(f"{base}/manifests/{first['digest']}", token)
        doc = json.loads(body)
    _, cfg = _get(f"{base}/blobs/{doc['config']['digest']}", token, accept="application/octet-stream")
    labels = (json.loads(cfg).get("config") or {}).get("Labels") or {}
    return digest, labels.get("org.opencontainers.image.revision")


def same_files(revision, paths):
    """True when every file that goes into the image is the same at `revision` and in the working copy."""
    if not revision or not paths:
        return False
    if subprocess.run(["git", "cat-file", "-e", f"{revision}^{{commit}}"], cwd=ROOT, capture_output=True).returncode:
        return False
    specs = [f":(glob){p}" for p in paths]
    return subprocess.run(["git", "diff", "--quiet", revision, "--", *specs], cwd=ROOT).returncode == 0


def pinned(t):
    kind, path = t["pin"]
    text = open(path, encoding="utf-8").read() if os.path.isfile(path) else ""
    if kind == "file":
        return text.strip()
    m = re.search(rf"ghcr\.io/themightytrex/{re.escape(t['repo'])}@(sha256:[0-9a-f]{{64}})", text)
    return m.group(1) if m else ""


def pin(t, digest):
    kind, path = t["pin"]
    if kind == "file":
        open(path, "w", encoding="utf-8").write(digest + "\n")
        return
    text = open(path, encoding="utf-8").read()
    new = re.sub(rf'(ghcr\.io/themightytrex/{re.escape(t["repo"])})(@sha256:[0-9a-f]{{64}}|:[A-Za-z0-9._-]+)?(?=")',
                 rf"\1@{digest}", text)
    open(path, "w", encoding="utf-8").write(new)


def main(argv):
    check = "--check" in argv
    changed = []
    for t in targets():
        have = pinned(t)
        digest, revision = registry(t["repo"], t["tag"])
        label = f"{t['name']} ({t['repo']}:{t['tag']})"
        if not digest or not DIGEST.match(digest):
            print(f"{label}: not built yet")
        elif digest == have:
            print(f"{label}: already pinned")
        elif not revision:
            print(f"{label}: built without a revision label, so it cannot be matched to these files; left as it is")
        elif not same_files(revision, t["paths"]):
            print(f"{label}: built from {revision[:7]}, but its files have changed since; waiting for the next build")
        else:
            print(f"{label}: {'would pin' if check else 'pinned'} {digest[:19]} (built from {revision[:7]})")
            if not check:
                pin(t, digest)
            changed.append(t["name"])
    print(f"{len(changed)} image(s) {'to pin' if check else 'pinned'}" + (f": {', '.join(changed)}" if changed else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
