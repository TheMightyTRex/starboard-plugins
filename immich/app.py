"""Immich: photo and video counts, storage used and the job queue of an Immich server, on cards.

Nothing runs at rest. The container starts when Starboard asks for a card, asks Immich with the API key (header x-api-key),
keeps each answer for a minute in memory so a dashboard that asks several cards makes one set of requests, and rests again.
The API key is a secret setting: read from the settings each time and never written to /data, a card or an error message.

What it asks (Immich's OpenAPI description, immich-app/immich open-api/immich-openapi-specs.json; not tried against a
real server, see the help). The key needs the permissions server.statistics, server.storage and queue.read (job.read on an
older Immich that has no /api/queues):
- GET /api/server/statistics: photos, videos, usage, usagePhotos, usageVideos, usageByUser.
- GET /api/server/storage: diskSizeRaw, diskUseRaw, diskAvailableRaw, diskUsagePercentage.
The job queues page (DASH-578) also changes queues, with a key that has queue.update (job.create on an older Immich):
- PUT /api/queues/<name> {"isPaused": true or false} pauses or resumes a queue; DELETE /api/queues/<name>/jobs {"failed": true}
  clears its failed jobs. On an older Immich, PUT /api/jobs/<name> {"command": "pause" | "resume" | "clear-failed", "force": false}.
  Neither was tried against a real server.
- GET /api/queues: a list of {name, isPaused, statistics: {active, waiting, failed, delayed, paused, completed}}; on an older
  Immich, GET /api/jobs: {name: {jobCounts: {...}, queueStatus: {isActive, isPaused}}}.
"""
import http.client
import json
import os
import re
import time
import urllib.error
import urllib.parse

import sbplugin as sb
from sbplugin import band, serve, setting

KEEP_SECONDS = 60
CACHE = {}
NAMES = {"thumbnailGeneration": "Thumbnails", "metadataExtraction": "Metadata", "videoConversion": "Video conversion", "faceDetection": "Face detection",
         "facialRecognition": "Facial recognition", "smartSearch": "Smart search", "duplicateDetection": "Duplicate detection",
         "backgroundTask": "Background tasks", "storageTemplateMigration": "Storage template", "migration": "Migration", "search": "Search",
         "sidecar": "Sidecar files", "library": "External libraries", "notifications": "Notifications", "backupDatabase": "Database backup",
         "ocr": "Text in pictures", "workflow": "Workflows", "integrityCheck": "Integrity check", "editor": "Editor"}


def clean(text):
    """An error with the key taken out."""
    text = str(text)
    key = str(setting("api_key", "") or "")
    if key:
        text = text.replace(key, "***")
    return text[:200]


def _why(e):
    code = getattr(e, "code", None)
    if code in (401, 403):
        return "it refused the API key (does the key have the server.statistics, server.storage and queue.read permissions?)"
    if code == 404:
        return "the address does not answer like Immich (is it the right address, without /api on the end?)"
    if code:
        return f"it answered with error {code}"
    if isinstance(e, (OSError, http.client.HTTPException)):
        return "it could not be reached"
    return clean(e)


def size_words(n):
    n = float(n or 0)
    for unit in ("bytes", "KB", "MB", "GB", "TB", "PB"):
        if n < 1000 or unit == "PB":
            return f"{n:.0f} {unit}" if unit in ("bytes", "KB") else f"{n:.1f} {unit}"
        n /= 1000


def count(n):
    return f"{int(n or 0):,}"


def _base():
    b = str(setting("address", "") or "").rstrip("/")
    if b.endswith("/api"):
        b = b[:-4]
    if not b:
        raise ValueError("Enter Immich's address first")
    return b


def _get(path):
    key = str(setting("api_key", "") or "")
    if not key:
        raise ValueError("Enter an API key first")
    return sb.fetch(_base() + "/api" + path, {"x-api-key": key}, timeout=10, limit=512 * 1024)


def cached(name, read, now=None):
    now = now if now is not None else time.monotonic()
    got = CACHE.get(name)
    if got and now - got[0] < KEEP_SECONDS:
        return got[1]
    value = read()
    CACHE[name] = (now, value)
    return value


def queues_of(answer):
    """[(name, active, waiting, failed, paused)] from /api/queues (a list) or the older /api/jobs (an object)."""
    out = []
    if isinstance(answer, list):
        for q in answer:
            st = (q or {}).get("statistics") or {}
            out.append((str(q.get("name")), int(st.get("active") or 0), int(st.get("waiting") or 0), int(st.get("failed") or 0), bool(q.get("isPaused"))))
    elif isinstance(answer, dict):
        for name, q in answer.items():
            jc, qs = (q or {}).get("jobCounts") or {}, (q or {}).get("queueStatus") or {}
            out.append((str(name), int(jc.get("active") or 0), int(jc.get("waiting") or 0), int(jc.get("failed") or 0), bool(qs.get("isPaused"))))
    return out


def read_queues():
    try:
        return queues_of(_get("/queues"))
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
        return queues_of(_get("/jobs"))  # an Immich from before /api/queues


def stats():
    return cached("stats", lambda: _get("/server/statistics"))


def storage():
    return cached("storage", lambda: _get("/server/storage"))


def queues():
    return cached("queues", read_queues)


def failed(e):
    """A card that could not ask says why, in the band."""
    return band({"state": "problem", "text": f"Immich: {_why(e)}"[:160]}, "problem", label="Cannot read it")


def _setup():
    if not setting("address") or not setting("api_key"):
        return band({"state": "warning", "text": "Enter Immich's address and an API key in Settings, Plug-ins, Immich."}, "needs_setup", label="Needs setting up")
    return None


def library():
    n = _setup()
    if n:  # a stat card must hold a number (Starboard checks): 0, with the words that say why
        return band({"value": 0, "label": "photos and videos", "note": "Needs setting up"}, n["status"], label=n.get("status_label"))
    try:
        s = stats()
    except Exception as e:  # noqa: BLE001 - said on the card
        return band({"value": 0, "label": "photos and videos", "note": _why(e)[:80]}, "problem", label="Cannot read it")
    photos, videos = int(s.get("photos") or 0), int(s.get("videos") or 0)
    return band({"value": photos + videos, "label": "photos and videos",
                 "note": f"{count(photos)} photos, {count(videos)} videos, {size_words(s.get('usage'))}"}, "ok")


def disk():
    n = _setup()
    if n:
        return band({"items": []}, n["status"], label=n.get("status_label"))
    try:
        s, d = stats(), storage()
    except Exception as e:  # noqa: BLE001
        return band({"items": []}, "problem", label="Cannot read it") | {"items": [{"title": "Immich", "detail": _why(e)[:180]}]}
    pct = float(d.get("diskUsagePercentage") or 0)
    items = [{"title": "Photos", "detail": f"{count(s.get('photos'))}, {size_words(s.get('usagePhotos'))}"},
             {"title": "Videos", "detail": f"{count(s.get('videos'))}, {size_words(s.get('usageVideos'))}"},
             {"title": "The disk Immich is on", "detail": f"{size_words(d.get('diskUseRaw'))} used of {size_words(d.get('diskSizeRaw'))} ({pct:.0f}%), {size_words(d.get('diskAvailableRaw'))} free"}]
    users = sorted((s.get("usageByUser") or []), key=lambda u: -int(u.get("usage") or 0))[:5]
    items += [{"title": str(u.get("userName") or "A person")[:40], "detail": f"{count(u.get('photos'))} photos, {count(u.get('videos'))} videos, {size_words(u.get('usage'))}"} for u in users]
    # The same limits as Starboard's own disk card: nearly full at 90%, full at 98%.
    if pct >= 98:
        return band({"items": items}, "problem", label="Full")
    if pct >= 90:
        return band({"items": items}, "warning", label="Nearly full")
    return band({"items": items}, "ok")


def jobs():
    n = _setup()
    if n:
        return n
    try:
        q = queues()
    except Exception as e:  # noqa: BLE001
        return failed(e)
    active = [x for x in q if x[1]]
    waiting = sum(x[2] for x in q)
    bad = sum(x[3] for x in q)
    paused = [x for x in q if x[4] and x[2]]
    if active or waiting:
        names = ", ".join(NAMES.get(x[0], x[0]) for x in (active or [x for x in q if x[2]])[:3])
        text = f"Working: {names}. {count(waiting)} waiting." + (f" {count(bad)} failed." if bad else "")
        return band({"state": "warning" if bad else "ok", "text": text[:160]}, "working", label="Working")
    if bad:
        return band({"state": "warning", "text": f"Idle, but {count(bad)} jobs have failed. Open Immich, Administration, Jobs to retry them."}, "warning", label="Needs attention")
    if paused:
        return band({"state": "warning", "text": "A queue with work waiting is paused."}, "paused", label="Paused")
    return band({"state": "ok", "text": "Nothing is waiting. Every queue is idle."}, "idle")


# The job queues page (DASH-578) -------------------------------------------------------------------------------------

def _send(method, path, body):
    key = str(setting("api_key", "") or "")
    return sb.fetch(_base() + "/api" + path, {"x-api-key": key}, data=body, method=method, timeout=10, limit=64 * 1024)


def _change(name, command):
    """pause, resume or clear-failed for one queue, through /api/queues, or /api/jobs on an Immich from before it."""
    q = urllib.parse.quote(name, safe="")
    try:
        if command == "clear-failed":
            return _send("DELETE", f"/queues/{q}/jobs", {"failed": True})
        return _send("PUT", f"/queues/{q}", {"isPaused": command == "pause"})
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
    return _send("PUT", f"/jobs/{q}", {"command": command, "force": False})


def _screen_item(name, active, waiting, failed, paused):
    bits = [f"{count(active)} working", f"{count(waiting)} waiting"] + ([f"{count(failed)} failed"] if failed else [])
    label = "Paused" if paused else "Failed jobs" if failed else "Working" if active else "Idle"
    item = {"id": name, "title": NAMES.get(name, name)[:120], "detail": ", ".join(bits), "on": not paused, "actions": ["toggle"],
            "state": "warning" if paused or failed else "ok", "state_label": label}
    if failed:
        item["choice"] = {"label": "Failed jobs", "value": "", "options": [["", "Leave them"], ["clear", "Clear failed jobs"]]}
    return item


def screen(said=None):
    """The queues as a list Starboard draws: a switch to pause or resume each, and a choice to clear its failed jobs."""
    n = _setup()
    if n:
        return {"type": "list", "title": "Job queues", "items": [], "intro": n["text"]}
    try:
        q = read_queues()
    except Exception as e:  # noqa: BLE001 - said on the page
        return {"type": "list", "title": "Job queues", "items": [], "intro": f"Immich did not answer: {_why(e)}"[:400]}
    out = {"type": "list", "title": "Job queues",
           "intro": "Each switch pauses or resumes one queue. Starboard asks Immich only when this page is open. "
                    "Your API key needs the permission queue.update (job.create on an older Immich) to change a queue.",
           "items": [_screen_item(*x) for x in q]}
    if said:
        out["said"] = said[:200]
    return out


def act(body):
    n = _setup()
    if n:
        raise ValueError(n["text"])
    action, name, value = str(body.get("action", "")), str(body.get("id", "")), str(body.get("value", ""))
    queues_now = {x[0]: x for x in read_queues()}
    if name not in queues_now:
        raise ValueError("Immich has no such queue")
    if action == "toggle":
        pause = not queues_now[name][4]
        command, said = ("pause", "Paused") if pause else ("resume", "Resumed")
    elif action == "choose" and value == "clear":
        command, said = "clear-failed", "Cleared the failed jobs of"
    elif action == "choose" and value == "":
        return screen()
    else:
        raise ValueError("Choose pause, resume or clear failed jobs")
    try:
        _change(name, command)
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise ValueError("Immich refused. Give the API key the permission queue.update (job.create on an older Immich)") from None
        raise ValueError(_why(e)) from None
    CACHE.clear()
    return screen(f"{said} {NAMES.get(name, name)}")


ROUTES = {"/library": library, "/storage": disk, "/jobs": jobs, "/screen/queues": screen, ("POST", "/screen/queues"): act}

if __name__ == "__main__":
    serve(ROUTES, port=int(os.environ.get("PORT", 8080)))
