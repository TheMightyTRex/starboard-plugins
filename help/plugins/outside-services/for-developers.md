# Outside services: For developers

How Outside services is built, for anyone who wants to change it or make one like it. It is MIT, by TheMightyTRexUK, and works with plug-in API `>=1.14 <2.0`.

## Its files

- [`starboard-plugin.json`](../../../outside-services/starboard-plugin.json)
- [`app.py`](../../../outside-services/app.py)
- [`sbplugin.py`](../../../outside-services/sbplugin.py)
- [`Dockerfile`](../../../outside-services/Dockerfile)
- [`install.py`](../../../outside-services/install.py)
- [`logo.svg`](../../../outside-services/logo.svg)
- [`CHANGELOG.md`](../../../outside-services/CHANGELOG.md)

## Containers

| Container | Network | Folders | Runs as | Starts | Limits |
|---|---|---|---|---|---|
| `main` | `lan` | `data` | `10001:10001` | `always` | 48 MB, 0.1 core |

Each image is pinned by digest in the manifest:

- `main`: `ghcr.io/themightytrex/starboard-plugin-examples@sha256:83b980f1828cdee537bcdf03702ddf6458710cba53f9009938225df430d34d9e`

## What Starboard calls

| Path | What it is |
|---|---|
| `GET /health` | Health: 200 while it can work |
| `GET /status` | The Outside services card (status) |
| `GET /card` | The Outside services card (list) |

## How it works

- `app.py` uses only Python's standard library and the shared helper `sbplugin.py`.
- A background job (`every()`) checks the first 20 addresses, 2 seconds after it starts and then at **Check every**. The interval is read once, when it starts.
- Each check is a `GET` with an 8 second time limit that reads at most 1 KB. An HTTP answer under 500 counts as up; a server error, a time-out or no connection counts as not answering.
- The results go in `rows.json` in its `data` folder. Both cards answer with `band()`: `ok` or `problem` with when `rows.json` last changed, `waiting` before the first check, and `needs_setup` with no addresses.

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
