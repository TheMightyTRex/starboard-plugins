"""Titles and descriptions in the station's language (0.6.0, owner, 21 November 2026).

Jellyfin keeps one language of titles and plots for each library, and its item lists cannot be asked for another.
Its remote search can: POST /Items/RemoteSearch/Movie or /Series with the item's provider ids (TMDB, IMDb, TVDB) and a
MetadataLanguage gives the provider's title and overview in that language, without changing anything in Jellyfin.
It has no remote search for episodes, so a series gets its name in the language, while an episode's own name and plot
stay as Jellyfin has them.

Lightweight first: nothing is fetched for English, nor for the whole library. Only programmes about to be drawn or
written are asked for (the next hours of a channel being watched, the guide's days in the nightly refresh, a promo
being made), at most PER_HOUR a rolling hour, each once: the answer, or that there was none, is kept on disk per item
and language. Anything that fails leaves Jellyfin's own text.
"""
import json
import os
import threading
import time

import tv_words as words

PER_HOUR = 60  # remote searches in any hour (each is two small asks of Jellyfin, which asks TMDB)
MOST_KEPT = 4000  # titles kept on disk; the oldest go first
MOST_WAITING = 300  # programmes waiting to be asked for
RETRY_DAYS = 7  # an item with no answer is asked for again after this long
PLOT = 400  # the longest plot kept, as library.entry keeps


def key_of(e):
    """(kind for the remote search, Jellyfin id) for a programme: a film itself, an episode's series."""
    if not e or not e.get("id"):
        return None
    if e.get("kind") == "Episode":
        return ("Series", e.get("group")) if e.get("group") else None
    return ("Movie", e["id"])


def remote(jf, kind, iid, lang):
    """The provider's (title, overview) for one Jellyfin film or series in `lang`, or None when there is none.
    jf(path, data=..., method=...) asks Jellyfin. Only an answer whose provider id is the item's own is taken."""
    meta = words.METADATA.get(words.code(lang))
    if not meta:
        return None
    got = jf(f"/Items?Ids={iid}&Fields=ProviderIds,ProductionYear") or {}
    items = got.get("Items") or []
    if not items:
        return None
    item = items[0]
    ids = {k.lower(): str(v) for k, v in (item.get("ProviderIds") or {}).items() if v}
    if not ids:
        return None
    info = {"Name": item.get("Name") or "", "ProviderIds": item.get("ProviderIds"), "MetadataLanguage": meta[0],
            "MetadataCountryCode": meta[1]}
    if item.get("ProductionYear"):
        info["Year"] = item["ProductionYear"]
    # IncludeDisabledProviders: the search works even where the library's own metadata fetchers are turned off.
    found = jf(f"/Items/RemoteSearch/{kind}", data={"SearchInfo": info, "ItemId": iid, "IncludeDisabledProviders": True},
               method="POST") or []
    for r in found if isinstance(found, list) else []:
        theirs = {k.lower(): str(v) for k, v in (r.get("ProviderIds") or {}).items() if v}
        if any(theirs.get(k) == v for k, v in ids.items()):
            name = " ".join(str(r.get("Name") or "").split())[:200]
            plot = " ".join(str(r.get("Overview") or "").split())[:PLOT]
            return (name, plot) if name or plot else None
    return None


class Titles:
    """The titles kept, in a small JSON file: {"lang:Kind:id": {"t": title, "o": overview, "at": when}}, or
    {"at": when, "none": 1} for an item the provider had nothing for."""

    def __init__(self, path, jf=None, per_hour=PER_HOUR, clock=time.time):
        self.path, self.jf, self.per_hour, self.clock = path, jf, per_hour, clock
        self.lock = threading.Lock()
        self.data = None
        self.asked = []  # when each recent remote search was made
        self.waiting = {}  # "lang:Kind:id" -> (kind, id, lang)
        self.working = False

    def _load(self):
        if self.data is None:
            try:
                with open(self.path, encoding="utf-8") as f:
                    got = json.load(f)
                self.data = got if isinstance(got, dict) else {}
            except (OSError, ValueError):
                self.data = {}
        return self.data

    def _save(self):
        data = self._load()
        if len(data) > MOST_KEPT:
            for k in sorted(data, key=lambda k: data[k].get("at") or 0)[: len(data) - MOST_KEPT]:
                del data[k]
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        part = self.path + ".part"
        with open(part, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        os.replace(part, self.path)

    @staticmethod
    def _k(kind, iid, lang):
        return f"{lang}:{kind}:{iid}"

    def kept(self, e, lang):
        """What is kept for a programme in `lang`: {"t", "o"}, {"none": 1}, or None when it has not been asked for."""
        k = key_of(e)
        if not k:
            return None
        with self.lock:
            return self._load().get(self._k(k[0], k[1], words.code(lang)))

    def localise(self, e, lang):
        """The programme with its title (and a film's plot) in `lang` where one is kept, else as it is; one not kept
        yet waits to be asked for. Never asks Jellyfin itself, so drawing never waits on it."""
        lang = words.code(lang)
        if lang == words.DEFAULT or not e:
            return e
        got = self.kept(e, lang)
        if got is None:
            self.want([e], lang)
            return e
        if got.get("none"):
            return e
        out = dict(e)
        if got.get("t"):
            out["title"] = got["t"]
        if got.get("o") and e.get("kind") != "Episode":  # an episode's plot is its own, not the series'
            out["plot"] = got["o"]
        return out

    def want(self, entries, lang, first=False):
        """Puts programmes not kept yet (or with no answer for RETRY_DAYS) in the queue to be asked for; with `first`,
        at the front of it (a promo being made)."""
        lang = words.code(lang)
        if lang == words.DEFAULT:
            return 0
        now, added = self.clock(), 0
        with self.lock:
            data = self._load()
            for e in entries:
                k = key_of(e)
                if not k:
                    continue
                kk = self._k(k[0], k[1], lang)
                got = data.get(kk)
                if first and kk in self.waiting:
                    self.waiting = {kk: self.waiting.pop(kk), **self.waiting}
                    continue
                if kk in self.waiting or (got and not (got.get("none") and now - (got.get("at") or 0) > RETRY_DAYS * 86400)):
                    continue
                if len(self.waiting) >= MOST_WAITING and not first:
                    break
                if first:
                    self.waiting = {kk: (k[0], k[1], lang), **self.waiting}
                else:
                    self.waiting[kk] = (k[0], k[1], lang)
                added += 1
        return added

    def _room(self):
        now = self.clock()
        self.asked = [t for t in self.asked if now - t < 3600]
        return self.per_hour - len(self.asked)

    def work(self, most=None, stop=None):
        """Asks for the programmes waiting, within the hourly limit (and `most`), and keeps the answers. Returns how
        many were asked for. `stop()` True ends it early, such as when the plug-in is about to be updated."""
        if not self.jf:
            return 0
        done = 0
        while True:
            with self.lock:
                if not self.waiting or self._room() <= 0 or (most is not None and done >= most) or (stop and stop()):
                    break
                kk, (kind, iid, lang) = next(iter(self.waiting.items()))
                del self.waiting[kk]
                self.asked.append(self.clock())
            try:
                got = remote(self.jf, kind, iid, lang)
            except Exception:  # noqa: BLE001 - Jellyfin or the provider could not answer: Jellyfin's own text stays
                got = None
            with self.lock:
                self._load()[kk] = ({"t": got[0], "o": got[1], "at": int(self.clock())} if got else
                                    {"none": 1, "at": int(self.clock())})
            done += 1
        if done:
            with self.lock:
                try:
                    self._save()
                except OSError:
                    pass
        return done

    def work_soon(self, stop=None):
        """Asks for the programmes waiting on a thread of its own, one at a time; nothing when one is running."""
        with self.lock:
            if self.working or not self.waiting or not self.jf:
                return False
            self.working = True

        def run():
            try:
                self.work(stop=stop)
            finally:
                with self.lock:
                    self.working = False
        threading.Thread(target=run, name="titles", daemon=True).start()
        return True
