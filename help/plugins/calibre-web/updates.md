# Calibre-Web: Updates

Calibre-Web 1.2.0 is the latest version. It needs Starboard with plug-in API 1.20 or later.

## Versions

| Version | Needs plug-in API | Released |
|---|---|---|
| 1.2.0 | 1.20 or later | 26 November 2026 |
| 1.1.1 | 1.14 or later | 17 November 2026 |
| 1.1.0 | 1.14 or later | 15 November 2026 |
| 1.0.0 | 1.13 or later | 13 November 2026 |

The catalogue offers each Starboard the newest version it can run, so an older Starboard keeps an earlier version.

## What is new in 1.2.0

Added:

- **Set up for you:** Calibre-Web no longer starts with the first sign-in everybody knows. Starboard makes a long password before it first starts, replaces the default one and shows it once on the plug-in's page, after you enter your Starboard password.
- **Your library is found:** if a Calibre library is in your media folder, in a folder called books-library (made by the Calibre library maker plug-in) or in books itself, Calibre-Web is set to it at its start, so there is nothing to enter in Admin.
- **Safe by default:** uploads, public sign-up, anonymous browsing and remote sign-in are off, and the admin cannot edit or delete books, as your books folder is read only. OPDS, for e-reader apps, works with your sign-in.

Changed:

- Needs Starboard with plug-in API 1.20 or later, which shows the password. A Starboard with an older plug-in API keeps version 1.1.1.

## What is new in 1.1.1

Changed:

- **Logo description:** where its logo stands on its own, a screen reader says "Calibre-Web logo", the plug-in's name, instead of a description of the symbol.

## What is new in 1.1.0

Added:

- **A logo** in Settings, Plug-ins and in the Catalogue.

Changed:

- Needs Starboard with plug-in API 1.14 or later. A Starboard with an older plug-in API keeps version 1.0.0.

## What is new in 1.0.0

Added:

- Calibre-Web as a plug-in, outside the main install, on its own page on your home network.

## How an update is kept safe

- Calibre-Web has no step before an update: Starboard stops it, installs the new version and starts it again. An install that is already set up keeps its password and its choices: the new start-up changes only a library that is not set.
- It has no health check of its own, so Starboard waits for its containers to start. If they do not, Starboard goes back to the version you had by itself.
- Your settings and its folder are kept.
- **Roll back** brings back the older Calibre-Web and your settings, but not its folder as it was: if the newer app changed its own data, that stays. Back up its folder first if you are unsure.

## Update it

1. Go to **Settings**, then **Plug-ins**. When a newer version is known, Calibre-Web has an **Update** chip in **Manage**.
2. Select **Calibre-Web** to open its tab.
3. In **Versions**, select **Update to** and the new version.
4. Read **What is new since** your version and **How the update is kept safe**, enter your Starboard password, and select **Update Calibre-Web**.
5. When the dialog says it is updated, select **Done**.

## Roll it back

1. On Calibre-Web's tab, in **Versions**, select **Roll back to** and the version you had.
2. Enter your Starboard password and select **Roll back**.
3. When the dialog says it is back on that version, select **Done**.

Rolling back needs no download, and only one earlier version is kept.

## Find out more

- [Update a plug-in and roll it back, in Starboard's help](https://themightytrex.github.io/starboard/help/topics/update-a-plugin.html)
- [Calibre-Web's changes, in full](../../../calibre-web/starboard-plugin.json)
- [Problems](problems.md)
