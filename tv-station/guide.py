"""The channel list (M3U) and the guide (XMLTV) Jellyfin reads, worked out from the schedule each time they are asked
for. Nothing is kept: Jellyfin asks for the guide when it refreshes its guide, about once a day."""
import datetime as dt
import time
from xml.sax.saxutils import escape, quoteattr

from schedule import Channel

NEW_DAYS = 30  # an episode or film first shown in the last 30 days is New in the guide; anything older is a repeat


def channel_key(ch):
    return f"tv-station-{ch['id']}"


def m3u(channels, base, station):
    """One line for each channel on air, in the owner's order. `base` is the address Jellyfin used to reach this
    plug-in, with its token, so each stream address works from where Jellyfin is."""
    lines = ["#EXTM3U"]
    for ch in channels:
        if not ch.get("on", True):
            continue
        name = ch.get("name") or "Channel"
        logo = f' tvg-logo="{base}/logo/{ch["id"]}.png"'
        lines.append(f'#EXTINF:-1 tvg-id="{channel_key(ch)}" tvg-chno="{ch["number"]}" tvg-name={quoteattr(name)}{logo} '
                     f'group-title={quoteattr(station)},{name}')
        lines.append(f"{base}/stream/{ch['id']}.ts")
    return "\n".join(lines) + "\n"


def is_new(entry, at):
    p = entry.get("premiere")
    if not p:
        return False
    try:
        first = dt.datetime.fromisoformat(str(p)[:10]).replace(tzinfo=dt.timezone.utc).timestamp()
    except ValueError:
        return False
    return 0 <= at - first <= NEW_DAYS * 86400


def _xmltime(t):
    return time.strftime("%Y%m%d%H%M%S +0000", time.gmtime(t))


def programme_title(entry):
    return entry.get("title") or "Programme"


def episode_words(entry):
    """The episode's name, with its series and episode numbers, such as "Series 2, episode 4: The Lift"."""
    bits = []
    if entry.get("s") is not None and entry.get("e") is not None:
        bits.append(f"Series {entry['s']}, episode {entry['e']}")
    if entry.get("ep"):
        bits.append(entry["ep"])
    return ": ".join(bits)


def xmltv(channels, base, station, start=None, days=7):
    """The guide for every channel on air, from the start of the current hour for `days` days."""
    now = time.time() if start is None else start
    since = now - now % 3600
    until = since + days * 86400
    out = ['<?xml version="1.0" encoding="UTF-8"?>', f'<tv generator-info-name={quoteattr(station + " (TV station plug-in)")}>']
    live = [ch for ch in channels if ch.get("on", True)]
    for ch in live:
        out.append(f'  <channel id={quoteattr(channel_key(ch))}>')
        out.append(f"    <display-name>{escape(ch.get('name') or 'Channel')}</display-name>")
        out.append(f"    <display-name>{escape(str(ch['number']))}</display-name>")
        out.append(f'    <icon src={quoteattr(base + "/logo/" + ch["id"] + ".png")}/>')
        out.append("  </channel>")
    for ch in live:
        for a in Channel(ch).airings(since, until):
            e = a["entry"]
            out.append(f'  <programme start="{_xmltime(a["start"])}" stop="{_xmltime(a["end"])}" channel={quoteattr(channel_key(ch))}>')
            out.append(f"    <title>{escape(programme_title(e))}</title>")
            if episode_words(e):
                out.append(f"    <sub-title>{escape(episode_words(e))}</sub-title>")
            if e.get("plot"):
                out.append(f"    <desc>{escape(e['plot'])}</desc>")
            for g in (e.get("genres") or [])[:3]:
                out.append(f"    <category>{escape(g)}</category>")
            out.append(f"    <category>{'Series' if e.get('kind') == 'Episode' else 'Movie'}</category>")
            if e.get("year"):
                out.append(f"    <date>{int(e['year'])}</date>")
            if e.get("art"):
                out.append(f'    <icon src={quoteattr(base + "/art/" + e["art"] + ".jpg")}/>')
            if e.get("s") is not None and e.get("e") is not None:
                out.append(f'    <episode-num system="xmltv_ns">{max(0, int(e["s"]) - 1)}.{max(0, int(e["e"]) - 1)}.</episode-num>')
            if is_new(e, a["start"]):
                out.append("    <new/>")
            else:
                out.append("    <previously-shown/>")
            out.append("  </programme>")
    out.append("</tv>")
    return "\n".join(out) + "\n"
