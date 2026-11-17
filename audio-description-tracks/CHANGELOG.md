# Changelog

## 1.1.3 (17 November 2026)

### Fixed
- Jellyfin 12: it sends Jellyfin's key the way Jellyfin 12 asks for it, so Jellyfin no longer refuses its requests where legacy authorisation is off. Older Jellyfin still works.


## 1.1.2 (16 November 2026)

### Changed
- Lighter at rest: it wakes about once a minute while nothing asks it anything, not twice a second.
- Starts faster: its image comes with Python's modules already compiled, so a start takes about a quarter of the processor time.


## 1.1.1 (15 November 2026)

### Fixed
- Its card says when it last looked: the grey band now shows when it last looked in the folder or a track last changed. Before, it never showed a time.

## 1.1.0 (15 November 2026)

### Added
- A logo in Settings, Plug-ins, in the Catalogue and on its dashboard cards.
- Its card says how things are: a status and when it last changed, in the grey band at the top of the card.
- Updates safely: before an update it finishes adding the track it is on and starts no other.

### Changed
- Needs Starboard with plug-in API 1.14 or later. A Starboard with an older plug-in API keeps version 1.0.0.

## 1.0.0 (13 November 2026)

### Added
- Add a description track you already have: put it in the audio-description folder in your media folder, or upload
  it, and it is matched to its film or episode by name.
- Lengths checked: added only when the track and the film are the same length, within the seconds you choose;
  otherwise it says the track is probably for another cut.
- Added as an extra sound track next to the film, named English (Audio Description), with the visual impaired flag;
  the film file is not changed.
- Nothing deleted: the original moves to Confirmed once you say it plays in step, and a wrong track moves to Taken off.
