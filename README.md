# Starboard plug-ins

Plug-ins for [Starboard](https://github.com/TheMightyTRex/starboard), the lightweight, accessible dashboard for
smaller home media servers. Each one has passed Starboard's plug-in tester, accessibility included.

| Plug-in | What it does | Install address | Download |
|---|---|---|---|
| [Styles](styles/) | Twenty-one accessible styles for Starboard's Display settings, with gradients, textures and glass (needs Starboard 0.16.5) | `https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/styles/starboard-plugin.json` | [styles.zip](https://github.com/TheMightyTRex/starboard-plugins/raw/main/zips/styles.zip) |
| [Audio description](audio-description/) | Films and series in Jellyfin with a described sound track for blind and partially sighted people, preferred in Reelix searches (not published yet: needs the shared image built again) | `https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/audio-description/starboard-plugin.json` | [audio-description.zip](https://github.com/TheMightyTRex/starboard-plugins/raw/main/zips/audio-description.zip) |
| [Audio description tracks](audio-description-tracks/) | Adds a description track you already have, such as one from AudioVault, to its film or episode in Jellyfin after checking the lengths match (needs plug-in API 1.12 and its own image, with ffmpeg; coming soon) | `https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/audio-description-tracks/starboard-plugin.json` | [audio-description-tracks.zip](https://github.com/TheMightyTRex/starboard-plugins/raw/main/zips/audio-description-tracks.zip) |
| [Disk forecast](disk-forecast/) | When each disk fills at the rate it has been filling over the last month. | `https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/disk-forecast/starboard-plugin.json` | [disk-forecast.zip](https://github.com/TheMightyTRex/starboard-plugins/raw/main/zips/disk-forecast.zip) |
| [Ad blocking](dns-blocking/) | How many adverts and trackers Pi-hole or AdGuard Home blocked today. | `https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/dns-blocking/starboard-plugin.json` | [dns-blocking.zip](https://github.com/TheMightyTRex/starboard-plugins/raw/main/zips/dns-blocking.zip) |
| [Download summary](download-summary/) | How much has downloaded today and this week, from what Starboard sees in the queue. | `https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/download-summary/starboard-plugin.json` | [download-summary.zip](https://github.com/TheMightyTRex/starboard-plugins/raw/main/zips/download-summary.zip) |
| [Home Assistant](home-assistant/) | Your house in one sentence on the dashboard: the things you choose from Home Assistant. | `https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/home-assistant/starboard-plugin.json` | [home-assistant.zip](https://github.com/TheMightyTRex/starboard-plugins/raw/main/zips/home-assistant.zip) |
| [Library health](library-health/) | Films and series in Jellyfin with no poster, no description or no year, so you can fix them. | `https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/library-health/starboard-plugin.json` | [library-health.zip](https://github.com/TheMightyTRex/starboard-plugins/raw/main/zips/library-health.zip) |
| [Line speed](line-speed/) | Tests your internet download speed once a night, outside download hours, and keeps a week of results. | `https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/line-speed/starboard-plugin.json` | [line-speed.zip](https://github.com/TheMightyTRex/starboard-plugins/raw/main/zips/line-speed.zip) |
| [Most watched](most-watched/) | The films and series most people watched in Jellyfin in the last week. | `https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/most-watched/starboard-plugin.json` | [most-watched.zip](https://github.com/TheMightyTRex/starboard-plugins/raw/main/zips/most-watched.zip) |
| [Notifications](notifications/) | Sends Starboard's events to email, Telegram, Discord, Signal, Pushover, ntfy or a webhook, in plain words, and a weekly New this week (needs plug-in API 1.11; coming soon) | `https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/notifications/starboard-plugin.json` | [notifications.zip](https://github.com/TheMightyTRex/starboard-plugins/raw/main/zips/notifications.zip) |
| [Outside services](outside-services/) | Up or down for things that are not on this server: your router, a NAS, a website. | `https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/outside-services/starboard-plugin.json` | [outside-services.zip](https://github.com/TheMightyTRex/starboard-plugins/raw/main/zips/outside-services.zip) |
| [Remote access](remote-access/) | Starboard, Jellyfin and Audiobookshelf away from home through Tailscale or Cloudflare Tunnel, with no port opened on your router. Download apps are never shared. Coming soon: its image is not published yet. | `https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/remote-access/starboard-plugin.json` | [remote-access.zip](https://github.com/TheMightyTRex/starboard-plugins/raw/main/zips/remote-access.zip) |
| [VPN check](vpn-check/) | Shows the address and country your downloads use through the VPN, and warns if it is your home address. | `https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/vpn-check/starboard-plugin.json` | [vpn-check.zip](https://github.com/TheMightyTRex/starboard-plugins/raw/main/zips/vpn-check.zip) |
| [Watch statistics](watch-stats/) | What was watched, by whom and when, and the top titles, from Jellyfin's Playback Reporting, with no second database (needs plug-in API 1.11; coming soon) | `https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/watch-stats/starboard-plugin.json` | [watch-stats.zip](https://github.com/TheMightyTRex/starboard-plugins/raw/main/zips/watch-stats.zip) |
| [Watching now](watching-now/) | Who is watching what in Jellyfin right now, with how far through they are. | `https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/watching-now/starboard-plugin.json` | [watching-now.zip](https://github.com/TheMightyTRex/starboard-plugins/raw/main/zips/watching-now.zip) |

## Add a plug-in

1. In Starboard, open **Settings**, **Plug-ins**, **Add a plug-in**.
2. Copy the plug-in's install address into **The plug-in's manifest address**.
3. Check what it may do, then add it. Activate it when you are ready.

Or download its zip, unzip it and run `python3 install.py` inside, or choose its `starboard-plugin.json` under
**Or its manifest file**.

Read [Add a plug-in](https://github.com/TheMightyTRex/starboard/blob/main/docs/help/topics/add-a-plugin.md) and
[What a plug-in can change](https://github.com/TheMightyTRex/starboard/blob/main/docs/help/basics/what-plugins-can-change.md).

The twelve examples (all but Styles) and Audio description share one small image, `ghcr.io/themightytrex/starboard-plugin-examples`
(Python's standard library only, about 14 MB of memory each while running), so Starboard downloads it once.
They are short on purpose: read any `app.py` to see how a plug-in answers Starboard's cards and buttons. Notifications and Watch statistics are
longer: they keep their own version, changelog and `app.py` in their folders, with tests in `tests/`
(`python3 -m unittest discover -s tests`). They name the image's next tag, 1.1.0, until it is built with them and its
digest pinned, so the catalogue shows them as coming soon until then.

## Make your own

Each plug-in is a folder with a `starboard-plugin.json`. Read
[Write a plug-in](https://github.com/TheMightyTRex/starboard/blob/main/docs/help/basics/write-a-plugin.md), test it in
**Settings**, **Plug-ins**, **Test a plug-in**, then run `python3 tools/make_zips.py` to make its zip.

## Licence

Each plug-in has its own licence file. All are MIT, by TheMightyTRexUK.
