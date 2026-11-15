# VPN check: For developers

How VPN check is built, for anyone who wants to change it or make one like it. It is MIT, by TheMightyTRexUK, and works with plug-in API `>=1.14 <2.0`.

## Its files

- [`starboard-plugin.json`](../../../vpn-check/starboard-plugin.json)
- [`app.py`](../../../vpn-check/app.py)
- [`sbplugin.py`](../../../vpn-check/sbplugin.py)
- [`Dockerfile`](../../../vpn-check/Dockerfile)
- [`install.py`](../../../vpn-check/install.py)
- [`logo.svg`](../../../vpn-check/logo.svg)
- [`CHANGELOG.md`](../../../vpn-check/CHANGELOG.md)

## Containers

| Container | Network | Folders | Runs as | Starts | Limits |
|---|---|---|---|---|---|
| `main` | `vpn` | `data` | `10001:10001` | `always` | 48 MB, 0.1 core |

Each image is pinned by digest in the manifest:

- `main`: `ghcr.io/themightytrex/starboard-plugin-examples@sha256:83b980f1828cdee537bcdf03702ddf6458710cba53f9009938225df430d34d9e`

## What Starboard calls

| Path | What it is |
|---|---|
| `GET /health` | Health: 200 while it can work |
| `GET /card` | The VPN card (status) |
| `POST /check` | The Check now button |

## How it works

- It runs inside the `gluetun` container's network (`"network": "vpn"`), on port 7791.
- A background job asks `https://ipinfo.io/json` every **Check every** minutes, read once when it starts, and keeps the address, country, city, how long it took and when in `/data/last.json`.
- `POST /check` (the **Check now** button) does the same at once and answers with what it found.
- `GET /card` compares the address with **Your home's public address**, read at each refresh. The status is `protected`, `warning` when the last check that worked is older than 3 times **Check every**, or `problem` when the home address shows, set with `band()` from `sbplugin.py`. Before its first check it is `waiting`, or `problem` with the last error.
- It declares no update steps, so Starboard stops it, updates it and starts it again.

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
