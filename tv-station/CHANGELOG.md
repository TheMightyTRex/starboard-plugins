# Changelog

## 0.1.1 (19 November 2026)

### Changed
- Its address for Jellyfin fills in by itself: with Starboard 0.23.0 and later, Starboard gives it its address on your home network, so Jellyfin's Live TV works without opening its page first. The setting is only for a different address.

### Fixed
- Channel names and numbers are accepted: with Starboard 0.23.0 and later, Add a channel, Rename and Change number take plain text, not only web addresses.

## 0.1.0 (17 and 18 November 2026)

Named Create your own TV channel (18 November 2026); its id and folder stay tv-station.

### Added
- Your own channels: name the station and each channel, with its number, logo and colour, and fill it from series, films, collections, playlists, genres or decades, in order or shuffled, with episodes of a series in a row.
- In Jellyfin's Live TV, first: numbered from 1 in your order, with a 7-day guide of titles, episode names, synopses, pictures and New or Repeat. Tuning in joins part way through, as on television.
- Breaks: idents, Jellyfin's trailers, your own clips, and Coming up next and Later cards with the programme's picture, title, date and time and a short synopsis.
- On-screen logo: the channel's logo or name in a corner you choose, with its size, opacity, a clock, a New, Repeat or Live label and a backing plate, for the station or each channel, with a preview.
- Light: nothing runs until someone chooses a channel, viewers of a channel share one stream, and it stops 30 seconds after the last one leaves.
- Broadcast pack: your own branding from a zip made from the template: the on-screen logo, the logo with its music as a sting, idents in a random order, transitions with transparency at each cut between programme and break, and Coming up next and promo backgrounds with the words drawn where pack.json says. Every file is checked before it is used. The station has one, and each channel can have its own.
- Schedule grid: a week for each channel in 15 minute steps; drag films and series onto it, or use buttons and the keyboard; copy a day; stripe a series across weekdays; choose where a series starts; suggest a week from watch history (suggest.py, also a script). Empty times keep the automatic line-up. Works in a desktop browser.
- Try the example pack: Example TV, made in code by example_pack.py, and offered as a download.
- Promos: made in quiet hours from short clips of a programme coming up, a music bed from the pack and its day and time from the schedule, kept and replaced as the settings say, and shown on the other channels too.
- Downloads: the template, with pack.json, pack.schema.json and a README, and placement guides for the Coming up next card, the promo and the on-screen logo.

### Changed
- The on-screen logo's distance from the side is a share of the picture's width, so Inside the safe area is inside the title safe area at the sides too.
- The stream carries on from the end of what it sent, so nothing is sent twice or passed over between pieces, and every looped input stops a second after its piece.
