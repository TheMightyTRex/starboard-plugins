# TV station: For developers

How TV station is built, for anyone who wants to change it or make one like it. It is MIT, by TheMightyTRexUK, and works with plug-in API `>=1.15 <2.0`.

## Its files

- [`starboard-plugin.json`](../../../tv-station/starboard-plugin.json)
- [`app.py`](../../../tv-station/app.py): the web server, Starboard's pages and card, and Jellyfin
- [`schedule.py`](../../../tv-station/schedule.py): the schedule and the breaks, with no input or output
- [`guide.py`](../../../tv-station/guide.py): the channel list (M3U) and the guide (XMLTV)
- [`dog.py`](../../../tv-station/dog.py): the on-screen logo, straps and cards as FFmpeg filters
- [`stream.py`](../../../tv-station/stream.py): one FFmpeg for each channel being watched, shared by its viewers
- [`library.py`](../../../tv-station/library.py): line-ups and clips from Jellyfin
- [`sbplugin.py`](../../../tv-station/sbplugin.py)
- [`Dockerfile`](../../../tv-station/Dockerfile)
- [`install.py`](../../../tv-station/install.py)
- [`logo.svg`](../../../tv-station/logo.svg)
- [`atkinson-hyperlegible-next.woff2`](../../../tv-station/atkinson-hyperlegible-next.woff2), the font on the television, with its licence, [`LICENSE-OFL.txt`](../../../tv-station/LICENSE-OFL.txt)
- [`CHANGELOG.md`](../../../tv-station/CHANGELOG.md)
- [`tests/test_tv_station.py`](../../../tests/test_tv_station.py)

## Containers

| Container | Network | Folders | Runs as | Starts | Limits |
|---|---|---|---|---|---|
| `main` | `lan`, published (it tries port 8790 first) | `data` | `10001:10001` | `always` | 768 MB, 2 cores |

Its image is built for amd64, arm64 and arm/v7 by `.github/workflows/tv-station-image.yml`, and pinned by digest in the manifest when it is published.

## How the schedule works

A channel is a function from time to programme, an idea from [Clickarr](https://github.com/thegregstengel/clickarr) (MIT); no code is copied. A channel keeps eras: each is a frozen line-up (every programme and its length), the moment it starts, a seed and the channel's order and times. What is on at any moment is worked out from those, so the guide, the card and the stream always agree, and nothing is kept or run between viewings.

- **Shuffled** uses a SplitMix64 random number generator of its own, so a shuffle is the same on every computer.
- **A new line-up** starts at the end of the programme on air, carrying on from the programme that would have come next.
- **Breaks** are planned from the same inputs: an ident, trailers and clips that fit, then Later and Coming up next cards for the rest.

## What Starboard and Jellyfin call

| Path | Who | What it is |
|---|---|---|
| `GET /health` | Starboard | 200 while it runs |
| `GET /card` | Starboard | **What is on now**, a guide card |
| `GET` and `POST /channels`, `/clips`, `/guide` | Starboard | Its custom pages; refused without the plug-in's own key in `X-Api-Key` |
| `POST /channels/file`, `/clips/file` | Starboard | A logo, ident or clip chosen on a page, streamed to its folder |
| `POST /actions/refresh`, `/actions/stop` | Starboard | Its two buttons |
| `POST /jobs/refresh` | Starboard | The nightly line-up refresh, at 04:40 |
| `POST /update/before`, `/update/after` | Starboard | Stops every stream before an update |
| `GET /` | People | A small page; opening it tells TV station its own address |
| `GET /t/<token>/channels.m3u` | Jellyfin | The channel list |
| `GET /t/<token>/guide.xml` | Jellyfin | The guide, 7 days |
| `GET /t/<token>/stream/<channel>.ts` | Jellyfin | A channel's stream, MPEG-TS |
| `GET /t/<token>/logo/<channel>.png`, `/art/<item>.jpg` | Jellyfin | Channel logos, and programme pictures from Jellyfin |
| `GET /t/<token>/preview/<channel>.png` | People | A frame with the on-screen logo, or `?kind=card` for a card |

`<token>` is a random word kept in its folder, given only to Jellyfin.

## Tests

`python3 -m unittest tests.test_tv_station`: the schedule (the same answer for the same time, joining part way, boundaries, breaks filling the gap, new episodes joining at the next boundary), the guide and channel list, the on-screen logo options, the pages, and, where FFmpeg is installed, a real run that tunes in part way through a made-up clip and checks the logo is drawn, then two viewers sharing one stream that stops after they leave.

## Find out more

- [Plug-in API](../../developers/plug-in-api.md)
- [App plug-ins](../../developers/app-plug-ins.md)
