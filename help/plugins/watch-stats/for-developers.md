# Watch statistics: For developers

How Watch statistics is built, for anyone who wants to change it or make one like it. It is MIT, by TheMightyTRexUK, and works with plug-in API `>=1.14 <2.0`.

## Its files

- [`starboard-plugin.json`](../../../watch-stats/starboard-plugin.json)
- [`app.py`](../../../watch-stats/app.py)
- [`sbplugin.py`](../../../watch-stats/sbplugin.py)
- [`Dockerfile`](../../../watch-stats/Dockerfile)
- [`install.py`](../../../watch-stats/install.py)
- [`logo.svg`](../../../watch-stats/logo.svg)
- [`CHANGELOG.md`](../../../watch-stats/CHANGELOG.md)
- [`tests/test_watch_stats.py`](../../../tests/test_watch_stats.py)

## Containers

| Container | Network | Folders | Runs as | Starts | Limits |
|---|---|---|---|---|---|
| `main` | `lan` | `data` | `10001:10001` | `when_needed` | 64 MB, 0.25 core |

Each image is pinned by digest in the manifest:

- `main`: `ghcr.io/themightytrex/starboard-plugin-examples@sha256:83b980f1828cdee537bcdf03702ddf6458710cba53f9009938225df430d34d9e`

## What Starboard calls

| Path | What it is |
|---|---|
| `GET /health` | Health: 200 while it can work |
| `GET /card/week` | The Plays this week card (stat) |
| `GET /card/top` | The Top titles card (list) |
| `GET /card/people` | The Who watched most card (list) |
| `GET /card/source` | The Watch statistics source card (status) |
| `POST /refresh` | The Read the figures again now button |
| `GET /screen/plays` | The Recent plays page |
| `GET /screen/titles` | The Top titles page |
| `GET /screen/people` | The People page |
| `POST /update/before` | The update's before step, 60 seconds at most |
| `POST /update/after` | The update's after step, 10 seconds at most |

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api-1-14.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
