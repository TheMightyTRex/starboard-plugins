# Library health

Films and series in Jellyfin with no poster, no description or no year, so you can fix them.

An example Starboard plug-in by TheMightyTRexUK, MIT licence.

## What it may do

- It uses Jellyfin's key, which Starboard keeps.
- It reaches your home network and the internet.
- It runs one small container (96 MB of memory at most).

## On the dashboard

- **Library health**: a stat card.
- **To fix in Jellyfin**: a list card.

## Updating

Before an update, it finishes any check or message it is part way through and starts no new one, so the update never cuts one short (plug-in API 1.14). What changed in each version is in [CHANGELOG.md](CHANGELOG.md), and Starboard shows it before you update.

## Add it

Needs Starboard with plug-in API 1.14 or later; a Starboard with an older plug-in API is offered the version before. In Starboard, go to **Settings**, then **Plug-ins**, then **Catalogue**, and find it under **Jellyfin**. Or, under **Add one from elsewhere**, give this address:

`https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/library-health/starboard-plugin.json`

Or run `python3 install.py` in this folder.
