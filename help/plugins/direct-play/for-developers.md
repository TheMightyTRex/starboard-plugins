# Direct play: For developers

How Direct play is built, for anyone who wants to change it or make one like it. It is MIT, by TheMightyTRexUK, and works with plug-in API `>=1.14 <2.0`.

## Its files

- [`starboard-plugin.json`](../../../direct-play/starboard-plugin.json)
- [`app.py`](../../../direct-play/app.py)
- [`sbplugin.py`](../../../direct-play/sbplugin.py)
- [`Dockerfile`](../../../direct-play/Dockerfile)
- [`install.py`](../../../direct-play/install.py)
- [`logo.svg`](../../../direct-play/logo.svg)
- [`HELP.md`](../../../direct-play/HELP.md)
- [`CHANGELOG.md`](../../../direct-play/CHANGELOG.md)
- [`tests/test_direct_play.py`](../../../tests/test_direct_play.py)

## Containers

| Container | Network | Folders | Runs as | Starts | Limits |
|---|---|---|---|---|---|
| `main` | `lan` | `data`, `media/movies`, `media/tv` | `media` | `always` | 512 MB, 1 core |

Each image is pinned by digest in the manifest:

- `main`: `ghcr.io/themightytrex/starboard-plugin-direct-play@sha256:5f98e9a8583c7cfaf909f939047777adccc235792ed67b9c7961bc33ca418830`

## What Starboard calls

| Path | What it is |
|---|---|
| `GET /health` | Health: 200 while it can work |
| `GET /card` | The Direct play card (list) |
| `GET /summary` | The Space saved by Direct play card (stat) |
| `POST /pause` | The Pause fixing button |
| `POST /resume` | The Resume fixing button |
| `POST /survey` | The Look at the library now button |
| `GET /files` | The Files page |
| `POST /jobs/quiet` | The job Direct play in quiet hours |
| `POST /update/before` | The update's before step, 60 seconds at most |
| `POST /update/after` | The update's after step, 10 seconds at most |

## Jobs

- `quiet`: every 1 hour, only in quiet hours, 1 minutes at most.

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api-1-14.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
