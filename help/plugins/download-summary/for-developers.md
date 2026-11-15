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

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api-1-14.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
