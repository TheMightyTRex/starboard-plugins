# Create your own TV channel: For developers

How Create your own TV channel is built, for anyone who wants to change it or make one like it. It is MIT, by TheMightyTRexUK, and works with plug-in API `>=1.15 <2.0`.

## Its files

- [`starboard-plugin.json`](../../../tv-station/starboard-plugin.json)
- [`app.py`](../../../tv-station/app.py): the web server, Starboard's pages and card, and Jellyfin
- [`schedule.py`](../../../tv-station/schedule.py): the schedule and the breaks, with no input or output
- [`guide.py`](../../../tv-station/guide.py): the channel list (M3U) and the guide (XMLTV)
- [`dog.py`](../../../tv-station/dog.py): the on-screen logo, straps and cards as FFmpeg filters
- [`stream.py`](../../../tv-station/stream.py): one FFmpeg for each channel being watched, shared by its viewers
- [`library.py`](../../../tv-station/library.py): line-ups and clips from Jellyfin
- [`pack.py`](../../../tv-station/pack.py): broadcast packs: the zip rules, the checks with ffprobe, loudness, the placement guides and the template
- [`pack.schema.json`](../../../tv-station/pack.schema.json): the JSON Schema for a pack's `pack.json`, checked with no library
- [`promo.py`](../../../tv-station/promo.py): which promos to make and replace, and the FFmpeg command for one
- [`grid.py`](../../../tv-station/grid.py): the schedule grid: every change as a function on a small JSON document, the week worked out, and the channel that follows it
- [`suggest.py`](../../../tv-station/suggest.py): suggests a week from watch history; also a script: `python3 suggest.py --url <Jellyfin> --key <key>`
- [`grid.html`](../../../tv-station/grid.html), [`grid.js`](../../../tv-station/grid.js), [`grid.css`](../../../tv-station/grid.css): the grid's own page, on [`ds-tokens.css`](../../../tv-station/ds-tokens.css), the design system's tokens (Mica): light unless Dark is chosen on the page
- [`example_pack.py`](../../../tv-station/example_pack.py): makes the Example TV pack with FFmpeg alone: `python3 example_pack.py <folder> --zip <file>`
- [`sbplugin.py`](../../../tv-station/sbplugin.py)
- [`Dockerfile`](../../../tv-station/Dockerfile)
- [`install.py`](../../../tv-station/install.py)
- [`logo.svg`](../../../tv-station/logo.svg)
- [`atkinson-hyperlegible-next.woff2`](../../../tv-station/atkinson-hyperlegible-next.woff2), the font on the television, with its licence, [`LICENSE-OFL.txt`](../../../tv-station/LICENSE-OFL.txt)
- [`CHANGELOG.md`](../../../tv-station/CHANGELOG.md)
- [`tests/test_tv_station.py`](../../../tests/test_tv_station.py) and [`tests/test_tv_station_pack.py`](../../../tests/test_tv_station_pack.py)

## Containers

| Container | Network | Folders | Runs as | Starts | Limits |
|---|---|---|---|---|---|
| `main` | `lan`, published (it tries port 8790 first) | `data` | `10001:10001` | `always` | 768 MB, 2 cores |

Its image is built for amd64, arm64 and arm/v7 by `.github/workflows/tv-station-image.yml`, and pinned by digest in the manifest when it is published.

## How the schedule works

A channel is a function from time to programme, an idea from [Clickarr](https://github.com/thegregstengel/clickarr) (MIT); no code is copied. A channel keeps eras. Each era is a frozen line-up (every programme and its length), the moment it starts, a seed, and the channel's order and times. The plug-in works out what is on at any moment from those. So the guide, the card and the stream always agree, and nothing is kept or run between viewings.

- **Shuffled** uses a SplitMix64 random number generator of its own, so a shuffle is the same on every computer.
- **A new line-up** starts at the end of the programme on air, carrying on from the programme that would have come next.
- **Breaks** are planned from the same inputs. They use a broadcast pack's logo with music, an ident, trailers, clips and promos that fit. Later and Coming up next cards fill the rest. The plug-in chooses a pack's idents at random from the break's seed, so the same break always has the same ident.
- **Transitions** sit on each cut between programme and break. The last half of a piece that ends on a cut plays as a piece of its own. So each FFmpeg run starts its transition at its own start, paced like the piece, and never holds frames waiting.
- **The stream** carries on from the end of what it has sent, within 8 seconds of the clock. So FFmpeg's first burst never sends anything twice, and a slow start never passes anything over. Every looped input is cut a second after its piece.

## Broadcast packs and promos

- **A pack** is unpacked to a new folder and checked. Only then does it take the place of the one in use, in `/data/packs/station`, `/data/packs/example` or `/data/packs/ch-<channel>`. What the stream uses is kept as `checked.json` beside it. [Make a broadcast pack](../../use/make-a-broadcast-pack.md) has the specification.
- **Promos** are made by `POST /jobs/promos`, which Starboard calls each hour of its quiet hours. It runs one FFmpeg at a time, at the lowest priority with one thread, and stops at once when a channel starts. They are kept in `/data/promos`.

## What Starboard and Jellyfin call

| Path | Who | What it is |
|---|---|---|
| `GET /health` | Starboard | 200 while it runs |
| `GET /card` | Starboard | **What is on now**, a guide card |
| `GET` and `POST /channels`, `/clips`, `/guide` | Starboard | Its custom pages; refused without the plug-in's own key in `X-Api-Key` |
| `GET` and `POST /pack` | Starboard | The **Broadcast pack** page |
| `POST /channels/file`, `/clips/file`, `/pack/file` | Starboard | A logo, ident, clip or pack zip chosen on a page, streamed to its folder |
| `POST /actions/example`, `/actions/promos`, `/actions/refresh`, `/actions/stop` | Starboard | Its four buttons |
| `POST /jobs/refresh` | Starboard | The nightly line-up refresh, at 04:40 |
| `POST /jobs/promos` | Starboard | Promos, each hour of Starboard's quiet hours |
| `POST /update/before`, `/update/after` | Starboard | Stops every stream before an update |
| `GET /` | People | A small page; opening it tells Create your own TV channel its own address |
| `GET /t/<token>/channels.m3u` | Jellyfin | The channel list |
| `GET /t/<token>/guide.xml` | Jellyfin | The guide, 7 days |
| `GET /t/<token>/stream/<channel>.ts` | Jellyfin | A channel's stream, MPEG-TS |
| `GET /t/<token>/logo/<channel>.png`, `/art/<item>.jpg` | Jellyfin | Channel logos, and programme pictures from Jellyfin |
| `GET /t/<token>/preview/<channel>.png` | People | A frame with the on-screen logo, or `?kind=card`, `ident`, `sting` or `promo` |
| `GET /t/<token>/grid` and `POST /t/<token>/grid/api/op` | People | The schedule grid's page, and each change to it (JSON only) |
| `GET` and `POST /schedule` | Starboard | The **Schedule grid** page: a link to each channel's grid |
| `GET /t/<token>/download/<file>` | People | `template.zip`, `placement-coming-next.png`, `placement-promo.png`, `placement-logo.png` and `example-pack.zip`, as downloads |

`<token>` is a random word kept in its folder, given only to Jellyfin.

## Tests

`python3 -m unittest tests.test_tv_station tests.test_tv_station_pack tests.test_tv_station_grid`

The tests cover these parts.

- **The schedule:** the same answer for the same time, joining part way, boundaries, breaks filling the gap, and new episodes joining at the next boundary.
- **Other checks:** the guide and channel list, the on-screen logo options and the pages.
- **A real FFmpeg run,** where FFmpeg is installed. It tunes in part way through a made-up clip and checks the logo is drawn. Then two viewers share one stream that stops after they leave.
- **Packs:** `pack.json` against its schema. The zip rules (paths outside the folder, links, unknown names, zip bombs, size limits). The example pack made small and checked, and broken copies of it refused. A card drawn from it, the random ident choice, and the logo with music. Both halves of a transition at each cut, and which promos are made and replaced. A real promo made by FFmpeg and stopped when someone watches. Promos on the other channels, the placement guides' marks and the template.
- **The grid:** the store, every change and its alternative to dragging, copy a day, stripe, and where a series starts. Also the guide following the grid, the suggester with made-up history, and the page's answers.

## Find out more

- [Plug-in API](../../developers/plug-in-api.md)
- [App plug-ins](../../developers/app-plug-ins.md)
