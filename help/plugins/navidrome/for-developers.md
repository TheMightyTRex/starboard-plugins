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

## How it works

- Navidrome is an app plug-in: it runs Navidrome's own image, pinned by digest, with no code of its own and no dashboard card.
- Its page is published on your home network (`network:port`). Starboard chooses the port, 4533 when it is free.
- `ND_DATAFOLDER` is `/data`, its own folder, and `ND_MUSICFOLDER` is `/media/music`, mounted read only.
- It has no health check and no update steps: Starboard waits for its container to start after an update.
- It uses about 20 MiB at rest, measured with `tools/app_check.py` on 13 November 2026, with an empty library.

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
