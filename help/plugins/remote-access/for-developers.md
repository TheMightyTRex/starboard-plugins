# Remote access: For developers

How Remote access is built, for anyone who wants to change it or make one like it. It is MIT, by TheMightyTRexUK, and works with plug-in API `>=1.14 <2.0`.

## Its files

- [`starboard-plugin.json`](../../../remote-access/starboard-plugin.json)
- [`app.py`](../../../remote-access/app.py)
- [`sbplugin.py`](../../../remote-access/sbplugin.py)
- [`Dockerfile`](../../../remote-access/Dockerfile)
- [`install.py`](../../../remote-access/install.py)
- [`logo.svg`](../../../remote-access/logo.svg)

## Containers

| Container | Network | Folders | Runs as | Starts | Limits |
|---|---|---|---|---|---|
| `main` | `lan` | `data` | `10001:10001` | `always` | 128 MB, 0.5 core |

Each image is pinned by digest in the manifest:

- `main`: `ghcr.io/themightytrex/starboard-plugin-remote-access@sha256:ef50260e2ded8917b42c216efe97f20eab495845f3192f496513a9bf1e0373d1`

## What Starboard calls

| Path | What it is |
|---|---|
| `GET /health` | Health: 200 while it can work |
| `GET /card` | The Away from home card (status) |
| `POST /test` | The Test remote access button |
| `POST /restart` | The Start remote access again button |
| `GET /screen` | The Addresses away from home page |

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api-1-14.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
