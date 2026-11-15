[Help centre](../README.md) · Use it · reference
<!-- help: use / everyday -->

# Memory and processor

The most memory and processor each plug-in may use, and what it was measured using, where it has been measured.
Starboard sets the limits, so a plug-in can never take more than its share of a small server.

## When would you use it

- You want to know how much a plug-in adds before you add it to a small server.
- You need to see which plug-ins rest when nobody is using them.

## The limits and the measurements

Measured figures are at rest unless they say otherwise, with Starboard's limits in place. "Not measured yet" means
nobody has measured that plug-in: the limit is the most it may use.

| Plug-in | Limit | When it runs | Measured |
|---|---|---|---|
| [Watching now](../plugins/watching-now/install.md) | 48 MB, 0.1 core | Always | Not measured yet |
| [Most watched](../plugins/most-watched/install.md) | 64 MB, 0.1 core | Always | Not measured yet |
| [Watch statistics](../plugins/watch-stats/install.md) | 64 MB, 0.25 core | Rests when idle | About 14 MB for a few seconds when asked |
| [Library health](../plugins/library-health/install.md) | 96 MB, 0.25 core | Always | Not measured yet |
| [Audio description](../plugins/audio-description/install.md) | 64 MB, 0.25 core | Rests when idle | Not measured yet |
| [Audio description tracks](../plugins/audio-description-tracks/install.md) | 96 MB, 0.5 core | Rests when idle | Not measured yet |
| [Direct play](../plugins/direct-play/install.md) | 512 MB, 1 core | Always | Not measured yet |
| [Picture shrinker](../plugins/picture-shrinker/install.md) | 128 MB, 0.5 core | Always | 12.1 MiB at rest, 28.0 MiB at its busiest (14 November 2026) |
| [Disk forecast](../plugins/disk-forecast/install.md) | 48 MB, 0.1 core | Always | Not measured yet |
| [Notifications](../plugins/notifications/install.md) | 48 MB, 0.1 core | Rests when idle | About 14 MB for about a second while it sends |
| [Download summary](../plugins/download-summary/install.md) | 48 MB, 0.1 core | Always | Not measured yet |
| [VPN check](../plugins/vpn-check/install.md) | 48 MB, 0.1 core | Always | Not measured yet |
| [Remote access](../plugins/remote-access/install.md) | 128 MB, 0.5 core | Always | About 20 to 32 MB (13 November 2026) |
| [Ad blocking](../plugins/dns-blocking/install.md) | 48 MB, 0.1 core | Always | Not measured yet |
| [Line speed](../plugins/line-speed/install.md) | 64 MB, 0.25 core | Always | Not measured yet |
| [Outside services](../plugins/outside-services/install.md) | 48 MB, 0.1 core | Always | Not measured yet |
| [Home Assistant](../plugins/home-assistant/install.md) | 48 MB, 0.1 core | Always | Not measured yet |
| [Styles](../plugins/styles/install.md) | None | Runs nothing | None: it runs nothing |
| [Jellystat](../plugins/jellystat/install.md) | 640 MB, 1.25 cores, in three containers | Always | 126.4 MiB (13 November 2026) |
| [Navidrome](../plugins/navidrome/install.md) | 256 MB, 0.5 core | Always | 20.0 MiB (13 November 2026) |
| [Kavita](../plugins/kavita/install.md) | 768 MB, 1 core | Always | 339.1 MiB (13 November 2026) |
| [Calibre-Web](../plugins/calibre-web/install.md) | 384 MB, 0.5 core | Always | 182.2 MiB (13 November 2026) |
| [Wizarr](../plugins/wizarr/install.md) | 384 MB, 0.5 core | Always | 126.8 MiB (13 November 2026) |
| [Maintainerr](../plugins/maintainerr/install.md) | 384 MB, 0.5 core | Always | 140.3 MiB (13 November 2026) |
| [Uptime Kuma](../plugins/uptime-kuma/install.md) | 384 MB, 0.5 core | Always | 115.6 MiB (13 November 2026) |
| [Seerr](../plugins/seerr/install.md) | 512 MB, 0.5 core | Always | 182.5 MiB (13 November 2026) |
| [Tdarr](../plugins/tdarr/install.md) | 2048 MB, 2 cores | Always | 59.1 MiB at rest, 748 MiB while converting (13 November 2026) |

## Things to note

- The apps were measured with `tools/app_check.py`: the median of 36 readings over 3 minutes, after 2 minutes to
  settle, with an empty library. A real library uses more.
- A plug-in that rests when idle uses no memory until Starboard wakes it for a card, a button, an event or a job.
- The twelve smaller plug-ins share one image, so Starboard downloads it once.

## Find out more

- [Choose the plug-ins for your server](../start/choose-plug-ins.md)
- [Memory and processor, in Starboard's help](https://themightytrex.github.io/starboard/help/comparisons/memory-and-processor.html)
