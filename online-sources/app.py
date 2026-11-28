"""Online sources: find free pictures and music, keep their licence and credit, and hand a pack to Create your own TV channel.

Plug-in API 1.25 (fetch and the tv-pack hand-off folder). Private draft: not in the catalogue.

What it does, and only when a person asks (nothing runs while idle):
- Searches Openverse (pictures and music, no key) and Pexels (pictures, a free key kept as a secret setting). Starboard makes
  every request, only to the sites in the manifest's fetch list, and keeps a record the person can read.
- Saves a chosen result in /data/files with who made it, its licence and where it came from (items.json).
- Builds a broadcast pack (a zip with pack.json, backgrounds, music and a LICENCE.txt that says where each file came from) and
  puts it in the hand-off folder /handoff/tv-pack, for Create your own TV channel to check and use. It never writes to that plug-in.
Never fetched: Jamendo (its terms forbid keeping its music on a server).
"""
import base64
import datetime as dt
import hashlib
import http.client
import json
import os
import re
import shutil
import threading
import urllib.parse
import zipfile

import sbplugin as sb

DATA = sb.DATA
FILES = os.path.join(DATA, "files")
INBOX = os.path.join(DATA, "fetched")
HANDOFF = os.environ.get("HANDOFF_TV_PACK", "/handoff/tv-pack")
COMMERCIAL = {"cc0", "pdm", "by", "by-sa"}  # fine for a channel at home; by-nc and by-nd are not
LICENCE_NAMES = {"pexels": "Pexels licence (free to use, no credit needed)", "cc0": "CC0 (public domain)", "pdm": "Public domain mark", "by": "CC BY", "by-sa": "CC BY-SA", "by-nc": "CC BY-NC",
                 "by-nd": "CC BY-ND", "by-nc-sa": "CC BY-NC-SA", "by-nc-nd": "CC BY-NC-ND"}
SLOTS = {"coming": ("Coming up next background", "coming-next/background"), "promo": ("Promo background", "promo/background"),
         "music": ("Promo music", "promo/music/")}
MUSIC_HOSTS = ("upload.wikimedia.org", "cdn.freesound.org")  # on the manifest's fetch list; Openverse music elsewhere is shown, not saved
MAX_MUSIC = 20
_lock = threading.Lock()


def _read(name, default):
    return sb._json_file(os.path.join(DATA, name), default)


def _write(name, value):
    os.makedirs(DATA, exist_ok=True)
    tmp = os.path.join(DATA, f".{name}.part")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(value, f)
    os.replace(tmp, os.path.join(DATA, name))


def _clean(text, most=120):
    return re.sub(r"[\x00-\x1f\x7f<>`]", " ", str(text or "")).strip()[:most]


# Asking Starboard to fetch -----------------------------------------------------------------------------------------
def starboard_fetch(url, what, headers=None, save_as=None, max_bytes=None):
    body = {"url": url, "what": what, **({"headers": headers} if headers else {}), **({"save_as": save_as} if save_as else {}),
            **({"max_bytes": max_bytes} if max_bytes else {}), "seconds": 60 if save_as else 20}
    if not (sb.API_SOCKET and os.path.exists(sb.API_SOCKET)):
        raise RuntimeError("Starboard's socket is not there, so this plug-in cannot fetch")
    c = sb._SocketConnection(sb.API_SOCKET, 90)
    try:
        c.request("POST", "/api/v1/plugin/fetch", body=json.dumps(body).encode(),
                  headers={"Authorization": f"Bearer {sb._key()}", "Content-Type": "application/json", "Accept": "application/json"})
        r = c.getresponse()
        out = json.loads(r.read(8 * 1024 * 1024) or b"{}")
    finally:
        c.close()
    if r.status == 429:
        raise RuntimeError("Starboard is fetching for something else. Try again in a few seconds")
    if r.status == 404:
        raise RuntimeError("Starboard has not allowed this plug-in to fetch. Check its permissions")
    if r.status >= 400:
        raise RuntimeError(_clean(out.get("title") or "Starboard could not fetch that", 200))
    if not 200 <= out.get("status", 0) < 300:
        raise RuntimeError(f"The site answered {out.get('status')}" + (" (is the key right?)" if out.get("status") in (401, 403) else ""))
    return out


def _json_of(out):
    try:
        return json.loads(base64.b64decode(out.get("body_base64") or "") or b"{}")
    except ValueError:
        raise RuntimeError("The site sent something that was not a list of results") from None


# Searching -----------------------------------------------------------------------------------------------------------
def licence_words(code, version=""):
    base = LICENCE_NAMES.get(str(code).lower(), f"Licence {_clean(code, 20)}")
    return f"{base} {version}".strip() if str(code).lower() in ("by", "by-sa", "by-nc", "by-nd", "by-nc-sa", "by-nc-nd") else base


def search_openverse(kind, words, show_all):
    q = {"q": words, "page_size": 12}
    if not show_all:
        q["license_type"] = "commercial"
    if kind == "music":
        q["source"] = "freesound,wikimedia_audio"  # not Jamendo
    out = _json_of(starboard_fetch(f"https://api.openverse.org/v1/{'audio' if kind == 'music' else 'images'}/?{urllib.parse.urlencode(q)}",
                                   "Search Openverse for music" if kind == "music" else "Search Openverse for pictures",
                                   {"Accept": "application/json"}))
    found = []
    for r in out.get("results") or []:
        if not isinstance(r, dict) or not r.get("id"):
            continue
        file_url = r.get("url") or ""
        if kind == "music":
            host = urllib.parse.urlsplit(file_url).hostname or ""
            file_url = file_url if host in MUSIC_HOSTS else ""
        else:
            file_url = f"https://api.openverse.org/v1/images/{urllib.parse.quote(str(r['id']), safe='')}/thumb/"  # Openverse's own smaller copy
        found.append({"id": f"ov-{r['id']}", "source": "Openverse", "title": _clean(r.get("title") or "Untitled", 100),
                      "maker": _clean(r.get("creator") or "Unknown", 80), "licence": str(r.get("license") or "").lower(),
                      "licence_version": _clean(r.get("license_version"), 8), "licence_url": _clean(r.get("license_url"), 300),
                      "page": _clean(r.get("foreign_landing_url"), 300), "file": file_url, "provider": _clean(r.get("provider"), 40),
                      "small": kind != "music"})
    return found


def search_pexels(words):
    key = sb.setting("pexels_key")
    if not key:
        raise RuntimeError("Pexels needs its free key. Add it in this plug-in's settings, under Pexels")
    out = _json_of(starboard_fetch("https://api.pexels.com/v1/search?" + urllib.parse.urlencode({"query": words, "per_page": 12, "orientation": "landscape"}),
                                   "Search Pexels for pictures", {"Authorization": str(key), "Accept": "application/json"}))
    found = []
    for r in out.get("photos") or []:
        src = (r.get("src") or {}).get("large2x") or ""
        if not isinstance(r, dict) or not r.get("id") or urllib.parse.urlsplit(src).hostname != "images.pexels.com":
            continue
        found.append({"id": f"px-{r['id']}", "source": "Pexels", "title": _clean(r.get("alt") or "Picture", 100), "maker": _clean(r.get("photographer") or "Unknown", 80),
                      "licence": "pexels", "licence_version": "", "licence_url": "https://www.pexels.com/license/", "page": _clean(r.get("url"), 300),
                      "file": src, "provider": "Pexels", "small": False})
    return found


def run_search(kind, words):
    words = _clean(words, 80)
    if len(words) < 2:
        raise ValueError("Enter a few words to search for, such as rain or city at night")
    show_all = bool(sb.setting("show_all", False))
    found = []
    errors = []
    sources = sb.setting("sources", "both")
    for name, fn in (("Openverse", lambda: search_openverse(kind, words, show_all)),
                     ("Pexels", lambda: search_pexels(words) if kind != "music" else [])):
        if sources != "both" and sources != name.lower():
            continue
        try:
            found += fn()
        except RuntimeError as e:
            errors.append(f"{name}: {e}")
    if not found and errors:
        raise RuntimeError("; ".join(errors))
    _write(f"results-{kind}.json", {"words": words, "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "results": found, "errors": errors})


# Saving ----------------------------------------------------------------------------------------------------------------
def sniff(head):
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg", "picture"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png", "picture"
    if head.startswith(b"ID3") or (len(head) > 1 and head[0] == 0xFF and head[1] & 0xE0 == 0xE0):
        return "mp3", "music"
    if head.startswith(b"OggS"):
        return "ogg", "music"
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "wav", "music"
    if head.startswith(b"fLaC"):
        return "flac", "music"
    if head[4:8] == b"ftyp":
        return "m4a", "music"
    return "", ""


def save_result(kind, rid, slot):
    if slot not in SLOTS or (slot == "music") != (kind == "music"):
        raise ValueError("Choose where it goes in the pack")
    got = next((r for r in (_read(f"results-{kind}.json", {}) or {}).get("results", []) if r.get("id") == rid), None)
    if not got:
        raise ValueError("That result is not on the list any more. Search again")
    if not got.get("file"):
        raise ValueError("This one is on a site Starboard may not fetch from. Open it on its own site, then add the file in the TV channel plug-in yourself")
    items = _read("items.json", [])
    if slot == "music" and sum(1 for i in items if i["slot"] == "music") >= MAX_MUSIC and not any(i["id"] == rid for i in items):
        raise ValueError(f"A pack holds up to {MAX_MUSIC} pieces of music")
    os.makedirs(INBOX, exist_ok=True)
    tmp = f"{hashlib.sha256(rid.encode()).hexdigest()[:16]}.part"
    host = urllib.parse.urlsplit(got["file"]).hostname
    headers = {"Authorization": str(sb.setting("pexels_key"))} if host == "api.pexels.com" else None
    starboard_fetch(got["file"], f"Save {'music' if kind == 'music' else 'a picture'} from {got['source']}", headers, save_as=tmp,
                    max_bytes=(25 if kind == "music" else 12) * 1024 * 1024)
    path = os.path.join(INBOX, tmp)
    try:
        with open(path, "rb") as f:
            head = f.read(16)
        ext, found_kind = sniff(head)
        if not ext or found_kind != ("music" if kind == "music" else "picture"):
            raise ValueError("What came back is not a picture or a piece of music Starboard's TV pack can use, so it was not kept")
        name = f"{slot}-{hashlib.sha256(rid.encode()).hexdigest()[:10]}.{ext}"
        os.makedirs(FILES, exist_ok=True)
        shutil.move(path, os.path.join(FILES, name))
    finally:
        if os.path.exists(path):
            os.unlink(path)
    with open(os.path.join(FILES, name), "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    with _lock:
        items = [i for i in _read("items.json", []) if i["id"] != rid and (slot == "music" or i["slot"] != slot)]
        for gone in [i for i in _read("items.json", []) if i["id"] != rid and slot != "music" and i["slot"] == slot]:
            try:
                os.unlink(os.path.join(FILES, gone["file"]))
            except OSError:
                pass
        items.append({k: got[k] for k in ("id", "source", "title", "maker", "licence", "licence_version", "licence_url", "page")}
                     | {"slot": slot, "file": name, "sha256": digest, "saved": dt.date.today().isoformat(), "size": os.path.getsize(os.path.join(FILES, name))})
        _write("items.json", items)
    return got


def remove_item(rid):
    with _lock:
        items = _read("items.json", [])
        for i in items:
            if i["id"] == rid:
                try:
                    os.unlink(os.path.join(FILES, i["file"]))
                except OSError:
                    pass
        _write("items.json", [i for i in items if i["id"] != rid])


# The pack and the hand-off ----------------------------------------------------------------------------------------------
def arc_name(i):
    return f"promo/music/{i['file']}" if i["slot"] == "music" else f"{SLOTS[i['slot']][1]}.{i['file'].rsplit('.', 1)[1]}"


def licence_text(items, name):
    lines = [f"{name}: where each file came from", "",
             "Every file here was found on a free site by the Online sources plug-in for Starboard, and kept with who made it and the licence it is under.",
             "Keep this file with the pack. A licence with BY in its name asks you to credit the maker: this list is the credit.", ""]
    for i in items:
        lines += [arc_name(i),
                  f"  Title: {i['title']}", f"  Made by: {i['maker']}", f"  From: {i['source']}, {i['page']}",
                  f"  Licence: {licence_words(i['licence'], i.get('licence_version', ''))}" + (f", {i['licence_url']}" if i.get("licence_url") else ""),
                  f"  Saved on: {i['saved']}", f"  Checksum (sha256): {i['sha256']}", ""]
    return "\n".join(lines) + "\n"


def pack_name():
    return _clean(sb.setting("pack_name", "Online sources pack"), 40) or "Online sources pack"


def build_pack(dest=None):
    items = _read("items.json", [])
    if not items:
        raise ValueError("Save at least one picture or piece of music first")
    name = pack_name()
    safe = re.sub(r"[^A-Za-z0-9 _.-]", "", name).strip().replace(" ", "-")[:40] or "pack"
    dest = dest or HANDOFF
    os.makedirs(dest, exist_ok=True)
    final = os.path.join(dest, f"online-sources-{safe}.zip")
    tmp = os.path.join(dest, f".online-sources-{safe}.part")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("pack.json", json.dumps({"pack": 1, "name": name, "made": dt.date.today().strftime("%d %B %Y"), "author": "Online sources, free sites"}, indent=1))
        for i in items:
            z.write(os.path.join(FILES, i["file"]), arc_name(i))
        z.writestr("LICENCE.txt", licence_text(items, name))
    os.chmod(tmp, 0o666)
    os.replace(tmp, final)  # whole before it has its name: the receiver never reads half a file
    return final, len(items)


# The style library ---------------------------------------------------------------------------------------------------------
# style-library/index.json in the starboard-plugins repository lists styles other people made, each MIT licensed, with credits, after
# the owner has read it. A "pack" entry has a zip, its size and sha256; a "link" entry is a name and a link to the author's page and
# is never hosted. The zip is fetched through Starboard (raw.githubusercontent.com only), checked against the sha256, and handed over.
LIBRARY = "https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/style-library/"
STYLE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,40}$")
MAX_STYLE = 25 * 1024 * 1024
NOTICE = {"id": "computer", "tone": "info", "title": "This page is for a computer screen", "text": "It is not made for phones."}


def clean_index(doc):
    """The styles of an index file Starboard fetched, each checked here again: MIT only, a real id, credits, and for a pack a size
    and a sha256. Anything else is left out, so a bad entry in the index can never be used."""
    out = []
    for s in (doc.get("styles") if isinstance(doc, dict) else None) or []:
        if not isinstance(s, dict) or not STYLE_ID.match(str(s.get("id", ""))) or s.get("licence") != "MIT" or not str(s.get("credits") or "").strip():
            continue
        kind = s.get("kind", "pack")
        base = {"id": s["id"], "kind": kind, "name": _clean(s.get("name"), 60), "maker": _clean(s.get("maker"), 60), "licence": "MIT",
                "credits": _clean(s.get("credits"), 300), "preview": _clean(s.get("preview"), 120)}
        if not base["name"] or not base["maker"]:
            continue
        if kind == "link":
            if str(s.get("link", "")).startswith("https://"):
                out.append({**base, "link": _clean(s["link"], 300)})
        elif kind == "pack" and re.match(r"^packs/[a-z0-9][a-z0-9.-]{1,60}\.zip$", str(s.get("file", ""))) and re.match(r"^[0-9a-f]{64}$", str(s.get("sha256", ""))) \
                and isinstance(s.get("size"), int) and 0 < s["size"] <= MAX_STYLE:
            out.append({**base, "file": s["file"], "sha256": s["sha256"], "size": s["size"]})
    return out


def refresh_library():
    out = _json_of(starboard_fetch(LIBRARY + "index.json", "Read the style library"))
    _write("styles.json", {"at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "styles": clean_index(out)})


def use_style(sid):
    got = next((s for s in (_read("styles.json", {}) or {}).get("styles", []) if s["id"] == sid and s["kind"] == "pack"), None)
    if not got:
        raise ValueError("That style is not on the list. Check the library again")
    os.makedirs(INBOX, exist_ok=True)
    tmp = f"style-{sid}.part"
    starboard_fetch(LIBRARY + got["file"], f"Get the style {got['name'][:40]}", save_as=tmp, max_bytes=got["size"] + 1)
    path = os.path.join(INBOX, tmp)
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(65536), b""):
                h.update(block)
        if h.hexdigest() != got["sha256"] or os.path.getsize(path) != got["size"]:
            raise ValueError("What came back is not the style that was read and listed (its checksum differs), so it was not used")
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            if "pack.json" not in names or any(n.startswith(("/", "..")) or ".." in n.split("/") for n in names):
                raise ValueError("That zip is not a broadcast pack, so it was not used")
        os.makedirs(HANDOFF, exist_ok=True)
        final = os.path.join(HANDOFF, f"style-{sid}.zip")
        part = os.path.join(HANDOFF, f".style-{sid}.part")
        shutil.copyfile(path, part)
        os.chmod(part, 0o666)
        os.replace(part, final)
    finally:
        if os.path.exists(path):
            os.unlink(path)
    return got


def share_style():
    """Makes the pack and its index entry for the library, in this plug-in's own folder. It lists nothing and posts nothing."""
    final, n = build_pack(os.path.join(DATA, "share"))
    with open(final, "rb") as f:
        data = f.read()
    entry = {"id": re.sub(r"[^a-z0-9]+", "-", pack_name().lower()).strip("-")[:40] or "my-style", "kind": "pack", "name": pack_name(), "maker": "Your name here",
             "licence": "MIT", "credits": "Say who made each file, as LICENCE.txt in the pack does", "size": len(data), "sha256": hashlib.sha256(data).hexdigest(),
             "file": "packs/NAME.zip", "preview": "previews/NAME.png"}
    with open(os.path.join(DATA, "share", "index-entry.json"), "w", encoding="utf-8") as f:
        json.dump(entry, f, indent=1)
    return final, entry


def styles_page(said=""):
    data = _read("styles.json", {}) or {}
    rows = []
    for s in data.get("styles", []):
        row = {"id": s["id"], "title": s["name"], "detail": f"{s['maker']}, {s['licence']}. Credits: {s['credits']}" + (f". {s['size'] // 1024} KB" if s.get("size") else ""),
               "state": "ok", "state_label": "Link only" if s["kind"] == "link" else "MIT licence", "actions": []}
        if s["kind"] == "link":
            row["link"] = {"url": s["link"], "label": f"Open {s['name'][:40]} on its maker's page"}
        else:
            row["choice"] = {"label": "Use this style", "value": "", "options": [["", "Choose"], ["use", "Send to Create your own TV channel"]]}
        rows.append(row)
    intro = ("Styles other people made. Every one is under the MIT licence with its credits, and the owner of Starboard's plug-ins read it before it was listed. "
             "Last read " + data["at"][:10] + ".") if data.get("at") else "Press Check the style library under Actions to read the list. Starboard fetches it from GitHub, and keeps a record under What it fetched."
    page = {"type": "list", "title": "Styles from the library", "intro": intro, "items": rows, "notices": [NOTICE]}
    # The "Ask an AI tool" slide-out (prompts and free AI sources) goes on this page once its content file exists
    # (/mnt/pool/Claude/mockups/tv-channel-ai-prompts-2026-11-28/prompts.json), with the shared design-system slide-out.
    return {**page, **({"said": said} if said else {})}


def styles_post(body):
    if body.get("action") == "choose" and body.get("value") == "use":
        got = use_style(str(body.get("id") or ""))
        return styles_page(f"Sent {got['name'][:40]} to the shared folder. Open Create your own TV channel to use it")
    return styles_page()


def refresh_action():
    refresh_library()
    n = len((_read("styles.json", {}) or {}).get("styles", []))
    return {"said": f"The style library has {n} style{'s' if n != 1 else ''}"}


def share_action():
    final, entry = share_style()
    return {"said": f"Made {os.path.basename(final)} in this plug-in's folder, data/plugins/online-sources/data/main/share, with index-entry.json. "
                    "Share only what you made or have the right to share. A style with an unknown source can be kept here, but the library lists only MIT packs that were read first"}


# Pages Starboard draws ----------------------------------------------------------------------------------------------------
def result_items(kind):
    saved = {i["id"] for i in _read("items.json", [])}
    data = _read(f"results-{kind}.json", {}) or {}
    out = []
    options = [["", "Choose where it goes"]] + ([["music", "Promo music"]] if kind == "music" else [["coming", "Coming up next background"], ["promo", "Promo background"]])
    for r in data.get("results", []):
        ok = r["licence"] in COMMERCIAL or r["licence"] == "pexels"
        words = f"{r['maker']}, {licence_words(r['licence'], r.get('licence_version', ''))}, {r['source']}"
        it = {"id": r["id"], "title": r["title"], "detail": words + (" (a small picture)" if r.get("small") else ""),
              "state": "ok" if r["id"] in saved else ("ok" if ok else "warning"), "state_label": "Saved" if r["id"] in saved else ("Free to use" if ok else "Check the licence"),
              "link": {"url": r["page"], "label": f"Open {r['title'][:40]} on {r['source']}"} if r["page"].startswith("https://") else None, "actions": []}
        if r.get("file"):
            it["choice"] = {"label": "Save as", "value": "", "options": options}
        else:
            it["detail"] += ". Open it on its own site: Starboard may not fetch it"
        out.append({k: v for k, v in it.items() if v is not None})
    return out, data


def find_page(kind, said=""):
    title = "Find music" if kind == "music" else "Find a picture"
    items, data = result_items(kind)
    page = {"type": "list", "title": title,
            "intro": ("Results for " + data["words"] + (f". {len(items)} found." if items else ". Nothing found.")) if data.get("words") else
            "Search for words such as rain or city at night. Starboard fetches from Openverse" + ("" if kind == "music" else " and Pexels") + " only, and keeps a record under What it fetched.",
            "add": {"label": "Search for", "hint": "A few words", "placeholder": "rain"}, "items": items, "notices": [NOTICE]}
    if data.get("errors"):
        page["notices"] += [{"id": "err", "tone": "warning", "title": "Part of the search failed", "text": _clean("; ".join(data["errors"]), 300)}]
    return {**page, **({"said": said} if said else {})}


def pack_page(said=""):
    items = _read("items.json", [])
    rows = [{"id": i["id"], "title": i["title"], "state": "ok", "state_label": SLOTS[i["slot"]][0],
             "detail": f"{i['maker']}, {licence_words(i['licence'], i.get('licence_version', ''))}, {i['source']}", "actions": ["remove"],
             **({"link": {"url": i["page"], "label": f"Open {i['title'][:40]} on {i['source']}"}} if i["page"].startswith("https://") else {})} for i in items]
    page = {"type": "list", "title": "Your pack", "intro": (f"{len(items)} saved. Use Send to Create your own TV channel under Actions: it puts the pack in a shared folder, "
                                                             "and the TV channel plug-in checks it before it uses it.") if items else "Nothing saved yet. Find a picture or music, and save it here.",
            "items": rows, "notices": [NOTICE]}
    return {**page, **({"said": said} if said else {})}


def page_for(kind):
    def get():
        return find_page(kind)

    def post(body):
        a, rid, val = body.get("action"), str(body.get("id") or ""), str(body.get("value") or "")
        # a ValueError or RuntimeError reaches Starboard as an error sentence, shown to the person
        if a == "add":
            run_search(kind, val)
            return find_page(kind, "Done. The results are in the list")
        if a == "choose" and val:
            got = save_result(kind, rid, val)
            return find_page(kind, f"Saved {got['title'][:60]} as {SLOTS[val][0].lower()}, with its maker and licence")
        return find_page(kind)
    return get, post


def pack_post(body):
    if body.get("action") == "remove":
        remove_item(str(body.get("id") or ""))
        return pack_page("Removed")
    return pack_page()


def send():
    path, n = build_pack()
    return {"said": f"Sent {n} file{'s' if n != 1 else ''} with a LICENCE.txt to the shared folder as {os.path.basename(path)}. Open Create your own TV channel to use it"}


if __name__ == "__main__":
    pf, pp = page_for("pictures")
    mf, mp = page_for("music")
    sb.serve({"/pictures": pf, ("POST", "/pictures"): pp, "/music": mf, ("POST", "/music"): mp, "/pack": pack_page, ("POST", "/pack"): pack_post,
              "/styles": styles_page, ("POST", "/styles"): styles_post, ("POST", "/actions/send"): send,
              ("POST", "/actions/refresh"): refresh_action, ("POST", "/actions/share"): share_action})
