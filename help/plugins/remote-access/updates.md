# Remote access: Updates

Remote access 1.1.3 is the latest version. It needs Starboard with plug-in API 1.14 or later.

## Versions

| Version | Needs plug-in API | Released |
|---|---|---|
| 1.1.3 | 1.14 or later | 17 November 2026 |
| 1.1.2 | 1.14 or later | 17 November 2026 |
| 1.1.1 | 1.14 or later | 16 November 2026 |
| 1.1.0 | 1.14 or later | 15 November 2026 |
| 1.0.0 | 1.8 or later | 13 November 2026 |

The catalogue offers each Starboard the newest version it can run, so an older Starboard keeps an earlier version.

## What is new in 1.1.3

Changed:

- **Clearer words:** **Cloudflare tunnel token** is now **Cloudflare Tunnel token**, and its messages say "the server" instead of "this computer".
- **Logo description:** where its logo stands on its own, a screen reader says "Remote access logo", the plug-in's name, instead of a description of the symbol.

## What is new in 1.1.2

Changed:

- **Shared helper:** its shared code sends Jellyfin's key the way Jellyfin 12 asks for it. Remote access does not ask Jellyfin anything, so it works as before.

## What is new in 1.1.1

Changed:

- **Lighter at rest:** it wakes about once a minute while nothing asks it anything, not twice a second.
- **Starts faster:** its image comes with Python's modules already compiled, so a start takes about a quarter of the processor time.

## What is new in 1.1.0

Added:

- **A logo** in Settings, Plug-ins, in the Catalogue and on its dashboard cards.
- **Its card says how things are:** a status and when it last changed, in the grey band at the top of the card.

Changed:

- Needs Starboard with plug-in API 1.14 or later. A Starboard with an older plug-in API keeps version 1.0.0.

## What is new in 1.0.0

Added:

- **Tailscale** in userspace networking, with an auth key or a sign-in link
- **Cloudflare Tunnel** with a tunnel token, stopped if a route leads anywhere but Starboard, Jellyfin or Audiobookshelf, or to Starboard without Cloudflare Access
- **Addresses away from home** for each shared app, with Test; download apps are never shared

## How an update is kept safe

- Remote access has no step before an update: Starboard stops it, installs the new version and starts it again.
- Starboard waits for the new version to answer. If it does not, Starboard goes back to the version you had by itself, with your settings as they were.
- Your settings and its folder are kept.

## Update it

1. Go to **Settings**, then **Plug-ins**. When a newer version is known, Remote access has an **Update** chip in **Manage**.
2. Select **Remote access** to open its tab.
3. In **Versions**, select **Update to** and the new version.
4. Read **What is new since** your version and **How the update is kept safe**, enter your Starboard password, and select **Update Remote access**.
5. When the dialog says it is updated, select **Done**.

## Roll it back

1. On Remote access's tab, in **Versions**, select **Roll back to** and the version you had.
2. Enter your Starboard password and select **Roll back**.
3. When the dialog says it is back on that version, select **Done**.

Rolling back needs no download, and only one earlier version is kept.

## Find out more

- [Update a plug-in and roll it back, in Starboard's help](https://themightytrex.github.io/starboard/help/topics/update-a-plugin.html)
- [Remote access's changes, in full](../../../remote-access/starboard-plugin.json)
- [Problems](problems.md)
