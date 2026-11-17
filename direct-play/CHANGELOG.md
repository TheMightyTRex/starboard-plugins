# Changelog

## 1.0.3 (17 November 2026)

### Changed
- Clearer words: Look at the library now is now Check the library now, and the size settings are Shrink 1080p files over, Shrink 720p files over and Shrink smaller files over. Its messages put the settings they name in quotation marks.
- Logo description: where its logo stands on its own, a screen reader says "Direct play logo", the plug-in's name, instead of a description of the symbol.

## 1.0.2 (17 November 2026)

### Fixed
- Jellyfin 12: it sends Jellyfin's key the way Jellyfin 12 asks for it, so Jellyfin no longer refuses its library refreshes and other requests where legacy authorisation is off. Older Jellyfin still works.


## 1.0.1 (16 November 2026)

### Changed
- Lighter at rest: it wakes about once a minute while nothing asks it anything, not twice a second; its minute's look for work reads its settings once, not about ninety times; and it writes nothing to its folder when a run goes well.
- Starts faster: its image comes with Python's modules already compiled, so a start takes about a quarter of the processor time.
- Lighter dashboard card: the cards and the minute's look for work no longer read every file's details each time; with 50,000 files the card answers in about 4 ms instead of 230 ms, and about 45 MB less memory is held.


## 1.0.0 (14 November 2026)

### Added
- Plays directly on the devices you choose: Rokus, Fire TV Sticks, Chromecast, smart TV apps, web browsers, Apple TV
  and Nvidia Shield.
- Four fixes, cheapest first: repackages the wrong container, adds a sound track your devices play beside the
  original, shrinks very large H.264 files and converts old formats to H.264.
- Checked before it replaces: the length, the picture, the first sound track and where sound and picture start; a
  file that fails is left as it was.
- One file at a time, at the lowest priority: at weekends, in quiet hours or any time, with Pause and Resume.
- On the dashboard: what is being converted, what is next and how much space it has saved.
