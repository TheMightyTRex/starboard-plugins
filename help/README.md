# Starboard plug-ins help

Help for every plug-in in the collection. The pages are built into a help centre by the design system's help
centre builder, with the settings in `help-centre.json` at the top of this repository.

## How it is laid out

- Every plug-in has the same eight pages, in the same order: Overview, Install, Settings, Dashboard card, Updates,
  Accessibility, Problems and For developers.
- **Overview** is the plug-in's own `README.md`, in its folder.
- The other seven are in `help/plugins/<plug-in>/`: `install.md`, `settings.md`, `dashboard-card.md`, `updates.md`,
  `accessibility.md`, `problems.md` and `for-developers.md`. A page with nothing to say keeps one line saying so.
- The groups in the side menu, and each plug-in's icon, are in `help-centre.json`, under `plugins`. A new plug-in
  goes in one group there, and gets its seven pages here.
- Articles about the whole collection go in `help/` with a `<!-- help: <area> / <group> -->` line under their
  first line, as the design system's `docs/HELP-WRITING.md`, section 11, says.

How these pages are written: [How this help is written](HOW-THIS-HELP-IS-WRITTEN.md).
