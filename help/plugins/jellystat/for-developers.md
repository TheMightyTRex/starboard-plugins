# Jellystat: For developers

How Jellystat is built, for anyone who wants to change it or make one like it. It is MIT, by TheMightyTRexUK, and works with plug-in API `>=1.14 <2.0`.

## Its files

- [`starboard-plugin.json`](../../../jellystat/starboard-plugin.json)
- [`app.py`](../../../jellystat/app.py)
- [`sbplugin.py`](../../../jellystat/sbplugin.py)
- [`Dockerfile`](../../../jellystat/Dockerfile)
- [`install.py`](../../../jellystat/install.py)
- [`logo.svg`](../../../jellystat/logo.svg)
- [`tests/test_jellystat.py`](../../../tests/test_jellystat.py)

## Containers

| Container | Network | Folders | Runs as | Starts | Limits |
|---|---|---|---|---|---|
| `main` | `default` | `data` | `70:70` | `always` | 64 MB, 0.25 core |
| `app` | `lan` | `data:/app/backend/backup-data` | `10001:10001` | `always` | 320 MB, 0.5 core, 128 processes |
| `db` | `default` | `data` | `70:70` | `always` | 256 MB, 0.5 core, 128 processes |

Each image is pinned by digest in the manifest:

- `main`: `ghcr.io/themightytrex/starboard-plugin-jellystat@sha256:c229ae7259f383b17d03d2a5877eb62b706957d917f4a7e289162169418960fa`
- `app`: `docker.io/cyfershepard/jellystat@sha256:e61c759ec706da378bc8374e797da1dfd298ab30f804cefd82d192c301a888c7`
- `db`: `docker.io/library/postgres@sha256:fc41cfa8a90c09e84dd723ee764be4b2f59ba6c98b1e5b3fca540adddf68a5ba`

## What Starboard calls

| Path | What it is |
|---|---|
| `GET /health` | Health: 200 while it can work |
| `GET /status` | The Jellystat card (status) |
| `POST /restore-now` | The Restore the backup button |
| `GET /restore` | The Restore a Jellystat backup page |
| `POST /update/before` | The update's before step, 60 seconds at most |
| `POST /update/after` | The update's after step, 10 seconds at most |

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api-1-14.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
