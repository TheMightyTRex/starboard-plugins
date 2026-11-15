# Audio description tracks: For developers

How Audio description tracks is built, for anyone who wants to change it or make one like it. It is MIT, by TheMightyTRexUK, and works with plug-in API `>=1.14 <2.0`.

## Its files

- [`starboard-plugin.json`](../../../audio-description-tracks/starboard-plugin.json)
- [`app.py`](../../../audio-description-tracks/app.py)
- [`sbplugin.py`](../../../audio-description-tracks/sbplugin.py)
- [`Dockerfile`](../../../audio-description-tracks/Dockerfile)
- [`install.py`](../../../audio-description-tracks/install.py)
- [`logo.svg`](../../../audio-description-tracks/logo.svg)
- [`CHANGELOG.md`](../../../audio-description-tracks/CHANGELOG.md)
- [`tests/test_audio_description_tracks.py`](../../../tests/test_audio_description_tracks.py)

## Containers

| Container | Network | Folders | Runs as | Starts | Limits |
|---|---|---|---|---|---|
| `main` | `lan` | `data`, `media/movies`, `media/tv`, `media/audio-description` | `media` | `when_needed` | 96 MB, 0.5 core |

Each image is pinned by digest in the manifest:

- `main`: `ghcr.io/themightytrex/starboard-plugin-audio-description-tracks@sha256:8325ae1902e619e97f78818dd9872ecdc982fde9208dd8e205b2f53769cbc168`

## What Starboard calls

| Path | What it is |
|---|---|
| `GET /health` | Health: 200 while it can work |
| `GET /count` | The Description tracks to check card (stat) |
| `POST /look` | The Look in the folder now button |
| `GET /inbox` | The Description tracks to add page |
| `POST /jobs/look` | The job Look for new description tracks |
| `POST /update/before` | The update's before step, 60 seconds at most |
| `POST /update/after` | The update's after step, 10 seconds at most |

## Jobs

- `look`: daily at 04:40, only in quiet hours, 30 minutes at most.

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api-1-14.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
