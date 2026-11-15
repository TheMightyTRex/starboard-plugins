# Library health: For developers

How Library health is built, for anyone who wants to change it or make one like it. It is MIT, by TheMightyTRexUK, and works with plug-in API `>=1.14 <2.0`.

## Its files

- [`starboard-plugin.json`](../../../library-health/starboard-plugin.json)
- [`app.py`](../../../library-health/app.py)
- [`sbplugin.py`](../../../library-health/sbplugin.py)
- [`Dockerfile`](../../../library-health/Dockerfile)
- [`install.py`](../../../library-health/install.py)
- [`logo.svg`](../../../library-health/logo.svg)
- [`CHANGELOG.md`](../../../library-health/CHANGELOG.md)

## Containers

| Container | Network | Folders | Runs as | Starts | Limits |
|---|---|---|---|---|---|
| `main` | `lan` | `data` | `10001:10001` | `always` | 96 MB, 0.25 core |

Each image is pinned by digest in the manifest:

- `main`: `ghcr.io/themightytrex/starboard-plugin-examples@sha256:83b980f1828cdee537bcdf03702ddf6458710cba53f9009938225df430d34d9e`

## What Starboard calls

| Path | What it is |
|---|---|
| `GET /health` | Health: 200 while it can work |
| `GET /count` | The Library health card (stat) |
| `GET /card` | The To fix in Jellyfin card (list) |
| `POST /check` | The Check now button |
| `POST /update/before` | The update's before step, 60 seconds at most |
| `POST /update/after` | The update's after step, 10 seconds at most |

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api-1-14.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
