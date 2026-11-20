[Help centre](../README.md) · Get started · reference
<!-- help: start / first -->

# Choose the plug-ins for your server

Every plug-in in the collection, by what it is for, with the most memory it may use. Add only the ones you want:
Starboard adds none by itself, and each one you add uses a little memory and processor.

## When would you use it

- You want to know what the collection offers before you add anything.
- You need to know which plug-ins suit a small server, such as a Raspberry Pi with 1 or 2 GB of memory.

## Watching and library

| Plug-in | What it does | Memory at most |
|---|---|---|
| [Watching now](../../watching-now/README.md) | Who is watching what in Jellyfin right now | 48 MB |
| [Most watched](../../most-watched/README.md) | The films and series most people watched in the last week | 64 MB |
| [Watch statistics](../../watch-stats/README.md) | What was watched, by whom and when, from Jellyfin's Playback Reporting | 64 MB, resting when idle |
| [Library health](../../library-health/README.md) | Films and series with no poster, description or year | 96 MB |
| [Audio description](../../audio-description/README.md) | Finds titles with a described sound track, and prefers them in Reelix | 64 MB, resting when idle |
| [Audio description tracks](../../audio-description-tracks/README.md) | Adds a description track you already have to its film or episode | 96 MB, resting when idle |
| [Direct play](../../direct-play/README.md) | Makes files play directly on your devices, so Jellyfin does not convert them as they play | 512 MB |
| [Picture shrinker](../../picture-shrinker/README.md) | Shrinks the posters, backdrops, logos and other pictures Jellyfin keeps | 128 MB |
| [Library clean-up](../../library-cleanup/README.md) | Moves films and series everyone has watched, or nobody watches, to the holding folder; never deletes | 128 MB, resting when idle |
| [Create your own TV channel](../../tv-station/README.md) | Your own TV channels in Jellyfin's Live TV, made from your films and series | 768 MB, and nothing runs until a channel is chosen |

## Server and downloads

| Plug-in | What it does | Memory at most |
|---|---|---|
| [Disk forecast](../../disk-forecast/README.md) | When each disk fills, at the rate it has been filling | 48 MB |
| [Notifications](../../notifications/README.md) | Sends Starboard's events to email, Telegram, Discord and more | 48 MB, resting when idle |
| [Download summary](../../download-summary/README.md) | How much downloaded today and this week | 48 MB |
| [VPN check](../../vpn-check/README.md) | The address your downloads use through the VPN | 48 MB |

## Network and safety

| Plug-in | What it does | Memory at most |
|---|---|---|
| [Remote access](../../remote-access/README.md) | Starboard, Jellyfin and Audiobookshelf away from home, with no port opened on your router | 128 MB |
| [Ad blocking](../../dns-blocking/README.md) | How many adverts and trackers Pi-hole or AdGuard Home blocked today | 48 MB |
| [Line speed](../../line-speed/README.md) | Your internet download speed, tested once a night | 64 MB |
| [Uptime and status](../../outside-services/README.md) | Checks your router, NAS and websites by address, port, ping, DNS or heartbeat, with a status page | 48 MB |

## Home and appearance

| Plug-in | What it does | Memory at most |
|---|---|---|
| [Home Assistant](../../home-assistant/README.md) | Your house in one sentence on the dashboard | 48 MB |
| [Philips Hue](../../philips-hue/README.md) | Your Hue lights by room, zone and type, with scenes and schedules, through the bridge on your home network | 48 MB |
| [Styles](../../styles/README.md) | 22 accessible styles for **Display** | None: it runs nothing |

## Apps you can add

Whole apps made by others, each with its own web page on your home network. They use more memory than the other
plug-ins, so check the figures before you add one to a small server.

| Plug-in | What it does | Memory at most |
|---|---|---|
| [Jellystat](../../jellystat/README.md) | Every figure about what was watched in Jellyfin, with its own database | 640 MB, in three containers |
| [Navidrome](../../navidrome/README.md) | Your music in Subsonic apps | 256 MB |
| [Kavita](../../kavita/README.md) | Comics, manga and books in the browser | 768 MB |
| [Calibre-Web](../../calibre-web/README.md) | A Calibre library in the browser | 384 MB |
| [Wizarr](../../wizarr/README.md) | Invitation links for Jellyfin | 384 MB |
| [Maintainerr](../../maintainerr/README.md) | Clean-up rules for Jellyfin | 384 MB |
| [Uptime Kuma](../../uptime-kuma/README.md) | Status checks beyond your apps | 384 MB |
| [Seerr](../../seerr/README.md) | A requests page | 512 MB |
| [Tdarr](../../tdarr/README.md) | Converts films and series to save space | 2048 MB |
| [Themearr](../../themearr/README.md) | A theme tune on each film's page in Jellyfin | 576 MB, in two containers |
| [Checkrr](../../checkrr/README.md) | Finds damaged films and episodes, and only reports them | 576 MB, in two containers |

## Things to note

- **Memory at most** is the limit Starboard sets, not what the plug-in uses. Measured figures are on each plug-in's
  Install page, and in [Memory and processor](../use/memory-and-processor.md).
- **Recommended** plug-ins come first in the catalogue: Direct play, Notifications and Disk forecast. Adding one is
  still your choice.
- Each plug-in lists what it may do before you add it. Read [What each plug-in may do](../use/what-each-plug-in-may-do.md).

## Find out more

- [Add your first plug-in](add-your-first-plug-in.md)
- [Memory and processor](../use/memory-and-processor.md)
- [The plug-in collection, in Starboard's help](https://themightytrex.github.io/starboard/help/basics/plugin-collection.html)
