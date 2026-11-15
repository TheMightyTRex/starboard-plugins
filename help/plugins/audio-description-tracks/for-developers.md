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
| `POST /inbox` | A choice on that page: the film or episode, or whether it plays in step |
| `POST /inbox/file` | A file uploaded on that page, streamed to it |
| `POST /jobs/look` | The job Look for new description tracks |
| `POST /update/before` | The update's before step, 60 seconds at most |
| `POST /update/after` | The update's after step, 10 seconds at most |

## Jobs

- `look`: daily at 04:40, only in quiet hours, 30 minutes at most.

## How it works

- Its own image adds mkvmerge, from MKVToolNix, chosen over ffmpeg because the image is 146 MB rather than 261 MB. The container rests when idle (`start: when_needed`) and runs as `media`, the owner of the media folder.
- It mounts the movies, tv and audio-description folders of the media folder. A file Jellyfin knows is found by the part of its path after `movies/` or `tv/`, and must really be inside the folder.
- A file name is read as a film and year, or a series with `S01E03` or `1x03`. Jellyfin's search finds the title. When more than one film could match, the person chooses.
- mkvmerge copies the sound, without converting it, into a Matroska file in the folder first, then measures it. Only a copy within **How close the lengths must be** goes next to the film, under a hidden name until it is whole. Then it asks Jellyfin to refresh that title.
- Uploads come as a `FILE` route (`POST /inbox/file`), streamed a piece at a time, up to 60 MB.
- It keeps each file's record in `/data/files.json`, and the newest 50 confirmed stay listed.
- The card sets its status with `band()` from `sbplugin.py`. Its before update step lets the track it is on finish and starts no other.

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
