# Notifications: For developers

How Notifications is built, for anyone who wants to change it or make one like it. It is MIT, by TheMightyTRexUK, and works with plug-in API `>=1.14 <2.0`.

## Its files

- [`starboard-plugin.json`](../../../notifications/starboard-plugin.json)
- [`app.py`](../../../notifications/app.py)
- [`sbplugin.py`](../../../notifications/sbplugin.py)
- [`Dockerfile`](../../../notifications/Dockerfile)
- [`install.py`](../../../notifications/install.py)
- [`logo.svg`](../../../notifications/logo.svg)
- [`CHANGELOG.md`](../../../notifications/CHANGELOG.md)
- [`tests/test_notifications.py`](../../../tests/test_notifications.py)

## Containers

| Container | Network | Folders | Runs as | Starts | Limits |
|---|---|---|---|---|---|
| `main` | `lan` | `data` | `10001:10001` | `when_needed` | 48 MB, 0.1 core |

Each image is pinned by digest in the manifest:

- `main`: `ghcr.io/themightytrex/starboard-plugin-examples@sha256:83b980f1828cdee537bcdf03702ddf6458710cba53f9009938225df430d34d9e`

## What Starboard calls

| Path | What it is |
|---|---|
| `GET /health` | Health: 200 while it can work |
| `GET /card` | The Notifications card (status) |
| `GET /recent` | The Notifications sent card (list) |
| `POST /test/email` | The Send a test email button |
| `POST /test/telegram` | The Send a test to Telegram button |
| `POST /test/discord` | The Send a test to Discord button |
| `POST /test/signal` | The Send a test by Signal button |
| `POST /test/pushover` | The Send a test by Pushover button |
| `POST /test/ntfy` | The Send a test by ntfy button |
| `POST /test/webhook` | The Send a test to the webhooks button |
| `POST /weekly-now` | The Send New this week now button |
| `POST /jobs/weekly` | The job Send New this week, at the day and hour in When to send New this week |
| `POST /events` | Events: `request.available`, `download.failed`, `app.down`, `app.up`, `disk.nearly_full`, `update.available`, `item.added` |
| `POST /update/before` | The update's before step, 60 seconds at most |
| `POST /update/after` | The update's after step, 10 seconds at most |

## Jobs

- `weekly`: on the schedule in the setting `weekly_when` (Monday 09:00 until you change it), 2 minutes at most.

## How it works

- Starboard runs it: each event is a `POST /events`, and New this week is a job on the schedule in `weekly_when` that sends only when `send_weekly` is activated, and not twice within 20 hours. The container rests 5 minutes after the last one (`start: when_needed`).
- `POST /events` answers at once and sends in the background, because Starboard waits 3 seconds and tries again once. The same event sent twice within 10 minutes is sent once.
- `item.added` is not sent: it is kept in `/data/week.json`, 8 days at most, for New this week, with the title, series, type and year only. New this week also reads Starboard's `recent`, what the download apps imported. It lists films, episodes by series, albums and books, 40 of each at most, and leaves out series, pictures and everything else.
- One message at a time. The last 20 results are kept in `/data/log.json`, cleaned of every secret first, for both cards.
- Secrets are read from the settings each time and never written to the log, the cards or `/data`.
- Words: meaning is always in the words, never in a symbol or colour, and a link has words before it, "Open Starboard:" and the address.
- Cards set their status with `band()` from `sbplugin.py`. Its before update step holds new runs and waits for one that is running.

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
