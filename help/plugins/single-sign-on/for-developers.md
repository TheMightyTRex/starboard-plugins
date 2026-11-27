# Single sign-on: For developers

How Single sign-on is built, for anyone who wants to change it or make one like it. It is MIT, by TheMightyTRexUK, and works with plug-in API `>=1.21 <2.0`. This is stage 1 of single sign-on in Starboard: the provider itself is not in it yet.

## Its files

- [`starboard-plugin.json`](../../../single-sign-on/starboard-plugin.json)
- [`app.py`](../../../single-sign-on/app.py)
- [`sbplugin.py`](../../../single-sign-on/sbplugin.py)
- [`Dockerfile`](../../../single-sign-on/Dockerfile)
- [`install.py`](../../../single-sign-on/install.py)
- [`logo.svg`](../../../single-sign-on/logo.svg)
- [`CHANGELOG.md`](../../../single-sign-on/CHANGELOG.md)
- [`tests/test_single_sign_on.py`](../../../tests/test_single_sign_on.py)

## Containers

| Container | Network | Folders | Runs as | Starts | Limits |
|---|---|---|---|---|---|
| `main` | default | `data` | `10001:10001` | `when_needed` | 32 MB, 0.1 core |

The image is the shared examples image. Until it is built and pinned by digest, the manifest names its next tag.

## What Starboard calls

| Path | What it is |
|---|---|
| `GET /health` | Health: 200 while it can work |
| `GET /card` | The Single sign-on card (status) |
| `POST /check` | The Check the name action: says where the name stands |
| `POST /use-new-address` | The Use the new address action, which asks first: keeps the name now in the settings |
| `POST /update/before` | The update's before step, 60 seconds at most |
| `POST /update/after` | The update's after step, 10 seconds at most |

## How it works

- It has no timer and no job: Starboard asks the card, the container wakes, works out its state from the two settings and one small file, and rests after 5 minutes with nothing to do.
- **The name** must be a MagicDNS name: a machine, the tailnet and `.ts.net`, in letters, numbers and hyphens. `https://`, a trailing slash and a trailing dot are removed. An IP address, a port, a path or a space is refused with the reason in words.
- **The kept name:** the first valid name found while the switch is on is written to the file `address.json` in its data folder. A later, different name is shown on the card as **Name changed** and never replaces the kept one until **Use the new address** is chosen, because passkeys are tied to the address.
- It makes no network call. The tests fail it if it tries to connect.
- Nothing is written to `/data` while it is off, or while the name is missing or wrong.

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
