# Uptime and status: For developers

How Uptime and status is built, for anyone who wants to change it or make one like it. It is MIT, by TheMightyTRexUK, and works with plug-in API `>=1.17 <2.0`. Its id and folder stay `outside-services`, so Outside services updates to it with its settings.

## Its files

- [`starboard-plugin.json`](../../../outside-services/starboard-plugin.json)
- [`app.py`](../../../outside-services/app.py): the rounds, alerts, cards, the Checks and Groups lists and the web server
- [`checks.py`](../../../outside-services/checks.py): each kind of check, the one-line form and certificates
- [`history.py`](../../../outside-services/history.py): 90 days of hours in 43 KB a check
- [`windows.py`](../../../outside-services/windows.py): maintenance windows
- [`page.py`](../../../outside-services/page.py): the status page
- [`make_css.py`](../../../outside-services/make_css.py): copies the design system for the page
- [`Dockerfile`](../../../outside-services/Dockerfile)
- [`CHANGELOG.md`](../../../outside-services/CHANGELOG.md)

## Containers

| Container | Network | Folders | Runs as | Starts | Limits |
|---|---|---|---|---|---|
| `main` | `lan`, with `publish` | `data` | `10001:10001` | `always` | 48 MB, 0.1 core |

Its own image, `ghcr.io/themightytrex/starboard-plugin-outside-services`, pinned by digest once GitHub has built it.

## What Starboard calls

| Path | What it is |
|---|---|
| `GET /health` | Health: 200 while it can work |
| `GET /status`, `/card`, `/groups`, `/certs` | The status and list cards |
| `GET /trend` | The Response times card (`sparkline`, plug-in API 1.17) |
| `GET` and `POST /manage/checks`, `/manage/groups` | The custom settings, only with the plug-in's key in `X-Api-Key` |
| `POST /run` | **Check everything now** |
| `POST /update/before`, `/update/after` | The update steps: the history is written first |

On the home network, the same port answers `/` (the status page), its files, and `/push/<secret>` for heartbeats.

## How it works

- Python's standard library only. Ping uses an unprivileged ICMP socket, which Docker allows without any capability; where it is refused, a TCP knock. DNS is one UDP question built by hand. Certificates are read from their DER bytes, with no package.
- One thread runs the rounds: up to four checks at once, then the alerts, then the page. It sleeps until the next check is due, at most a minute.
- Alerts go to `POST /api/v1/plugin/alerts` (plug-in API 1.17), once raised and once cleared, keyed `check-<id>` and `cert-<id>`, and never while the group is paused or in a maintenance window. A Starboard that answers 404 is asked again only after an hour.
- What is kept: `checks.json`, `groups.json`, `state.json` (written only when something changes) and `history/<id>.bin` (written once an hour). The status page is written to `/tmp`, in memory.

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
