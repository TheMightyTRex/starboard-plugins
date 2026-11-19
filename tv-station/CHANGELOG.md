# Changelog

## 0.2.1 (19 November 2026)

### Added
- Choose the hours a suggestion fills: Suggest a schedule asks for the hours to fill on weekdays and at the weekend, such as 18:00 to 23:00, and fills them one programme after another, leaving out one that would run past the end. The hours are remembered for each channel.

## 0.2.0 (19 November 2026)

Parts marked Starboard 0.23.0 need Starboard 0.23.0 (plug-in API 1.16); with an older Starboard those pages are as in 0.1.1.

### Added
- Choose from your library (Starboard 0.23.0): a slide-out on a channel's What it shows card lists every series, film, collection, playlist, genre and decade in Jellyfin, a page at a time, with search and a filter for each kind; tick several and add them at once. Those already on the channel show as added.
- A holding slide: upload a picture, or a video of up to 60 seconds, for the station or for one channel, with a countdown to the next programme and its name, Back soon, or no words. It loops at the end of each break, after the promos, until the next programme starts, drawn with FFmpeg like the cards and timed to the second.
- Music for promos: upload MP3, M4A, OGG or FLAC music for the station or for one channel, checked with FFmpeg and levelled to -23 LUFS, listed and removed. Promos use it with the pack's music, or in its place, as Music the promos use says. A channel with music but no pack promo gets plain promos on its colour.
- Jellyfin's guide: the Guide page says when Jellyfin last read the guide and how many programmes it had, and Refresh Jellyfin's guide in Actions asks it to read it again.
- Suggest a schedule asks what to make the week from: Watch history, General watch history, All TV, All films or TV and Films, remembered for each channel. suggest.py takes --from too.
- A logo shows on its row as a small picture, with words, once uploaded; so does the station pack's on-screen logo.

### Changed
- Channels in cards (Starboard 0.23.0): each channel is a card in the list, and an opened channel has a card each for its name and number, what it shows, its breaks, its on-screen logo and branding, its holding slide and promos, and today and tomorrow, each saying what it is for.
- Changes save in place (Starboard 0.23.0): a change answers with that channel only, so the page keeps the open channel, where you were and focus, and says what was saved beside it, such as Corner: Bottom left.
- Renaming the station renames its tuner in Jellyfin's Live TV.
- Idents and clips is now Idents, clips and music, with the station's holding slide and music for promos.

### Fixed
- The schedule grid opens (Starboard 0.23.0): Open the schedule grid uses the address Starboard was opened with, at the plug-in's port, so it opens from a server name or another address, not only the home network address the plug-in knows. With no channels, the grid page says to add one in place of failing to draw.

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
