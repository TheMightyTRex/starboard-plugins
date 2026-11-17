[Help centre](../README.md) · Use it · reference
<!-- help: use / everyday -->

# What each plug-in may do

What every plug-in in the collection may read, reach and change, as Starboard lists it before you add one. A plug-in
can do only what is listed here, and only after you agree.

## When would you use it

- You want to know which plug-ins can change files on your server before you add them.
- You need to check which plug-ins use Jellyfin's or Reelix's key.

## Every plug-in

| Plug-in | What it may use | What it may change |
|---|---|---|
| [Watching now](../plugins/watching-now/install.md) | Jellyfin's key, Home network and internet | Only its own folder |
| [Most watched](../plugins/most-watched/install.md) | Jellyfin's key, Home network and internet | Only its own folder |
| [Watch statistics](../plugins/watch-stats/install.md) | Jellyfin's key, Home network and internet | Only its own folder |
| [Library health](../plugins/library-health/install.md) | Jellyfin's key, Home network and internet | Only its own folder |
| [Audio description](../plugins/audio-description/install.md) | Jellyfin's key, Reelix's key, Home network and internet | Only its own folder |
| [Audio description tracks](../plugins/audio-description-tracks/install.md) | Jellyfin's key, Home network and internet | `media/movies`, `media/tv`, `media/audio-description` |
| [Direct play](../plugins/direct-play/install.md) | Jellyfin's key, Reelix's key, Home network and internet | `media/movies`, `media/tv` |
| [Picture shrinker](../plugins/picture-shrinker/install.md) | Jellyfin's pictures and details | Jellyfin's metadata folder |
| [Disk forecast](../plugins/disk-forecast/install.md) | Processor, memory and disks | Only its own folder |
| [Notifications](../plugins/notifications/install.md) | Your apps, Downloads, Your media, Processor, memory and disks, Home network and internet | Only its own folder |
| [Download summary](../plugins/download-summary/install.md) | Downloads | Only its own folder |
| [VPN check](../plugins/vpn-check/install.md) | Inside your VPN | Only its own folder |
| [Remote access](../plugins/remote-access/install.md) | Your apps, Home network and internet | Only its own folder |
| [Ad blocking](../plugins/dns-blocking/install.md) | Home network and internet | Only its own folder |
| [Line speed](../plugins/line-speed/install.md) | Home network and internet | Only its own folder |
| [Outside services](../plugins/outside-services/install.md) | Home network and internet | Only its own folder |
| [Home Assistant](../plugins/home-assistant/install.md) | Home network and internet | Only its own folder |
| [Styles](../plugins/styles/install.md) | Styles | Only its own folder |
| [Jellystat](../plugins/jellystat/install.md) | Jellyfin's key, Home network and internet, Its own web page | Only its own folder |
| [Navidrome](../plugins/navidrome/install.md) | Home network and internet, Its own web page | Only its own folder |
| [Kavita](../plugins/kavita/install.md) | Home network and internet, Its own web page | Only its own folder |
| [Calibre-Web](../plugins/calibre-web/install.md) | Home network and internet, Its own web page | Only its own folder |
| [Wizarr](../plugins/wizarr/install.md) | Home network and internet, Its own web page | Only its own folder |
| [Maintainerr](../plugins/maintainerr/install.md) | Home network and internet, Its own web page | Only its own folder |
| [Uptime Kuma](../plugins/uptime-kuma/install.md) | Home network and internet, Its own web page | Only its own folder |
| [Seerr](../plugins/seerr/install.md) | Home network and internet, Its own web page | Only its own folder |
| [Tdarr](../plugins/tdarr/install.md) | Home network and internet, Its own web page | `media/tdarr-cache`, `media/movies`, `media/tv` |
| [Themearr](../plugins/themearr/install.md) | Reelix's key, Home network and internet, Its own web page | `media/movies`: adds `theme.mp3` to each film's folder |
| [Checkrr](../plugins/checkrr/install.md) | Home network and internet, Its own web page | Only its own folder; reads `media/movies` and `media/tv` |

Every plug-in may also change its own folder in Starboard's data, `data/plugins/<its id>`.

## What no plug-in can do

Whatever it asks for, no plug-in gets the Docker socket, administrator rights, the computer's own network, other apps'
settings or passwords, Starboard's own data, or any folder but its own and the ones listed. Each runs read only, as a
user that is not root, with no extra rights, and its image is pinned by digest, so what you approved is what runs.

## Things to note

- **Jellyfin's key** and **Reelix's key** are kept by Starboard and handed to the plug-in; the plug-in never receives your
  passwords. Removing the plug-in stops it using them.
- The plug-ins that change files check each file before it replaces the original. Read
  [Plug-ins that change your files](plug-ins-that-change-files.md).

## Find out more

- [What a plug-in can change, in Starboard's help](https://themightytrex.github.io/starboard/help/basics/what-plugins-can-change.html)
- [Memory and processor](memory-and-processor.md)
- [Choose the plug-ins for your server](../start/choose-plug-ins.md)
