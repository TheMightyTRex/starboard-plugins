# Audio description: For developers

How Audio description is built, for anyone who wants to change it or make one like it. It is MIT, by TheMightyTRexUK, and works with plug-in API `>=1.14 <2.0`.

## Its files

- [`starboard-plugin.json`](../../../audio-description/starboard-plugin.json)
- [`app.py`](../../../audio-description/app.py)
- [`sbplugin.py`](../../../audio-description/sbplugin.py)
- [`Dockerfile`](../../../audio-description/Dockerfile)
- [`install.py`](../../../audio-description/install.py)
- [`logo.svg`](../../../audio-description/logo.svg)
- [`rules.json`](../../../audio-description/rules.json), shared with the Jellyfin version and copied by `tools/sync_audio_description_rules.py`
- [`CHANGELOG.md`](../../../audio-description/CHANGELOG.md)
- [`tests/test_audio_description.py`](../../../tests/test_audio_description.py)

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
| `POST /scan` | The Check for described titles now button |
| `POST /reelix` | The Check the Reelix choice now button |
| `GET /people` | The People who want audio description page |
| `GET /titles` | The Titles with audio description page |
| `GET /elsewhere` | The Audio description elsewhere page |
| `GET /audiovault` | The Search AudioVault page |
| `GET /youdescribe` | The Search YouDescribe page |
| `GET /apps` | The MovieReading and Earcatch page |
| `GET /play` | The Play the described track page |
| `POST /events` | Starboard's `playback.started` event |
| `POST /jobs/scan` | The job Check for titles with audio description |
| `POST /jobs/reelix` | The job Check the audio description choice in Reelix |
| `POST /update/before` | The update's before step, 60 seconds at most |
| `POST /update/after` | The update's after step, 10 seconds at most |

## Jobs

- `scan`: daily at 04:20, only in quiet hours, 20 minutes at most.
- `reelix`: when Starboard starts, 2 minutes at most.

## How it works

- The container rests when idle (`start: when_needed`, resting after 10 minutes). Starboard wakes it for its jobs, its buttons and its pages. Nothing runs on a timer of its own.
- `scan` reads every film and episode from Jellyfin's `/Items`, 200 at a time with their streams only. Then it reads every series once with its tags and year. So memory stays flat whatever the library's size. A track counts when its title, display title or comment names audio description and does not mention commentary.
- It keeps three files.
  - `/data/result.json` holds the described titles, and is the only file **Titles with audio description** reads. For each film it keeps the Jellyfin id, name, year, track and when it was added (DateCreated). For each series it keeps the id, year, counts and described episodes with their numbers and tracks.
  - `/data/seen.json` holds when each title was first found, for the Recently found card.
  - `/data/without.json` holds titles without a described track, for the Sources' links.
- `reelix` only reads Reelix, with the manager key Starboard gives (issue #144). It uses `GET /customformats/builtin/audio_description`, or on an older Reelix `GET /customformats` by name, and `GET /qualityprofiles`. It counts the video levels that give the format a score of more than 0. It never posts a format or puts a quality level, because Reelix allows that only with an admin key. It never fails the job. It answers with what to do.
- For each person turned on, it sets Jellyfin's **RememberAudioSelections** and keeps what they had in `/data/people.json`, to put back when they are off. It tries Jellyfin 10.9's `/Users/Configuration` first, then 10.8's address.
- After reading the library, `scan` tags only the items whose tag changes. It uses `POST /Items/{id}` with the whole item, read with `GET /Items/{id}`, as Jellyfin's metadata editor saves it. It keeps the collection with `/Collections`. It skips both when Jellyfin's `/Plugins` lists the Jellyfin version (`7a591954-9c27-4ba7-80c3-dc5f0a140692`), asked at most every 10 minutes.
- On `playback.started`, it reads `/Sessions`. A session qualifies when a chosen person plays a title whose described track is not playing, and the app lists `SetAudioStreamIndex` in its supported commands. For each such session, it sends `POST /Sessions/{id}/Command` with that command and the track's `Index`. Each start is handled once.
- **Check for described titles now** runs the scan in the background, because a button must answer in 10 seconds.
- Cards set their status with `band()` from `sbplugin.py`. Its before update step holds new runs and waits for one that is running.

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
