# Changelog

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
