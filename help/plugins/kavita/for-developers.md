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

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api-1-14.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
