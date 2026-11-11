# Starboard plug-ins

Plug-ins for [Starboard](https://github.com/TheMightyTRex/starboard), the lightweight, accessible dashboard for
smaller home media servers. Each one has passed Starboard's plug-in tester, accessibility included.

| Plug-in | What it does | Install address | Download |
|---|---|---|---|
| [Styles](styles/) | Thirteen accessible styles for Starboard's Display settings, with gradients, textures and glass (needs Starboard 0.16.5) | `https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/styles/starboard-plugin.json` | [styles.zip](https://github.com/TheMightyTRex/starboard-plugins/raw/main/zips/styles.zip) |

## Add a plug-in

1. In Starboard, open **Settings**, **Plug-ins**, **Add a plug-in**.
2. Copy the plug-in's install address into **The plug-in's manifest address**.
3. Check what it may do, then add it. Activate it when you are ready.

Or download its zip, unzip it and run `python3 install.py` inside, or choose its `starboard-plugin.json` under
**Or its manifest file**.

Read [Add a plug-in](https://github.com/TheMightyTRex/starboard/blob/main/docs/help/topics/add-a-plugin.md) and
[What a plug-in can change](https://github.com/TheMightyTRex/starboard/blob/main/docs/help/basics/what-plugins-can-change.md).

## Make your own

Each plug-in is a folder with a `starboard-plugin.json`. Read
[Write a plug-in](https://github.com/TheMightyTRex/starboard/blob/main/docs/help/basics/write-a-plugin.md), test it in
**Settings**, **Plug-ins**, **Test a plug-in**, then run `python3 tools/make_zips.py` to make its zip.

## Licence

Each plug-in has its own licence file. Styles is MIT, by TheMightyTRexUK.
