# Sports streams

A Starboard plug-in that shows live and upcoming sports matches from a Stremio sports addon.

It checks the addon every few minutes (5 by default) and shows what is live on the dashboard: a status card with the count and a list card with each match and its sport.

## Settings

| Setting | What it does |
|---|---|
| **Addon address** | The base address of the Stremio sports addon. Default: `https://sports.highfly.dev` |
| **Check every** | How often to check, in minutes (1 to 60, default 5). |

## Install

From Starboard: **Settings, Plug-ins, Catalogue**, under **Sports**.

Or from this folder:

```
python3 install.py
```

Needs Starboard with plug-in API 1.14 or later.

## Licence

MIT — see [LICENSE](LICENSE).
