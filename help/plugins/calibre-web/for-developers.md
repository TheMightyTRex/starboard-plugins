# Calibre-Web: For developers

How Calibre-Web is built, for anyone who wants to change it or make one like it. It is MIT, by TheMightyTRexUK, and works with plug-in API `>=1.14 <2.0`.

## Its files

- [`starboard-plugin.json`](../../../calibre-web/starboard-plugin.json)
- [`install.py`](../../../calibre-web/install.py)
- [`logo.svg`](../../../calibre-web/logo.svg)

## Containers

| Container | Network | Folders | Runs as | Starts | Limits |
|---|---|---|---|---|---|
| `app` | `lan` | `data:/config`, `media/books:ro` | `10001:10001` | `always` | 384 MB, 0.5 core, 128 processes |

Each image is pinned by digest in the manifest:

- `app`: `lscr.io/linuxserver/calibre-web@sha256:8eabbc9ac4d7fcbc252434493078ba22e4e8c3aa461e11b102020b040c5fc3e6`

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api-1-14.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
