# Starboard plug-ins

Add more to [Starboard](https://github.com/TheMightyTRex/starboard), the lightweight, accessible dashboard for home
media servers. Every plug-in here has passed Starboard's plug-in tester, accessibility included, and runs in a
locked-down container that can only reach what it says it needs.

**Help:** the [plug-ins help centre](https://themightytrex.github.io/starboard-plugins/help/) has a page for every
plug-in: what it does, what it may change, its settings, its dashboard card, updates, accessibility and fixes for
problems.

## Add a plug-in

1. In Starboard, go to **Settings**, then **Plug-ins**, then **Catalogue**.
2. Find the plug-in and select **Install…**. Read what it may do, enter your Starboard password and select **Install**.
3. Select **Activate** when you are ready.

That is all most people need. Starboard keeps each plug-in up to date from the catalogue, and you can roll one back
from its page. Other ways to add one are under [Advanced](#advanced).

## Recommended

Starboard shows these first in the Catalogue, with a Recommended chip. It never adds them by itself.

- **[Direct play](https://themightytrex.github.io/starboard-plugins/help/plugins/direct-play/index.html):** films and series play directly on your devices, with no converting
  as they play.
- **[Disk forecast](https://themightytrex.github.io/starboard-plugins/help/plugins/disk-forecast/index.html):** when each disk will be full.
- **[Notifications](https://themightytrex.github.io/starboard-plugins/help/plugins/notifications/index.html):** Starboard's alerts on your phone, by email or chat.

## All the plug-ins

### Jellyfin

| Plug-in | What it does |
|---|---|
| [Direct play](https://themightytrex.github.io/starboard-plugins/help/plugins/direct-play/index.html) | Makes your films and series play directly on the devices you choose, so Jellyfin does not convert them as they play: one file at a time, in the hours you choose. |
| [Library clean-up](library-cleanup/) | Moves films and series everyone has watched, or nobody watches, to the holding folder after a Preview. It never deletes, and each can be put back. Needs Starboard 0.19.0. |
| [Library health](https://themightytrex.github.io/starboard-plugins/help/plugins/library-health/index.html) | Films and series in Jellyfin with no poster, no description or no year, so you can fix them. |
| [Most watched](https://themightytrex.github.io/starboard-plugins/help/plugins/most-watched/index.html) | The films and series most people watched in Jellyfin in the last week. |
| [Picture shrinker](https://themightytrex.github.io/starboard-plugins/help/plugins/picture-shrinker/index.html) | Shrinks the posters and photos of people Jellyfin keeps, so they take less space. Each picture is checked before it replaces the one Jellyfin saved. |
| [Watch statistics](https://themightytrex.github.io/starboard-plugins/help/plugins/watch-stats/index.html) | What was watched, by whom and when, and the top titles, from Jellyfin's Playback Reporting, with no second database. |
| [Watching now](https://themightytrex.github.io/starboard-plugins/help/plugins/watching-now/index.html) | Who is watching what in Jellyfin right now, with how far through they are. |

### Downloads

| Plug-in | What it does |
|---|---|
| [Download summary](https://themightytrex.github.io/starboard-plugins/help/plugins/download-summary/index.html) | How much has downloaded today and this week, from the download queue in Starboard. |
| [VPN check](https://themightytrex.github.io/starboard-plugins/help/plugins/vpn-check/index.html) | Shows the address and country your downloads use through the VPN, and warns if it is your home address. |

### System

| Plug-in | What it does |
|---|---|
| [Disk forecast](https://themightytrex.github.io/starboard-plugins/help/plugins/disk-forecast/index.html) | When each disk fills at the rate it has been filling over the last month. |
| [Notifications](https://themightytrex.github.io/starboard-plugins/help/plugins/notifications/index.html) | Sends Starboard's events to email, Telegram, Discord, Signal, Pushover, ntfy or a webhook, in plain words, and a weekly New this week. |

### Network

| Plug-in | What it does |
|---|---|
| [Ad blocking](https://themightytrex.github.io/starboard-plugins/help/plugins/dns-blocking/index.html) | How many adverts and trackers Pi-hole or AdGuard Home blocked today. |
| [Line speed](https://themightytrex.github.io/starboard-plugins/help/plugins/line-speed/index.html) | Tests your internet download speed once a night, outside download hours, and keeps a week of results. |
| [Outside services](https://themightytrex.github.io/starboard-plugins/help/plugins/outside-services/index.html) | Up or down for things that are not on this server: your router, a NAS, a website. |
| [Remote access](https://themightytrex.github.io/starboard-plugins/help/plugins/remote-access/index.html) | Starboard, Jellyfin and Audiobookshelf away from home through Tailscale or Cloudflare Tunnel, with no port opened on your router. |

### Home

| Plug-in | What it does |
|---|---|
| [Home Assistant](https://themightytrex.github.io/starboard-plugins/help/plugins/home-assistant/index.html) | Your house in one sentence on the dashboard: the things you choose from Home Assistant. |

### Accessibility

| Plug-in | What it does |
|---|---|
| [Audio description](https://themightytrex.github.io/starboard-plugins/help/plugins/audio-description/index.html) | Finds films and series in Jellyfin with a described sound track for blind and partially sighted people, and prefers releases with one in Reelix. |
| [Audio description tracks](https://themightytrex.github.io/starboard-plugins/help/plugins/audio-description-tracks/index.html) | Adds a description track you already have, such as one from AudioVault, to its film or episode in Jellyfin, after checking that the lengths match. |

### Appearance

| Plug-in | What it does |
|---|---|
| [Styles](https://themightytrex.github.io/starboard-plugins/help/plugins/styles/index.html) | 21 accessible styles for Display: six change every part of Starboard (cards, buttons, tabs, menus), checked for contrast. |

## Apps you can add

Whole apps kept out of the main install. Each opens on its own page on your home network, from **Open** on its
plug-in page. They run in the same locked-down containers as every plug-in: read only, never as root and only with
their own folders. Removing one keeps its data.

| App | What it does | Memory at rest | Folders it reads or changes |
|---|---|---|---|
| [Calibre-Web](https://themightytrex.github.io/starboard-plugins/help/plugins/calibre-web/index.html) | Calibre-Web, a browser page for a Calibre library: read, search and send books to an e-reader. It reads your books folder and never changes it. | about 182 MB | `media/books`, read only |
| [Checkrr](https://themightytrex.github.io/starboard-plugins/help/plugins/checkrr/index.html) | Checkrr checks your films and series for damaged files each Sunday night and lists them. It only reports: it never deletes, moves or replaces a file, and reads your media read only. | about 19 MB | `media/movies` and `media/tv`, read only |
| [Jellystat](https://themightytrex.github.io/starboard-plugins/help/plugins/jellystat/index.html) | Jellystat, the full watch statistics app for Jellyfin, with its own PostgreSQL database, kept apart from the main install. Opens on its own web page. | about 117 MB | its own only |
| [Kavita](https://themightytrex.github.io/starboard-plugins/help/plugins/kavita/index.html) | Kavita, a reader for comics, manga and books in the browser and in e-reader apps (OPDS). It reads your books and comics folders and never changes them. | about 337 MB | `media/books` and `media/comics`, read only |
| [Maintainerr](https://themightytrex.github.io/starboard-plugins/help/plugins/maintainerr/index.html) | Maintainerr, clean-up rules for Jellyfin, such as films everyone has watched. It changes nothing until you give it keys and a rule that removes. | about 127 MB | its own only |
| [Navidrome](https://themightytrex.github.io/starboard-plugins/help/plugins/navidrome/index.html) | Navidrome, a music server for Subsonic apps on phones and in the car. It reads your music folder and never changes it. | about 16 MB | `media/music`, read only |
| [Seerr](https://themightytrex.github.io/starboard-plugins/help/plugins/seerr/index.html) | Seerr, a requests page for Jellyfin users. Reelix already has requests in Starboard, so most people do not need it. | about 127 MB | its own only |
| [Tdarr](https://themightytrex.github.io/starboard-plugins/help/plugins/tdarr/index.html) | Tdarr converts films and series to save space, in Starboard's quiet hours. It can copy the Tdarr you already have, with its libraries and history. | about 59 MB | `media/movies` and `media/tv`, read and write |
| [Themearr](https://themightytrex.github.io/starboard-plugins/help/plugins/themearr/index.html) | Themearr puts a theme tune, theme.mp3, in the folder of each film Reelix has, and Jellyfin plays it on the film's page. It needs a RapidAPI key to fetch the tunes. | about 48 MB | `media/movies`, adds `theme.mp3` |
| [Uptime Kuma](https://themightytrex.github.io/starboard-plugins/help/plugins/uptime-kuma/index.html) | Uptime Kuma, status checks for websites and services, with alerts and status pages. Starboard already watches your apps; this is for more. | about 116 MB | its own only |
| [Wizarr](https://themightytrex.github.io/starboard-plugins/help/plugins/wizarr/index.html) | Wizarr, invitation links for Jellyfin: send someone a link and they make their own Jellyfin account, with the libraries you choose. | about 124 MB | its own only |

## Advanced

### Add a plug-in from elsewhere

- **By address:** in **Settings**, **Plug-ins**, under **Add one from elsewhere**, paste the address into **The
  plug-in's manifest address**, such as `https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/disk-forecast/starboard-plugin.json`.
- **From a file:** download [the plug-in's ZIP file from the zips folder](zips/), unzip it and run `python3 install.py` inside, or choose
  its `starboard-plugin.json` under **Or its manifest file**.

### Starboard versions

Every plug-in here needs plug-in API 1.14 (Starboard 0.18.0 or newer). An older Starboard is offered the version
before from the catalogue, and says so when a plug-in needs a newer one.

### How plug-ins are published

- A plug-in is published when every image it runs is pinned by digest (`@sha256:`), so Starboard downloads exactly
  what was built and tested. Until then the catalogue marks it 'Coming soon'.
- The small example plug-ins share one image, `ghcr.io/themightytrex/starboard-plugin-examples` (Python's standard
  library only, about 14 MB of memory each while running), so Starboard downloads it once.
- Images are built for amd64, arm64 and arm/v7, except Remote access (amd64 and arm64: cloudflared has no 32-bit Arm
  build).
- Each logo is `logo.svg` in the plug-in's folder, drawn by `tools/make_logos.py`: an original symbol on a rounded tile.
- **Published by itself:** after an image is built on main, the Publish built images workflow pins each image built
  from the files there now to its digest (`tools/publish_images.py`, which reads the commit each image was built
  from), remakes the catalogue and zips, runs the checks and opens a pull request. Merging it publishes the plug-in;
  nothing reaches the catalogue before. A new plug-in's image workflow goes in that workflow's list (a test checks).
- `tools/make_examples.py` writes `catalogue.json` and the example plug-ins; `tools/make_zips.py` makes the zips;
  `tools/app_check.py` runs an app plug-in as Starboard would and measures it at rest.
- Dozzle is not here: it would need every app's details from Docker, passwords included, so it cannot be a safe
  plug-in. Starboard's **System**, **Logs** does its job.

### Make your own

Each plug-in is a folder with a `starboard-plugin.json`. Start with the
[developers' pages](https://themightytrex.github.io/starboard-plugins/help/areas/dev.html), test it in Starboard's
**Settings**, **Plug-ins**, **Test a plug-in**, then run `python3 tools/make_zips.py`. The tests run with
`python3 -m unittest discover -s tests`.

## Licence

Each plug-in has its own licence file. All are MIT, by TheMightyTRexUK.
