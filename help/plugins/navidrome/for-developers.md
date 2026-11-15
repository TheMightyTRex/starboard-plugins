# Navidrome: For developers

How Navidrome is built, for anyone who wants to change it or make one like it. It is MIT, by TheMightyTRexUK, and works with plug-in API `>=1.14 <2.0`.

## Its files

- [`starboard-plugin.json`](../../../navidrome/starboard-plugin.json)
- [`install.py`](../../../navidrome/install.py)
- [`logo.svg`](../../../navidrome/logo.svg)

## Containers

| Container | Network | Folders | Runs as | Starts | Limits |
|---|---|---|---|---|---|
| `app` | `lan` | `data`, `media/music:ro` | `10001:10001` | `always` | 256 MB, 0.5 core, 128 processes |

Each image is pinned by digest in the manifest:

- `app`: `docker.io/deluan/navidrome@sha256:38dc2727bfcfd5ede290f8ada114fc90368146f265ae4701ddddbcbe2a44ee52`

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api-1-14.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
