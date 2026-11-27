# Changelog

## Unreleased

### Changed
- The status page's copy of the TRex Design System (`ds.css`) is up to date with the library: the second level menu row condenses when the names do not fit, and the unused cover card, cover actions and book row styles are gone. No change to what the page shows.

## 2.1.0 (25 November 2026)

### Added
- A certificate check: `Site: cert example.org` watches a certificate alone, with no web request. It is up while the certificate is good and says the days left, and down when it has run out or is not trusted. The alert some days before it ends is the one already set under Warn when a certificate has this long left.

## 2.0.0 (20 November 2026)

### Added
- More kinds of check: a port (tcp), ping (with a knock on common ports where ping is not allowed), a DNS record, and words on a web page (keyword), beside web addresses.
- Heartbeats: a push check gives an address for a backup or a script to call; no call within its grace time means down.
- 90 days of history: response times and uptime an hour and a day, about 43 KB a check, with no database.
- Certificates for every https address and every port checked with tls: the days left and the names it was issued for.
- Groups, tags and maintenance windows: write in Home after a check; a group's alerts pause in its maintenance windows.
- Alerts through Starboard, to where it sends its own, once when a check is down and once when it is up again.
- A status page on your home network, which only shows names, up or down, response times and uptime.
- Three more cards: Groups, Response times (a small line for each check) and Certificates.

### Changed
- Outside services is now Uptime and status. Your Addresses to check and Check every stay as they were and are checked as before, in the group Outside services.
- Needs Starboard with plug-in API 1.17 or later, for the Response times card and the alerts. A Starboard with an older plug-in API keeps version 1.1.4.
- Its own image, with the status page's files, in place of the image the examples share.

## 1.1.4 (19 November 2026)

### Changed
- Reaches Starboard on any network: with Starboard 0.23.0 or later it calls Starboard through a socket in its own folder, so it works on its own closed network too. An older Starboard works as before.

## 1.1.3 (17 November 2026)

### Changed
- Clearer words: the band says Not answering, and the card names each one. Its description spells out NAS.
- Logo description: where its logo stands on its own, a screen reader says "Outside services logo", the plug-in's name, instead of a description of the symbol.

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
- Up or down for things that are not on this server: your router, a NAS (network storage device), a website.
