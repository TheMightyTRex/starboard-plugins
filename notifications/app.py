"""Notifications: Sends Starboard's events to email, Telegram, Discord, Signal, Pushover, ntfy or a webhook, in plain words.

Starboard drives it: each event is a POST to /events and the weekly message is a daily job, so the container rests
between them (start: when_needed). Secrets come from settings.json each time and are never written to the log, the
card or /data: every error is cleaned of them first (DASH-401)."""
import datetime as dt
import hashlib
import json
import os
import smtplib
import ssl
import threading
import time
import urllib.parse
from email.message import EmailMessage

from sbplugin import fetch, keep, remember, serve, setting, settings, starboard

SECRETS = ("smtp_password", "telegram_token", "discord_webhook", "pushover_user", "pushover_token", "ntfy_token", "webhooks")
CHANNELS = {"email": "Email", "telegram": "Telegram", "discord": "Discord", "signal": "Signal", "pushover": "Pushover",
            "ntfy": "ntfy", "webhook": "Webhooks"}
KINDS = {"request.available": "send_requests", "download.failed": "send_failed", "app.down": "send_apps", "app.up": "send_apps",
         "disk.nearly_full": "send_disk", "update.available": "send_updates", "weekly": "send_weekly"}
DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
TIMEOUT = 8  # a Test button has 10 seconds


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
    if event == "update.available":
        have = f" You have {d['current']}." if d.get("current") else ""
        return (f"An update for {d.get('app') or 'an app'}: {d.get('latest')}",
                f"{d.get('app') or 'An app'} {d.get('latest')} is ready.{have} Update it in Starboard's Settings, Updates.", "info")
    if event == "test":
        return "A test from Starboard", "This is a test message from Starboard's Notifications plug-in. If you can read it, it works.", "info"
    return f"Starboard: {event}", "Something happened in Starboard.", "info"


def link():
    """Starboard's address, if given, for 'Open Starboard: <address>' (a link with words before it)."""
    return str(setting("starboard_address", "") or "").strip()


def with_link(body):
    return f"{body}\n\nOpen Starboard: {link()}" if link() else body


# Channels ------------------------------------------------------------------------------------------------------

def _missing(*keys):
    gone = [k for k in keys if not str(setting(k, "") or "").strip()]
    if gone:
        raise ValueError("Fill in " + ", ".join(k.replace("_", " ") for k in gone) + " first")


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
    sent, failed = deliver(title, body_text, tone, kind=event)
    if event == "request.available" and setting("tell_requester", True) is True:
        sent += tell_person(data, title, body_text, tone)
    return {"ok": True, "sent": sent, "failed": failed}


def weekly_words(items):
    films = sorted({_named(x["title"], x.get("year")) for x in items if x.get("type") == "Movie" and x.get("title")})
    series = {}
    for x in items:
        if x.get("type") == "Episode" and x.get("series"):
            series[x["series"]] = series.get(x["series"], 0) + 1
        elif x.get("type") == "Series" and x.get("title"):
            series.setdefault(x["title"], 0)
    other = sorted({x["title"] for x in items if x.get("type") not in ("Movie", "Episode", "Series") and x.get("title")})
    lines = []
    if films:
        lines += [f"Films ({len(films)}):"] + [f"- {f}" for f in films[:30]]
    if series:
        lines += [f"Series ({len(series)}):"] + [f"- {s}" + (f", {n} new episode{'s' if n != 1 else ''}" if n else "")
                                                  for s, n in sorted(series.items())[:30]]
    if other:
        lines += [f"Music, books and more ({len(other)}):"] + [f"- {o}" for o in other[:30]]
    return "\n".join(lines)


def weekly(force=False):
    """The daily job: on the chosen day, once a week, 'New this week' from what arrived in the last 7 days."""
    with _work:
        return _weekly(force)


def _weekly(force):
    today = dt.date.today()
    week_id = today.strftime("%G-%V")
    if not force:
        if setting("send_weekly", True) is not True:
            return {"said": "The weekly message is deactivated"}
        if DAYS[today.weekday()] != setting("weekly_day", "monday") or remember("weekly_sent") == week_id:
            return {"said": "Not the day for the weekly message"}
    since = time.time() - 7 * 86400
    items = [x for x in remember("week", []) or [] if x.get("at", 0) >= since]
    try:  # what the download apps imported, as a second source; nothing is lost if it does not answer
        for r in (starboard("recent") or {}).get("items") or []:
            items.append({"title": r.get("title"), "type": "Movie" if r.get("detail") == "Film" else "Other", "year": ""})
    except Exception:  # noqa: BLE001
        pass
    text = weekly_words(items)
    if not text:
        if not force:
            keep("weekly_sent", week_id)
        return {"said": "Nothing new this week, so nothing was sent"}
    sent, failed = deliver("New this week", f"New in your library in the last 7 days:\n{text}", "info", kind="weekly")
    if not force:
        keep("weekly_sent", week_id)
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
        return {"state": "warning", "text": "No channel is active. Activate one in Settings, Plug-ins, Notifications."}
    if not real:
        return {"state": "ok", "text": f"Ready to send by {', '.join(CHANNELS[c] for c in active())}. Nothing sent yet."}
    last = real[-1]
    when = time.strftime("%a %H:%M", time.localtime(last["at"]))
    if last["failed"]:
        return {"state": "problem", "text": f"{when}, {last['title']}: not sent by {'; '.join(last['failed'])}"[:160]}
    return {"state": "ok", "text": f"{when}, {last['title']}: sent by {', '.join(last['sent'])}"[:160]}


def recent():
    rows = []
    for x in reversed((remember("log", []) or [])[-10:]):
        state = "not sent by " + "; ".join(x["failed"]) if x["failed"] else "sent by " + ", ".join(x["sent"]) if x["sent"] else "no channel active"
        rows.append({"title": x["title"], "detail": f"{time.strftime('%a %d %b %H:%M', time.localtime(x['at']))}, {state}"})
    return {"items": rows or [{"title": "Nothing sent yet", "detail": "Messages appear here as Starboard sends them"}]}


ROUTES = {"/card": card, "/recent": recent, ("POST", "/events"): on_event, ("POST", "/jobs/weekly"): lambda: weekly(),
          ("POST", "/weekly-now"): weekly_now, **{("POST", f"/test/{c}"): test(c) for c in CHANNELS}}

if __name__ == "__main__":
    serve(ROUTES, port=int(os.environ.get("PORT", 8080)))
