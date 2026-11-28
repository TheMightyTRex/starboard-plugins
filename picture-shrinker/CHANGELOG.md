# Changelog

## 1.2.4 (28 November 2026)

### Changed
- Turn on and turn off: the text and the help pages now say turn on and turn off. How it works has not changed.

## 1.2.2 (17 November 2026)

### Added
- Space saved by type: a dashboard card with the space each type of picture saved, such as posters, backdrops and photos of cast and crew, how many of each were shrunk, and the last run.
- Saved by type in its settings: a table of the same figures, with the size before and now. Pictures shrunk before 1.2.2 were not counted by type, so they share one row.

### Changed
- Space saved card: with nothing shrunk yet, it says so and what to do next: choose a backup in Original pictures first, then Shrink now or the next run. Its note no longer runs past what the card shows.
- Sizes as Starboard shows them: a kilobyte is 1,024 bytes in its words too, so the figures on its cards and pages agree with the number Starboard draws on the Space saved card.
- Light as before: both cards read the figures kept after each run; nothing is measured or scanned when a card asks.

## 1.2.1 (17 November 2026)

### Changed
- Clearer words: Just shrink, with no backup is now Shrink without a backup. The card's band says Scheduled, and the card says when it runs next.
- Logo description: where its logo stands on its own, a screen reader says "Picture shrinker logo", the plug-in's name, instead of a description of the symbol.

## 1.2.0 (17 November 2026)

### Added
- Choose the backup: Original pictures asks whether to keep a backup copy of each original or just shrink, once it is added and again after this update. Nothing is shrunk until you choose; a backup you already have is kept.
- Start again in its actions, for the pictures it shrinks or for every picture: deletes the backup and the records, and has Jellyfin download the pictures again at full size. A picture Jellyfin cannot download again is put back after a day.
- Every picture type: posters, photos of people, backdrops, thumbnails, logos, banners, disc art and clear art, each with its own size and all activated when you add it, with Shrink all picture types to shrink them all in one setting. Backdrops were asked for by Lentzeris in the Jellyfin version's issue #2.

### Changed
- Rules 1.2: the same rules file as the Jellyfin version (SYNC.md in its repository).

### Removed
- Back up each original before it is replaced: replaced by Original pictures.

## 1.1.1 (16 November 2026)

### Changed
- Lighter at rest: it wakes about once a minute while nothing asks it anything, not twice a second.
- Starts faster: its image comes with Python's modules already compiled, so a start takes about a quarter of the processor time.


## 1.1.0 (15 November 2026, not released)

### Added
- Backup first: each original is copied to the plug-in's own folder before its first shrink, and a picture whose original cannot be backed up is not shrunk. Activated by default.
- Restore original pictures and Delete backup in its actions; Space saved shows the pictures now, the backup and the space saved.
- Quality, posters and photos of people are settings, as in the Jellyfin version.
- Stays idle when Jellyfin's own Picture shrinker is installed, so the two never shrink the same pictures. To see that, it reads Jellyfin's list of plug-ins with Jellyfin's key.

### Changed
- Rules 1.1: the same rules file and shared test pictures as the Jellyfin version (SYNC.md in its repository).
- Quiet when it finishes: a run changes only the figures on its card and page; the card no longer shows a problem status.

## 1.0.0 (15 November 2026)

### Added
- Shrinks Jellyfin's pictures: posters to 900 pixels tall and photos of cast and crew to 400 pixels wide, both settings. Smaller pictures are left alone.
- Checked before it replaces: each picture is written beside the original, opened again and checked, and swapped in only when it is smaller.
- When you choose: every day, week or month at a time, with Shrink now, at the lowest priority.
- New pictures in quiet hours: deactivated unless you activate it.
- Space saved: on its page and on a dashboard card.
