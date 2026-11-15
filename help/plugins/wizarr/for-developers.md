# Wizarr: For developers

How Wizarr is built, for anyone who wants to change it or make one like it. It is MIT, by TheMightyTRexUK, and works with plug-in API `>=1.14 <2.0`.

## Its files

- [`starboard-plugin.json`](../../../wizarr/starboard-plugin.json)
- [`install.py`](../../../wizarr/install.py)
- [`logo.svg`](../../../wizarr/logo.svg)

## Containers

| Container | Network | Folders | Runs as | Starts | Limits |
|---|---|---|---|---|---|
| `app` | `lan` | `data` | `10001:10001` | `always` | 384 MB, 0.5 core, 128 processes |

Each image is pinned by digest in the manifest:

- `app`: `ghcr.io/wizarrrr/wizarr@sha256:08f2c6de534ec7d36d39a4f55b7c5c379021ca881dc519c702aad0ddafbdc67a`

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api-1-14.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
