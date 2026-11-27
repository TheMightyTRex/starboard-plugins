"""Notifications: Sends Starboard's events to email, Telegram, Discord, Signal, Pushover, ntfy or a webhook, in plain words.

Starboard drives it: each event is a POST to /events and the weekly message is a job on the day and hour you choose, so the container rests
between them (start: when_needed). Secrets come from settings.json each time and are never written to the log, the
card or /data: every error is cleaned of them first (DASH-401)."""
import hashlib
import json
import os
import smtplib
import ssl
import threading
import time
import urllib.parse
from email.message import EmailMessage

from sbplugin import band, fetch, keep, remember, serve, setting, settings, starboard

SECRETS = ("smtp_password", "telegram_token", "discord_webhook", "pushover_user", "pushover_token", "ntfy_token", "webhooks")
CHANNELS = {"email": "Email", "telegram": "Telegram", "discord": "Discord", "signal": "Signal", "pushover": "Pushover",
            "ntfy": "ntfy", "webhook": "Webhooks"}
KINDS = {"request.available": "send_requests", "download.failed": "send_failed", "app.down": "send_apps", "app.up": "send_apps",
         "disk.nearly_full": "send_disk", "disk.changed": "send_disk_changes", "update.available": "send_updates", "weekly": "send_weekly"}
TIMEOUT = 8  # a Test button has 10 seconds
URGENT = {"app.down", "disk.nearly_full", "disk.changed"}  # sent at once in quiet hours unless "Still send urgent ones" is off
HELD_MAX = 200  # the most held in one night; the summary lists 40 and says how many more
HELD_LISTED = 40


# Words ---------------------------------------------------------------------------------------------------------

def _size(n):
    n = float(n or 0)
    for unit in ("bytes", "KB", "MB", "GB", "TB"):
        if n < 1000 or unit == "TB":
            return f"{n:.0f} {unit}" if unit in ("bytes", "KB") else f"{n:.1f} {unit}"
        n /= 1000


def _named(title, year=""):
    return f"{title} ({year})" if year else str(title or "Something")


def words(event, data):
    """(title, body, tone) in plain sentences. Meaning is always in the words, never in a symbol or colour."""
    d = data or {}
    if event == "request.available":
        who = f", which {d['by']} asked for," if d.get("by") else ""
        return (f"Ready to watch: {_named(d.get('title'), d.get('year'))}",
                f"{_named(d.get('title'), d.get('year'))}{who} is ready to watch in Jellyfin.", "success")
    if event == "download.failed":
        why = f" {str(d['reason']).rstrip('.')}." if d.get("reason") else ""
        return (f"A download failed: {d.get('title') or 'one download'}",
                f"{d.get('title') or 'A download'} stopped in {d.get('app') or 'the download app'}.{why} "
                "Check it on Starboard's Downloads page.", "failure")
    if event == "app.down":
        return (f"{d.get('app') or 'An app'} is not answering",
                f"Starboard has had no answer from {d.get('app') or 'one of your apps'} twice in a row.", "failure")
    if event == "app.up":
        return f"{d.get('app') or 'An app'} is answering again", f"{d.get('app') or 'The app'} is back.", "success"
    if event == "disk.nearly_full":
        return (f"{d.get('disk') or 'A disk'} is {d.get('percent', '')}% full",
                f"{d.get('disk') or 'The disk'} has {_size(d.get('free'))} free. Starboard's Clean up page shows what can go.", "warning")
    if event == "disk.changed":
        disk = d.get("disk") or "A disk"
        did = {"add": "was added to the pool", "remove": "was taken out of the pool", "balance": "pool was balanced"}.get(d.get("action"), "changed")
        if d.get("action") == "balance":
            did, disk = "was balanced", "The pool"
        erased = [x for x in d.get("erased") or [] if x]
        failed = d.get("state") == "failed"
        title = f"{disk} {did}" + (" (it stopped with a problem)" if failed else "")
        text = (f"Erased: {', '.join(erased)}. " if erased else "") + (f"{d['result']} " if d.get("result") else "")
        text += "If you did not start this, check Starboard's System, Disks and its log now."
        return title, text.strip(), "warning" if erased or failed else "info"
    if event == "update.available":
        have = f" You have {d['current']}." if d.get("current") else ""
        return (f"An update for {d.get('app') or 'an app'}: {d.get('latest')}",
                f"{d.get('app') or 'An app'} {d.get('latest')} is ready.{have} Update it in Starboard's Settings, Updates.", "info")
    if event == "test":
        return "A test from Starboard", "This is a test message from Starboard's Notifications plug-in. If you can read it, it works.", "info"
    return f"Starboard: {event}", "Starboard has an alert. Open Starboard for the details.", "info"


def link():
    """Starboard's address, if given, for 'Open Starboard: <address>' (a link with words before it)."""
    return str(setting("starboard_address", "") or "").strip()


def with_link(body):
    return f"{body}\n\nOpen Starboard: {link()}" if link() else body


# Channels ------------------------------------------------------------------------------------------------------

def _missing(*keys):
    gone = [k for k in keys if not str(setting(k, "") or "").strip()]
    if gone:
        raise ValueError("Enter " + ", ".join(k.replace("_", " ") for k in gone) + " first")


def _list(key):
    v = setting(key, []) or []
    return [x.strip() for x in (v if isinstance(v, list) else str(v).replace(",", "\n").splitlines()) if x.strip()]


def send_email(title, body, tone, to=None):
    _missing("smtp_host", "email_from")
    rcpt = to or _list("email_to")
    if not rcpt:
        raise ValueError("Add at least one address under Send email to")
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = title, setting("email_from"), ", ".join(rcpt)
    msg.set_content(with_link(body))
    host, port, mode = setting("smtp_host"), int(setting("smtp_port", 587)), setting("smtp_security", "starttls")
    context = ssl.create_default_context()
    if mode == "ssl":
        server = smtplib.SMTP_SSL(host, port, timeout=TIMEOUT, context=context)
    else:
        server = smtplib.SMTP(host, port, timeout=TIMEOUT)
    with server:
        if mode == "starttls":
            server.starttls(context=context)
        if setting("smtp_user"):
            server.login(setting("smtp_user"), setting("smtp_password", ""))
        server.send_message(msg)


def send_telegram(title, body, tone, to=None):
    _missing("telegram_token")
    chats = to or _list("telegram_chat")
    if not chats:
        raise ValueError("Add a chat id under Telegram chat")
    for chat in chats:
        fetch(f"https://api.telegram.org/bot{setting('telegram_token')}/sendMessage", timeout=TIMEOUT,
              data={"chat_id": chat, "text": f"{title}\n\n{with_link(body)}", "disable_web_page_preview": True})


def send_discord(title, body, tone, to=None):
    _missing("discord_webhook")
    fetch(str(setting("discord_webhook")).strip(), timeout=TIMEOUT, raw=True,
          data={"content": f"{title}\n{with_link(body)}"[:2000], "allowed_mentions": {"parse": []}})


def send_signal(title, body, tone, to=None):
    _missing("signal_api", "signal_number")
    rcpt = to or _list("signal_to")
    if not rcpt:
        raise ValueError("Add at least one number under Send Signal messages to")
    fetch(str(setting("signal_api")).rstrip("/") + "/v2/send", timeout=TIMEOUT, raw=True,
          data={"message": f"{title}\n\n{with_link(body)}", "number": setting("signal_number"), "recipients": rcpt})


def send_pushover(title, body, tone, to=None):
    _missing("pushover_user", "pushover_token")
    msg = {"token": setting("pushover_token"), "user": setting("pushover_user"), "title": title[:250], "message": body[:1024],
           "priority": 1 if tone == "failure" else 0}
    if link():
        msg.update(url=link(), url_title="Open Starboard")
    fetch("https://api.pushover.net/1/messages.json", timeout=TIMEOUT, data=msg)


def send_ntfy(title, body, tone, to=None):
    _missing("ntfy_topic")
    base = str(setting("ntfy_url", "") or "https://ntfy.sh").rstrip("/")
    msg = {"topic": setting("ntfy_topic"), "title": title, "message": body, "priority": 4 if tone == "failure" else 3}
    if link():
        msg["actions"] = [{"action": "view", "label": "Open Starboard", "url": link()}]
    token = setting("ntfy_token", "")
    fetch(base + "/", timeout=TIMEOUT, data=msg, headers={"Authorization": f"Bearer {token}"} if token else None)


def send_webhook(title, body, tone, to=None):
    """Apprise-style: {title, body, type} as JSON, which the Apprise API's /notify takes as it is, and any address that
    reads JSON. One or more addresses, separated by spaces."""
    urls = str(setting("webhooks", "") or "").split()
    if not urls:
        raise ValueError("Add a webhook address first")
    for url in urls:
        fetch(url, timeout=TIMEOUT, raw=True, data={"title": title, "body": with_link(body), "type": tone, "link": link()})


SENDERS = {"email": send_email, "telegram": send_telegram, "discord": send_discord, "signal": send_signal,
           "pushover": send_pushover, "ntfy": send_ntfy, "webhook": send_webhook}


def clean(text):
    """An error's words with every secret, and any address that can hold one, taken out, for the card and /data."""
    text = str(text or "")
    values = settings()
    for k in SECRETS:
        for part in str(values.get(k) or "").split():
            if len(part) >= 4:
                text = text.replace(part, "[hidden]")
                text = text.replace(urllib.parse.quote(part, safe=""), "[hidden]")
    if values.get("telegram_token"):
        text = text.replace("bot" + str(values["telegram_token"]), "bot[hidden]")
    return text[:200]


def _why(e):
    code = getattr(e, "code", None)
    if code in (401, 403):
        return "it refused the sign-in or token"
    if code == 404:
        return "the address or chat was not found"
    if code:
        return f"it answered with error {code}"
    if isinstance(e, smtplib.SMTPAuthenticationError):
        return "the email server refused the user name or password"
    if isinstance(e, (smtplib.SMTPException, OSError)) and not isinstance(e, ValueError):
        return f"it could not be reached ({type(e).__name__})"
    return str(e)


def active():
    return [c for c in CHANNELS if setting(f"{c}_active", False) is True]


def deliver(title, body, tone, channels=None, kind="event"):
    """Sends to each channel; returns (sent, failed) channel names. Keeps the last result for the card, without secrets."""
    sent, failed = [], []
    for c in channels if channels is not None else active():
        try:
            SENDERS[c](title, body, tone)
            sent.append(CHANNELS[c])
        except Exception as e:  # noqa: BLE001 - one channel failing never stops the others
            failed.append(f"{CHANNELS[c]}: {clean(_why(e))}")
    log = (remember("log", []) or [])[-19:]
    log.append({"at": time.time(), "kind": kind, "title": clean(title)[:120], "sent": sent, "failed": failed})
    keep("log", log)
    return sent, failed


# Per person: "your request is ready" ---------------------------------------------------------------------------

def people():
    """'Sam, sam@example.com' or 'Sam, telegram 123456' lines: {name lower: (channel, address)}."""
    out = {}
    for line in _list("people"):
        name, _, where = line.partition(",")
        where = where.strip()
        if not name.strip() or not where:
            continue
        if where.lower().startswith("telegram "):
            out[name.strip().lower()] = ("telegram", where.split(None, 1)[1].strip())
        elif "@" in where:
            out[name.strip().lower()] = ("email", where)
    return out


def tell_person(data, title, body, tone):
    who = people().get(str((data or {}).get("by") or "").strip().lower())
    if not who:
        return []
    channel, address = who
    try:
        SENDERS[channel](title, body, tone, to=[address])
        return [f"{CHANNELS[channel]} to {data['by']}"]
    except Exception as e:  # noqa: BLE001
        log = (remember("log", []) or [])[-19:]
        log.append({"at": time.time(), "kind": "person", "title": clean(title)[:120], "sent": [], "failed": [f"{CHANNELS[channel]} to {data['by']}: {clean(_why(e))}"]})
        keep("log", log)
        return []


# What Starboard calls ------------------------------------------------------------------------------------------

_seen = {}
_lock = threading.Lock()


def on_event(body, wait=False):
    """Answers at once and sends in the background: Starboard waits 3 seconds and tries again once, so a slow email
    server must never make it send twice. The same event sent twice (Starboard's retry) is sent once."""
    key = hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()
    with _lock:
        now = time.time()
        for k in [k for k, t in _seen.items() if t < now - 600]:
            del _seen[k]
        if key in _seen:
            return {"ok": True, "said": "Already had this one"}
        _seen[key] = now
    if wait:
        return handle(body)
    threading.Thread(target=handle, args=(body,), daemon=True).start()
    return {"ok": True, "said": "Sending"}


_work = threading.RLock()  # one message at a time, so the files in /data are never written by two at once


def handle(body):
    with _work:
        return _handle(body)


def _minutes(key, default):
    when = setting(key, None)
    t = str(when.get("time") if isinstance(when, dict) else "") or default
    try:
        h, m = t.split(":")
        return max(0, min(int(h), 23)) * 60 + max(0, min(int(m), 59))
    except ValueError:
        h, m = default.split(":")
        return int(h) * 60 + int(m)


def in_quiet(now=None):
    """True inside the quiet hours (only the hour of each schedule counts; the day is ignored), in Starboard's time zone."""
    if setting("quiet_on", False) is not True:
        return False
    start, end = _minutes("quiet_from", "22:00"), _minutes("quiet_until", "07:00")
    if start == end:
        return False
    t = time.localtime(now if now is not None else time.time())
    m = t.tm_hour * 60 + t.tm_min
    return start <= m < end if start < end else (m >= start or m < end)


def hold(event, data, title, body, tone):
    """Keeps a message that is not urgent until the quiet hours end. Nothing is sent now."""
    held = (remember("held", []) or [])[-(HELD_MAX - 1):]
    held.append({"at": time.time(), "event": event, "title": clean(title)[:120], "body": body, "tone": tone,
                 "by": str((data or {}).get("by") or "")[:60]})
    keep("held", held)
    return {"ok": True, "said": "Held until the quiet hours end"}


def summary_words(held):
    lines = [f"- {time.strftime('%H:%M', time.localtime(x['at']))} {x['title']}" for x in held[:HELD_LISTED]]
    if len(held) > HELD_LISTED:
        lines.append(f"- and {len(held) - HELD_LISTED} more")
    return "\n".join(lines)


def release(force=False):
    """Sends what quiet hours held as one summary, then tells each person whose request is ready. Does nothing while the
    quiet hours last, unless forced, and keeps what it could not send for the next time."""
    with _work:
        held = remember("held", []) or []
        if not held:
            return {"said": "Nothing was held"}
        if not force and in_quiet():
            return {"said": "Still in the quiet hours"}
        n = len(held)
        sent, failed = deliver(f"{n} thing{'s' if n != 1 else ''} while you were away", "Held in the quiet hours:\n\n" + summary_words(held),
                               "info", kind="summary")
        if sent or not active():  # with no channel active there is nothing to wait for either
            if setting("tell_requester", True) is True:
                for x in [x for x in held if x["event"] == "request.available" and x.get("by")][:20]:
                    tell_person({"by": x["by"]}, x["title"], x["body"], x["tone"])
            keep("held", [])
        return {"said": _said(sent, failed, "The quiet hours summary")}


def held_now():
    """The button: held messages go in the background, as New this week does."""
    threading.Thread(target=release, kwargs={"force": True}, daemon=True).start()
    return {"said": "Sending what quiet hours held now. The Notifications card says when it has gone"}


def _handle(body):
    event, data = str(body.get("event") or ""), body.get("data") or {}
    if event == "item.added":  # kept for the weekly message only, 8 days at most
        week = [x for x in remember("week", []) or [] if x.get("at", 0) > time.time() - 8 * 86400][-500:]
        week.append({"at": time.time(), "title": str(data.get("title") or "")[:120], "series": str(data.get("series") or "")[:120],
                     "type": str(data.get("type") or "")[:20], "year": data.get("year") or ""})
        keep("week", week)
        return {"ok": True}
    if KINDS.get(event) and setting(KINDS[event], True) is not True:
        return {"ok": True, "said": "Not sent: this kind is deactivated"}
    title, body_text, tone = words(event, data)
    if in_quiet() and not (event in URGENT and setting("quiet_urgent", True) is True):
        return hold(event, data, title, body_text, tone)
    if remember("held", []):  # the quiet hours ended: the summary goes before the new message
        release()
    sent, failed = deliver(title, body_text, tone, kind=event)
    if event == "request.available" and setting("tell_requester", True) is True:
        sent += tell_person(data, title, body_text, tone)
    return {"ok": True, "sent": sent, "failed": failed}


LISTED = 40  # the most titles under one heading, so the email stays short
EPISODES = 6  # the most episode titles after one series


def _more(lines, rest):
    return lines + ([f"- and {rest} more"] if rest > 0 else [])


def weekly_words(items):
    """The plain-text list for New this week: titles and years only, no pictures. Films, episodes (by series), albums
    and books, each once however many times Jellyfin reported it."""
    films, albums, books, series = {}, {}, {}, {}
    for x in items:
        kind, title = x.get("type"), str(x.get("title") or "").strip()
        if not title:
            continue
        if kind == "Movie":
            films[_named(title, x.get("year"))] = 1
        elif kind == "Episode" and x.get("series"):
            series.setdefault(x["series"], {})[title] = 1
        elif kind == "MusicAlbum":
            albums[_named(title, x.get("year"))] = 1
        elif kind in ("Book", "AudioBook"):
            books[_named(title, x.get("year"))] = 1
    lines = []
    for heading, found in (("Films", films), ("Albums", albums), ("Books", books)):
        if found:
            names = sorted(found)
            lines += [f"{heading} ({len(names)}):"] + _more([f"- {n}" for n in names[:LISTED]], len(names) - LISTED) + [""]
    if series:
        count = sum(len(v) for v in series.values())
        lines += [f"Episodes ({count}):"]
        shown = sorted(series.items())
        for name, eps in shown[:LISTED]:
            titles = sorted(eps)
            lines.append(f"- {name}: " + ", ".join(titles[:EPISODES]) + (f" and {len(titles) - EPISODES} more" if len(titles) > EPISODES else ""))
        lines += _more([], len(shown) - LISTED) + [""]
    return "\n".join(lines).strip()


def weekly(force=False):
    """The job Starboard runs at the day and hour chosen under When to send New this week."""
    with _work:
        return _weekly(force)


def _weekly(force):
    if not force:
        if setting("send_weekly", False) is not True:
            return {"said": "The weekly message is deactivated"}
        if time.time() - float(remember("weekly_sent", 0) or 0) < 20 * 3600:  # Starboard's retry or a double start
            return {"said": "Already sent today"}
    since = time.time() - 7 * 86400
    items = [x for x in remember("week", []) or [] if x.get("at", 0) >= since]
    try:  # what the download apps imported, as a second source; nothing is lost if it does not answer
        for r in (starboard("recent") or {}).get("items") or []:
            if r.get("detail") == "Film":
                items.append({"title": r.get("title"), "type": "Movie", "year": ""})
    except Exception:  # noqa: BLE001
        pass
    text = weekly_words(items)
    if not text:
        if not force:
            keep("weekly_sent", time.time())
        return {"said": "Nothing new this week, so nothing was sent"}
    by = ["email"] if setting("weekly_by", "email") != "all" else None
    if by and "email" not in active():
        return {"said": "New this week: email is not activated. Activate it under Email, or send by every way you activated"}
    sent, failed = deliver("New on your server this week", f"Added to Jellyfin in the last 7 days:\n\n{text}", "info", channels=by, kind="weekly")
    if not force and sent:
        keep("weekly_sent", time.time())
    return {"said": _said(sent, failed, "New this week")}


def weekly_now():
    """The button: a button has 10 seconds, so the message goes in the background and the card says how it went."""
    threading.Thread(target=weekly, kwargs={"force": True}, daemon=True).start()
    return {"said": "Sending New this week now. The Notifications card says when it has gone"}


def _said(sent, failed, what):
    if not sent and not failed:
        return f"{what}: no channel is active. Activate one in Settings first"
    bits = ([f"sent by {', '.join(sent)}"] if sent else []) + ([f"not sent by {'; '.join(failed)}"] if failed else [])
    return f"{what}: " + "; ".join(bits)


def test(channel):
    def run():
        title, body, tone = words("test", {})
        with _work:
            sent, failed = deliver(title, body, tone, channels=[channel], kind="test")
        return {"said": f"Test sent by {CHANNELS[channel]}. Check it arrived" if sent else f"Test not sent. {failed[0]}"}
    return run


def card():
    log = remember("log", []) or []
    real = [x for x in log if x.get("kind") != "test"]
    if not active():
        return band({"state": "warning", "text": "No channel is active. Activate one in Settings, Plug-ins, Notifications."},
                    "needs_setup", label="No channel active")
    held = len(remember("held", []) or [])
    if held and in_quiet():
        return band({"state": "ok", "text": f"Quiet hours. {held} held until they end."}, "ok", label="Quiet hours")
    if not real:
        return band({"state": "ok", "text": f"Ready to send by {', '.join(CHANNELS[c] for c in active())}. Nothing sent yet."}, "ready")
    last = real[-1]
    when = time.strftime("%a %H:%M", time.localtime(last["at"]))
    if last["failed"]:
        return band({"state": "problem", "text": f"{when}, {last['title']}: not sent by {'; '.join(last['failed'])}"[:160]},
                    "problem", last["at"], "Last one not sent")
    return band({"state": "ok", "text": f"{when}, {last['title']}: sent by {', '.join(last['sent'])}"[:160]}, "ok", last["at"])


def recent():
    rows, log = [], (remember("log", []) or [])[-10:]
    for x in reversed(log):
        state = "not sent by " + "; ".join(x["failed"]) if x["failed"] else "sent by " + ", ".join(x["sent"]) if x["sent"] else "no channel active"
        rows.append({"title": x["title"], "detail": f"{time.strftime('%a %d %b %H:%M', time.localtime(x['at']))}, {state}"})
    if not rows:
        return band({"items": [{"title": "Nothing sent yet", "detail": "Messages appear here as Starboard sends them"}]},
                    "ready" if active() else "needs_setup")
    failed = sum(1 for x in log if x["failed"])
    return band({"items": rows}, "warning" if failed else "ok", log[-1]["at"], "Not sent" if failed else None)


ROUTES = {"/card": card, "/recent": recent, ("POST", "/events"): on_event, ("POST", "/jobs/weekly"): lambda: weekly(),
          ("POST", "/weekly-now"): weekly_now, ("POST", "/jobs/quiet-end"): lambda: release(), ("POST", "/held-now"): held_now, **{("POST", f"/test/{c}"): test(c) for c in CHANNELS}}

if __name__ == "__main__":
    serve(ROUTES, port=int(os.environ.get("PORT", 8080)))
