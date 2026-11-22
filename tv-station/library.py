"""What a channel shows, read from Jellyfin: series, films, collections, playlists, genres and decades, and the clips
for its breaks. Asked only when a channel changes and once a night, never while anyone watches."""
import re
import urllib.parse

import three_d
import tv_words

MAX_ENTRIES = 5000  # the most programmes in one channel's line-up
PAGE = 200
FIELDS = "Overview,PremiereDate,Genres,MediaStreams,ProductionYear,ParentBackdropItemId,Path,Video3DFormat"  # 0.5.5: 3D
VIDEO_TYPES = "Movie,Episode"
KINDS = {"series": "Series", "film": "Film", "collection": "Collection", "playlist": "Playlist", "genre": "Genre",
         "decade": "Decade"}
ID = re.compile(r"^[0-9a-fA-F-]{32,36}$")


def _q(**params):
    return urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "")})


def _pages(jf, path, **params):
    """Every item of a Jellyfin list, a page at a time, so no answer is over a few hundred kilobytes."""
    start = 0
    while True:
        got = jf(f"{path}?{_q(StartIndex=start, Limit=PAGE, **params)}") or {}
        items = got.get("Items") or []
        yield from items
        start += len(items)
        if not items or start >= int(got.get("TotalRecordCount") or 0) or start >= MAX_ENTRIES:
            return


def entry(item):
    """One programme in a line-up, from a Jellyfin item. None for an item with no length (nothing to play)."""
    ticks = item.get("RunTimeTicks") or 0
    if ticks <= 0 or item.get("IsFolder"):
        return None
    audio = [s for s in item.get("MediaStreams") or [] if s.get("Type") == "Audio"]
    # The sound track as FFmpeg numbers it inside the file (0.5.4, owner, 19 November 2026: Late ink showed only the
    # fallback slate). Jellyfin's Index counts external files too (an .srt beside the video is often 0), so it is not
    # the file's own stream number; the default track's place among the file's own sound tracks is, as 0:a:N.
    inside = sorted((s for s in audio if not s.get("IsExternal")), key=lambda s: s.get("Index") or 0)
    default = next((s for s in inside if s.get("IsDefault")), inside[0] if inside else None)
    # Each of those tracks' languages (0.6.0), kept only when there is a choice, so the station's language can pick
    # its track as the programme plays (sound_for), and a change of language needs no new read of the line-up.
    langs = [str(s.get("Language") or "").strip().lower() for s in inside] if len(inside) > 1 else []
    episode = item.get("Type") == "Episode"
    out = {"id": item["Id"], "dur": round(ticks / 1e7, 2), "kind": "Episode" if episode else "Movie",
           "title": (item.get("SeriesName") if episode else item.get("Name")) or item.get("Name") or "Programme",
           "group": item.get("SeriesId") if episode else item["Id"],
           "plot": (item.get("Overview") or "")[:400], "year": item.get("ProductionYear"),
           "premiere": (item.get("PremiereDate") or "")[:10], "genres": (item.get("Genres") or [])[:3],
           "art": item["Id"], "backdrop": item.get("ParentBackdropItemId") or item.get("SeriesId") or item["Id"],
           "audio_n": inside.index(default) if default else None, "has_audio": bool(inside),
           "three_d": three_d.said(item)}  # 0.5.5: why Jellyfin or the file name says it is 3D, or ""
    if any(langs):
        out["audio_langs"] = langs
    if described_tracks(inside):  # 0.7.0: kept only when the file has one, for audio description on promos
        out["audio_ad"] = described_tracks(inside)
    if episode:
        out.update({"ep": item.get("Name") or "", "s": item.get("ParentIndexNumber"), "e": item.get("IndexNumber")})
    return out


# A sound track that is audio description, by its name, as the Audio description plug-ins read it (their rules.json,
# described_track): "English (Audio Description)", "AD", "Descriptive audio", "DVS". A commentary never counts.
TRACK_AD = re.compile(r"(?i)(?:\baudio[ ._-]?descri(?:ption|bed)\b|\bdescriptive[ ._-]?(?:audio|video)\b|\bdescribed\b|\bDVS\b|(?:^|[\s\[(._-])AD(?:$|[\s\])._-]))")
COMMENTARY = re.compile(r"(?i)comment(?:ary)?")


def described_tracks(streams):
    """Which of the file's own sound tracks are audio description: their places among them (0:a:N)."""
    out = []
    for n, s in enumerate(streams):
        words = " ".join(str(s.get(k) or "") for k in ("Title", "DisplayTitle", "Comment"))
        if TRACK_AD.search(words) and not COMMENTARY.search(words):
            out.append(n)
    return out


def sound_for(e, lang="en", described=False):
    """Which of the file's own sound tracks to play (0:a:N): the first in the station's language (0.6.0, owner,
    21 November 2026), else the default track (audio_n, 0.5.4), else None. Jellyfin gives languages as ISO 639-2,
    such as fre or fra, ger or deu (tv_words.SOUND_CODES).

    described (0.7.0, audio description on promos): a described track first, in the station's language when one is,
    else any described track; a programme with none plays as before."""
    codes = tv_words.sound_codes(lang)
    if described and e.get("audio_ad"):
        langs = e.get("audio_langs") or []
        return next((n for n in e["audio_ad"] if n < len(langs) and langs[n] in codes), e["audio_ad"][0])
    for n, code in enumerate(e.get("audio_langs") or []):
        if code in codes:
            return n
    return e.get("audio_n")


def _episodes(jf, series_id):
    items = _pages(jf, "/Items", ParentId=series_id, IncludeItemTypes="Episode", Recursive="true", IsMissing="false",
                   SortBy="ParentIndexNumber,IndexNumber,SortName", Fields=FIELDS)
    return [i for i in items if (i.get("ParentIndexNumber") or 0) != 0]  # specials (series 0) are left out


def _expand(jf, items):
    """Films as they are, series as their episodes in aired order."""
    for i in items:
        if i.get("Type") == "Series":
            yield from _episodes(jf, i["Id"])
        elif i.get("Type") in ("Movie", "Episode", "Video", "MusicVideo"):
            yield i


def source_items(jf, source):
    kind, value = source.get("kind"), source.get("id") or source.get("value")
    if kind == "series":
        return _episodes(jf, value)
    if kind == "film":
        got = jf(f"/Items?{_q(Ids=value, Fields=FIELDS)}") or {}
        return got.get("Items") or []
    if kind == "collection":
        return list(_expand(jf, _pages(jf, "/Items", ParentId=value, Fields=FIELDS, SortBy="ProductionYear,SortName")))
    if kind == "playlist":
        return list(_expand(jf, _pages(jf, f"/Playlists/{value}/Items", Fields=FIELDS)))
    if kind == "genre":
        return list(_expand(jf, _pages(jf, "/Items", Genres=value, IncludeItemTypes="Movie,Series", Recursive="true",
                                       SortBy="SortName", Fields=FIELDS)))
    if kind == "decade":
        start = int(value)
        years = ",".join(str(y) for y in range(start, start + 10))
        return list(_expand(jf, _pages(jf, "/Items", Years=years, IncludeItemTypes="Movie,Series", Recursive="true",
                                       SortBy="ProductionYear,SortName", Fields=FIELDS)))
    return []


def lineup(jf, sources):
    """The channel's programmes, in the order its sources give them, each once. A playlist keeps its own order, so
    each of its items is a group of its own."""
    out, seen = [], set()
    for src in sources:
        for item in source_items(jf, src):
            e = entry(item)
            if not e or e["id"] in seen:
                continue
            if src.get("kind") == "playlist":
                e["group"] = e["id"]
            seen.add(e["id"])
            out.append(e)
            if len(out) >= MAX_ENTRIES:
                return out
    return out


def search(jf, kind, words):
    """Up to 8 matches for what the owner entered: [(id or value, words people read)]."""
    words = (words or "").strip()
    if not words:
        return []
    if kind == "decade":
        m = re.match(r"^(\d{2,4})s?$", words.replace("'", ""))
        if not m:
            return []
        y = int(m.group(1))
        y = y + 1900 if y < 100 else y
        y -= y % 10
        return [(str(y), f"The {y}s")]
    if kind == "decade":
        # Every decade the library has, from Jellyfin's list of years (one small answer), newest first.
        got = jf(f"/Years?{_q(IncludeItemTypes='Movie,Series', Recursive='true', SortBy='SortName')}") or {}
        decades = sorted({int(y["Name"]) // 10 * 10 for y in got.get("Items") or [] if str(y.get("Name") or "").isdigit()}, reverse=True)
        rows = [(str(d), f"The {d}s", "Decade") for d in decades if not words or words.lower() in f"the {d}s"]
        return rows[start:start + limit], len(rows)
    if kind == "genre":
        got = jf(f"/Genres?{_q(SearchTerm=words, Limit=8)}") or {}
        return [(g["Name"], g["Name"]) for g in got.get("Items") or []]
    types = {"series": "Series", "film": "Movie", "collection": "BoxSet", "playlist": "Playlist", "clips": "BoxSet,Folder,CollectionFolder"}[kind]
    got = jf(f"/Items?{_q(SearchTerm=words, IncludeItemTypes=types, Recursive='true', Limit=8, Fields='ProductionYear')}") or {}
    out = []
    for i in got.get("Items") or []:
        year = f" ({i['ProductionYear']})" if i.get("ProductionYear") and f"({i['ProductionYear']})" not in (i.get("Name") or "") else ""
        out.append((i["Id"], f"{i.get('Name') or 'Untitled'}{year}"))
    return out


BROWSE_TYPES = {"series": "Series", "film": "Movie", "collection": "BoxSet", "playlist": "Playlist"}


def browse(jf, kind, words="", start=0, limit=100):
    """A page of the library for Choose from your library (0.2.0): ([(id or name, title, detail)], how many in all).
    Every series, film, collection, playlist, genre or decade, by name, a page at a time; only those matching the
    words when there are any."""
    words = (words or "").strip()[:80]
    start = max(0, int(start or 0))
    if kind == "decade":
        # Every decade the library has, from Jellyfin's list of years (one small answer), newest first.
        got = jf(f"/Years?{_q(IncludeItemTypes='Movie,Series', Recursive='true', SortBy='SortName')}") or {}
        decades = sorted({int(y["Name"]) // 10 * 10 for y in got.get("Items") or [] if str(y.get("Name") or "").isdigit()}, reverse=True)
        rows = [(str(d), f"The {d}s", "Decade") for d in decades if not words or words.lower() in f"the {d}s"]
        return rows[start:start + limit], len(rows)
    if kind == "genre":
        got = jf(f"/Genres?{_q(SearchTerm=words, StartIndex=start, Limit=limit, SortBy='SortName', IncludeItemTypes='Movie,Series', Recursive='true')}") or {}
        return [(g["Name"], g["Name"], "Genre") for g in got.get("Items") or [] if g.get("Name")], int(got.get("TotalRecordCount") or 0)
    t = BROWSE_TYPES.get(kind, "Series")
    got = jf(f"/Items?{_q(SearchTerm=words, IncludeItemTypes=t, Recursive='true', SortBy='SortName', StartIndex=start, Limit=limit, Fields='ProductionYear,ChildCount')}") or {}
    out = []
    for i in got.get("Items") or []:
        year = i.get("ProductionYear")
        detail = KINDS.get(kind, "Series") + (f", {year}" if year else "")
        if kind in ("collection", "playlist") and i.get("ChildCount"):
            detail += f", {i['ChildCount']} items"
        out.append((i["Id"], i.get("Name") or "Untitled", detail))
    return out, int(got.get("TotalRecordCount") or 0)


def names(jf, ids):
    """The names of Jellyfin items by id, with their year: {id: "Name (1999)"}."""
    out = {}
    for k in range(0, len(ids), 50):
        got = jf(f"/Items?{_q(Ids=','.join(ids[k:k + 50]), Fields='ProductionYear')}") or {}
        for i in got.get("Items") or []:
            year = f" ({i['ProductionYear']})" if i.get("ProductionYear") and f"({i['ProductionYear']})" not in (i.get("Name") or "") else ""
            out[i["Id"]] = f"{i.get('Name') or 'Untitled'}{year}"
    return out


def best(matches, words):
    """The match whose name is the words entered, else the first."""
    w = (words or "").strip().lower()
    for m in matches:
        if m[1].lower() == w or re.sub(r" \(\d{4}\)$", "", m[1]).lower() == w:
            return m
    return matches[0] if matches else None


def jellyfin_clips(jf, folder_id, role):
    """The videos in a Jellyfin collection or folder, as clips for breaks."""
    out = []
    for i in _pages(jf, "/Items", ParentId=folder_id, Recursive="true", IsFolder="false", Fields="MediaStreams"):
        e = entry(i)
        if e and e["dur"] <= 600:  # a clip longer than 10 minutes is not a break
            out.append({"id": f"jf-{i['Id']}", "src": f"jf:{i['Id']}", "dur": e["dur"], "title": i.get("Name") or "Clip",
                        "role": role, "has_audio": e["has_audio"], "audio_n": e["audio_n"],
                        **({"audio_langs": e["audio_langs"]} if e.get("audio_langs") else {})})
    return out


def trailers(jf, entries, most=60):
    """Jellyfin's own trailers (local trailers) of the films in a line-up, as clips for breaks."""
    out = []
    for e in [e for e in entries if e.get("kind") == "Movie"][:most]:
        try:
            got = jf(f"/Items/{e['id']}/LocalTrailers") or []
        except Exception:  # noqa: BLE001 - a film with no trailers, or an older Jellyfin
            continue
        for t in got[:1]:
            ticks = t.get("RunTimeTicks") or 0
            if 0 < ticks / 1e7 <= 600:
                out.append({"id": f"tr-{t['Id']}", "src": f"jf:{t['Id']}", "dur": round(ticks / 1e7, 2),
                            "title": f"Trailer: {e['title']}", "role": "trailer", "has_audio": True, "audio": None})
    return out
