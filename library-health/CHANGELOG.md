# Changelog

## 1.1.2 (17 November 2026)

### Fixed
- Jellyfin 12: it sends Jellyfin's key the way Jellyfin 12 asks for it, so Jellyfin no longer refuses its requests where legacy authorisation is off. Older Jellyfin still works.

## 1.1.1 (16 November 2026)

### Changed
- Lighter at rest: it wakes about once a minute while nothing asks it anything, not twice a second, and writes nothing to its folder when a run goes well.
- Starts faster: its image comes with Python's modules already compiled, so a start takes about a quarter of the processor time.

### Fixed
- Large libraries: it asks Jellyfin a page of 500 titles at a time, so a large library no longer makes the check fail.

## 1.1.0 (15 November 2026)

### Added
- A logo in Settings, Plug-ins, in the Catalogue and on its dashboard cards.
- Its cards say how things are: a status and when they last changed, in the grey band at the top of each card.
- Updates safely: before an update it finishes what it is doing and starts nothing new.

### Changed
- Needs Starboard with plug-in API 1.14 or later. A Starboard with an older plug-in API keeps version 1.0.0.

## 1.0.0 (12 November 2026)

### Added
- Films and series in Jellyfin with no poster, no description or no year, so you can fix them.
