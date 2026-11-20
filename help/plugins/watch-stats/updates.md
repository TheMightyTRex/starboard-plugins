# Watch statistics: Updates

Watch statistics 1.1.4 is the latest version. It needs Starboard with plug-in API 1.14 or later.

## Versions

| Version | Needs plug-in API | Released |
|---|---|---|
| 1.1.4 | 1.14 or later | 19 November 2026 |
| 1.1.3 | 1.14 or later | 17 November 2026 |
| 1.1.2 | 1.14 or later | 17 November 2026 |
| 1.1.1 | 1.14 or later | 16 November 2026 |
| 1.1.0 | 1.14 or later | 15 November 2026 |
| 1.0.0 | 1.11 or later | 13 November 2026 |

The catalogue offers each Starboard the newest version it can run, so an older Starboard keeps an earlier version.

## What is new in 1.1.4

Changed:

- **Reaches Starboard on any network:** with Starboard 0.23.0 or later it calls Starboard through a socket in its own folder, so it works on its own closed network too. An older Starboard works as before.

## What is new in 1.1.3

Changed:

- **Clearer words:** **Read the figures again now** is now **Check now**, as on the other plug-ins.
- **Logo description:** where its logo stands on its own, a screen reader says "Watch statistics logo", the plug-in's name, instead of a description of the symbol.

## What is new in 1.1.2

Fixed:

- **Jellyfin 12:** it sends Jellyfin's key the way Jellyfin 12 asks for it, so Jellyfin no longer refuses its requests where legacy authorisation is off. Older Jellyfin still works.

## What is new in 1.1.1

Changed:

- **Lighter at rest:** it wakes about once a minute while nothing asks it anything, not twice a second, and writes nothing to its folder when a run goes well.
- **Starts faster:** its image comes with Python's modules already compiled, so a start takes about a quarter of the processor time.

## What is new in 1.1.0

Added:

- **A logo** in Settings, Plug-ins, in the Catalogue and on its dashboard cards.
- **Its cards say how things are:** a status and when they last changed, in the grey band at the top of each card.
- **Updates safely:** before an update it finishes what it is doing and starts nothing new.

Changed:

- Needs Starboard with plug-in API 1.14 or later. A Starboard with an older plug-in API keeps version 1.0.0.

## What is new in 1.0.0

Added:

- **Three tables:** recent plays by day, top titles and people, each to read only, with search and sorting.
- **Four cards:** plays this week, top titles, who watched most, and where the figures come from.
- Reads Jellyfin's Playback Reporting with one query, so a Full install can go without Jellystat and its PostgreSQL.
- Without Playback Reporting it says so and how to add it, and shows each person's last plays from Jellyfin itself.
- Rests when not in use, and keeps each answer for 15 minutes.

## How an update is kept safe

- **Before the update** Starboard asks Watch statistics to get ready: it starts nothing new and lets anything running finish, for up to 60 seconds. If it is not ready, nothing changes and Starboard says why.
- **After the update,** or after a Roll back, it carries on with its work.
- Starboard waits for the new version to answer. If it does not, Starboard goes back to the version you had by itself, with your settings as they were.
- Your settings and its folder are kept.

## Update it

1. Go to **Settings**, then **Plug-ins**. When a newer version is known, Watch statistics has an **Update** chip in **Manage**.
2. Select **Watch statistics** to open its tab.
3. In **Versions**, select **Update to** and the new version.
4. Read **What is new since** your version and **How the update is kept safe**, enter your Starboard password, and select **Update Watch statistics**.
5. When the dialog says it is updated, select **Done**.

## Roll it back

1. On Watch statistics' tab, in **Versions**, select **Roll back to** and the version you had.
2. Enter your Starboard password and select **Roll back**.
3. When the dialog says it is back on that version, select **Done**.

Rolling back needs no download, and only one earlier version is kept.

## Find out more

- [Update a plug-in and roll it back, in Starboard's help](https://themightytrex.github.io/starboard/help/topics/update-a-plugin.html)
- [Watch statistics' changes, in full](../../../watch-stats/CHANGELOG.md)
- [Problems](problems.md)
