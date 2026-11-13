"""Audio description: finds the films and series in Jellyfin with a described sound track, prefers releases with one
in Reelix, and helps each person who wants it keep the described track.

Audio description (AD) is a second sound track in which a narrator says what is happening on screen, for blind and
partially sighted people. Research: ACCESSIBILITY-FEATURES-2026-11-13.md (DASH-400).

Lightweight: the container rests when idle (start when_needed). Starboard wakes it for a nightly job (the library
check, in quiet hours), a job when Starboard starts (the Reelix format), its buttons and its screens. Nothing runs on a
timer of its own, and the library is read 200 items at a time, so memory stays flat whatever the library's size.

What it never does: download from or scrape any site, record from a broadcaster's app, or change a media file.

Sources (DASH-410): each is its own switch in Sources, and only links out. AudioVault states no licence and no terms
for automated use and limits each account to 25 downloads a day, so the plug-in links to AudioVault's own search for
each title without audio description and never reads AudioVault. Adding a track the person already holds is the
separate Audio description tracks plug-in, which needs write access to the media folder.
"""
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
from collections import defaultdict

import sbplugin
from sbplugin import fetch, keep, plural, remember, serve, setting

# Release names: TRaSH Guides' "WiTH AD" pattern (a word before "AD", so "A.D." in a title never counts) with the
# longer phrases added (research, part (a) 1). Reelix's patterns are case-insensitive already; (?i) keeps Python the same.
RELEASE_AD = (r"(?i)\b(?:(?:WiTH|MULTi|FRENCH|ENG(?:LISH)?|(?:BA?|A)SL[ ._-]and)[ ._-](?:AD|Audio[ ._-]?Description)"
              r"|Audio[ ._-]?Descri(?:ption|bed)|Descriptive[ ._-](?:Audio|Video)|Described[ ._-]Video|DVS)\b")
# Track titles in the library: short, so a bare AD counts there. Jellyfin does not pass on the visual impaired flag
# (research, part (a) 5), so the title, display title and comment are what can be read.
TRACK_AD = re.compile(r"(?i)(?:\baudio[ ._-]?descri(?:ption|bed)\b|\bdescriptive[ ._-]?(?:audio|video)\b|\bdescribed\b"
                      r"|\bDVS\b|(?:^|[\s\[(._-])AD(?:$|[\s\])._-]))")
COMMENTARY = re.compile(r"(?i)comment(?:ary)?")
FORMAT_NAME = "Audio description"
PREFER = 100  # the score Starboard writes for Prefer (reelix_quality.PREFER)
PAGE = 200
# Legal places with audio description, opened in their own apps (research, part (a) 2 to 4). Nothing is fetched.
ELSEWHERE = [
    ("bbc", "BBC iPlayer", "Audio described programmes, in the iPlayer app or website", "https://www.bbc.co.uk/iplayer/categories/audio-described/featured"),
    ("itvx", "ITVX", "Choose AD in the player on programmes that have it", "https://www.itv.com/"),
    ("channel4", "Channel 4", "Audio description in the Channel 4 app on many programmes", "https://www.channel4.com/"),
    ("my5", "My5", "Audio description on some Channel 5 programmes", "https://www.channel5.com/"),
    ("netflix", "Netflix", "Search for audio description in the app", "https://www.netflix.com/browse/audio-description"),
    ("rnib", "RNIB", "Advice on audio description, and RNIB's own reading services", "https://www.rnib.org.uk/living-with-sight-loss/assistive-aids-and-technology/tv-audio-and-gaming/audio-description/"),
    ("adp", "The Audio Description Project", "A list of described films and series, by the American Council of the Blind", "https://adp.acb.org/"),
    ("audiovault", "AudioVault", "A community library of description tracks for blind people. Starboard does not download from it: sign in there and keep to its rules", "https://audiovault.net/"),
]
# AudioVault's own search, as its Movies and Shows pages send it (a GET form, `search`). A link the person opens; the
# plug-in never calls it (DASH-410).
AUDIOVAULT = {"film": "https://audiovault.net/movies?search=", "series": "https://audiovault.net/shows?search="}
# YouDescribe's own search page (its site's /search?q=). Its programming interface serves its own site and is not
# offered to others, so the plug-in only links to the search (DASH-410).
YOUDESCRIBE = "https://youdescribe.org/search?q="
# MovieReading and Earcatch (DASH-410): phone apps that play a description in step by listening. Neither publishes a
# list of titles that other apps may read (MovieReading's site names only the films in cinemas now; Earcatch's terms
# forbid collecting its content with automated tools for AI and give no list), so this is a guide with links only.
APPS = [
    ("MovieReading", [
        ("mr-what", "What it is", "Info", "A free phone app from Italy. It plays a film's description in step by listening to the film. Mostly Italian "
         "cinema titles, and it lists only the films it has now.", None),
        ("mr-ios", "MovieReading for iPhone and iPad", "Link only", "", ("https://apps.apple.com/app/id460349347", "MovieReading on the App Store")),
        ("mr-android", "MovieReading for Android", "Link only", "", ("https://play.google.com/store/apps/details?id=com.unimaccess.umaclient",
                                                                 "MovieReading on Google Play")),
        ("mr-films", "The films it has now", "Link only", "", ("https://www.moviereading.com/#film", "MovieReading's films, on its website"))]),
    ("Earcatch", [
        ("ec-what", "What it is", "Info", "A free phone app from the Netherlands. It plays a description in step by listening, for films and "
         "series at home or in the cinema. Mostly Dutch and Flemish titles.", None),
        ("ec-ios", "Earcatch for iPhone and iPad", "Link only", "", ("https://apps.apple.com/app/id1021220730", "Earcatch on the App Store")),
        ("ec-android", "Earcatch for Android", "Link only", "", ("https://play.google.com/store/apps/details?id=nl.q42.soundfocus", "Earcatch on Google Play")),
        ("ec-search", "Its titles", "Link only", "", ("https://www.earcatch.nl/zoeken/", "Search Earcatch's titles, on its website"))]),
    ("Using one with Jellyfin", [
        ("step-1", "Get the description first", "Step 1", "Install the app on your phone and download the description for your film in the app, "
         "at home on Wi-Fi. It must be for the same cut of the film as yours.", None),
        ("step-2", "Start the film in Jellyfin", "Step 2", "Play it on your television with its original sound track, loud enough for the "
         "phone to hear. Keep the phone near the television.", None),
        ("step-3", "Start the description", "Step 3", "Open the film in the app and press play. It listens to the film's sound and plays "
         "the description in step, wherever the film is.", None),
        ("step-4", "Listen with headphones", "Step 4", "Use headphones or earbuds on the phone, so others in the room hear only the film.", None),
        ("step-5", "If it loses its place", "Step 5", "After a pause or a skip in Jellyfin it finds its place again in a few seconds. If it "
         "does not, close the description in the app and open it again.", None)]),
]
MENU_SPLIT = 80  # more titles than this in Films or Series: sub menus by first letter, so no page is too long


# Jellyfin and Reelix ---------------------------------------------------------------------------------------------

def _run_file(name):
    try:
        with open(os.path.join(sbplugin.RUN, name), encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, ValueError):
        return {}


def jellyfin(path, data=None, method=None):
    jf = _run_file("jellyfin.json")
    if not jf.get("url") or not jf.get("api_key"):
        raise LookupError("Starboard has no Jellyfin key to give yet: add Jellyfin in Settings, Apps")
    return fetch(jf["url"].rstrip("/") + path, {"X-Emby-Token": jf["api_key"]}, data=data, method=method, timeout=30)


def reelix(path, data=None, method=None):
    rx = _run_file("reelix.json")
    if not rx.get("url") or not rx.get("api_key"):
        raise LookupError("Starboard has no Reelix key to give yet: add Reelix in Settings, Apps")
    return fetch(rx["url"].rstrip("/") + "/api/v1" + path, {"X-Api-Key": rx["api_key"]}, data=data, method=method, timeout=30)


# The library -----------------------------------------------------------------------------------------------------

def described_track(streams):
    """The first audio track that is audio description, by its words, or None. Commentary tracks never count."""
    for s in streams or []:
        if not isinstance(s, dict) or s.get("Type") != "Audio":
            continue
        words = " ".join(str(s.get(k) or "") for k in ("Title", "DisplayTitle", "Comment"))
        if TRACK_AD.search(words) and not COMMENTARY.search(words):
            return {"index": s.get("Index"), "name": str(s.get("DisplayTitle") or s.get("Title") or "Audio description")[:120]}
    return None


def _items():
    """Every film and episode, a page at a time, with its streams only."""
    start = 0
    while True:
        q = urllib.parse.urlencode({"Recursive": "true", "IncludeItemTypes": "Movie,Episode", "Fields": "MediaStreams",
                                    "EnableImages": "false", "EnableUserData": "false", "StartIndex": start, "Limit": PAGE})
        got = jellyfin(f"/Items?{q}") or {}
        items = got.get("Items") or []
        yield from items
        start += len(items)
        if len(items) < PAGE or start >= int(got.get("TotalRecordCount") or 0):
            return


def scan():
    """Reads every film and episode's audio tracks and keeps which have audio description."""
    films, series, total, without = [], {}, 0, []
    for it in _items():
        total += 1
        track = described_track(it.get("MediaStreams"))
        if it.get("Type") == "Episode":
            name = str(it.get("SeriesName") or "Unknown series")
            row = series.setdefault(name, {"name": name, "described": 0, "episodes": 0, "track": ""})
            row["episodes"] += 1
            if track:
                row["described"] += 1
                row["track"] = row["track"] or track["name"]
        elif track:
            year = it.get("ProductionYear")
            films.append({"id": str(it.get("Id") or ""), "name": f"{it.get('Name')}" + (f" ({year})" if year else ""), "track": track["name"]})
        elif it.get("Type") == "Movie" and it.get("Name"):  # kept small: a name and a year, for the Sources' links
            without.append([str(it["Name"])[:120], int(it.get("ProductionYear") or 0)])
    series_rows = sorted((s for s in series.values() if s["described"]), key=lambda s: s["name"].lower())
    films.sort(key=lambda f: f["name"].lower())
    seen = remember("seen", {}) or {}
    now = time.time()
    keys = [f"film:{f['name']}" for f in films] + [f"series:{s['name']}" for s in series_rows]
    seen = {k: seen.get(k, now) for k in keys}  # when each was first found, for Recently found
    keep("seen", seen)
    keep("result", {"at": now, "total": total, "films": films, "series": series_rows})
    # Titles without a described track, for the links in Sources: films by name and year, series not fully described.
    keep("without", {"at": now, "films": sorted(without, key=lambda f: (f[0].lower(), f[1])),
                     "series": sorted(([s["name"], s["described"], s["episodes"]] for s in series.values() if s["described"] < s["episodes"]),
                                      key=lambda x: x[0].lower())})
    return {"said": f"Found {plural(len(films), 'film')} and {plural(len(series_rows), 'series', 'series')} with audio description, of {total:,} films and episodes"}


# Reelix ----------------------------------------------------------------------------------------------------------

def reelix_format():
    """The Audio description custom format, as Reelix keeps it."""
    return {"name": FORMAT_NAME, "include_in_rename": False,
            "specifications": [{"name": "Audio description in the name", "type": "release_title", "value": RELEASE_AD,
                                "negate": False, "required": True}]}


def plan_profiles(profiles, format_id, prefer):
    """Which video quality levels change, and how: Prefer scores the format PREFER (a score someone set themselves is
    kept); deactivated, the format's score goes back to 0 (neutral). Returns [(profile, new profile)]."""
    out = []
    for p in profiles or []:
        if not isinstance(p, dict) or p.get("family", "video") != "video" or "id" not in p:
            continue
        items = [dict(i) for i in p.get("format_items") or [] if isinstance(i, dict)]
        mine = next((i for i in items if int(i.get("format_id", -1)) == format_id), None)
        score = int((mine or {}).get("score") or 0)
        if prefer and score <= 0:
            items = [i for i in items if i is not mine] + [{"format_id": format_id, "score": PREFER}]
        elif not prefer and score > 0:
            items = [i for i in items if i is not mine]
        else:
            continue
        out.append((p, {**p, "format_items": items}))
    return out


def apply_reelix():
    """Keeps Reelix in step with the setting: the format there, and scored in every video quality level."""
    prefer = bool(setting("prefer_in_reelix", True))
    formats = reelix("/customformats") or []
    found = next((f for f in formats if isinstance(f, dict) and str(f.get("name", "")).lower() == FORMAT_NAME.lower()), None)
    if not found and not prefer:
        keep("reelix", {"at": time.time(), "prefer": False, "levels": 0})
        return {"said": "Reelix has no Audio description format, so there is nothing to change"}
    if not found:
        found = reelix("/customformats", data=reelix_format(), method="POST") or {}
        if "id" not in found:
            raise LookupError("Reelix did not add the Audio description format")
    changes = plan_profiles(reelix("/qualityprofiles") or [], int(found["id"]), prefer)
    for old, new in changes:
        reelix(f"/qualityprofiles/{int(old['id'])}", data=new, method="PUT")
    levels = sum(1 for p in reelix("/qualityprofiles") or [] if isinstance(p, dict) and p.get("family", "video") == "video"
                 and any(int(i.get("format_id", -1)) == int(found["id"]) and int(i.get("score") or 0) > 0 for i in p.get("format_items") or []))
    keep("reelix", {"at": time.time(), "prefer": prefer, "levels": levels})
    if prefer:
        return {"said": f"Reelix prefers releases with audio description in {plural(levels, 'quality level')}"}
    return {"said": f"Reelix no longer prefers audio description ({plural(len(changes), 'quality level')} changed)"}


# People ----------------------------------------------------------------------------------------------------------

def _user_config(uid):
    return ((jellyfin(f"/Users/{urllib.parse.quote(uid)}") or {}).get("Configuration")) or {}


def _save_user_config(uid, cfg):
    q = urllib.parse.quote(uid)
    try:
        jellyfin(f"/Users/Configuration?userId={q}", data=cfg, method="POST")  # Jellyfin 10.9 and later
    except urllib.error.HTTPError as e:
        if e.code not in (404, 405):
            raise
        jellyfin(f"/Users/{q}/Configuration", data=cfg, method="POST")  # Jellyfin 10.8


def set_person(uid, want):
    """For someone who wants audio description, Jellyfin remembers the sound track they choose, so choosing the
    described track once is enough for each film or series. Jellyfin has no setting that picks it by itself
    (research, part (a) 5). Taking someone off puts back what they had."""
    people = remember("people", {}) or {}
    cfg = dict(_user_config(uid))
    if want:
        if uid not in people:
            people[uid] = {"remember_before": bool(cfg.get("RememberAudioSelections", True))}
        cfg["RememberAudioSelections"] = True
    else:
        before = (people.pop(uid, None) or {}).get("remember_before", True)
        cfg["RememberAudioSelections"] = bool(before)
    _save_user_config(uid, cfg)
    keep("people", people)


def people_screen(said=""):
    people = remember("people", {}) or {}
    users = jellyfin("/Users") or []
    items = [{"id": str(u.get("Id")), "title": str(u.get("Name") or "Unnamed"), "on": str(u.get("Id")) in people, "actions": ["toggle"],
              "state": "ok" if str(u.get("Id")) in people else "off",
              "detail": "Jellyfin keeps the sound track they choose for each film and series" if str(u.get("Id")) in people
              else "Not chosen"} for u in users if isinstance(u, dict) and u.get("Id")]
    out = {"type": "list", "title": "People who want audio description",
           "intro": "Activate each person who wants audio description. Jellyfin then remembers the sound track they choose, so "
                    "choosing the described track once is enough for each film and series. Jellyfin cannot yet pick it by itself.",
           "items": items}
    return {**out, "said": said} if said else out


def people(body=None):
    if not body:
        return people_screen()
    if body.get("action") != "toggle" or not body.get("id"):
        raise ValueError("Choose a person to activate or deactivate")
    uid = str(body["id"])
    users = {str(u.get("Id")): str(u.get("Name") or "Unnamed") for u in jellyfin("/Users") or [] if isinstance(u, dict)}
    if uid not in users:
        raise ValueError("That person is not in Jellyfin any more. Reload the page")
    want = uid not in (remember("people", {}) or {})
    set_person(uid, want)
    return people_screen(f"Audio description activated for {users[uid]}" if want else f"Audio description deactivated for {users[uid]}")


# Screens and cards -----------------------------------------------------------------------------------------------

def _checked_words(r):
    if not r:
        return "Not checked yet. Run Look for described titles now, or wait for tonight's check."
    return time.strftime("Checked %d %B at %H:%M", time.localtime(r["at"])).replace(" 0", " ")


def titles(body=None):
    r = remember("result") or {}
    items = [{"id": f"film:{f['name']}", "title": f["name"], "detail": f["track"], "group": "Films", "state": "ok", "actions": []}
             for f in r.get("films", [])]
    items += [{"id": f"series:{s['name']}", "title": s["name"], "group": "Series", "state": "ok" if s["described"] == s["episodes"] else "warning",
               "detail": f"{s['described']:,} of {plural(s['episodes'], 'episode')} described", "actions": []} for s in r.get("series", [])]
    count = len(r.get("films", [])) + len(r.get("series", []))
    intro = (f"{plural(len(r.get('films', [])), 'film')} and {plural(len(r.get('series', [])), 'series', 'series')} in Jellyfin have a "
             f"described sound track. {_checked_words(r)}." if r else _checked_words(r))
    if r and not count:
        intro = f"No film or series in Jellyfin has a described sound track yet. {_checked_words(r)}."
    return {"type": "list", "title": "Titles with audio description", "intro": intro, "items": items}


def elsewhere(body=None):
    return {"type": "list", "title": "Audio description elsewhere",
            "intro": "Places that offer audio description in their own apps. Starboard only lists them: it never downloads, "
                     "records or copies from them.",
            "items": [{"id": i, "title": t, "detail": d, "group": "Services", "state": "ok", "state_label": "Link only", "actions": [],
                       "link": {"url": a, "label": f"Open {t}"}} for i, t, d, a in ELSEWHERE]}


# Sources (DASH-410) ----------------------------------------------------------------------------------------------

def _letter(name):
    first = re.sub(r"^(?:the|a|an)\s+", "", name.strip(), flags=re.I)[:1].upper()
    return first if first.isalpha() and first.isascii() else "0 to 9 and others"


def _menus_for(items):
    """Films and Series as menus; each with a sub menu per first letter when it is long. Puts `menu` on each item."""
    menus, by_group = [], defaultdict(list)
    for it in items:
        by_group[it["group"]].append(it)
    for group, rows in by_group.items():
        gid = group.lower()
        menus.append({"id": gid, "title": group, "group": "Your library", "detail": plural(len(rows), "title")})
        if len(rows) <= MENU_SPLIT:
            for it in rows:
                it["menu"] = gid
            continue
        letters = defaultdict(list)
        for it in rows:
            letters[_letter(it["title"])].append(it)
        for letter in sorted(letters, key=lambda x: (len(x) > 1, x)):
            mid = f"{gid}-{letter[:1].lower()}"
            menus.append({"id": mid, "title": letter, "parent": gid, "group": "By first letter", "detail": plural(len(letters[letter]), "title")})
            for it in letters[letter]:
                it["menu"] = mid
    return menus


def _off_screen(title, switch, what):
    return {"type": "list", "title": title, "items": [],
            "intro": f"{switch} is deactivated, so nothing is shown here. Activate it under Sources to see {what}."}


def audiovault(body=None):
    """For each film and series without audio description, a link to AudioVault's own search for it. AudioVault is
    never called: the person opens the link, signs in there and keeps to its rules (25 downloads a day)."""
    title = "Search AudioVault"
    if not setting("audiovault_links", False):
        return _off_screen(title, "AudioVault search links", "a link to AudioVault's search for each title without audio description")
    w = remember("without") or {}
    items = [{"id": f"film:{n}:{y}", "title": f"{n} ({y})" if y else n, "group": "Films", "state": "off", "state_label": "No description here",
              "actions": [], "link": {"url": AUDIOVAULT["film"] + urllib.parse.quote(n), "label": f"Search AudioVault for {n}" + (f" ({y})" if y else "")}}
             for n, y in w.get("films", [])]
    items += [{"id": f"series:{n}", "title": n, "group": "Series", "state": "off" if not d else "warning",
               "state_label": "No description here" if not d else f"{d:,} of {e:,} described",
               "detail": "" if not d else f"{plural(e - d, 'episode')} without a described track",
               "actions": [], "link": {"url": AUDIOVAULT["series"] + urllib.parse.quote(n), "label": f"Search AudioVault for {n}"}}
              for n, d, e in w.get("series", [])]
    intro = ("AudioVault is a free community library of description tracks for blind and partially sighted people. Each link opens its "
             "own search for a title without audio description. Starboard never downloads from AudioVault or reads its pages. It states no "
             "licence, so using it is your choice: sign in there and keep to its 25 downloads a day. Add a track with Audio description tracks.")
    if not w:
        intro = "Not checked yet. Run Look for described titles now, or wait for tonight's check."
    elif not items:
        intro = "Every film and series in Jellyfin has a described sound track, so there is nothing to search for."
    out = {"type": "list", "title": title, "intro": intro[:400], "items": items}
    if items:
        out["menus"] = _menus_for(items)
    return out


def count():
    r = remember("result")
    if not r:
        return {"value": 0, "label": "titles", "note": sbplugin.last_error() or "Not checked yet"}
    n = len(r.get("films", [])) + len(r.get("series", []))
    return {"value": n, "label": "described" if n != 1 else "described title", "note": f"of {r.get('total', 0):,} films and episodes"}


def recent():
    r = remember("result") or {}
    seen = remember("seen", {}) or {}
    rows = [(seen.get(f"film:{f['name']}", 0), f["name"], f["track"]) for f in r.get("films", [])]
    rows += [(seen.get(f"series:{s['name']}", 0), s["name"], f"{s['described']:,} of {plural(s['episodes'], 'episode')} described") for s in r.get("series", [])]
    rows.sort(key=lambda x: -x[0])
    items = [{"title": name, "detail": detail} for _, name, detail in rows[:10]]
    return {"items": items or [{"title": "None found yet", "detail": "Titles with a described sound track show here after the nightly check"}]}


def _background(job, label):
    """A button answers within 10 seconds, so the work goes on in the background and the result is kept."""
    def go():
        try:
            keep(f"_{label}", {"at": time.time(), "said": job().get("said", "Done")})
            keep("_error", None)
        except Exception as e:  # noqa: BLE001 - kept for the card, never fatal
            keep("_error", {"at": time.time(), "text": f"{type(e).__name__}: {e}"[:200]})
    threading.Thread(target=go, daemon=True).start()


def scan_now():
    _background(scan, "scan")
    return {"said": "Looking for described titles. The list updates in a minute or two"}


def reelix_now():
    return _guarded(apply_reelix)


def _guarded(job):
    try:
        out = job()
        keep("_error", None)
        return out
    except Exception as e:  # noqa: BLE001
        keep("_error", {"at": time.time(), "text": f"{type(e).__name__}: {e}"[:200]})
        raise


def youdescribe(body=None):
    """For each film and series in Jellyfin, a link to YouDescribe's own search: volunteers there describe YouTube
    videos, such as trailers. Nothing is fetched from YouDescribe."""
    title = "Search YouDescribe"
    if not setting("youdescribe_links", True):
        return _off_screen(title, "YouDescribe search links", "a link to YouDescribe's search for each title")
    r, w = remember("result") or {}, remember("without") or {}
    rows = [(re.sub(r" \(\d{4}\)$", "", f["name"]), f["name"], "Films", True) for f in r.get("films", [])]
    rows += [(n, f"{n} ({y})" if y else n, "Films", False) for n, y in w.get("films", [])]
    rows += [(x["name"], x["name"], "Series", x["described"] == x["episodes"]) for x in r.get("series", [])]
    rows += [(n, n, "Series", False) for n, d, e in w.get("series", [])]  # a partly described series is in both
    once = {}
    for row in rows:
        once.setdefault((row[2], row[1]), row)
    rows = sorted(once.values(), key=lambda x: (x[2], x[1].lower()))
    items = [{"id": f"{g.lower()}:{shown}", "title": shown, "group": g, "actions": [],
              "state": "ok" if has else "off", "state_label": "Described here" if has else "No description here",
              "link": {"url": YOUDESCRIBE + urllib.parse.quote(q), "label": f"Search YouDescribe for {shown}"[:80]}}
             for q, shown, g, has in rows]
    intro = ("YouDescribe is a free website where volunteers describe YouTube videos, such as trailers and clips, for blind and partially "
             "sighted people. Each link opens YouDescribe's own search for a title in Jellyfin, and plays there in your browser. YouDescribe "
             "offers no way for other apps to search it, so Starboard only links to it.")
    if not r:
        intro = "Not checked yet. Run Look for described titles now, or wait for tonight's check."
    out = {"type": "list", "title": title, "intro": intro[:400], "items": items}
    if items:
        out["menus"] = _menus_for(items)
    return out


def apps(body=None):
    """MovieReading and Earcatch: what they are, a guide to using one alongside Jellyfin, and where to get them."""
    title = "MovieReading and Earcatch"
    if not setting("apps_guide", True):
        return _off_screen(title, "MovieReading and Earcatch", "how to use these apps alongside Jellyfin")
    items = []
    for group, rows in APPS:
        for rid, t, label, detail, link in rows:
            item = {"id": rid, "title": t, "detail": detail, "group": group, "actions": [], "state": "off" if label.startswith("Step") else "ok",
                    "state_label": label}
            if link:
                item["link"] = {"url": link[0], "label": link[1]}
            items.append(item)
    return {"type": "list", "title": title, "items": items,
            "intro": ("MovieReading and Earcatch are free phone apps that play a description through headphones, in step with a film, by "
                      "listening to its sound. Neither publishes a list of titles that other apps may read, so Starboard cannot say which of "
                      "your films they have. RNIB says they are not offered in the UK yet.")}


ROUTES = {"/count": count, "/recent": recent, "/titles": titles, ("POST", "/titles"): titles,
          "/people": people, ("POST", "/people"): people, "/elsewhere": elsewhere, ("POST", "/elsewhere"): elsewhere,
          "/audiovault": audiovault, ("POST", "/audiovault"): audiovault,
          "/youdescribe": youdescribe, ("POST", "/youdescribe"): youdescribe,
          "/apps": apps, ("POST", "/apps"): apps,
          ("POST", "/jobs/scan"): lambda: _guarded(scan), ("POST", "/jobs/reelix"): reelix_now,
          ("POST", "/scan"): scan_now, ("POST", "/reelix"): reelix_now}

if __name__ == "__main__":
    serve(ROUTES)
