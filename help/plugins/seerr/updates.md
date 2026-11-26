# Seerr: Updates

Seerr 1.1.2 is the latest version. It needs Starboard with plug-in API 1.14 or later.

## Versions

| Version | Needs plug-in API | Released |
|---|---|---|
| 1.1.2 | 1.14 or later | Not released yet |
| 1.1.1 | 1.14 or later | 17 November 2026 |
| 1.1.0 | 1.14 or later | 15 November 2026 |
| 1.0.0 | 1.13 or later | 13 November 2026 |

The catalogue offers each Starboard the newest version it can run, so an older Starboard keeps an earlier version.

## What is new in 1.1.1

Changed:

- **Logo description:** where its logo stands on its own, a screen reader says "Seerr logo", the plug-in's name, instead of a description of the symbol.

## What is new in 1.1.0

Added:

- **A logo** in Settings, Plug-ins and in the Catalogue.

Changed:

- Needs Starboard with plug-in API 1.14 or later. A Starboard with an older plug-in API keeps version 1.0.0.

## What is new in 1.0.0

Added:

- Seerr as a plug-in, outside the main install, on its own page on your home network.

## How an update is kept safe

- Seerr has no step before an update: Starboard stops it, installs the new version and starts it again.
- It has no health check of its own, so Starboard waits for its containers to start. If they do not, Starboard goes back to the version you had by itself.
- Your settings and its folder are kept.
- **Roll back** brings back the older Seerr and your settings. It does not bring back its folder as it was. If the newer app changed its own data, that stays. Back up its folder first if you are unsure.

## Update it

1. Go to **Settings**, then **Plug-ins**. When a newer version is known, Seerr has an **Update** chip in **Manage**.
2. Select **Seerr** to open its tab.
3. In **Versions**, select **Update to** and the new version.
4. Read **What is new since** your version and **How the update is kept safe**, enter your Starboard password, and select **Update Seerr**.
5. When the dialog says it is updated, select **Done**.

## Roll it back

1. On Seerr's tab, in **Versions**, select **Roll back to** and the version you had.
2. Enter your Starboard password and select **Roll back**.
3. When the dialog says it is back on that version, select **Done**.

Rolling back needs no download, and only one earlier version is kept.

## Find out more

- [Update a plug-in and roll it back, in Starboard's help](https://themightytrex.github.io/starboard/help/topics/update-a-plugin.html)
- [Seerr's changes, in full](../../../seerr/starboard-plugin.json)
- [Problems](problems.md)
