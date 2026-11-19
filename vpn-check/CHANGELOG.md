# Changelog

## 1.1.4 (19 November 2026)

### Changed
- Reaches Starboard on any network: with Starboard 0.23.0 or later it calls Starboard through a socket in its own folder, so it works on its own closed network too. An older Starboard works as before.

## 1.1.3 (17 November 2026)

### Changed
- Clearer words: the hint and the card's example use addresses kept for examples, and the hint says the card says Problem, not what colour it turns.
- Logo description: where its logo stands on its own, a screen reader says "VPN check logo", the plug-in's name, instead of a description of the symbol.

## 1.1.2 (17 November 2026)

### Changed
- Shared helper: the helper every example shares sends Jellyfin's key the way Jellyfin 12 asks for it. This plug-in does not ask Jellyfin anything, so it works as before.

## 1.1.1 (16 November 2026)

### Changed
- Lighter at rest: it wakes about once a minute while nothing asks it anything, not twice a second, and writes nothing to its folder when a run goes well.
- Starts faster: its image comes with Python's modules already compiled, so a start takes about a quarter of the processor time.

## 1.1.0 (15 November 2026)

### Added
- A logo in Settings, Plug-ins, in the Catalogue and on its dashboard cards.
- Its cards say how things are: a status and when they last changed, in the grey band at the top of each card.

### Changed
- Needs Starboard with plug-in API 1.14 or later. A Starboard with an older plug-in API keeps version 1.0.0.

## 1.0.0 (12 November 2026)

### Added
- Shows the address and country your downloads use through the VPN, and warns if it is your home address.
