# Audio description: For developers

How Audio description is built, for anyone who wants to change it or make one like it. It is MIT, by TheMightyTRexUK, and works with plug-in API `>=1.14 <2.0`.

## Its files

- [`starboard-plugin.json`](../../../audio-description/starboard-plugin.json)
- [`app.py`](../../../audio-description/app.py)
- [`sbplugin.py`](../../../audio-description/sbplugin.py)
- [`Dockerfile`](../../../audio-description/Dockerfile)
- [`install.py`](../../../audio-description/install.py)
- [`logo.svg`](../../../audio-description/logo.svg)
- [`CHANGELOG.md`](../../../audio-description/CHANGELOG.md)
- [`tests/test_audio_description.py`](../../../tests/test_audio_description.py)
- [`tests/test_audio_description_tracks.py`](../../../tests/test_audio_description_tracks.py)

## Containers

| Container | Network | Folders | Runs as | Starts | Limits |
|---|---|---|---|---|---|
| `main` | `lan` | `data` | `10001:10001` | `when_needed` | 64 MB, 0.25 core |

Each image is pinned by digest in the manifest:

- `main`: `ghcr.io/themightytrex/starboard-plugin-examples@sha256:83b980f1828cdee537bcdf03702ddf6458710cba53f9009938225df430d34d9e`

## What Starboard calls

| Path | What it is |
|---|---|
| `GET /health` | Health: 200 while it can work |
| `GET /count` | The Audio description card (stat) |
| `GET /recent` | The Recently found with audio description card (list) |
| `POST /scan` | The Look for described titles now button |
| `POST /reelix` | The Apply the Reelix choice now button |
| `GET /people` | The People who want audio description page |
| `GET /titles` | The Titles with audio description page |
| `GET /elsewhere` | The Audio description elsewhere page |
| `GET /audiovault` | The Search AudioVault page |
| `GET /youdescribe` | The Search YouDescribe page |
| `GET /apps` | The MovieReading and Earcatch page |
| `POST /jobs/scan` | The job Look for titles with audio description |
| `POST /jobs/reelix` | The job Keep the audio description choice in Reelix |
| `POST /update/before` | The update's before step, 60 seconds at most |
| `POST /update/after` | The update's after step, 10 seconds at most |

## Jobs

- `scan`: daily at 04:20, only in quiet hours, 20 minutes at most.
- `reelix`: when Starboard starts, 2 minutes at most.

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api-1-14.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
