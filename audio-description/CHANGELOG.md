# Changelog

## 1.2.2 (17 November 2026)

### Fixed
- Jellyfin 12: it sends Jellyfin's key the way Jellyfin 12 asks for it, so Jellyfin no longer refuses its requests where legacy authorisation is off. Older Jellyfin still works.


## 1.2.1 (16 November 2026)

### Changed
- Lighter at rest: it wakes about once a minute while nothing asks it anything, not twice a second, and writes nothing to its folder when a run goes well.
- Starts faster: its image comes with Python's modules already compiled, so a start takes about a quarter of the processor time.


## 1.2.0 (15 November 2026)

### Added
- A logo in Settings, Plug-ins, in the Catalogue and on its dashboard cards.
- Its cards say how things are: a status and when they last changed, in the grey band at the top of each card.
- Updates safely: before an update it finishes what it is doing and starts nothing new.

### Changed
- Needs Starboard with plug-in API 1.14 or later. A Starboard with an older plug-in API keeps version 1.1.0.

## 1.1.0 (13 November 2026)

### Added
- AudioVault search links: for each film and series without audio description, a link to AudioVault's own search.
  Deactivated until you activate it in Sources; Starboard never downloads from AudioVault.
- YouDescribe search links: for each film and series, a link to YouDescribe's own search, where volunteers describe
  YouTube videos such as trailers.
- MovieReading and Earcatch: how to use these phone apps alongside Jellyfin, which play a description in step by
  listening, and where to get them.

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
