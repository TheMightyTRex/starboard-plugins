"""The plug-in's own page Choose a style for my channel (0.10.0): the server side of Import a kit (and, from the next
change, Make a style here). It is a wizard (the design system's docs/WIZARD.md), drawn by style.html and style.js.

Work lives in /data/styles/<kit>/: in/ holds the files as added, pack/ the branding being made, state.json what the page
shows. A kit is kept for a day, then removed. One build runs at a time, with one FFmpeg thread at the lowest priority,
and never while a channel is being watched (a channel that starts to play stops it at once).
"""
import json
import os
import re
import secrets
import shutil
import tempfile
import threading
import time

import draw
import flash
import kit
import pack
import sbplugin
import recipes

KEEP_SECONDS = 86400
MOST_KITS = 4
MOST_TOTAL = 400 * 1024 * 1024
_ids = re.compile(r"^[0-9a-f]{12}$")
_job_lock = threading.Lock()
_ctx = {}


def bind(**things):
    """The few things the page needs from app.py: state, save, lock, pack_dir, drop_pack, playing."""
    _ctx.update(things)


def root():
    return os.path.join(sbplugin.DATA, "styles")


def kit_dir(kid):
    if not _ids.match(str(kid or "")):
        raise ValueError("That kit is not here any more. Start again")
    path = os.path.join(root(), kid)
    if not os.path.isdir(path):
        raise ValueError("That kit is not here any more. Start again")
    return path


def _read(kid):
    with open(os.path.join(kit_dir(kid), "state.json"), encoding="utf-8") as f:
        return json.load(f)


def _write(kid, st):
    path = os.path.join(kit_dir(kid), "state.json")
    with open(path + ".new", "w", encoding="utf-8") as f:
        json.dump(st, f)
    os.replace(path + ".new", path)


def tidy():
    """Kits older than a day go, and only the newest few stay."""
    try:
        names = [n for n in os.listdir(root()) if _ids.match(n)]
    except OSError:
        return
    dated = sorted(((os.path.getmtime(os.path.join(root(), n)), n) for n in names), reverse=True)
    for i, (when, n) in enumerate(dated):
        if i >= MOST_KITS or time.time() - when > KEEP_SECONDS:
            shutil.rmtree(os.path.join(root(), n), ignore_errors=True)


def new_kit():
    tidy()
    kid = secrets.token_hex(6)
    os.makedirs(os.path.join(root(), kid, "in"))
    st = {"id": kid, "name": "", "colours": ["#10202C", "#1B8A7F"], "files": [], "skipped": [], "result": None, "job": {}, "ready": "", "pack_origin": "",
          "pack_link": "", "mode": "import", "style": "", "logo": "", "still": False}
    _write(kid, st)
    return st


def used_bytes(kid):
    total = 0
    for base, _, files in os.walk(os.path.join(kit_dir(kid), "in")):
        total += sum(os.path.getsize(os.path.join(base, f)) for f in files)
    return total


def public(st):
    """What the page is told: the kit, with each file's choices, and what a person may answer."""
    files = [dict(f, roles=kit.roles_for(f["kind"])) for f in st["files"]]
    return {**st, "files": files, "styles": [{"id": k, "name": v["name"], "blurb": v["blurb"]} for k, v in recipes.STYLES.items()], "roles": kit.ROLES, "origins": kit.ORIGINS, "reminder": kit.REMINDER,
            "playing": bool(_ctx["playing"]()), "version": 1}


def state_of(kid):
    return public(_read(kid)) if kid else {}


def overview(kid=""):
    chans = [{"id": c["id"], "name": c["name"]} for c in (_ctx["state"]().get("channels") or [])]
    return {"kit": state_of(kid) if kid else None, "channels": chans, "busy": _job_lock.locked(), "playing": bool(_ctx["playing"]())}


def upload(kid, name, length, rfile):
    """One file or one zip, streamed to disk. Raises ValueError with a sentence."""
    base = kit.safe_name(name)
    ext = kit.extension(base)
    zipped = ext == "zip"
    most = pack.MAX_ZIP if zipped else kit.MAX_FILE
    if length <= 0:
        raise ValueError("That file is empty")
    if length > most:
        raise ValueError(f"{base} is over {most // (1024 * 1024)} MB, the most for {'a zip' if zipped else 'one file'}")
    if not kid:
        st = new_kit()
        kid = st["id"]
    d = kit_dir(kid)
    st = _read(kid)
    if st["job"].get("running"):
        raise ValueError("The branding is being made. Wait for it to finish")
    if st.get("mode") == "make" and zipped:
        raise ValueError("Add the logo as a PNG, not a zip")
    if len(st["files"]) >= kit.MAX_FILES:
        raise ValueError(f"A kit holds up to {kit.MAX_FILES} files")
    if used_bytes(kid) + length > MOST_TOTAL:
        raise ValueError("The kit is over 400 MB. Take some files out first")
    folder = os.path.join(d, "in")
    target = kit.unique(folder, base)
    path = os.path.join(folder, target)
    left = length
    with open(path, "wb") as f:
        while left > 0:
            chunk = rfile.read(min(1 << 20, left))
            if not chunk:
                break
            f.write(chunk)
            left -= len(chunk)
    if left:
        os.remove(path)
        raise ValueError(f"{base} did not arrive whole. Add it again")
    try:
        if zipped:
            _add_zip(st, d, path)
        else:
            _add_file(st, folder, target)
    finally:
        if zipped:
            with_suppress_remove(path)
        _write(kid, st)
    return overview(kid)


def with_suppress_remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def _add_file(st, folder, name):
    path = os.path.join(folder, name)
    try:
        info = kit.inspect(path)
    except kit.KitError as e:
        os.remove(path)
        raise ValueError(f"{name}: {e}") from None
    if st.get("mode") == "make":  # a style takes one thing from you: a logo, a PNG with a clear background
        if info["kind"] != "still" or kit.extension(name) != "png" or pack.has_transparency(path) is not True:
            os.remove(path)
            raise ValueError(f"{name}: a logo is a PNG with a clear background. Export it again with the background turned off")
        if st.get("logo") and st["logo"] != name:
            with_suppress_remove(os.path.join(folder, st["logo"]))
        st["logo"] = name
        return
    given = (st.get("given") or {}).get(name) or {}
    st["files"].append({"name": name, "kind": info["kind"], "dur": info["dur"], "w": info["w"], "h": info["h"], "audio": info["audio"],
                        "role": kit.guess_role(name, info), "origin": given.get("origin", ""), "link": given.get("link", ""), "flash": ""})


def _add_zip(st, d, zpath):
    folder = os.path.join(d, "in")
    if kit.has_pack_json(zpath):
        dest = os.path.join(d, "ready")
        shutil.rmtree(dest, ignore_errors=True)
        try:
            pack.unpack(zpath, dest)
        except pack.PackError as e:
            raise ValueError(f"The zip cannot be used: {e}"[:300]) from None
        st["ready"] = "pack"
        st["files"] = []
        doc = {}
        try:
            with open(os.path.join(dest, "pack.json"), encoding="utf-8") as f:
                doc = json.load(f)
        except (OSError, ValueError):
            pass
        st["name"] = st["name"] or kit.draw.clean_words(doc.get("name")) or "My channel"
        return
    try:
        got = kit.unzip_into(zpath, folder)
    except kit.KitError as e:
        raise ValueError(str(e)[:300]) from None
    st["skipped"] = (st.get("skipped") or [])[:20] + got["skipped"][:20]
    if got["kit"]:
        try:
            doc = kit.read_kit_json(got["kit"])
        except kit.KitError as e:
            st["skipped"].append(f"kit.json: {e}")
            doc = {"files": {}}
        st["name"] = st["name"] or doc.get("name", "")
        if doc.get("colours"):
            st["colours"] = doc["colours"]
        st.setdefault("given", {}).update(doc.get("files", {}))
    for name in got["saved"]:
        try:
            _add_file(st, folder, name)
        except ValueError as e:
            st["skipped"].append(str(e)[:120])


def remove_file(kid, name):
    st = _read(kid)
    if st["job"].get("running"):
        raise ValueError("The branding is being made. Wait for it to finish")
    st["files"] = [f for f in st["files"] if f["name"] != name]
    with_suppress_remove(os.path.join(kit_dir(kid), "in", kit.safe_name(name)))
    st["result"] = None
    _write(kid, st)


def op(body):
    """A change from the page: set, remove, build, use or discard."""
    what = body.get("op")
    kid = str(body.get("kit") or "")
    if what == "new":
        return overview(new_kit()["id"])
    if what == "discard":
        shutil.rmtree(kit_dir(kid), ignore_errors=True)
        return overview("")
    if what == "remove":
        remove_file(kid, str(body.get("name") or ""))
        return overview(kid)
    if what == "set":
        st = _read(kid)
        if st["job"].get("running"):
            raise ValueError("The branding is being made. Wait for it to finish")
        if body.get("mode") in ("import", "make"):
            st["mode"] = body["mode"]
        if body.get("style") in recipes.STYLES:
            st["style"] = body["style"]
        if "still" in body:
            st["still"] = bool(body["still"])
        if body.get("drop_logo"):
            with_suppress_remove(os.path.join(kit_dir(kid), "in", kit.safe_name(st.get("logo") or "")))
            st["logo"] = ""
        if "name" in body:
            st["name"] = draw.clean_words(body.get("name"))
        if isinstance(body.get("colours"), list) and len(body["colours"]) == 2:
            st["colours"] = [draw.colour(c, old) for c, old in zip(body["colours"], st["colours"])]
        if "pack_origin" in body:
            st["pack_origin"] = body["pack_origin"] if body["pack_origin"] in kit.ORIGINS else ""
            st["pack_link"] = kit.link_of(body.get("pack_link"))
        for given in body.get("files") or []:
            f = next((x for x in st["files"] if x["name"] == given.get("name")), None)
            if not f:
                continue
            if given.get("role") in kit.roles_for(f["kind"]):
                f["role"] = given["role"]
            if "origin" in given:
                f["origin"] = given["origin"] if given["origin"] in kit.ORIGINS else ""
            if "link" in given:
                f["link"] = kit.link_of(given["link"])
        st["result"] = None
        _write(kid, st)
        return overview(kid)
    if what == "build":
        return start_build(kid)
    if what == "use":
        return use(kid, str(body.get("to") or "station"))
    raise ValueError("That cannot be done here")


def start_build(kid):
    st = _read(kid)
    if not st["name"]:
        raise ValueError("Give the channel a name")
    if _ctx["playing"]():
        raise ValueError("A channel is being watched. Making branding waits until nobody is watching: try again then")
    if st.get("mode") == "make":
        if st["style"] not in recipes.STYLES:
            raise ValueError("Choose a style first")
    elif st["ready"] != "pack":
        todo = [f for f in st["files"] if f["role"] != "skip"]
        if not todo:
            raise ValueError("Mark at least one file as something")
        missing = [f["name"] for f in todo if not f["origin"]]
        if missing:
            raise ValueError(f"Say where {missing[0]} came from")
    if not _job_lock.acquire(blocking=False):
        raise ValueError("Another style is being made. Wait for it to finish")
    st["job"] = {"running": True, "step": 0, "of": 1, "words": "Starting", "error": ""}
    st["result"] = None
    _write(kid, st)
    draw.clear()
    threading.Thread(target=_run_build, args=(kid,), name="style-build", daemon=True).start()
    return overview(kid)


def _progress(kid, step, of, words):
    st = _read(kid)
    st["job"].update({"step": step, "of": of, "words": words})
    _write(kid, st)


def _run_build(kid):
    try:
        with sbplugin.working("a style being made"):
            st = _read(kid)
            d = kit_dir(kid)
            out = os.path.join(d, "pack")
            made = kit.today()
            if st.get("mode") == "make":
                logo = os.path.join(d, "in", st["logo"]) if st.get("logo") else None
                recipes.make(out, st["style"], st["name"], st["colours"], made, logo=logo, still=bool(st.get("still")),
                            progress=lambda step, of, words: _progress(kid, step, of, words))
            elif st["ready"] == "pack":
                shutil.rmtree(out, ignore_errors=True)
                shutil.copytree(os.path.join(d, "ready"), out)
                origin = {"name": "the whole pack", "role": "ident", "origin": st["pack_origin"] or "other", "link": st["pack_link"]}
                with open(os.path.join(out, "LICENCE.txt"), "w", encoding="utf-8") as f:
                    f.write(kit.licence_text(st["name"], [origin], made).replace("(short title clip)", "(a ready made pack)"))
            else:
                src = os.path.join(d, "in")
                files = [f for f in st["files"] if f["role"] != "skip"]
                for i, f in enumerate(files):
                    if f["kind"] == "video":
                        _progress(kid, i, len(files) + 3, f"Reading {f['name']} for fast flashing")
                        f["flash"] = flash.words(flash.check(os.path.join(src, f["name"])))
                st = _read(kid)
                for f in st["files"]:
                    f["flash"] = next((g["flash"] for g in files if g["name"] == f["name"]), f.get("flash", ""))
                _write(kid, st)
                kit.build(src, out, st["name"], st["colours"], st["files"], made,
                          progress=lambda step, of, words: _progress(kid, step, of, words))
            got = pack.install_folder(out, out)
            st = _read(kid)
            extra = []
            roles = {f["role"] for f in st["files"]}
            if st.get("mode") == "make":
                look = recipes.plan(st["style"], st["name"], *st["colours"])
                if look["adjusted"]:
                    extra.append("Your " + " and ".join({"c1": "main colour", "c2": "second colour"}[k] for k in look["adjusted"])
                                 + " was made a little darker or lighter, so the words reach 7 to 1 and are easy to read")
            if "music" in roles and not roles & {"promo"} and st["ready"] != "pack" and st.get("mode") != "make":
                extra.append("The music is not used yet: it plays in coming-up trailers, which need a background. Add a picture or video marked as the background for coming-up trailers")
            st["result"] = {"ok": got["ok"], "problems": got["problems"][:12], "notes": (extra + got["notes"])[:20], "summary": pack.summary(got["pack"]) if got["ok"] else ""}
            st["job"] = {"running": False, "error": ""}
            _write(kid, st)
    except draw.Stopped:
        _fail(kid, "A channel started to play, so the branding stopped. Make it again when nobody is watching")
    except (kit.KitError, RuntimeError, OSError, ValueError) as e:
        _fail(kid, str(e)[:300])
    except Exception as e:  # noqa: BLE001 - said on the page
        _fail(kid, f"{type(e).__name__}: {e}"[:300])
    finally:
        _job_lock.release()


def _fail(kid, words):
    try:
        st = _read(kid)
        st["job"] = {"running": False, "error": words}
        _write(kid, st)
    except (ValueError, OSError):
        pass


def use(kid, to):
    """Puts the branding in place for the station or one channel, then removes the kit's work."""
    st = _read(kid)
    d = kit_dir(kid)
    if not st["result"] or not st["result"]["ok"]:
        raise ValueError("Make the branding first, and fix what the check lists")
    with _ctx["lock"]:
        s = _ctx["state"]()
        if to == "station":
            target = "station"
        else:
            ch = next((c for c in s.get("channels") or [] if c["id"] == to), None)
            if not ch:
                raise ValueError("That channel has gone")
            target = f"ch-{ch['id']}"
        got = pack.install_folder(os.path.join(d, "pack"), _ctx["pack_dir"](target))
        if not got["ok"]:
            raise ValueError("The check no longer passes: " + kit.words_for_problems(got))
        _ctx["drop_pack"](target)
        if to == "station":
            s["station_pack"] = "station"
            s.pop("pack_before_example", None)
        else:
            ch["pack"] = "own"
        _ctx["save"](s)
    shutil.rmtree(d, ignore_errors=True)
    where = "every channel without a pack of its own" if to == "station" else f"the channel {ch['name']}"
    out = overview("")
    out["said"] = f"{st['name']} is now the branding for {where}"
    return out


_still_lock = threading.Lock()


def preview(q):
    """One still picture of what a style draws, as PNG bytes, before any video is made. q: style, name, c1, c2, part (title, bumper or card), variant."""
    if _ctx["playing"]():
        raise ValueError("A channel is being watched. The picture waits until nobody is watching: try again then")
    style = str(q.get("style") or "")
    part = str(q.get("part") or "title")
    if style not in recipes.STYLES or part not in ("title", "bumper", "card"):
        raise ValueError("Choose one of the styles")
    name = draw.clean_words(q.get("name")) or "Your channel"
    try:
        variant = max(0, min(len(recipes.VARIANTS) - 1, int(q.get("variant") or 0)))
    except ValueError:
        variant = 0
    if _job_lock.locked():
        raise ValueError("A style is being made. Wait for it to finish")
    os.makedirs(root(), exist_ok=True)
    with _still_lock, tempfile.TemporaryDirectory(dir=root(), prefix=".still-") as tmp:
        dst = os.path.join(tmp, "still.png")
        draw.clear()
        with sbplugin.working("a picture being drawn"):
            try:
                recipes.title_still(style, name, draw.colour(q.get("c1"), "#10202C"), draw.colour(q.get("c2"), "#1B8A7F"), dst, tmp, variant=variant, part=part)
            except draw.Stopped:
                raise ValueError("A channel started to play, so the picture stopped") from None
            except RuntimeError as e:
                raise ValueError(str(e)[:200]) from None
        with open(dst, "rb") as f:
            return f.read()
