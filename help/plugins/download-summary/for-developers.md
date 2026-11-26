# Download summary: For developers

How Download summary is built, for anyone who wants to change it or make one like it. It is MIT, by TheMightyTRexUK, and works with plug-in API `>=1.14 <2.0`.

## Its files

- [`starboard-plugin.json`](../../../download-summary/starboard-plugin.json)
- [`app.py`](../../../download-summary/app.py)
- [`sbplugin.py`](../../../download-summary/sbplugin.py)
- [`Dockerfile`](../../../download-summary/Dockerfile)
- [`install.py`](../../../download-summary/install.py)
- [`logo.svg`](../../../download-summary/logo.svg)
- [`CHANGELOG.md`](../../../download-summary/CHANGELOG.md)

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
| `GET /card` | The Downloaded today card (stat) |

## How it works

- Every 60 seconds, in a background job, it asks Starboard's API for `downloads` with its own key.
- For each item (keyed by its client and id) it works out how much is done from its size and progress. It adds the growth since the last reading to today's total.
- It keeps the last reading in `/data/seen.json` and the last 14 days' totals in `/data/days.json`.
- `GET /card` answers a stat card: `value` is today's total in bytes, and `note` is the week's total, or the last error from the background job. The status is `ok`, or `problem` while there is an error, set with `band()` from `sbplugin.py`.
- It declares no update steps, so Starboard stops it, updates it and starts it again.

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
