# Checkrr: For developers

How Checkrr is built, for anyone who wants to change it or make one like it. It is MIT, by TheMightyTRexUK, and works with plug-in API `>=1.14 <2.0`.

## Its files

- [`starboard-plugin.json`](../../../checkrr/starboard-plugin.json)
- [`helper.py`](../../../checkrr/helper.py), the helper
- [`checkrr.yaml`](../../../checkrr/checkrr.yaml), Checkrr's settings file
- [`install.py`](../../../checkrr/install.py)
- [`logo.svg`](../../../checkrr/logo.svg)
- [`tests/test_app_helpers.py`](../../../tests/test_app_helpers.py) and [`tests/test_app_plugins.py`](../../../tests/test_app_plugins.py)
- [`tools/make_app_helpers.py`](../../../tools/make_app_helpers.py), which copies `helper.py` and `checkrr.yaml` into the manifest

## Containers

| Container | Network | Folders | Runs as | Starts | Limits |
|---|---|---|---|---|---|
| `main` | `default` | `data:/helper` | `10001:10001` | `always` | 64 MB, 0.25 core |
| `app` | `lan` | `data:/etc/checkrr`, `media/movies:ro`, `media/tv:ro` | `10001:10001` | `always` | 512 MB, 1 core, 128 processes |

Each image is pinned by digest in the manifest:

- `main`: `docker.io/library/python@sha256:c5ba3deef00c7758561a0f03c26f44f10589263d40e732b8748e0d1f38f6dd89`, the official Python 3.12 image on Alpine
- `app`: `docker.io/aetaric/checkrr@sha256:c817e081e9397c240e5b13b09363fe26c9f94248489d3b4f0279e67495b1f12e`, Checkrr 3.6.1

## What Starboard calls

| Path | What it is |
|---|---|
| `GET /health` | Health: 200 while the helper runs |
| `GET /card` | The Damaged files card (stat) |
| `GET /bad-files` | The Files that failed the check page |
| `POST /check-now` | The Check now button |

## How it works

- **No image of ours.** The helper, `helper.py`, is Python's standard library only. It is in the manifest's `files` as `app-1.0.0.py`: Starboard writes it once into the helper's own folder before its first start, and `command` runs it in the official Python image. The version in the file name means an update writes the new helper beside the old one.
- **Checkrr's settings** are `checkrr.yaml`, also in `files`, written once into Checkrr's folder, which is mounted at `/etc/checkrr`. Checkrr finds it there by itself, so the image runs as it is, with no command. Its database (`checkrr.db`) and list of bad files (`badfiles.csv`) go in the same folder.
- **Report only.** The settings file names no Radarr, Sonarr or Lidarr. Checkrr's own replacing (`DeleteMovieFiles`, then a search) needs one of them, so it never runs, and with none Checkrr only records a bad file in its database and list. Checkrr has no code that deletes a file itself, and the `movies` and `tv` folders are mounted read only.
- **Not given Reelix.** Reelix answers Radarr's and Sonarr's API, but Checkrr's replacing deletes the file first. Reelix does not answer that delete today, but it is not given the chance: the plug-in asks for no `reelix:key`.
- **The helper** asks Checkrr's `GET /api/stats/current`, `GET /api/files/bad` and `GET /api/schedule` every 5 minutes (every 30 seconds during a check), and **Check now** calls `POST /api/run`.
- **The check:** FFprobe and the file's first bytes, with `ffmpeg-quick` and `ffmpeg-full` off, each Sunday at 03:30 (`cron: "30 3 * * 0"`) in the server's time zone (Starboard passes `TZ`).

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api.md)
- [App plug-ins](../../developers/app-plug-ins.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
