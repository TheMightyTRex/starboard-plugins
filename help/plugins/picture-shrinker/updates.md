# Picture shrinker: Updates

Picture shrinker 1.2.3 is the latest version. It needs Starboard with plug-in API 1.14 or later.

## Versions

| Version | Needs plug-in API | Released |
|---|---|---|
| 1.2.3 | 1.14 or later | Not released yet |
| 1.2.2 | 1.14 or later | 17 November 2026 |
| 1.2.1 | 1.14 or later | 17 November 2026 |
| 1.2.0 | 1.14 or later | 17 November 2026 |
| 1.1.1 | 1.14 or later | 16 November 2026 |
| 1.1.0 | 1.14 or later | 15 November 2026 |
| 1.0.0 | 1.14 or later | 15 November 2026 |

The catalogue offers each Starboard the newest version it can run, so an older Starboard keeps an earlier version.

## What is new in 1.2.2

Added:

- **Space saved by type:** a dashboard card. For each type of picture it shows the space saved and how many were shrunk. The types include posters, backdrops and photos of cast and crew. It also shows the last run.
- **Saved by type** in its settings: a table of the same figures, with the size before and now. Earlier versions did not count by type, so pictures shrunk before 1.2.2 share one row.

Changed:

- **Space saved card:** with nothing shrunk yet, it says so and tells you what to do next. Choose a backup in Original pictures first, then select Shrink now or wait for the next run.
- **Sizes as Starboard shows them:** a kilobyte is 1,024 bytes in its words too. The figures on its cards and pages now agree with the number Starboard draws on the Space saved card.
- **Light as before:** both cards read the figures it keeps after each run. It measures and scans nothing when a card asks.

## What is new in 1.2.1

Changed:

- **Clearer words:** **Just shrink, with no backup** is now **Shrink without a backup**. The card's band says **Scheduled**, and the card says when it runs next.
- **Logo description:** where its logo stands on its own, a screen reader says "Picture shrinker logo", the plug-in's name. It no longer describes the symbol.

## What is new in 1.2.0

Added:

- **Choose the backup:** Original pictures asks whether to keep a backup copy of each original or just shrink. It asks once when you add the plug-in and again after this update. It shrinks nothing until you choose, and it keeps any backup you already have.
- **Start again** in its actions, for the pictures it shrinks or for every picture. It deletes the backup and the records, and has Jellyfin download the pictures again at full size. If Jellyfin cannot download a picture again, the plug-in puts it back after a day.
- **Every picture type:** posters, photos of people, backdrops, thumbnails, logos, banners, disc art and clear art. Each has its own size. The plug-in activates them all when you add it. Shrink all picture types shrinks them all in one setting. Lentzeris asked for backdrops in the Jellyfin version's issue #2.

Changed:

- **Rules 1.2:** the same rules file as the Jellyfin version.

Removed:

- **Back up each original before it is replaced:** replaced by Original pictures.

After this update, open Picture shrinker's tab and choose in **Original pictures**: until you do, it shrinks nothing and its card says **Choose a backup**.

## What is new in 1.1.1

Changed:

- **Lighter at rest:** it wakes about once a minute while nothing asks it anything, not twice a second.
- **Starts faster:** its image comes with Python's modules already compiled, so a start takes about a quarter of the processor time.

## What is new in 1.1.0

Added:

- **Backup first:** it copies each original to the plug-in's own folder before its first shrink. It does not shrink a picture whose original it cannot back up.
- **Restore original pictures** and **Delete backup** in its actions; **Space saved** shows the pictures now, the backup and the space saved.
- **Quality**, posters and photos of people are settings, as in the Jellyfin version.
- **Stays idle when Jellyfin's own Picture shrinker is installed,** so the two never shrink the same pictures. To find that out, it reads Jellyfin's list of plug-ins with Jellyfin's key.

Changed:

- **Quiet when it finishes:** a run changes only the figures on its card and page; the card no longer shows a problem status.

## What is new in 1.0.0

Added:

- **Shrinks Jellyfin's pictures:** posters to 900 pixels tall and photos of cast and crew to 400 pixels wide, both settings. Smaller pictures are left alone.
- **Checked before it replaces:** each picture is written beside the original, opened again and checked, and swapped in only when it is smaller.
- **When you choose:** every day, week or month at a time, with Shrink now, at the lowest priority.
- **New pictures in quiet hours:** deactivated unless you activate it.
- **Space saved:** on its page and on a dashboard card.

## How an update is kept safe

- **Before the update** Starboard asks Picture shrinker to get ready. It stops after the picture it is on and starts no new run, so nothing is left half done. If a picture is still being shrunk, it says "A picture is still being shrunk. Try again in a minute" and nothing changes.
- **After the update,** or after a Roll back, it says when the next run is. That run carries on where the last one stopped.
- Starboard waits for the new version to answer. If it does not, Starboard goes back to the version you had by itself, with your settings as they were.
- Starboard keeps your settings and its folder.

## Update it

1. Go to **Settings**, then **Plug-ins**. When a newer version is known, Picture shrinker shows an **Update** chip in **Manage**.
2. Select **Picture shrinker** to open its tab.
3. In **Versions**, select **Update to** and the new version.
4. Read **What is new since** your version and **How the update is kept safe**, enter your Starboard password, and select **Update Picture shrinker**.
5. When the dialog says it is updated, select **Done**.

## Roll it back

1. On Picture shrinker's tab, in **Versions**, select **Roll back to** and the version you had.
2. Enter your Starboard password and select **Roll back**.
3. When the dialog says it is back on that version, select **Done**.

Rolling back needs no download, and only one earlier version is kept.

## Find out more

- [Update a plug-in and roll it back, in Starboard's help](https://themightytrex.github.io/starboard/help/topics/update-a-plugin.html)
- [Picture shrinker's changes, in full](../../../picture-shrinker/CHANGELOG.md)
- [Problems](problems.md)
