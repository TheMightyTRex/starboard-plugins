# Maintainerr: For developers

How Maintainerr is built, for anyone who wants to change it or make one like it. It is MIT, by TheMightyTRexUK, and works with plug-in API `>=1.14 <2.0`.

## Its files

- [`starboard-plugin.json`](../../../maintainerr/starboard-plugin.json)
- [`install.py`](../../../maintainerr/install.py)
- [`logo.svg`](../../../maintainerr/logo.svg)
- [`tests/test_app_plugins.py`](../../../tests/test_app_plugins.py), the checks it shares with the other app plug-ins

## How it works

- It has no code of its own: Starboard runs the app's own image, pinned by digest, with the limits in `resources`.
- Its container is on the `lan` network with `publish` set, and `network:port` lets Starboard open its page on the home network. `host_port` is the port Starboard tries first; when it is in use, Starboard takes the next free one and shows it on the tab.
- It has no `settings`, `cards`, `actions` or `health`, so Starboard waits for its container to start after an update.
- It runs read only, as a user that is not root, with no extra rights. What it writes goes in its own folder, `data/plugins/maintainerr`.
- It runs as `1000:1000`, the user its image expects, and keeps its data in `/opt/data`, its folder in Starboard's data.
- It lists `needs: ["jellyfin"]` but asks for no `jellyfin:key` and mounts no media folder: it removes only through Jellyfin or Seerr, with keys people give it.

## Containers

| Container | Network | Folders | Runs as | Starts | Limits |
|---|---|---|---|---|---|
| `app` | `lan` | `data:/opt/data` | `1000:1000` | `always` | 384 MB, 0.5 core, 128 processes |

Each image is pinned by digest in the manifest:

- `app`: `ghcr.io/maintainerr/maintainerr@sha256:5dcd5bef9d49c614bb74453df3da198afc05a38d8e2cd96b3669bc2c76a94112`

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
