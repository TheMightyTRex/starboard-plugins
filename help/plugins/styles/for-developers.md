# Styles: For developers

How Styles is built, for anyone who wants to change it or make one like it. It is MIT, by TheMightyTRexUK, and works with plug-in API `>=1.14 <2.0`.

## Its files

- [`starboard-plugin.json`](../../../styles/starboard-plugin.json)
- [`install.py`](../../../styles/install.py)
- [`logo.svg`](../../../styles/logo.svg)
- [`CHANGELOG.md`](../../../styles/CHANGELOG.md)

## How it works

- It has no container (`"containers": []`) and asks only for `appearance:styles`. Starboard reads the `styles` list in its manifest and writes the CSS itself.
- Each style has an `id`, a `name`, a `description`, a corner `radius`, a `font`, a `shadow`, and a `light` and a `dark` set of colours, such as `bg`, `surface`, `text`, `accent` and `focus`.
- Starboard checks every colour pair against WCAG 2.2: 4.5:1 for text, and 3:1 for edges and the focus ring. A style that fails cannot be added.
- 17 styles use the style settings from plug-in API 1.2 for cards, buttons, borders, tabs, the header, the side menu and chips (`card_style`, `button_fill`, `tab_style`, `header_style`, `rail_style` and `chip_style`). Aurora, Sunset, Winter, Large and clear and Classic do not set them.
- A style's `id` stays when it is redesigned, so a saved choice moves to the new design: in 1.6.0, `midnight` is Dusk, `frost` Liquid glass, `bold` Brutal, `paper` Almanac, `forest` Garden, `retro` Terminal, `vivid` Riso, `graphite` Vantage, `editorial` Newsprint and `nordic` Piste.
- Dusk, Vantage, Riso, Garden, Almanac, Terminal, Newsprint, Piste and Brutal take their colours and ideas from themes in Hallmark (MIT), as [What Styles does](../../../styles/README.md) says.

## Change it

1. Edit `starboard-plugin.json`.
2. Test it: run `python3 -m starboard.plugin_tester path/to/styles` from Starboard's folder, or go to **Settings**, then **Plug-ins**, then **Test a plug-in**.

## Find out more

- [The plug-in collection's developer pages](../../developers/plug-in-api.md)
- [Plug-in manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
