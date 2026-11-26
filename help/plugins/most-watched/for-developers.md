# Most watched: For developers

How Most watched is built, for anyone who wants to change it or make one like it. It is MIT, by TheMightyTRexUK, and works with plug-in API `>=1.14 <2.0`.

## Its files

- [`starboard-plugin.json`](../../../most-watched/starboard-plugin.json)
- [`app.py`](../../../most-watched/app.py)
- [`sbplugin.py`](../../../most-watched/sbplugin.py)
- [`Dockerfile`](../../../most-watched/Dockerfile)
- [`install.py`](../../../most-watched/install.py)
- [`logo.svg`](../../../most-watched/logo.svg)
- [`CHANGELOG.md`](../../../most-watched/CHANGELOG.md)

## Containers

| Container | Network | Folders | Runs as | Starts | Limits |
|---|---|---|---|---|---|
| `main` | `lan` | `data` | `10001:10001` | `always` | 64 MB, 0.1 core |

Each image is pinned by digest in the manifest:

- `main`: `ghcr.io/themightytrex/starboard-plugin-examples@sha256:83b980f1828cdee537bcdf03702ddf6458710cba53f9009938225df430d34d9e`

## What Starboard calls

| Path | What it is |
|---|---|
| `GET /health` | Health: 200 while it can work |
| `GET /card` | The Most watched card (list) |
| `POST /update/before` | The update's before step, 60 seconds at most |
| `POST /update/after` | The update's after step, 10 seconds at most |

## How it works

- `app.py` counts once an hour with `every()` from `sbplugin.py`, starting 5 seconds after it starts. For each Jellyfin user it asks for up to 200 films and episodes marked as played, newest first. It keeps those played within **Over the last** (`days`).
- Titles are ranked by how many people watched them, then by plays. The top 10 are kept in `/data/top.json`, and the card reads that file, so the card never waits on Jellyfin.
- `band()` sets the card's status. It is `ok` with a list, `idle` with no list and no error, and `problem` with no list and the last error from `last_error()`.

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
