# Calibre library maker: For developers

How Calibre library maker is built, for anyone who wants to change it or make one like it. It is MIT, by TheMightyTRexUK, and works with plug-in API `>=1.14 <2.0`.

## Its files

- [`starboard-plugin.json`](../../../calibre-library/starboard-plugin.json)
- [`app.py`](../../../calibre-library/app.py), the small server Starboard talks to
- [`Dockerfile`](../../../calibre-library/Dockerfile)
- [`sbplugin.py`](../../../calibre-library/sbplugin.py), the helper every plug-in here shares
- [`install.py`](../../../calibre-library/install.py) and [`logo.svg`](../../../calibre-library/logo.svg)
- [`tests/test_calibre_library.py`](../../../tests/test_calibre_library.py)

## How it works

- Its one container, `main`, is `start: when_needed` with `idle_stop_minutes` 5, so Starboard stops it when it is idle and starts it for its page or a button. It has no card and no `health`, because either would wake it.
- It is on the `default` network, so it can reach nothing. It asks for no permission.
- `media/books:ro` mounts the books folder read only; `media/books-library` mounts the new library folder for writing. It runs as the default user, `10001:10001`, the same as Calibre-Web's, so Calibre-Web can read what it writes.
- `app.py` scans the books folder, leaves out files that cannot be books (empty, cut short, not what the name says), and runs `calibredb add --with-library /media/books-library` on batches of 20 files. A batch that fails is listed, and the run carries on. `calibredb` copies each file, which is why the plug-in says the library needs room.
- Re-running is safe twice over: handled files are remembered in `/data/done.json` by path and size, and Calibre skips a book that is already in the library.
- The image is Debian with Calibre's package, with the web browser engine and graphics drivers removed in the same step, about 0.7 GB instead of 1.2 GB. `calibredb --version` runs at the end of the build.

## Containers

| Container | Network | Folders | Runs as | Starts | Limits |
|---|---|---|---|---|---|
| `main` | `default` | `data`, `media/books:ro`, `media/books-library` | `10001:10001` | `when_needed` | 320 MB, 1 core, 128 processes |

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
