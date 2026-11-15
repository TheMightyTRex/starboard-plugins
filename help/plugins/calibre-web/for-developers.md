# Calibre-Web: For developers

How Calibre-Web is built, for anyone who wants to change it or make one like it. It is MIT, by TheMightyTRexUK, and works with plug-in API `>=1.14 <2.0`.

## Its files

- [`starboard-plugin.json`](../../../calibre-web/starboard-plugin.json)
- [`install.py`](../../../calibre-web/install.py)
- [`logo.svg`](../../../calibre-web/logo.svg)
- [`tests/test_app_plugins.py`](../../../tests/test_app_plugins.py), the checks it shares with the other app plug-ins

## How it works

- It has no code of its own: Starboard runs the app's own image, pinned by digest, with the limits in `resources`.
- Its container is on the `lan` network with `publish` set, and `network:port` lets Starboard open its page on the home network. `host_port` is the port Starboard tries first; when it is in use, Starboard takes the next free one and shows it on the tab.
- It has no `settings`, `cards`, `actions` or `health`, so Starboard waits for its container to start after an update.
- It runs read only, as a user that is not root, with no extra rights. What it writes goes in its own folder, `data/plugins/calibre-web`.
- `entrypoint` starts Calibre-Web's `cps.py` straight away, without the LinuxServer image's start-up, which needs root. `HOME` is `/tmp` and its cache is a `tmpfs`, so it runs read only.
- `media/books:ro` mounts only the books folder, read only, at `/media/books`. `CALIBRE_DBPATH` keeps its own database in `/config`, its folder in Starboard's data.

## Containers

| Container | Network | Folders | Runs as | Starts | Limits |
|---|---|---|---|---|---|
| `app` | `lan` | `data:/config`, `media/books:ro` | `10001:10001` | `always` | 384 MB, 0.5 core, 128 processes |

Each image is pinned by digest in the manifest:

- `app`: `lscr.io/linuxserver/calibre-web@sha256:8eabbc9ac4d7fcbc252434493078ba22e4e8c3aa461e11b102020b040c5fc3e6`

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
