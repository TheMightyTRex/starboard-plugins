# Line speed

Tests your internet download speed once a night, outside download hours, and keeps a week of results.

An example Starboard plug-in by TheMightyTRexUK, MIT licence.

## What it may do

- It reaches your home network and the internet.
- It runs one small container (64 MB of memory at most).

## On the dashboard

- **Line speed**: a stat card.
- **Line speed this week**: a list card.

## Settings

- **Test at**: Choose an hour when nothing is downloading.
- **Test size**: Larger is more accurate on fast lines, and uses more of any data allowance.

## Updating

Before an update, it finishes a speed test it is part way through and starts no new one, so the update never cuts one short (plug-in API 1.14). What changed in each version is in [CHANGELOG.md](CHANGELOG.md), and Starboard shows it before you update.

## Add it

In Starboard, open **Settings**, **Plug-ins**, **Add a plug-in**, and give this address:

`https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/line-speed/starboard-plugin.json`

Or run `python3 install.py` in this folder.
