[Help centre](../README.md) · Developers · reference
<!-- help: dev / build -->

# App plug-ins

An app plug-in runs a whole app made by others, such as Seerr or Kavita, in Starboard's locked-down containers, with
its own web page on your home network. Nine plug-ins here are app plug-ins.

## When would you use it

- You want to add an app to the collection rather than to Starboard's main install.
- You need to know what Starboard allows an app to do.

## What makes one

- `network:port` and a container with `"publish": true` on the `lan` network: Starboard chooses a free port on the
  home network, trying `host_port` first, and shows the address with **Open**.
- Its folders at the paths the app expects, such as `data:/config`, and media folders read only where it only reads,
  such as `media/books:ro`.
- `tmpfs` for folders the app writes to in memory, and `pids` for apps with many threads.
- `adopt`, to copy an app the main install already runs into the plug-in, as Tdarr does.
- Higher limits than a card plug-in: up to 2048 MB and 4 cores a container with `network:port`.

## Rules

- The image is the app's own, pinned by digest. Every app runs read only, as a user that is not root, with no extra
  rights, like every plug-in.
- Measure it at rest with `tools/app_check.py`, which runs it as Starboard writes it, on closed networks, and put the
  figures in its README.
- Say in its help that its own web page was not checked for accessibility by Starboard.
- Removing it keeps its data: in `data/plugins/.removed`, or the holding folder.

## The app plug-ins here

Jellystat, Navidrome, Kavita, Calibre-Web, Wizarr, Maintainerr, Uptime Kuma, Seerr and Tdarr. Each one's For
developers page lists its containers and folders, such as [Tdarr's](../plugins/tdarr/for-developers.md).

## Find out more

- [App plug-ins, in Starboard's manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html#app-plug-ins)
- [Make a plug-in for the collection](make-a-plug-in-for-the-collection.md)
