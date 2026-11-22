# Changelog

## 1.3.0 (22 November 2026)

### Added
- New this week, by email: a weekly email of what was added to Jellyfin: films, episodes, albums and books, with titles and years only and no pictures. You choose the day and the hour, and it can go by email alone or by every way you activated.

### Changed
- Deactivated at first: New this week is now deactivated until you activate it under What to send. Send New this week on is replaced by When to send New this week, one setting for the day and the hour.

## 1.2.0 (19 November 2026)

### Added
- Disk changes: a message whenever a disk is erased, added to the pool or taken out of it, however it was asked for, so an erase you did not start reaches you at once. Needs Starboard with plug-in API 1.16 or later; an older Starboard keeps 1.1.3.

## 1.1.4 (19 November 2026)

### Changed
- Reaches Starboard on any network: with Starboard 0.23.0 or later it calls Starboard through a socket in its own folder, so it works on its own closed network too. An older Starboard works as before.

## 1.1.3 (17 November 2026)

### Changed
- Clearer words: each channel's switch says what to enter before you activate it, the band says Not sent, and a message about an event it does not know says "Starboard has an alert. Open Starboard for the details."
- Logo description: where its logo stands on its own, a screen reader says "Notifications logo", the plug-in's name, instead of a description of the symbol.

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
- Updates safely: before an update it finishes what it is doing and starts nothing new.

### Changed
- Needs Starboard with plug-in API 1.14 or later. A Starboard with an older plug-in API keeps version 1.0.0.

## 1.0.0 (13 November 2026)

### Added
- Seven ways to send: email, Telegram, Discord, Signal (through signal-cli-rest-api), Pushover, ntfy and Apprise-style webhooks, each with a Test button.
- What it sends: a request ready to watch (to the person who asked too), a failed download, an app down and back, a disk nearly full, an update ready, and New this week.
- Plain words with no meaning in symbols, and links with words before them.
- Rests between messages: Starboard's events and its daily job wake it, so it uses no memory while idle.
