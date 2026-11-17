# TV station

Your own TV channels in Jellyfin's Live TV, made from your films and series. Each channel runs to a schedule, like
broadcast television: choose a channel and you join it at the point it has reached, part way through a programme if
that is what is on. Between programmes, the breaks have idents, trailers, your own clips and Coming up next cards,
and each channel can have its own on-screen logo.

Starboard never adds it by itself: you choose to add it from the catalogue.

## What it does

- **A station and its channels.** You name the station, and each channel: its name, number, logo and colour.
- **What each channel shows.** Series, films, collections, playlists, genres or decades from Jellyfin, in order or
  shuffled, with up to 6 episodes of a series in a row. Programmes run back to back, or start on the quarter, half or
  whole hour with a break filling the time to it. New episodes join the line-up at the end of the programme on air.
- **Breaks.** Idents for each channel or for the whole station, in order or in a random order; Jellyfin's own
  trailers of the films on the channel; your own clips; and Coming up next and Later cards with the programme's
  picture, title, the date and time it is shown and a short synopsis. At the end of each programme, Up next shows
  during the end credits.
- **The on-screen logo (the DOG).** The channel's logo or name, or the station's name, in the corner you choose,
  with its size, distance from the edge and opacity. It can show always, only during programmes, or during
  programmes and cards; fade in after the opening; have a clock beside it; and a New, Repeat or Live label in words.
  A backing plate keeps it clear on any picture. The station sets it for every channel, and each channel can have
  its own. **Preview a frame** opens a frame drawn with the settings.
- **In Jellyfin's Live TV, first.** Its channels are numbered from 1 in your order, before the free channels from
  101, with a 7-day guide: titles, episode names, synopses, pictures, and New or Repeat.

## How it stays light

- **Nothing runs while nobody watches.** The schedule is worked out from the time, the line-up and a fixed seed
  (the idea comes from [Clickarr](https://github.com/thegregstengel/clickarr), MIT, an Android TV app; no code is
  copied). The guide is worked out when Jellyfin asks for it, about once a day.
- **A stream starts only when a channel is chosen,** at the right point, and stops 30 seconds after the last viewer
  leaves. People watching the same channel share one stream.
- **One conversion for each channel being watched,** at 720p unless you choose 1080p, and at most 2 channels at once
  unless you change it. A channel with no on-screen logo and no straps copies its programmes with no converting.
- **Measured** (17 November 2026, as Starboard runs it): 16.4 MiB of memory and no measurable processor (0.00%) at rest;
  while one channel played at 720p with the on-screen logo, about 140 MiB and 0.9 of a processor core.

## What it may do

- It uses Jellyfin's key, which Starboard keeps, to read your films and series, play them, and add its channels and
  guide to Jellyfin's Live TV.
- It reaches your home network, and has its own web page on it, at a port Starboard chooses. Jellyfin reads the
  channel list, the guide and the streams there, at addresses with a random word in them that only Jellyfin is given.
- It runs one container with 768 MB of memory and 2 processor cores at most.
- It keeps its channels, idents, clips and logos in its own folder. It never changes your films, series or Jellyfin's
  library.

## Add it

Needs Starboard with plug-in API 1.15 or later, and Jellyfin added in **Settings**, then **Apps**. In Starboard, go
to **Settings**, then **Plug-ins**, then **Catalogue**, and find it under **Jellyfin**. Then:

1. On its page, select **Open** once, so it knows the address Jellyfin can reach it at.
2. In **Channels**, add a channel, open it and add a series, film, collection or playlist.
3. In Jellyfin's Live TV, your channels are first in the list.

The [help pages](https://themightytrex.github.io/starboard-plugins/help/plugins/tv-station/index.html) have each step.

Or, under **Add one from elsewhere**, give this address:

`https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/tv-station/starboard-plugin.json`

Or run `python3 install.py` in this folder.

## Removing it

Removing it keeps its folder, with its channels and clips, in `data/plugins/.removed` or the holding folder. Its
channels stay in Jellyfin's Live TV list with nothing to play until you remove the tuner named after the station in
Jellyfin's **Live TV** settings.

## Credits

- The idea of a channel as a function of time, and of line-ups that change at a programme's end: Clickarr, by
  thegregstengel, MIT.
- The font on the television: Atkinson Hyperlegible Next, SIL Open Font License 1.1 (`LICENSE-OFL.txt`).
- FFmpeg, LGPL and GPL, from Alpine Linux.
