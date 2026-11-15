# Maintainerr: For developers

How Maintainerr is built, for anyone who wants to change it or make one like it. It is MIT, by TheMightyTRexUK, and works with plug-in API `>=1.14 <2.0`.

## Its files

- [`starboard-plugin.json`](../../../maintainerr/starboard-plugin.json)
- [`install.py`](../../../maintainerr/install.py)
- [`logo.svg`](../../../maintainerr/logo.svg)

## Containers

| Container | Network | Folders | Runs as | Starts | Limits |
|---|---|---|---|---|---|
| `app` | `lan` | `data:/opt/data` | `1000:1000` | `always` | 384 MB, 0.5 core, 128 processes |

Each image is pinned by digest in the manifest:

- `app`: `ghcr.io/maintainerr/maintainerr@sha256:5dcd5bef9d49c614bb74453df3da198afc05a38d8e2cd96b3669bc2c76a94112`

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api-1-14.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
