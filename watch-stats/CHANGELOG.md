# Changelog

## 1.1.4 (19 November 2026)

### Changed
- Reaches Starboard on any network: with Starboard 0.23.0 or later it calls Starboard through a socket in its own folder, so it works on its own closed network too. An older Starboard works as before.

## 1.1.3 (17 November 2026)

### Changed
- Clearer words: Read the figures again now is now Check now, as on the other plug-ins.
- Logo description: where its logo stands on its own, a screen reader says "Watch statistics logo", the plug-in's name, instead of a description of the symbol.

## 1.1.2 (17 November 2026)

### Fixed
- Jellyfin 12: it sends Jellyfin's key the way Jellyfin 12 asks for it, so Jellyfin no longer refuses its requests where legacy authorisation is off. Older Jellyfin still works.

## 1.1.1 (16 November 2026)

### Changed
- Lighter at rest: it wakes about once a minute while nothing asks it anything, not twice a second, and writes nothing to its folder when a run goes well.
- Starts faster: its image comes with Python's modules already compiled, so a start takes about a quarter of the processor time.

## 1.1.0 (15 November 2026)

### Added
- A logo in Settings, Plug-ins, in the Catalogue and on its dashboard cards.
- Its cards say how things are: a status and when they last changed, in the grey band at the top of each card.
- Updates safely: before an update it finishes what it is doing and starts nothing new.

### Changed
- Needs Starboard with plug-in API 1.14 or later. A Starboard with an older plug-in API keeps version 1.0.0.

## 1.0.0 (13 November 2026)

### Added
- Three tables: recent plays by day, top titles and people, each to read only, with search and sorting.
- Four cards: plays this week, top titles, who watched most, and where the figures come from.
- Reads Jellyfin's Playback Reporting with one query, so a Full install can go without Jellystat and its PostgreSQL.
- Without Playback Reporting it says so and how to add it, and shows each person's last plays from Jellyfin itself.
- Rests when not in use, and keeps each answer for 15 minutes.
