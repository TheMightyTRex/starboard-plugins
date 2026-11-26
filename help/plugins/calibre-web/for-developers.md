# Calibre-Web: For developers

How Calibre-Web is built, for anyone who wants to change it or make one like it. It is MIT, by TheMightyTRexUK, and works with plug-in API `>=1.20 <2.0`.

## Its files

- [`starboard-plugin.json`](../../../calibre-web/starboard-plugin.json)
- [`install.py`](../../../calibre-web/install.py)
- [`start.py`](../../../calibre-web/start.py), the start-up Starboard writes into its data folder
- [`logo.svg`](../../../calibre-web/logo.svg)
- [`tools/sync_calibre_start.py`](../../../tools/sync_calibre_start.py), which puts `start.py` into the manifest
- [`tests/test_calibre_web.py`](../../../tests/test_calibre_web.py)
- [`tests/test_app_plugins.py`](../../../tests/test_app_plugins.py), the checks it shares with the other app plug-ins

## How it works

- It runs the app's own image, pinned by digest, with the limits in `resources`, and one small start-up file of its own.
- Its container is on the `lan` network with `publish` set. `network:port` lets Starboard open its page on the home network. `host_port` is the port Starboard tries first. When it is in use, Starboard takes the next free one and shows it on the tab.
- It has no `settings`, `cards`, `actions` or `health`, so Starboard waits for its container to start after an update.
- It runs read only, as a user that is not root, with no extra rights. What it writes goes in its own folder, `data/plugins/calibre-web`.
- `entrypoint` starts `starboard-start-1.py` (`start.py`), which sets Calibre-Web up and then starts its `cps.py`, without the LinuxServer image's start-up, which needs root. `HOME` is `/tmp` and its cache is a `tmpfs`, so it runs read only. Starboard writes the file once, so a changed `start.py` gets a new file name.
- **First start only** (no `app.db` yet): Calibre-Web's own code makes `app.db`, then the start-up sets the admin password from `STARBOARD_ADMIN_PASSWORD` (a `{secret:admin_password}`; the start-up takes it out of the environment, never prints it and never puts it on a command line), turns uploads, public sign-up, anonymous browsing and remote sign-in off, and takes upload, edit and delete from the admin. It writes `starboard-first-sign-in.done`, the `ready_file` of `first_sign_in` (plug-in API 1.20), which lets Starboard show the password once, and makes its data folder `711` at every start, so Starboard (another user) can check that one file is there and cannot list the folder. If it cannot, it stops rather than start with the default password.
- **Every start:** if Calibre-Web has no working library and `/media/books-library` or `/media/books` has `metadata.db`, it is set. A library you chose that still works is never changed.
- `media/books:ro` and `media/books-library:ro` mount two folders, read only, at `/media/books` and `/media/books-library`. `CALIBRE_DBPATH` keeps its own database in `/config`, its folder in Starboard's data.

## Containers

| Container | Network | Folders | Runs as | Starts | Limits |
|---|---|---|---|---|---|
| `app` | `lan` | `data:/config`, `media/books:ro`, `media/books-library:ro` | `10001:10001` | `always` | 384 MB, 0.5 core, 128 processes |

Each image is pinned by digest in the manifest:

- `app`: `lscr.io/linuxserver/calibre-web@sha256:8eabbc9ac4d7fcbc252434493078ba22e4e8c3aa461e11b102020b040c5fc3e6`

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
