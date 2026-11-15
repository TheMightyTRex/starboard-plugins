# Uptime Kuma: For developers

How Uptime Kuma is built, for anyone who wants to change it or make one like it. It is MIT, by TheMightyTRexUK, and works with plug-in API `>=1.14 <2.0`.

## Its files

- [`starboard-plugin.json`](../../../uptime-kuma/starboard-plugin.json)
- [`install.py`](../../../uptime-kuma/install.py)
- [`logo.svg`](../../../uptime-kuma/logo.svg)
- [`tests/test_app_plugins.py`](../../../tests/test_app_plugins.py), the checks it shares with the other app plug-ins

## How it works

- It has no code of its own: Starboard runs the app's own image, pinned by digest, with the limits in `resources`.
- Its container is on the `lan` network with `publish` set, and `network:port` lets Starboard open its page on the home network. `host_port` is the port Starboard tries first; when it is in use, Starboard takes the next free one and shows it on the tab.
- It has no `settings`, `cards`, `actions` or `health`, so Starboard waits for its container to start after an update.
- It runs read only, as a user that is not root, with no extra rights. What it writes goes in its own folder, `data/plugins/uptime-kuma`.
- It runs as `1000:1000`, the user its image expects, and keeps its data in `/app/data`, its folder in Starboard's data.

## Containers

| Container | Network | Folders | Runs as | Starts | Limits |
|---|---|---|---|---|---|
| `app` | `lan` | `data:/app/data` | `1000:1000` | `always` | 384 MB, 0.5 core, 128 processes |

Each image is pinned by digest in the manifest:

- `app`: `docker.io/louislam/uptime-kuma@sha256:d213a1d2b6a7d7c00afbcb936b53f585afea3e1620432b3a161b68bfffa13dac`

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
