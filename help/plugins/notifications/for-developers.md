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
| `POST /jobs/weekly` | The job Send New this week on the chosen day |
| `POST /events` | Events: `request.available`, `download.failed`, `app.down`, `app.up`, `disk.nearly_full`, `update.available`, `item.added` |
| `POST /update/before` | The update's before step, 60 seconds at most |
| `POST /update/after` | The update's after step, 10 seconds at most |

## Jobs

- `weekly`: daily at 09:00, 2 minutes at most.

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api-1-14.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
