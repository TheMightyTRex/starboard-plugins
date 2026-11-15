# Wizarr: Settings

Wizarr has no settings in Starboard. Everything is set in the app itself, on its own page: open it with **Open Wizarr** on its tab.

## Buttons

Wizarr's tab, in **Settings**, then **Plug-ins**, then **Wizarr**, has these buttons:

- **Open Wizarr** opens its own page in a new tab. It is there while it is active.
- **Activate** starts it, and Starboard chooses a free port for its page. **Deactivate** stops it and keeps its folder.
- **Try again** starts it again when it did not start.
- **Look for an update** is there when this Starboard is newer than the version was made for.
- **Remove Wizarr** stops it and takes it away. You choose where its folder goes; nothing is deleted.

## Things to note

- Starboard does not give Wizarr Jellyfin's key. Make one for it in Jellyfin's **Dashboard**, **API keys**, so you can stop it there at any time.
- Wizarr reaches Jellyfin on this computer at `http://host.docker.internal:8096`.
- Invitation links work on your home network only, unless you use the [Remote access](../remote-access/install.md) plug-in or your own address.
- Wizarr keeps its invitations and choices in its own folder in Starboard's data, `data/plugins/wizarr`.
- Its settings are kept when you update or deactivate it, and when you remove it they stay in its folder.

## Find out more

- [Install](install.md)
- [Dashboard card](dashboard-card.md)
- [Problems](problems.md)
