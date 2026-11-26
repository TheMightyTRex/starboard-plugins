# Kavita: For developers

How Kavita is built, for anyone who wants to change it or make one like it. It is MIT, by TheMightyTRexUK, and works with plug-in API `>=1.14 <2.0`.

## Its files

- [`starboard-plugin.json`](../../../kavita/starboard-plugin.json)
- [`install.py`](../../../kavita/install.py)
- [`logo.svg`](../../../kavita/logo.svg)

## Containers

| Container | Network | Folders | Runs as | Starts | Limits |
|---|---|---|---|---|---|
| `app` | `lan` | `data:/kavita/config`, `media/books:ro`, `media/comics:ro` | `10001:10001` | `always` | 768 MB, 1 core, 256 processes |

Each image is pinned by digest in the manifest:

- `app`: `docker.io/jvmilazz0/kavita@sha256:31181a32f0dda73cae68721867028a7253d57881b58bea5754cd9e578e75421a`

## How it works

- Kavita is an app plug-in. It runs Kavita's own image, pinned by digest, started with `/kavita/Kavita`. It has no code of its own and no dashboard card.
- Its page is published on your home network (`network:port`). Starboard chooses the port, 5000 when it is free.
- Its own folder is mounted at `/kavita/config`. `/media/books` and `/media/comics` are mounted read only.
- `appsettings.json` is written into its folder once, before Kavita first starts, with `{secret:token_key}` filled in with a sign-in key Starboard makes for this install. It is never written over what Kavita or the owner changed.
- It has no health check and no update steps: Starboard waits for its container to start after an update.
- It uses about 339 MiB at rest, measured with `tools/app_check.py` on 13 November 2026, with an empty library.

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
