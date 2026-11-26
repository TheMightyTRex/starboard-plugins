# Home Assistant: For developers

How Home Assistant is built, for anyone who wants to change it or make one like it. It is MIT, by TheMightyTRexUK, and works with plug-in API `>=1.14 <2.0`.

## Its files

- [`starboard-plugin.json`](../../../home-assistant/starboard-plugin.json)
- [`app.py`](../../../home-assistant/app.py)
- [`sbplugin.py`](../../../home-assistant/sbplugin.py)
- [`Dockerfile`](../../../home-assistant/Dockerfile)
- [`install.py`](../../../home-assistant/install.py)
- [`logo.svg`](../../../home-assistant/logo.svg)
- [`CHANGELOG.md`](../../../home-assistant/CHANGELOG.md)

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
| `GET /card` | The Home card (status) |

## How it works

- `app.py` uses only Python's standard library and the shared helper `sbplugin.py`. It keeps nothing on disk and runs no background job: it asks only when Starboard asks for the card.
- For each of the first 8 entity ids it reads `/api/states/<id>` from Home Assistant's REST API, with the token as a bearer token. It joins each friendly name, state and unit into one sentence.
- The card answers with `band()`. The status is `warning` when any state is in **Warn when any is**, otherwise `ok`, with the time it asked. It is `needs_setup` when the address, token or ids are missing. If any read fails, `/card` answers 502 and Starboard shows "No answer from Home Assistant".

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
