# Ad blocking: For developers

How Ad blocking is built, for anyone who wants to change it or make one like it. It is MIT, by TheMightyTRexUK, and works with plug-in API `>=1.14 <2.0`.

## Its files

- [`starboard-plugin.json`](../../../dns-blocking/starboard-plugin.json)
- [`app.py`](../../../dns-blocking/app.py)
- [`sbplugin.py`](../../../dns-blocking/sbplugin.py)
- [`Dockerfile`](../../../dns-blocking/Dockerfile)
- [`install.py`](../../../dns-blocking/install.py)
- [`logo.svg`](../../../dns-blocking/logo.svg)
- [`CHANGELOG.md`](../../../dns-blocking/CHANGELOG.md)

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
| `GET /card` | The Blocked today card (stat) |

## How it works

- `app.py` uses only Python's standard library and the shared helper `sbplugin.py`. It keeps nothing on disk and runs no background job: it asks only when Starboard asks for the card.
- **Pi-hole 6:** it signs in at `/api/auth` with the password, reads `/api/stats/summary` and signs out again with `DELETE /api/auth`, so no session is left open.
- **AdGuard Home:** it reads `/control/stats` with the user name and password (basic sign-in).
- The card answer uses `band()`: `protected` with the time it asked, or `needs_setup` when there is no address. If Pi-hole or AdGuard Home fails, `/card` answers 502 and Starboard shows "No answer from Ad blocking".

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
