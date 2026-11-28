# Styles, a Starboard plug-in

22 styles for Starboard, chosen from current interface trends and checked for accessibility in light and dark.

| Style | What it is like |
|---|---|
| Mica | Starboard's own design since 18 November 2026: calm greys, small corners, drop shadows and frosted menus |
| Dusk | Periwinkle on blue slate, smoked-glass panels and floating menus |
| Liquid glass | Clear glass panels over soft colour, rounded and bright |
| Brutal | Neo-brutalist poster: thick black rules, hard shadows, square corners and acid yellow |
| Bento | A grid of rounded tonal boxes in soft pastels, pill tabs and a floating side menu |
| Almanac | A printed sheet on cool slate: serif reading text, square corners and two rule weights |
| Garden | Warm oat paper and deep green ink, serif headings, hairlines and pill buttons |
| Terminal | Phosphor green on near-black, every word in monospace, scan lines and boxed tabs |
| Riso | Risograph print: blue ink on warm paper, fluorescent pink fills and grain |
| Aurora | Deep night blue with violet and teal glows, rounded and calm |
| Piste | Snow white and cold black, capital labels, 2px rules and one cobalt |
| Sunset | Warm coral and plum on soft peach |
| Vantage | Lime on blue-black, hairline frames, pill buttons and a faint grid |
| Newsprint | Pale newsprint, warm black serif type, column rules and one dried-brick red |
| Winter | Pine and berry over a frosty page, with snow dots, glows and glass |
| Large and clear | Strong contrast, heavy headings and wide focus rings, for reading with low vision |
| Studio | A quiet product style: hairline borders, one indigo accent, outlined buttons |
| Expressive | Tonal colour blocks, big round shapes and pill buttons |
| Swiss | White, black and red on a grid, heavy rules and capital labels |
| Neon | Synthwave glows on a faint grid, with a gradient button |
| Clay | Puffy, matte soft-3D panels in calm pastels |
| Classic | Starboard's design before Mica: teal on cool blue-grey, square corners and flat cards |

Mica is Starboard's own style since 18 November 2026, so Classic keeps the design from before it. Mica, the eleven redesigned on 20 November 2026 (Dusk to Piste) and the five from Studio to Clay change every part of Starboard. That means cards, buttons, tabs, the header, the side menu and chips (Starboard's plug-in API 1.2).

## Install

Needs Starboard with plug-in API 1.14 or later. An older Starboard keeps version 1.3.0.

1. Run `python3 install.py` and give your Starboard's address. Your browser opens Settings, Plug-ins, Catalogue
   with Styles ready to add.
2. Select **Install**, read what it may do (add styles to Display, nothing else), enter your Starboard password
   and select **Install Styles**.
3. Select **Turn on** on its tab, then open **Display** and choose a style.

Or find Styles in Settings, Plug-ins, Catalogue. No installer? There, choose this folder's `starboard-plugin.json` under **Or its manifest file**.

## What it can and cannot change

It changes colours, corner shapes, the fonts (from fonts already on your device), shadows, the page's gradient, a light texture and glass panels. It runs nothing: no
container, no code and no network access. Starboard writes the CSS itself after checking contrast (WCAG 2.2:
4.5:1 for text, 3:1 for edges and the focus ring). High contrast, text size, spacing, underlined links and reduced
motion in Display always win over a style.

## Change it

Edit `starboard-plugin.json`, then test it: `python3 -m starboard.plugin_tester path/to/styles` from Starboard's
folder, or Settings, Plug-ins, **Test a plug-in**. A style that fails contrast cannot be added.

Licence: MIT. Author: TheMightyTRexUK.

Dusk, Vantage, Riso, Garden, Almanac, Terminal, Newsprint, Piste and Brutal are after themes in [Hallmark](https://github.com/Nutlope/hallmark) by the Hallmark contributors (MIT): colours and ideas only.
