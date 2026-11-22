# Backups watch: For developers

How Backups watch is built, for anyone who wants to change it or make one like it. It is MIT, by TheMightyTRexUK, and works with plug-in API `>=1.17 <2.0`.

## Its files

- [`starboard-plugin.json`](../../../backups-watch/starboard-plugin.json)
- [`app.py`](../../../backups-watch/app.py)
- [`sbplugin.py`](../../../backups-watch/sbplugin.py)
- [`Dockerfile`](../../../backups-watch/Dockerfile)
- [`install.py`](../../../backups-watch/install.py)
- [`logo.svg`](../../../backups-watch/logo.svg)
- [`CHANGELOG.md`](../../../backups-watch/CHANGELOG.md)
- [`tests/test_backups_watch.py`](../../../tests/test_backups_watch.py)

## Containers

| Container | Network | Folders | Runs as | Starts | Limits |
|---|---|---|---|---|---|
| `main` | `lan` | `data` | `10001:10001` | `when_needed` | 48 MB, 0.1 core |

The image is the shared examples image. Until it is built and pinned by digest, the manifest names its next tag.

## What Starboard calls

| Path | What it is |
|---|---|
| `GET /health` | Health: 200 while it can work |
| `GET /card` | The Backups card (status) |
| `GET /runs` | The Backup runs card (list) |
| `GET /sizes` | The Backup sizes card (sparkline) |
| `POST /check` | The Check now button |
| `POST /jobs/check` | The job Check the backups, every hour, 2 minutes at most |
| `POST /update/before` | The update's before step, 60 seconds at most |
| `POST /update/after` | The update's after step, 10 seconds at most |

## How it works

- The job asks the tool once and keeps the answer in `/data/state.json`. The three cards read only that file, so a card never wakes the backup tool.
- **Backrest:** `POST <address>/v1.Backrest/GetSummaryDashboard` with a JSON body of `{}` and the header `Connect-Protocol-Version: 1`. Each entry of `planSummaries` is one backup: `recentBackups` (times, statuses and bytes added in step), `backupsFailed30days`, `protectedBytes`. 64 bit numbers may arrive as text.
- **Kopia:** `GET <address>/api/v1/control/sources` with HTTP Basic sign-in. Each entry of `sources` is one backup: `lastSnapshot` with `endTime`, `stats.totalSize`, `stats.errorCount` and `incomplete`.
- Neither was tried against the real program. The tests use recorded sample answers built from each tool's published API (Backrest's `service.proto`, Kopia's `serverapi.go`). Duplicati's server API could not be checked from its documentation, so it is not offered.
- **Alerts:** `POST /api/v1/plugin/alerts` with the permission `alerts:send`, once as `raised` and once as `cleared` for each key (`overdue:<backup>`, `failed:<backup>`). What was raised is kept in `/data/raised.json`, so a restart sends nothing twice. A Starboard that answers 404 is not asked again for an hour.
- The password is read from the settings each time and is never written to `/data`, a card or an error.
- It starts when needed and stops after 5 minutes with nothing to do.

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
