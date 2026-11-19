"""What a channel shows, read from Jellyfin: series, films, collections, playlists, genres and decades, and the clips
for its breaks. Asked only when a channel changes and once a night, never while anyone watches."""
import re
import urllib.parse

MAX_ENTRIES = 5000  # the most programmes in one channel's line-up
PAGE = 200
FIELDS = "Overview,PremiereDate,Genres,MediaStreams,ProductionYear,ParentBackdropItemId"
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
    default = next((s for s in audio if s.get("IsDefault")), audio[0] if audio else None)
    episode = item.get("Type") == "Episode"
    out = {"id": item["Id"], "dur": round(ticks / 1e7, 2), "kind": "Episode" if episode else "Movie",
           "title": (item.get("SeriesName") if episode else item.get("Name")) or item.get("Name") or "Programme",
           "group": item.get("SeriesId") if episode else item["Id"],
           "plot": (item.get("Overview") or "")[:400], "year": item.get("ProductionYear"),
           "premiere": (item.get("PremiereDate") or "")[:10], "genres": (item.get("Genres") or [])[:3],
           "art": item["Id"], "backdrop": item.get("ParentBackdropItemId") or item.get("SeriesId") or item["Id"],
           "audio": default.get("Index") if default else None, "has_audio": bool(audio)}
    if episode:
        out.update({"ep": item.get("Name") or "", "s": item.get("ParentIndexNumber"), "e": item.get("IndexNumber")})
    return out


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
                        "role": role, "has_audio": e["has_audio"], "audio": e["audio"]})
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
