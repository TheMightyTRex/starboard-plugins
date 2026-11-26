# Watching now: For developers

How Watching now is built, for anyone who wants to change it or make one like it. It is MIT, by TheMightyTRexUK, and works with plug-in API `>=1.14 <2.0`.

## Its files

- [`starboard-plugin.json`](../../../watching-now/starboard-plugin.json)
- [`app.py`](../../../watching-now/app.py)
- [`sbplugin.py`](../../../watching-now/sbplugin.py)
- [`Dockerfile`](../../../watching-now/Dockerfile)
- [`install.py`](../../../watching-now/install.py)
- [`logo.svg`](../../../watching-now/logo.svg)
- [`CHANGELOG.md`](../../../watching-now/CHANGELOG.md)

## Containers

| Container | Network | Folders | Runs as | Starts | Limits |
|---|---|---|---|---|---|
| `main` | `lan` | None | `10001:10001` | `always` | 48 MB, 0.1 core |

Each image is pinned by digest in the manifest:

- `main`: `ghcr.io/themightytrex/starboard-plugin-examples@sha256:83b980f1828cdee537bcdf03702ddf6458710cba53f9009938225df430d34d9e`

## What Starboard calls

| Path | What it is |
|---|---|
| `GET /health` | Health: 200 while it can work |
| `GET /card` | The Watching now card (list) |

## How it works

- Each time the card is asked, `app.py` asks Jellyfin for `/Sessions?ActiveWithinSeconds=120` through `jellyfin()` in `sbplugin.py`, and lists each session that has something playing. It keeps nothing, so it needs no folder.
- The card's status comes from `band()`: `running` with how many are watching, or `idle` when nobody is.
- Without a Jellyfin key, `jellyfin()` raises "Starboard has no Jellyfin key to give yet: add Jellyfin in Settings, Apps". The card answers 502 with that message.

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
