# Immich: For developers

How Immich is built, for anyone who wants to change it or make one like it. It is MIT, by TheMightyTRexUK, and works with plug-in API `>=1.17 <2.0`.

## Its files

- [`starboard-plugin.json`](../../../immich/starboard-plugin.json)
- [`app.py`](../../../immich/app.py)
- [`sbplugin.py`](../../../immich/sbplugin.py)
- [`Dockerfile`](../../../immich/Dockerfile)
- [`install.py`](../../../immich/install.py)
- [`logo.svg`](../../../immich/logo.svg)
- [`CHANGELOG.md`](../../../immich/CHANGELOG.md)
- [`tests/test_immich.py`](../../../tests/test_immich.py)

## Containers

| Container | Network | Folders | Runs as | Starts | Limits |
|---|---|---|---|---|---|
| `main` | `lan` | `data` | `10001:10001` | `when_needed` | 32 MB, 0.1 core |

The image is the shared examples image. Until it is built and pinned by digest, the manifest names its next tag.

## What Starboard calls

| Path | What it is |
|---|---|
| `GET /health` | Health: 200 while it can work |
| `GET /library` | The Immich library card (stat) |
| `GET /storage` | The Immich storage card (list) |
| `GET /jobs` | The Immich jobs card (status) |
| `POST /update/before` | The update's before step, 60 seconds at most |
| `POST /update/after` | The update's after step, 10 seconds at most |

## How it works

- It has no timer and no job: Starboard asks a card, the container wakes, asks Immich, and rests after 5 minutes with nothing to do. Each answer is kept in memory for a minute, so the three cards of one dashboard make one set of requests. Nothing is written to `/data`.
- **Immich's API,** with the key in the `x-api-key` header: `GET /api/server/statistics` (`photos`, `videos`, `usage`, `usagePhotos`, `usageVideos`, `usageByUser`), `GET /api/server/storage` (`diskSizeRaw`, `diskUseRaw`, `diskAvailableRaw`, `diskUsagePercentage`) and `GET /api/queues` (a list of `name`, `isPaused` and `statistics`).
  On a 404, it asks an older Immich `GET /api/jobs` instead (`jobCounts` and `queueStatus` for each queue).
- The shapes are from Immich's OpenAPI description (`open-api/immich-openapi-specs.json`). It was not tried against a real server: the tests use a made-up Immich that answers as that description says.
- The key is read from the settings each time and is never written to `/data`, a card or an error.
- The storage card's limits, 90% and 98%, are the same as Starboard's own disk card.

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
