# Uptime Kuma: For developers

How Uptime Kuma is built, for anyone who wants to change it or make one like it. It is MIT, by TheMightyTRexUK, and works with plug-in API `>=1.14 <2.0`.

## Its files

- [`starboard-plugin.json`](../../../uptime-kuma/starboard-plugin.json)
- [`install.py`](../../../uptime-kuma/install.py)
- [`logo.svg`](../../../uptime-kuma/logo.svg)

## Containers

| Container | Network | Folders | Runs as | Starts | Limits |
|---|---|---|---|---|---|
| `app` | `lan` | `data:/app/data` | `1000:1000` | `always` | 384 MB, 0.5 core, 128 processes |

Each image is pinned by digest in the manifest:

- `app`: `docker.io/louislam/uptime-kuma@sha256:d213a1d2b6a7d7c00afbcb936b53f585afea3e1620432b3a161b68bfffa13dac`

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api-1-14.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
