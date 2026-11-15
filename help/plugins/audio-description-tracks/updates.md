# Audio description tracks: Updates

Audio description tracks 1.1.0 is the latest version. It needs Starboard with plug-in API 1.14 or later.

## Versions

| Version | Needs plug-in API | Released |
|---|---|---|
| 1.1.0 | 1.14 or later | 2026-11-15 |
| 1.0.0 | 1.12 or later | 2026-11-13 |

The catalogue offers each Starboard the newest version it can run, so an older Starboard keeps an earlier version.

## What is new in 1.1.0

Added:

- **A logo** in Settings, Plug-ins, in the Catalogue and on its dashboard cards.
- **Its card says how things are:** a status and when it last changed, in the grey band at the top of the card.
- **Updates safely:** before an update it finishes adding the track it is on and starts no other.

Changed:

- Needs Starboard with plug-in API 1.14 or later. A Starboard with an older plug-in API keeps version 1.0.0.

## What is new in 1.0.0

Added:

- **Add a description track you already have:** put it in the audio-description folder in your media folder, or upload it, and it is matched to its film or episode by name
- **Lengths checked:** added only when the track and the film are the same length, within the seconds you choose; otherwise it says the track is probably for another cut
- **Added as an extra sound track** next to the film, named English (Audio Description), with the visual impaired flag; the film file is not changed
- **Nothing deleted:** the original moves to Confirmed once you say it plays in step, and a wrong track moves to Taken off

## How an update is kept safe

- **Before the update** Starboard asks Audio description tracks to get ready: it starts nothing new and lets anything running finish, for up to 60 seconds. If it is not ready, nothing changes and Starboard says why.
- **After the update,** or after a Roll back, it carries on with its work.
- Starboard waits for the new version to answer. If it does not, Starboard goes back to the version you had by itself, with your settings as they were.
- Your settings and its folder are kept.

## Update it

1. Go to **Settings**, then **Plug-ins**. When a newer version is known, Audio description tracks has an **Update** chip in **Manage**.
2. Select **Audio description tracks** to open its tab.
3. In **Versions**, select **Update to** and the new version.
4. Read **What is new since** your version and **How the update is kept safe**, enter your Starboard password, and select **Update Audio description tracks**.
5. When the dialog says it is updated, select **Done**.

## Roll it back

1. On Audio description tracks's tab, in **Versions**, select **Roll back to** and the version you had.
2. Enter your Starboard password and select **Roll back**.
3. When the dialog says it is back on that version, select **Done**.

Rolling back needs no download, and only one earlier version is kept.

## Find out more

- [Update a plug-in and roll it back, in Starboard's help](https://themightytrex.github.io/starboard/help/topics/update-a-plugin.html)
- [Audio description tracks's changes, in full](../../../audio-description-tracks/CHANGELOG.md)
- [Problems](problems.md)
