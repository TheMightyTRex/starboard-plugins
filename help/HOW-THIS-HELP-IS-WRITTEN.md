# How this help is written

The plug-ins help follows the design system's guides, as Starboard's help does:

- [Help writing guide](https://github.com/TheMightyTRex/design-system/blob/main/docs/HELP-WRITING.md), section 11 for
  the help centre standard: the top menu, the side menu, flow charts, the journey and the plug-in pages.
- [Content design guide](https://github.com/TheMightyTRex/design-system/blob/main/docs/CONTENT-DESIGN.md): British
  English, sentence case, no em dashes and no contractions. Settings are activated or deactivated.

## Only in the plug-ins help

- **Eight pages for every plug-in,** in the same order. Keep each page to its subject: Install says how to add it,
  Settings lists every setting, Dashboard card says what the card shows and how often it refreshes, Updates says
  what to know before updating, Accessibility says what was checked, Problems starts with a flow chart, and For
  developers says how it is built.
- **Problems pages start with a flow chart** in a `flow` block, with numbered answers as sections.
- **Build it to check it** from this folder's parent:

  ```bash
  python3 <design-system>/tools/help_centre/build.py --config help-centre.json --out _site
  ```
