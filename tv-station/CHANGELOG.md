# Changelog

## 0.5.5 (19 November 2026)

### Added
- Leave out 3D films (owner, 19 November 2026: "I dont want any 3d films as it plays as 2 images"), Yes unless changed: a film Jellyfin marks as 3D, or whose file name says 3D (3D, SBS, HSBS, HOU and the like), is left out of every channel's line-up when it is read. As some 3D films are named like any film (the owner's Cloudy with a Chance of Meatballs was), a new quiet-hours job, Check films for 3D, also checks each film on the channels once: two frames, at 30% and 60%, compared half against half for two pictures side by side or one over the other, at the lowest priority and never while anyone is watching (it stops at once when someone starts). What it finds is kept in three_d.json, and a channel with a film found to be 3D is read again, so the film is left out. Reading a channel says how many 3D films were left out.

### Fixed
- Read the channels from Jellyfin again (and the nightly refresh) now brings each programme's details up to date even when the line-up has the same programmes: which sound track it plays (the 0.5.4 fix reaches line-ups read before it), its title, episode, plot and pictures. What the timing rests on (each programme's id, length, series and kind) is never changed this way, so the schedule stays exactly as it was. Before, a line-up with the same programmes was kept as it was.

## 0.5.4 (19 November 2026)

### Fixed
- A programme with an external subtitle file showed only the fallback card, the station's and channel's names (owner, 19 November 2026: "Late ink just shows a card with the words T-Rex TV - late ink on it"). The plug-in mapped the programme's sound by Jellyfin's stream Index, which counts external files such as an .srt beside the video (often as 0), so in a file with an embedded subtitle FFmpeg was asked to use a subtitle as sound and stopped ("Encoder not found"), and every try fell back to the card. The sound is now mapped as the default track's place among the file's own sound tracks (0:a:N), for programmes and for clips from Jellyfin. Line-ups read before 0.5.4 use the first sound track until they are read again (the daily refresh, or Read the channels from Jellyfin again).

## 0.5.3 (19 November 2026)

### Fixed
- A broadcast pack's logo was refused as having no transparent parts when the check could not run, because the plug-in was busy (FFmpeg did not start). The check now tries again up to three times, and if it still cannot run it says the logo could not be read at the moment and to upload the pack again in a minute.

## 0.5.2 (19 November 2026)

### Added
- The station's logo on promos (owner, 19 November 2026: "I want the T-Rex TV logo to also show somewhere in the promos"): a promo made with a channel's own pack, or a plain design, shows the station pack's logo/dog.png small in the top right corner (an eighth of the width, inside the title safe area, above the clip area), fading in with the clips. Promos made with the station's own pack carry it already, so they are unchanged. Show the station's logo on promos (Yes unless changed) turns it off. Promos already made keep their look until they are replaced.

## 0.5.1 (19 November 2026)

### Fixed
- A channel's promos are made again when its broadcast pack changes. Each promo now records the design it was made with (the pack, and when it was checked, or the plain colour); one made with a design the channel no longer uses is not shown in any break, and is removed and made again in the next quiet hour. Before, a promo made minutes before a new pack arrived kept the old pack's look for up to two days. Promos made before 0.5.1 are kept.

## 0.5.0 (19 November 2026)

### Added
- Promos and clips in each break (owner, 19 November 2026: "up to 2, 3, 4 or 6 promos and clips per break; the holding slide fills the rest"): a choice on each channel's Breaks card, Up to 3 unless changed. Each promo, trailer and clip plays once at most in a break, in a random order, where a long break repeated the same few until it was full.
- Extra videos (owner: "an additional space to upload custom video to fit in after the promos ... as many additional videos as I want and it plays at random"): upload videos of up to 10 minutes and 90 MB for the station (Idents, clips and music) or for one channel (its Breaks card), as many as you like. One plays at random after the promos in each break when it fits. Extra videos on each channel chooses this channel's, the station's, both or none.

### Changed
- A break between programmes (owner: "New program would play bumper, promos, holding slide, ident"): a bumper, the promos and clips, an extra video, the holding slide (or cards, or a slate), and the ident with its music immediately before the new programme. The closing bumper of 0.4.0 is gone.
- A break inside a programme (owner: "Breaks should play bumper, promos, holding slide, bumper. Not an ident"): a bumper, the promos and clips, an extra video, the holding slide with Back soon for the rest of its time (No words when the slide has none), and a bumper. Without a holding slide it is as long as what plays.

## 0.4.0 (19 November 2026)

### Added
- Bumpers (owner, 19 November 2026: "a very short version of the ident but with no music"): a broadcast pack may have bumpers/bumper01.mp4 and on, 0.5 to 10 seconds, up to 20, in pack.json and pack.schema.json as "bumpers". One opens and one closes every break; any sound in them is not played.
- Breaks inside programmes (owner: "use the video to guess where the break would be"): Breaks inside programmes on a channel's Breaks card, Off unless chosen, or up to 1, 2 or 3 minutes each. A new quiet-hours job, Find breaks inside programmes, looks at the programmes each such channel airs in the next 48 hours, once each: Jellyfin's Commercial media segments first, else FFmpeg listens to the sound alone for silences and checks 3 seconds of a small picture round each of the 12 longest for a black frame. Points between 20% and 85% of the running time, 8 minutes apart, at most 1, 2 or 3 by length, nearest to even spacing. Kept in breaks.json. Each break inside is a bumper, trailers or promos that fit, and a bumper, and is left out when nothing fits; its time comes from the end break, so the schedule never moves. The programme is played in parts, each starting where the last stopped.

### Changed
- A break's order (owner: "It should play at the start and end of the break only. The Ident should just play before the program"): a bumper, trailers, clips and promos, the holding slide (or cards, or a slate), a bumper, then one ident with its music immediately before the next programme. When a break is short the ident comes first, then the bumpers. The logo with music no longer opens the break; it plays before the programme when there are no idents.
- A transition plays at every cut between a programme, or a part of it, and a break.
## 0.3.2 (19 November 2026)

### Added
- Create initial schedule (owner, 19 November 2026): a button on a channel's What it shows card, with the hours to fill (Weekdays 18:00 to 23:00, weekends 12:00 to 23:00 unless changed). It makes a week from the channel's own series and films, in its order and whether watched or not: series one after another on weekdays, each the next episode every day, and films at the weekend. The week is kept as the schedule grid's unsaved suggestion, so a saved grid stays as it is until the new one is saved; the row links to the grid.
- This channel's line-up, a new choice in Suggest a schedule on the grid page, does the same from the grid.

## 0.3.1 (19 November 2026)

### Changed
- Preview a frame of a Coming up next card or a promo is taken 1.5 seconds into the pack's background video, where it took the first frame, so a background that opens with a movement (such as the T-Rex TV pack's bands sweeping off) shows as it rests. Streams are unchanged.

## 0.3.0 (19 November 2026)

### Added
- Animation on and off (owner, 19 November 2026): the Coming up next and Later cards, the straps, the on-screen logo, the clock, the New, Repeat or Live label and the words on the holding slide each come on and go off with None, Fade, Slide from the left, the right or the bottom, Wipe or Grow, at Quick (0.3 seconds), Normal (0.6) or Slow (1). Chosen on the new Animation page for every channel, or on a channel's Animation card. Each thing is drawn on a small layer of its own and moved by FFmpeg's overlay with expressions of t, faded with the fade filter, wiped with a moving crop and grown with a scale, so None draws exactly as before and timing stays inside each thing's own time.
- A Preview for each animation: a few seconds as MP4, drawn with the choices saved, over a made-up picture, in a new tab.
- Broadcast packs: an optional animation part in pack.json and pack.schema.json, in the template, its README and the placement guides. The settings come first when chosen.
- What each channel has played (owner, 19 November 2026): for each episode and film, when it was on and how many seconds were streamed to someone watching, in a small file for each channel (the newest 5,000, written about once a minute while it plays). An episode with 70% or more played counts as watched for From the next episode not watched, with Count what this channel has played as watched (Yes unless changed). Nothing is sent to Jellyfin.
- Played on this channel, a card on each channel: the last 5 programmes, the setting, and Remove to forget the record.

- Promos with the programme's sound (owner, 19 November 2026): each clip plays with its own sound, brought to -23 LUFS, and the music falls to 20% under it (Music under the programme's sound: 10%, 20%, 30% or 50%), at full before the first clip and after the last. Use the programme's sound in promos (Yes unless changed) turns it off; a programme with no sound FFmpeg can read gets the music alone.
- Promo length: As the pack says, or 10, 15, 20, 30, 45 or 60 seconds. Clips in each promo: by its length (about one every 5 seconds) or 2 to 6, from different parts of the programme, moved a little for each promo so two seldom show the same moments.
- Background loops for promos: upload videos of 2 to 60 seconds, or pictures, up to 90 MB and 20 of each, for the station in Idents, clips and music and for one channel on its Holding slide and promos card. Each promo chooses one at random from the channel's, the station's and its pack's promo background. Music or a loop alone is enough for plain promos.

### Changed
- Promos take their clips from 12% to 78% of the programme, as many as their length needs, where they took three from fixed places.
- From the next episode not watched starts at the first episode, in the channel's order, that is neither played in Jellyfin nor watched on the channel, where it took the first not played in Jellyfin's order before.

## 0.2.1 (19 November 2026)

### Added
- Choose the hours a suggestion fills: Suggest a schedule asks for the hours to fill on weekdays and at the weekend, such as 18:00 to 23:00, and fills them one programme after another, leaving out one that would run past the end. The hours are remembered for each channel.

### Changed
- Longer holding slides: a holding slide's video may be up to 120 seconds and 90 MB. Starboard 0.24.1 or later takes files that big; an older Starboard stops at 60 MB.

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
