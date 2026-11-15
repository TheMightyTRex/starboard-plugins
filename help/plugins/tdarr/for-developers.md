# Tdarr: For developers

How Tdarr is built, for anyone who wants to change it or make one like it. It is MIT, by TheMightyTRexUK, and works with plug-in API `>=1.14 <2.0`.

## Its files

- [`starboard-plugin.json`](../../../tdarr/starboard-plugin.json)
- [`install.py`](../../../tdarr/install.py)
- [`logo.svg`](../../../tdarr/logo.svg)

## Containers

| Container | Network | Folders | Runs as | Starts | Limits |
|---|---|---|---|---|---|
| `server` | `lan` | `data/server:/app/server`, `data/configs:/app/configs`, `data/logs:/app/logs`, `data/cache:/temp`, `data/node-plugins:/app/Tdarr_Node/assets/app/plugins`, `media/tdarr-cache`, `media/movies`, `media/tv` | `media` | `always` | 2048 MB, 2 core, 512 processes |

Each image is pinned by digest in the manifest:

- `server`: `ghcr.io/haveagitgat/tdarr@sha256:84743e5ae433a5b49cb463b2dff2679eb02f0cac24fb88c830f49bf8aa9f1c04`

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api-1-14.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
