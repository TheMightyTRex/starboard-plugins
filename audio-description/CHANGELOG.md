# Changelog

## 1.1.0 (13 November 2026)

### Added
- AudioVault search links: for each film and series without audio description, a link to AudioVault's own search.
  Deactivated until you activate it in Sources; Starboard never downloads from AudioVault.
- YouDescribe search links: for each film and series, a link to YouDescribe's own search, where volunteers describe
  YouTube videos such as trailers.

### Changed
- Audio description elsewhere: each place is now a link that opens in a new tab.

## 1.0.0 (13 November 2026)

### Added
- Finds the films and series in Jellyfin with a described sound track, once a night in quiet hours.
- Adds an Audio description format to Reelix and prefers it in every video quality level, while Prefer releases with
  audio description is activated.
- People who want audio description: Jellyfin remembers the sound track each of them chooses.
- Audio description elsewhere: places with audio description in their own apps.
- Two dashboard cards: how many titles are described, and the newest ten found.
