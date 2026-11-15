# Seerr: For developers

How Seerr is built, for anyone who wants to change it or make one like it. It is MIT, by TheMightyTRexUK, and works with plug-in API `>=1.14 <2.0`.

## Its files

- [`starboard-plugin.json`](../../../seerr/starboard-plugin.json)
- [`install.py`](../../../seerr/install.py)
- [`logo.svg`](../../../seerr/logo.svg)

## Containers

| Container | Network | Folders | Runs as | Starts | Limits |
|---|---|---|---|---|---|
| `app` | `lan` | `data:/app/config` | `1000:1000` | `always` | 512 MB, 0.5 core, 128 processes |

Each image is pinned by digest in the manifest:

- `app`: `ghcr.io/seerr-team/seerr@sha256:aadee014b40e28cf9aa4928bc9d1183a6eb08f8c44d543cddc9efdcb16549be2`

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api-1-14.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
