# Direct play: Settings

Direct play's settings are on its own tab: go to **Settings**, then **Plug-ins**, then **Direct play**. Starboard draws them and keeps them; secrets are never shown again once saved.

## Files

| Setting | What it does | Default |
|---|---|---|
| **Files** | A page of its own on Direct play's tab. | None |

## Devices

| Setting | What it does | Default |
|---|---|---|
| **Roku Express and older Rokus** | H.264 up to 1080p; Dolby Digital, AAC and MP3 sound. No HEVC, DTS or TrueHD. Activated or deactivated. | Activated |
| **Roku 4K** | Roku Express 4K, Streaming Stick 4K and Ultra: H.264 and HEVC up to 4K. No DTS or TrueHD. Activated or deactivated. | Deactivated |
| **Fire TV Sticks** | H.264 and HEVC up to 1080p, so the HD sticks play them too. No DTS or TrueHD. Activated or deactivated. | Deactivated |
| **Chromecast** | H.264 up to 1080p; AAC, MP3, Opus and FLAC sound. No HEVC, Dolby Digital, DTS or TrueHD. Activated or deactivated. | Deactivated |
| **Smart TV apps** | Jellyfin on Samsung and LG televisions: H.264 and HEVC up to 4K. No DTS or TrueHD. Activated or deactivated. | Deactivated |
| **Web browsers** | H.264 up to 4K; AAC, MP3, Opus and FLAC sound. No HEVC or Dolby Digital, so files with only Dolby Digital get a stereo track. Activated or deactivated. | Deactivated |
| **Apple TV** | H.264 and HEVC up to 4K; Dolby Digital, AAC and FLAC sound. No DTS or TrueHD. Activated or deactivated. | Deactivated |
| **Nvidia Shield** | Nearly everything, DTS and TrueHD included, up to 4K. Activated or deactivated. | Deactivated |

## When it works

| Setting | What it does | Default |
|---|---|---|
| **When it works** | One file at a time, at the lowest priority. The file being converted always finishes. One of: At weekends, In Starboard's quiet hours, Any time. | At weekends |

## Shrink

| Setting | What it does | Default |
|---|---|---|
| **Shrink very large H.264 files** | Converts H.264 files with a higher bitrate than below again, at the same picture quality. A file is kept as it was when it would not get at least a tenth smaller. Activated or deactivated. | Activated |
| **Shrink 1080p files above** | A number from 4 to 80 Mbps. | 15 Mbps |
| **Shrink 720p files above** | A number from 2 to 40 Mbps. | 8 Mbps |
| **Shrink smaller files above** | A number from 1 to 20 Mbps. | 5 Mbps |

## More

| Setting | What it does | Default |
|---|---|---|
| **Convert HEVC to H.264** | Only when none of your devices plays HEVC. H.264 files are larger, so this uses more space. Activated or deactivated. | Deactivated |
| **Keep the originals** | Moves each original to a .direct-play-originals folder in movies or tv instead of replacing it, so you can delete them yourself. Saves no space until you do. Activated or deactivated. | Deactivated |
| **Card updates every** | How often the Direct play card on the dashboard shows the progress while a file is converted. One of: 10 seconds, 30 seconds, 1 minute, 5 minutes. | 30 seconds |

## Buttons

These are on Direct play's tab.

- **Pause fixing**
- **Resume fixing**
- **Look at the library now**

## Things to note

- A setting you change is used straight away; you do not need to deactivate it first.
- Settings are kept when you update or deactivate it, and when you remove it they stay in its folder.

## Find out more

- [Install](install.md)
- [Dashboard card](dashboard-card.md)
- [Problems](problems.md)
