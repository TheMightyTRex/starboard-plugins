# Direct play: Updates

Direct play 1.0.2 is the latest version. It needs Starboard with plug-in API 1.14 or later.

## Versions

| Version | Needs plug-in API | Released |
|---|---|---|
| 1.0.2 | 1.14 or later | 2026-11-17 |
| 1.0.1 | 1.14 or later | 2026-11-16 |
| 1.0.0 | 1.14 or later | 2026-11-14 |

The catalogue offers each Starboard the newest version it can run, so an older Starboard keeps an earlier version.

## What is new in 1.0.2

Fixed:

- **Jellyfin 12:** it sends Jellyfin's key the way Jellyfin 12 asks for it, so Jellyfin no longer refuses its library refreshes and other requests where legacy authorisation is off. Older Jellyfin still works.

## What is new in 1.0.1

Changed:

- **Lighter at rest:** it wakes about once a minute while nothing asks it anything, not twice a second, and writes nothing to its folder when a run goes well.
- **Starts faster:** its image comes with Python's modules already compiled, so a start takes about a quarter of the processor time.
- **Lighter dashboard card:** the cards and the minute's look for work no longer read every file's details each time; with 50,000 files the card answers in about 4 ms instead of 230 ms, and about 45 MB less memory is held.

## What is new in 1.0.0

Added:

- **Plays directly on the devices you choose:** Rokus, Fire TV Sticks, Chromecast, smart TV apps, web browsers, Apple TV and Nvidia Shield
- **Four fixes, cheapest first:** repackages the wrong container, adds a sound track your devices play beside the original, shrinks very large H.264 files and converts old formats to H.264
- **Checked before it replaces:** the length, the picture, the first sound track and where sound and picture start; a file that fails is left as it was
- **One file at a time, at the lowest priority:** at weekends, in quiet hours or any time, with Pause and Resume
- **On the dashboard:** what is being converted, what is next and how much space it has saved
- **A logo and a status on its cards:** the grey band at the top of each card says whether it is converting, waiting, paused or done, and when it last changed.
- **Updates safely:** before an update it stops the file being converted, which is converted again afterwards, and starts no new one.

## How an update is kept safe

- **Before the update** Starboard asks Direct play to get ready: it stops the file being converted, removes its unfinished copy and starts no new file, as **Pause fixing** does. The original stays as it was. If a file is still being converted after 30 seconds, it says "A file is still being converted. Try again in a minute" and nothing changes.
- **After the update,** or after a Roll back, it carries on, and converts that file again from the start.
- Starboard waits for the new version to answer. If it does not, Starboard goes back to the version you had by itself, with your settings as they were.
- Your settings and its folder are kept.

## Update it

1. Go to **Settings**, then **Plug-ins**. When a newer version is known, Direct play has an **Update** chip in **Manage**.
2. Select **Direct play** to open its tab.
3. In **Versions**, select **Update to** and the new version.
4. Read **What is new since** your version and **How the update is kept safe**, enter your Starboard password, and select **Update Direct play**.
5. When the dialog says it is updated, select **Done**.

## Roll it back

1. On Direct play's tab, in **Versions**, select **Roll back to** and the version you had.
2. Enter your Starboard password and select **Roll back**.
3. When the dialog says it is back on that version, select **Done**.

Rolling back needs no download, and only one earlier version is kept.

## Find out more

- [Update a plug-in and roll it back, in Starboard's help](https://themightytrex.github.io/starboard/help/topics/update-a-plugin.html)
- [Direct play's changes, in full](../../../direct-play/CHANGELOG.md)
- [Problems](problems.md)
