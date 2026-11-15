# Maintainerr: Settings

Maintainerr has no settings in Starboard. Everything is set in the app itself, on its own page: open it with **Open Maintainerr** on its tab.

## Buttons

Maintainerr's tab, in **Settings**, then **Plug-ins**, then **Maintainerr**, has these buttons:

- **Open Maintainerr** opens its own page in a new tab. It is there while it is active.
- **Activate** starts it, and Starboard chooses a free port for its page. **Deactivate** stops it and keeps its folder.
- **Try again** starts it again when it did not start.
- **Look for an update** is there when this Starboard is newer than the version was made for.
- **Remove Maintainerr** stops it and takes it away. You choose where its folder goes; nothing is deleted.

## Things to note

- Maintainerr changes nothing until you give it keys and a rule with an action that removes.
- Starboard gives it no key and no media folder: anything it removes, it removes through Jellyfin or Seerr, with the keys you gave it.
- Maintainerr keeps its rules and choices in its own folder in Starboard's data, `data/plugins/maintainerr`.
- Its settings are kept when you update or deactivate it, and when you remove it they stay in its folder.

## Find out more

- [Install](install.md)
- [Dashboard card](dashboard-card.md)
- [Problems](problems.md)
