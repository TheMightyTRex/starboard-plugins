# Disk forecast: For developers

How Disk forecast is built, for anyone who wants to change it or make one like it. It is MIT, by TheMightyTRexUK, and works with plug-in API `>=1.14 <2.0`.

## Its files

- [`starboard-plugin.json`](../../../disk-forecast/starboard-plugin.json)
- [`app.py`](../../../disk-forecast/app.py)
- [`sbplugin.py`](../../../disk-forecast/sbplugin.py)
- [`Dockerfile`](../../../disk-forecast/Dockerfile)
- [`install.py`](../../../disk-forecast/install.py)
- [`logo.svg`](../../../disk-forecast/logo.svg)
- [`CHANGELOG.md`](../../../disk-forecast/CHANGELOG.md)

## Containers

| Container | Network | Folders | Runs as | Starts | Limits |
|---|---|---|---|---|---|
| `main` | `default` | `data` | `10001:10001` | `always` | 48 MB, 0.1 core |

Each image is pinned by digest in the manifest:

- `main`: `ghcr.io/themightytrex/starboard-plugin-examples@sha256:83b980f1828cdee537bcdf03702ddf6458710cba53f9009938225df430d34d9e`

## What Starboard calls

| Path | What it is |
|---|---|
| `GET /health` | Health: 200 while it can work |
| `GET /card` | The Disk forecast card (status) |

## How it works

- Once an hour, in a background job, it asks Starboard's API for `system` with its own key and reads each disk's label (or mount or name), used and total.
- It keeps one reading a day for each disk, the last 35 days, in `/data/history.json`.
- `GET /card` compares the newest reading with the oldest for each disk. The status is `problem` under 14 days, `warning` under 60 days and `ok` otherwise, set with `band()` from `sbplugin.py`, with `updated` as when `history.json` last changed.
- Before it has any reading, the card is `waiting` with the label "Measuring", or `problem` with the last error from the background job.
- It declares no update steps, so Starboard stops it, updates it and starts it again.

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
