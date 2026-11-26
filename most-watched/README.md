# Most watched

The films and series most people watched in Jellyfin in the last week.

An example Starboard plug-in by TheMightyTRexUK, MIT licence.

## What it may do

- It uses Jellyfin's key, which Starboard keeps.
- It reaches your home network and the internet.
- It runs one small container (64 MB of memory at most).

## On the dashboard

- **Most watched**: a list card.

## Settings

- **Over the last**

## Updating

Before an update, it finishes any check or message it is part way through and starts no new one. So the update never cuts one short (plug-in API 1.14). What changed in each version is in [CHANGELOG.md](CHANGELOG.md), and Starboard shows it before you update.

## Add it

Needs Starboard with plug-in API 1.14 or later. A Starboard with an older plug-in API is offered the version before. In Starboard, go to **Settings**, then **Plug-ins**, then **Catalogue**, and find it under **Jellyfin**. Or, under **Add one from elsewhere**, give this address:

`https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/most-watched/starboard-plugin.json`

Or run `python3 install.py` in this folder.
