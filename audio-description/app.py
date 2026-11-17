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

Rules 1.0 (17 November 2026): the words that mean audio description, the tag, the collection and Play the described
track come from rules.json, shared with the Jellyfin version (TheMightyTRex/jellyfin-plugins, audio-description; its
SYNC.md says what must match). tools/sync_audio_description_rules.py copies it here. When the Jellyfin version is
installed, this plug-in leaves the tag, the collection and Play the described track to it, and says so on its card.
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
from sbplugin import band, changed, fetch, keep, plural, remember, serve, setting

# Release names: TRaSH Guides' "WiTH AD" pattern (a word before "AD", so "A.D." in a title never counts) with the
# longer phrases added (research, part (a) 1). Reelix's patterns are case-insensitive already; (?i) keeps Python the same.
RELEASE_AD = (r"(?i)\b(?:(?:WiTH|MULTi|FRENCH|ENG(?:LISH)?|(?:BA?|A)SL[ ._-]and)[ ._-](?:AD|Audio[ ._-]?Description)"
              r"|Audio[ ._-]?Descri(?:ption|bed)|Descriptive[ ._-](?:Audio|Video)|Described[ ._-]Video|DVS)\b")
# The rules shared with the Jellyfin version (rules.json, beside this file in the image).
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules.json"), encoding="utf-8") as _f:
    RULES = json.load(_f)
# Track titles in the library: short, so a bare AD counts there. Jellyfin does not pass on the visual impaired flag
# (research, part (a) 5), so the title, display title and comment are what can be read.
TRACK_AD = re.compile(RULES["described_track"]["pattern"])
COMMENTARY = re.compile(RULES["described_track"]["ruled_out_pattern"])
TAG = RULES["tag"]
COLLECTION = RULES["collection"]["name"]
PLAY = RULES["play_described_track"]
JELLYFIN_PLUGIN = "7a591954-9c27-4ba7-80c3-dc5f0a140692"  # the Jellyfin version's id (SYNC.md)
JELLYFIN_CHECK_EVERY = 600  # seconds between asks of Jellyfin's plug-in list
IDLE = ("Idle: Jellyfin's own Audio description plug-in is installed, so it does the tag, the collection and Play the "
        "described track, and this one does not")
now = time.time  # replaced in tests
_jf = {"at": 0.0, "installed": False}
FORMAT_NAME = "Audio description"
PAGE = 200
# Legal places with audio description, opened in their own apps (research, part (a) 2 to 4). Nothing is fetched.
ELSEWHERE = [
    ("bbc", "BBC iPlayer", "Audio described programmes, in the iPlayer app or website", "https://www.bbc.co.uk/iplayer/categories/audio-described/featured"),
    ("itvx", "ITVX", "Choose AD (audio description) in the player on programmes that have it", "https://www.itv.com/"),
    ("channel4", "Channel 4", "Audio description in the Channel 4 app on many programmes", "https://www.channel4.com/"),
    ("my5", "My5", "Audio description on some Channel 5 programmes", "https://www.channel5.com/"),
    ("netflix", "Netflix", "Search for audio description in the app", "https://www.netflix.com/browse/audio-description"),
    ("rnib", "RNIB", "Advice on audio description, and the Royal National Institute of Blind People's own reading services", "https://www.rnib.org.uk/living-with-sight-loss/assistive-aids-and-technology/tv-audio-and-gaming/audio-description/"),
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
    return fetch(jf["url"].rstrip("/") + path, sbplugin.jellyfin_headers(jf["api_key"]), data=data, method=method, timeout=30)


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
        # CollapseBoxSetItems=false: without it, Jellyfin 12 answers a key with no person with the Audio description
        # collection in place of the films in it, so they would drop out of the check and lose their tag.
        q = urllib.parse.urlencode({"Recursive": "true", "IncludeItemTypes": "Movie,Episode", "Fields": "MediaStreams,Tags", "CollapseBoxSetItems": "false",
                                    "EnableImages": "false", "EnableUserData": "false", "StartIndex": start, "Limit": PAGE})
        got = jellyfin(f"/Items?{q}") or {}
        items = got.get("Items") or []
        yield from items
        start += len(items)
        if len(items) < PAGE or start >= int(got.get("TotalRecordCount") or 0):
            return


def _episode_row(it, track):
    """One described episode for Titles with audio description: its id, series and episode numbers, name and track."""
    num = lambda k: int(it[k]) if isinstance(it.get(k), int) else None  # noqa: E731
    return {"id": str(it.get("Id") or ""), "season": num("ParentIndexNumber"), "episode": num("IndexNumber"),
            "name": str(it.get("Name") or "")[:120], "track": track["name"]}


def scan():
    """Reads every film and episode's audio tracks and keeps which have audio description: for Titles with audio
    description, each film's id, name, year and track, and each series' id, year and described episodes."""
    films, series, total, without = [], {}, 0, []
    tags = {"want": set(), "have": set(), "series": set(), "films": []}  # for Find and tag, ids only
    for it in _items():
        total += 1
        track = described_track(it.get("MediaStreams"))
        iid = str(it.get("Id") or "")
        if iid and TAG.lower() in [str(t).lower() for t in it.get("Tags") or []]:
            tags["have"].add(iid)
        if iid and track:
            tags["want"].add(iid)
            if it.get("Type") == "Episode" and it.get("SeriesId"):
                tags["series"].add(str(it["SeriesId"]))
            elif it.get("Type") == "Movie":
                tags["films"].append(iid)
        if it.get("Type") == "Episode":
            name = str(it.get("SeriesName") or "Unknown series")
            row = series.setdefault(name, {"name": name, "described": 0, "episodes": 0, "track": "", "id": str(it.get("SeriesId") or ""), "items": []})
            row["episodes"] += 1
            if track:
                row["described"] += 1
                row["track"] = row["track"] or track["name"]
                row["items"].append(_episode_row(it, track))
        elif track:
            year = it.get("ProductionYear")
            films.append({"id": iid, "name": f"{it.get('Name')}" + (f" ({year})" if year else ""), "title": str(it.get("Name") or "")[:120],
                          "year": int(year or 0), "track": track["name"]})
        elif it.get("Type") == "Movie" and it.get("Name"):  # kept small: a name and a year, for the Sources' links
            without.append([str(it["Name"])[:120], int(it.get("ProductionYear") or 0)])
    # Every series once, a page at a time: their tags for Find and tag, and their years for Titles with audio description.
    all_series = _ids({"IncludeItemTypes": "Series", "Fields": "Tags"})
    years = {str(x.get("Id")): int(x.get("ProductionYear") or 0) for x in all_series if isinstance(x, dict)}
    series_rows = sorted((s for s in series.values() if s["described"]), key=lambda s: s["name"].lower())
    for s in series_rows:
        s["year"] = years.get(s["id"], 0)
        s["items"].sort(key=lambda e: (e["season"] is None, e["season"] or 0, e["episode"] is None, e["episode"] or 0, e["name"].lower()))
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
    said = f"Found {plural(len(films), 'film')} and {plural(len(series_rows), 'series', 'series')} with audio description, of {total:,} films and episodes"
    if jellyfin_version_installed(force=True):
        keep("tagged", {"at": time.time(), "idle": True})
        return {"said": said + ". " + IDLE}
    done = find_and_tag(tags, all_series)
    return {"said": said + f". Tagged {done['tagged']:,}, took the tag off {done['untagged']:,}"}


# Find and tag (rules 1.0) ------------------------------------------------------------------------------------------

def jellyfin_version_installed(force=False):
    """True when Jellyfin's own Audio description plug-in is installed and not deactivated (asked of Jellyfin's
    /Plugins at most every 10 minutes). Then this one leaves the tag, the collection and Play the described track to
    it. When Jellyfin cannot be asked, it carries on as before."""
    if not force and now() - _jf["at"] < JELLYFIN_CHECK_EVERY:
        return _jf["installed"]
    try:
        plugins = jellyfin("/Plugins") or []
        _jf["installed"] = any(str(p.get("Id") or "").replace("-", "").lower() == JELLYFIN_PLUGIN.replace("-", "")
                               and str(p.get("Status") or "") not in ("Disabled", "Deleted", "Superseded", "NotSupported")
                               for p in plugins if isinstance(p, dict))
    except Exception:  # noqa: BLE001 - no key yet, or Jellyfin is restarting: keep the last answer
        pass
    _jf["at"] = now()
    return _jf["installed"]


def _ids(query):
    """Every item a query finds, a page at a time: [{Id, Tags}]."""
    start, out = 0, []
    while True:
        got = jellyfin("/Items?" + urllib.parse.urlencode({**query, "Recursive": "true", "CollapseBoxSetItems": "false", "EnableImages": "false", "EnableUserData": "false",
                                                           "StartIndex": start, "Limit": PAGE})) or {}
        items = got.get("Items") or []
        out += items
        start += len(items)
        if len(items) < PAGE or start >= int(got.get("TotalRecordCount") or 0):
            return out


def _full_item(iid):
    """The whole item, as Jellyfin's metadata editor reads it before saving (10.9 and later; else through a person)."""
    q = urllib.parse.quote(iid)
    try:
        return jellyfin(f"/Items/{q}") or {}
    except urllib.error.HTTPError as e:
        if e.code not in (404, 405):
            raise
    uid = next((str(u.get("Id")) for u in jellyfin("/Users") or [] if isinstance(u, dict) and (u.get("Policy") or {}).get("IsAdministrator")), "")
    return jellyfin(f"/Users/{urllib.parse.quote(uid)}/Items/{q}") or {}


def set_tag(iid, want):
    """Adds or takes off the tag, keeping every other tag, as the metadata editor saves an item."""
    item = _full_item(iid)
    tags = [t for t in item.get("Tags") or [] if str(t).lower() != TAG.lower()]
    item["Tags"] = tags + [TAG] if want else tags
    jellyfin(f"/Items/{urllib.parse.quote(iid)}", data=item, method="POST")


def plan_tags(want, have):
    """(ids to tag, ids to take the tag off): only what changes is written."""
    return sorted(want - have), sorted(have - want)


def find_and_tag(tags, series=None):
    """Tags each film and episode with a described track, and each series with one, and takes the tag off the rest.
    While the collection is activated, keeps the collection's films and series the same as the tagged ones. `series`:
    every series with its tags, when the scan has read them already."""
    series = _ids({"IncludeItemTypes": "Series", "Fields": "Tags"}) if series is None else series
    have_series = {str(x.get("Id")) for x in series if TAG.lower() in [str(t).lower() for t in x.get("Tags") or []]}
    add, take = plan_tags(tags["want"] | tags["series"], tags["have"] | have_series)
    for iid in add:
        set_tag(iid, True)
    for iid in take:
        set_tag(iid, False)
    done = {"at": now(), "tagged": len(add), "untagged": len(take), "collection": None}
    if setting("collection", RULES["collection"]["default"]) is True:
        done["collection"] = keep_collection(set(tags["films"]) | tags["series"])
    keep("tagged", done)
    return done


def keep_collection(want):
    """The collection named in rules.json holds exactly the films and series with a described track."""
    boxes = (jellyfin("/Items?" + urllib.parse.urlencode({"IncludeItemTypes": "BoxSet", "Recursive": "true", "searchTerm": COLLECTION})) or {}).get("Items") or []
    box = next((b for b in boxes if str(b.get("Name") or "").lower() == COLLECTION.lower()), None)
    if not box:
        if not want:
            return {"added": 0, "taken": 0}
        jellyfin("/Collections?" + urllib.parse.urlencode({"Name": COLLECTION, "Ids": ",".join(sorted(want)), "IsLocked": "false"}), data=b"", method="POST")
        return {"added": len(want), "taken": 0}
    bid = urllib.parse.quote(str(box["Id"]))
    members = {str(x.get("Id")) for x in _ids({"ParentId": str(box["Id"])})}
    add, take = sorted(want - members), sorted(members - want)
    for chunk in range(0, len(add), 100):
        jellyfin(f"/Collections/{bid}/Items?Ids=" + ",".join(add[chunk:chunk + 100]), data=b"", method="POST")
    for chunk in range(0, len(take), 100):
        jellyfin(f"/Collections/{bid}/Items?Ids=" + ",".join(take[chunk:chunk + 100]), method="DELETE")
    return {"added": len(add), "taken": len(take)}


# Play the described track (rules 1.0) ------------------------------------------------------------------------------

def index_to_play(streams, playing):
    """The described track's Index when it should be chosen, or None: none, or it is already playing."""
    track = described_track(streams)
    return None if not track or track["index"] == playing else track["index"]


def accepts(session):
    cmds = session.get("SupportedCommands") or (session.get("Capabilities") or {}).get("SupportedCommands") or []
    return PLAY["command"] in cmds


def play_described(body=None):
    """Starboard's playback.started event: for each session of a person who chose it, playing a title with a described
    track while another plays, sends Jellyfin's SetAudioStreamIndex command. An app that does not accept it is left
    alone, and the plug-in notes it for the Play the described track page."""
    chosen = set(remember("play", []) or [])
    if not chosen:
        return {"ok": True, "said": "Nobody chose Play the described track"}
    if jellyfin_version_installed():
        return {"ok": True, "said": IDLE}
    sent, notes = remember("play_sent", {}) or {}, []
    for s in jellyfin("/Sessions?ActiveWithinSeconds=120") or []:
        item = (s or {}).get("NowPlayingItem") or {}
        if str(s.get("UserId") or "").replace("-", "") not in {c.replace("-", "") for c in chosen} or not item.get("Id"):
            continue
        key = f"{s.get('Id')}|{item['Id']}"
        if key in sent:
            continue  # once for each start: the person may choose another track themselves
        got = (jellyfin("/Items?" + urllib.parse.urlencode({"Ids": item["Id"], "Fields": "MediaStreams"})) or {}).get("Items") or [{}]
        idx = index_to_play(got[0].get("MediaStreams"), (s.get("PlayState") or {}).get("AudioStreamIndex"))
        if idx is None:
            continue
        sent[key] = now()
        if not accepts(s):
            notes.append(f"{s.get('Client') or 'An app'} on {s.get('DeviceName') or 'a device'} does not accept the command to change the sound track")
            continue
        jellyfin(f"/Sessions/{urllib.parse.quote(str(s['Id']))}/Command", data={"Name": PLAY["command"], "Arguments": {PLAY["argument"]: str(idx)}}, method="POST")
        notes.append(f"Chose the described track of {item.get('Name') or 'a title'} on {s.get('Client') or 'an app'}")
    keep("play_sent", {k: t for k, t in sent.items() if now() - t < 86400})
    if notes:
        keep("play_last", {"at": now(), "notes": notes[-5:]})
    return {"ok": True, "said": "; ".join(notes) or "Nothing to change"}


def on_event(body=None):
    if (body or {}).get("event") != "playback.started":
        return {"ok": True, "said": "Not an event it uses"}
    return play_described(body)


def play_screen(said=""):
    chosen = set(remember("play", []) or [])
    users = jellyfin("/Users") or []
    items = [{"id": str(u.get("Id")), "title": str(u.get("Name") or "Unnamed"), "on": str(u.get("Id")) in chosen, "actions": ["toggle"],
              "state": "ok" if str(u.get("Id")) in chosen else "off",
              "detail": "The described track is chosen when they start a title that has one" if str(u.get("Id")) in chosen else "Inactive"}
             for u in users if isinstance(u, dict) and u.get("Id")]
    last = remember("play_last") or {}
    intro = ("Inactive until you activate a person. When they start a title with a described track and another plays, Starboard asks their "
             "app to change to it, within about half a minute. Not every Jellyfin app accepts this: one that does not plays as it is.")
    if last.get("notes"):
        intro += " Last: " + last["notes"][-1] + "."
    out = {"type": "list", "title": "Play the described track", "intro": intro[:400], "items": items}
    if jellyfin_version_installed():
        out["notices"] = [{"id": "jellyfin", "tone": "info", "title": "Idle: Jellyfin's own Audio description is installed",
                           "text": "Choose the people in Jellyfin's own Audio description plug-in instead. This list does nothing while it is installed."}]
    return {**out, "said": said} if said else out


def play(body=None):
    if not body:
        return play_screen()
    if body.get("action") != "toggle" or not body.get("id"):
        raise ValueError("Choose a person to activate or deactivate")
    uid = str(body["id"])
    users = {str(u.get("Id")): str(u.get("Name") or "Unnamed") for u in jellyfin("/Users") or [] if isinstance(u, dict)}
    if uid not in users:
        raise ValueError("That person is not in Jellyfin any more. Reload the page")
    chosen = list(remember("play", []) or [])
    want = uid not in chosen
    chosen = chosen + [uid] if want else [c for c in chosen if c != uid]
    keep("play", chosen)
    return play_screen(f"Play the described track activated for {users[uid]}" if want else f"Play the described track deactivated for {users[uid]}")


# Reelix ----------------------------------------------------------------------------------------------------------

def _reelix_or_none(path):
    """A Reelix answer, or None when Reelix has no such route (404, 405) or the key may not read it (403)."""
    try:
        return reelix(path)
    except urllib.error.HTTPError as e:
        if e.code in (403, 404, 405):
            return None
        raise


def find_reelix_format():
    """Reelix's own Audio description format: its built-in one, or on an older Reelix, one of that name. Reelix lets
    only an admin key add formats or change quality levels, and Starboard never gives plug-ins one (issue #144), so the
    plug-in only reads."""
    found = _reelix_or_none("/customformats/builtin/audio_description")
    if isinstance(found, dict) and "id" in found:
        return found
    formats = _reelix_or_none("/customformats") or []
    return next((f for f in formats if isinstance(f, dict) and str(f.get("name", "")).lower() == FORMAT_NAME.lower()), None)


def preferring_levels(profiles, format_id):
    """How many video quality levels give the format a score of more than 0."""
    return sum(1 for p in profiles or [] if isinstance(p, dict) and p.get("family", "video") == "video"
               and any(int(i.get("format_id", -1)) == format_id and int(i.get("score") or 0) > 0 for i in p.get("format_items") or []))


REELIX_PLACE = "Settings, Reelix, Picture quality"


def apply_reelix():
    """Says how Reelix treats releases with audio description, and where to change it. It never writes to Reelix and
    never fails the job for this (issue #144): Reelix's own format is set to Prefer in Starboard's Settings, Reelix,
    Picture quality."""
    prefer = bool(setting("prefer_in_reelix", True))
    try:
        found = find_reelix_format()
        levels = None
        if found:
            profiles = _reelix_or_none("/qualityprofiles")
            levels = None if profiles is None else preferring_levels(profiles, int(found["id"]))
    except (LookupError, OSError, ValueError) as e:
        keep("reelix", {"at": time.time(), "prefer": prefer, "levels": 0, "said": str(e)[:150]})
        return {"said": f"{e}"[:200]}
    if not found:
        said = "Reelix has no Audio description format yet. It comes with the next Reelix update"
    elif levels:
        said = f"Reelix prefers releases with audio description in {plural(levels, 'quality level')}"
    elif prefer:
        said = f"To prefer releases with audio description, set Audio description to Prefer in {REELIX_PLACE}"
    else:
        said = f"Reelix does not prefer releases with audio description. To change that, set Audio description to Prefer in {REELIX_PLACE}"
    keep("reelix", {"at": time.time(), "prefer": prefer, "levels": levels or 0, "said": said})
    return {"said": said}


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
                    "choosing the described track once is enough for each film and series. Jellyfin does not pick it by itself.",
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
        return "Not checked yet. Select 'Check for described titles now', or wait for tonight's check."
    return time.strftime("Checked %d %B at %H:%M", time.localtime(r["at"])).replace(" 0", " ")


# Titles with audio description (owner, 17 November 2026: "a page ... to list the items with audio description", the
# same page as the Jellyfin version's): every film and every described episode, by series, from the result the nightly
# check keeps. Nothing more is read from Jellyfin to draw it. Films and Series are the two menus, each with its count;
# each series opens to its described episodes. Each title links to its page in Jellyfin.
TITLES = "Titles with audio description"
ITEMS_MAX = 4000  # Starboard draws up to 4000 items on a page
SERIES_MENUS_MAX = 150  # menus are up to 200: more series than this are listed by first letter, each series a heading
NOT_LINKABLE = ("host.docker.internal", "localhost", "jellyfin", "127.0.0.1", "::1")  # addresses a browser cannot open


def jellyfin_page_base():
    """Jellyfin's address in a browser: the setting, else Starboard's own address for Jellyfin when a browser can
    open it, else "" (no links). Starboard gives plug-ins Jellyfin's address as their container reaches it, which is
    often host.docker.internal."""
    own = str(setting("jellyfin_address", "") or "").strip().rstrip("/")
    if re.match(r"^https?://[^\s<>\"]+$", own):
        return own
    url = str(_run_file("jellyfin.json").get("url") or "").strip().rstrip("/")
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    return "" if not url or host in NOT_LINKABLE or host.startswith("127.") else url


def _jellyfin_link(base, iid, what):
    if not base or not iid:
        return None
    return {"url": f"{base}/web/#/details?id={urllib.parse.quote(iid)}", "label": f"Open {what} in Jellyfin"[:80]}


def episode_words(e):
    """S1 E3: Name, or the name alone when Jellyfin has no numbers for it."""
    if e.get("season") is not None and e.get("episode") is not None:
        return f"S{e['season']} E{e['episode']}: {e['name']}" if e.get("name") else f"S{e['season']} E{e['episode']}"
    return e.get("name") or "An episode"


def series_words(s):
    """The series' status in words: All 6 episodes described, or 3 of 6 episodes described."""
    if s["described"] == s["episodes"]:
        if s["episodes"] > 1:
            return f"All {s['episodes']:,} episodes described"
    return f"{s['described']:,} of {plural(s['episodes'], 'episode')} described"


def titles(body=None):
    r = remember("result") or {}
    films, series = r.get("films", []), r.get("series", [])
    base = jellyfin_page_base()
    episodes = sum(len(s.get("items") or []) for s in series)
    # Starboard adds how many titles each menu holds, so Films needs no count of its own, and Series says how many series.
    menus = [{"id": "films", "title": "Films", "group": "Show"},
             {"id": "series", "title": "Series", "group": "Show", "detail": plural(len(series), "series", "series")}]
    items = [{"id": f"film:{f.get('id') or f['name']}", "title": f["name"], "detail": f"Described track: {f['track']}", "group": "Films",
              "menu": "films", "state": "ok", "state_label": "Described", "actions": [],
              **({"link": link} if (link := _jellyfin_link(base, f.get("id"), f["name"])) else {})} for f in films]
    by_letter = len(series) > SERIES_MENUS_MAX
    letters = set()
    for s in series:
        shown = f"{s['name']} ({s['year']})" if s.get("year") else s["name"]
        sid = f"series:{s.get('id') or s['name']}"
        menu = sid
        if by_letter:  # a long list: Series opens by first letter, and each series is a heading there
            letter = _letter(s["name"])
            menu = f"series-{letter[:1].lower()}"
            if letter not in letters:
                letters.add(letter)
                menus.append({"id": menu, "title": letter, "parent": "series", "group": "By first letter"})
        else:
            menus.append({"id": sid, "title": shown[:80], "parent": "series", "group": "Series",
                          "detail": f"{series_words(s)}. Described track: {s['track']}"[:200]})
        for e in s.get("items") or []:
            what = episode_words(e)
            items.append({"id": f"episode:{e.get('id') or s['name'] + what}", "title": what, "detail": f"Described track: {e['track']}",
                          "group": shown[:40] if by_letter else "Episodes", "menu": menu, "state": "ok", "state_label": "Described", "actions": [],
                          **({"link": link} if (link := _jellyfin_link(base, e.get("id"), f"{s['name']} {what}")) else {})})
    cut = len(items) > ITEMS_MAX
    items = items[:ITEMS_MAX]
    if not r:
        intro = _checked_words(r)
    elif not films and not series:
        intro = f"No film or series in Jellyfin has a described sound track yet. {_checked_words(r)}."
    else:
        intro = (f"{plural(len(films), 'film')} and {plural(episodes, 'episode')} in {plural(len(series), 'series', 'series')} have a described "
                 f"sound track. {_checked_words(r)}.")
        if series and any("items" not in s for s in series):
            intro += " Select 'Check for described titles now' to list each series' episodes."
        if cut:
            intro += f" Only the first {ITEMS_MAX:,} are listed."
        intro += (" Each title opens its page in Jellyfin, in a new tab." if base else
                  " To open each title in Jellyfin from here, enter the address you open Jellyfin at in 'Jellyfin address for links'.")
    out = {"type": "list", "title": TITLES, "intro": intro[:400], "items": items}
    if r and (films or series):
        out["menus"] = menus[:200]
    return out


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
            "intro": f"{switch} is deactivated, so nothing is shown here. Activate it under 'Sources' to show {what}."}


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
        intro = "Not checked yet. Select 'Check for described titles now', or wait for tonight's check."
    elif not items:
        intro = "Every film and series in Jellyfin has a described sound track, so there is nothing to search for."
    out = {"type": "list", "title": title, "intro": intro[:400], "items": items}
    if items:
        out["menus"] = _menus_for(items)
    return out


def count():
    r = remember("result")
    if not r:
        err = sbplugin.last_error()
        return band({"value": 0, "label": "titles", "note": err or "Not checked yet"}, "problem" if err else "scheduled",
                    label=None if err else "Checks tonight")
    n = len(r.get("films", [])) + len(r.get("series", []))
    if jellyfin_version_installed():
        return band({"value": n, "label": "described" if n != 1 else "described title", "note": "Idle: Jellyfin's own Audio description tags them"},
                    "idle", changed("result"), "Idle")
    return band({"value": n, "label": "described" if n != 1 else "described title", "note": f"of {r.get('total', 0):,} films and episodes"},
                "ok", changed("result"))


def recent():
    r = remember("result") or {}
    seen = remember("seen", {}) or {}
    rows = [(seen.get(f"film:{f['name']}", 0), f["name"], f["track"]) for f in r.get("films", [])]
    rows += [(seen.get(f"series:{s['name']}", 0), s["name"], f"{s['described']:,} of {plural(s['episodes'], 'episode')} described") for s in r.get("series", [])]
    rows.sort(key=lambda x: -x[0])
    items = [{"title": name, "detail": detail} for _, name, detail in rows[:10]]
    if not items:
        return band({"items": [{"title": "None found yet", "detail": "Titles with a described sound track show here after the nightly check"}]},
                    "scheduled" if not r else "ok", changed("result"), "Checks tonight" if not r else None)
    return band({"items": items}, "ok", changed("result"))


def _background(job, label):
    """A button answers within 10 seconds, so the work goes on in the background and the result is kept."""
    def go():
        try:
            with sbplugin.working(label):  # an update waits for it (plug-in API 1.14)
                keep(f"_{label}", {"at": time.time(), "said": job().get("said", "Done")})
            keep("_error", None)
        except Exception as e:  # noqa: BLE001 - kept for the card, never fatal
            keep("_error", {"at": time.time(), "text": f"{type(e).__name__}: {e}"[:200]})
    threading.Thread(target=go, daemon=True).start()


def scan_now():
    _background(scan, "scan")
    return {"said": "Checking for described titles. The list updates in a minute or two"}


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
        intro = "Not checked yet. Select 'Check for described titles now', or wait for tonight's check."
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
                      "your films they have. The Royal National Institute of Blind People (RNIB) says they are not offered in the UK.")}


ROUTES = {"/count": count, "/recent": recent, "/titles": titles, ("POST", "/titles"): titles,
          "/people": people, ("POST", "/people"): people, "/elsewhere": elsewhere, ("POST", "/elsewhere"): elsewhere,
          "/audiovault": audiovault, ("POST", "/audiovault"): audiovault,
          "/youdescribe": youdescribe, ("POST", "/youdescribe"): youdescribe,
          "/apps": apps, ("POST", "/apps"): apps,
          "/play": play, ("POST", "/play"): play, ("POST", "/events"): on_event,
          ("POST", "/jobs/scan"): lambda: _guarded(scan), ("POST", "/jobs/reelix"): reelix_now,
          ("POST", "/scan"): scan_now, ("POST", "/reelix"): reelix_now}

if __name__ == "__main__":
    serve(ROUTES)
