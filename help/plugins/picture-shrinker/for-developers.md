# Picture shrinker: For developers

How Picture shrinker is built, for anyone who wants to change it or make one like it. It is MIT, by TheMightyTRexUK, and works with plug-in API `>=1.14 <2.0`.

## Its files

- [`starboard-plugin.json`](../../../picture-shrinker/starboard-plugin.json)
- [`app.py`](../../../picture-shrinker/app.py)
- [`sbplugin.py`](../../../picture-shrinker/sbplugin.py)
- [`Dockerfile`](../../../picture-shrinker/Dockerfile)
- [`install.py`](../../../picture-shrinker/install.py)
- [`logo.svg`](../../../picture-shrinker/logo.svg)
- [`HELP.md`](../../../picture-shrinker/HELP.md)
- [`CHANGELOG.md`](../../../picture-shrinker/CHANGELOG.md)
- [`tests/test_picture_shrinker.py`](../../../tests/test_picture_shrinker.py)

## Containers

| Container | Network | Folders | Runs as | Starts | Limits |
|---|---|---|---|---|---|
| `main` | `default` | `data`, `jellyfin-metadata` | `media` | `always` | 128 MB, 0.5 core |

Each image is pinned by digest in the manifest:

- `main`: `ghcr.io/themightytrex/starboard-plugin-picture-shrinker@sha256:aa8c586d5766acd23fe9bacb6ca68d236387b2949881fc9c6417bf5e261a3cad`

## What Starboard calls

| Path | What it is |
|---|---|
| `GET /health` | Health: 200 while it can work |
| `GET /card` | The Space saved card (stat) |
| `POST /shrink-now` | The Shrink now button |
| `POST /stop` | The Stop shrinking button |
| `GET /saved` | The Space saved page |
| `POST /jobs/shrink` | The job Shrink pictures |
| `POST /jobs/new` | The job Shrink new pictures in quiet hours |
| `POST /update/before` | The update's before step, 60 seconds at most |
| `POST /update/after` | The update's after step, 10 seconds at most |

## Jobs

- `shrink`: on the schedule in its `when` setting, 120 minutes at most.
- `new`: every 1 hour, only in quiet hours, 30 minutes at most.

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api-1-14.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
