# Library clean-up: For developers

How Library clean-up is built, for anyone who wants to change it or make one like it. It is MIT, by TheMightyTRexUK, and works with plug-in API `>=1.15 <2.0`.

## Its files

- [`starboard-plugin.json`](../../../library-cleanup/starboard-plugin.json)
- [`app.py`](../../../library-cleanup/app.py)
- [`sbplugin.py`](../../../library-cleanup/sbplugin.py)
- [`Dockerfile`](../../../library-cleanup/Dockerfile)
- [`install.py`](../../../library-cleanup/install.py)
- [`logo.svg`](../../../library-cleanup/logo.svg)
- [`HELP.md`](../../../library-cleanup/HELP.md)
- [`CHANGELOG.md`](../../../library-cleanup/CHANGELOG.md)
- [`tests/test_library_cleanup.py`](../../../tests/test_library_cleanup.py)

## Containers

| Container | Network | Folders | Runs as | Starts | Limits |
|---|---|---|---|---|---|
| `main` | `lan` | `data`, `media:holding` | `media` | `when_needed`, rests after 15 minutes | 128 MB, 0.5 core |

Its image is pinned by digest in the manifest:

- `main`: `ghcr.io/themightytrex/starboard-plugin-library-cleanup@sha256:3628026fa40597cf465848f2e9daddcb444b44dc873cf7339925f4821e808cb6` (version 1.0.0)

## What Starboard calls

| Path | What it is |
|---|---|
| `GET /health` | Health: 200 while it can work |
| `GET /card` | The Holding folder card (stat, in bytes) |
| `GET /preview` and `POST /preview` | The Preview page |
| `GET /held` and `POST /held` | The Holding folder page, with **Put back** on each row |
| `GET /libraries` and `POST /libraries` | The Libraries page |
| `POST /preview-again` | The Preview again button |
| `POST /jobs/move` | The job Move items to the holding folder |
| `POST /update/before` | The update's before step, 60 seconds at most |
| `POST /update/after` | The update's after step, 10 seconds at most |

## Jobs

- `move`: every 24 hours, only in quiet hours, 60 minutes at most. It moves nothing unless the `active` setting (**Move items each day**) is on.

## How it works

- It asks for `library:holding` (plug-in API 1.15) and mounts `media:holding`: the whole media folder, read and write, at `/media`. What it moves goes in `/media/.holding/library-cleanup/`, keeping the folders it was in.
- A series moves as its folder. A film in its own folder moves as the folder. A film that shares a folder with other films, or sits at the top of the library, moves as its file. The files beside it that share its name, such as subtitles, move with it.
- A move is a rename inside the one mount, so it is instant and needs no free space. A move that would have to copy is refused, and something with the same name already in the holding folder is never overwritten. It never moves the library folder itself, the holding folder, or anything outside the media folder.
- Its code has no call that deletes a file or a folder; `tests/test_library_cleanup.py` checks that.
- **Put back** is the `restore` action on a row of the `held` custom setting (plug-in API 1.15), drawn by Starboard as a **Put back** button.
- With `reelix:key`, it stops Reelix following what moves, with each followed episode, and rescans it; **Put back** follows again exactly what was followed. With `jellyfin:key`, it reads each person's watched state, favourites, Continue watching and collections. It tells Jellyfin the path was deleted, or created on **Put back**, so Jellyfin updates at once. Without Reelix it still moves.
- **Preview** is worked out in the background when opened, when a setting changes, after six hours, or with **Preview again**. A run moves up to 200 items, within 50 minutes; the next carries on.
- Before an update it finishes the item it is moving and starts no new run, so nothing is left half moved.
- It runs as `media`, the owner of the media folder, so moved folders keep their owner.

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
