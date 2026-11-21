# Create your own TV channel

Your own TV channels in Jellyfin's Live TV, made from your films and series. Each channel runs to a schedule, like
broadcast television: choose a channel and you join it at the point it has reached, part way through a programme if
that is what is on. Between programmes, the breaks have idents, trailers, promos, your own clips and Coming up next
cards, and a broadcast pack gives the channels your own branding: the on-screen logo, the logo with its music, idents,
transitions and the card and promo backgrounds. Try the example pack, Example TV, to find out how it works.

Its id and folder stay `tv-station`, so nothing that already uses it changes.

**Works in a desktop browser.** Setting up channels, the schedule grid and the broadcast pack are made for a computer; on a phone or tablet the grid says to use a computer. The dashboard card works anywhere.

Starboard never adds it by itself: you choose to add it from the catalogue.

## What it needs, and what it leaves alone

- **It needs [Starboard](https://github.com/TheMightyTRex/starboard).** It is a Starboard plug-in, added from Starboard's plug-in catalogue, with Jellyfin added in Starboard in **Settings**, then **Apps**. It does not run on its own.
- **It works alongside the \*arr stack.** Sonarr, Radarr and the rest go on adding films and series as they do; the plug-in reads films and series from Jellyfin only, so whatever reaches Jellyfin can be on a channel.
- **It never changes other apps or your library.** Your films, series, their files and Jellyfin's library, watched marks and **Continue watching** stay as they are. Its only change to Jellyfin is adding its channels and their guide to Live TV.

## Help

- [Its pages in the help centre](https://themightytrex.github.io/starboard/help/plugins/tv-station/index.html): install, every setting with an example of its result, the dashboard card and problems.
- [Use a broadcast pack](../help/use/use-a-broadcast-pack.md): add a pack to the station or a channel, replace or remove it, and try the example pack.
- [Make a broadcast pack](../help/use/make-a-broadcast-pack.md): step by step, with the template, the placement guides, every file, `pack.json` and what each problem means.

## What it does

- **A station and its channels.** You name the station, and each channel: its name, number, logo and colour.
- **What each channel shows.** Series, films, collections, playlists, genres or decades from Jellyfin, ticked in a
  slide-out that lists every one (Choose from your library, Starboard 0.23.0 and later), in order or shuffled, with up to 6 episodes of a series in a row. Programmes run back to back, or start on the quarter, half or
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
- **Animation on and off.** The Coming up next and Later cards, the straps, the on-screen logo, the clock, the label
  and the holding slide's words can fade, slide in from the left, the right or the bottom, wipe or grow, and go off
  the same ways, quick, normal or slow: for every channel on the **Animation** page, or for one channel, or as its
  broadcast pack says. Each has a **Preview**, a few seconds of it. Timing stays exact: nothing runs past its end.
- **A broadcast pack.** One zip with set names: `logo/dog.png` for the on-screen logo, `logo/logo-with-music.mp4` as
  a sting, `idents/identNN.mp4` played in a random order, `coming-next/background.mp4` and `promo/background.mp4` with
  a clip area and text fields placed in `pack.json`, music beds in `promo/music`, and transitions with transparency in
  `transitions`. The station has one, and each channel can have its own. Every file is checked before it is used. The
  plug-in's page offers the template, placement guides that mark where the clip, each text field and the safe areas
  go, and the example pack. [Use a broadcast pack](../help/use/use-a-broadcast-pack.md) says how to add one, and [Make a broadcast pack](../help/use/make-a-broadcast-pack.md) how to make one.
- **Promos.** Made in quiet hours from a few short clips of a programme coming up, a music bed you upload or from the pack, and its
  title, channel and day and time from the schedule. Each channel keeps 3 unless you change it, and old ones are
  replaced after 2 days. They play on their own channel and on your other channels.
- **A holding slide.** A picture or short video, with a countdown to the next programme or Back soon, that loops at
  the end of each break until the next programme starts, so the channel never shows black.
- **A schedule grid.** A week for each channel in 15 minute steps: drag films and series onto it, or use buttons and
  the keyboard; copy a day; stripe a series across weekdays with a number of episodes a day; choose where a series
  starts; or suggest a week from watch history, everyone's history, all TV, all films or both (`suggest.py`, also a script). Empty times keep the automatic line-up.
- **It remembers what it has played.** Each channel keeps what it played to someone watching, so From the next
  episode not watched passes over an episode watched on the channel, 70% or more of it. Jellyfin's own watched marks
  are never changed.
- **In your language.** English unless you change it, or French, German, Spanish, Italian, Portuguese, Dutch,
  Swedish, Danish or Norwegian: the words drawn on the picture and in the guide, the sound track where a
  programme has one in that language, and film and series titles and descriptions, read from the film database through
  Jellyfin for programmes about to be shown, at most 60 an hour, and kept.
- **In Jellyfin's Live TV, first.** Its channels are numbered from 1 in your order, before the free channels from
  101, with a 7-day guide: titles, episode names, synopses, pictures, and New or Repeat.

## How it stays light

- **Nothing runs while nobody watches.** The schedule is worked out from the time, the line-up and a fixed seed
  (the idea comes from [Clickarr](https://github.com/thegregstengel/clickarr), MIT, an Android TV app; no code is
  copied). The guide is worked out when Jellyfin asks for it, about once a day.
- **A stream starts only when a channel is chosen,** at the right point, and stops 30 seconds after the last viewer
  leaves. People watching the same channel share one stream.
- **Promos are made one at a time,** by one FFmpeg at the lowest priority with one thread, in Starboard's quiet
  hours, and never while anyone is watching: a channel starting stops it at once.
- **One conversion for each channel being watched,** at 720p unless you choose 1080p, and at most 2 channels at once
  unless you change it. A channel with no on-screen logo and no straps copies its programmes with no converting.
- **Measured** (17 November 2026, as Starboard runs it): 16.4 MiB of memory and no measurable processor (0.00%) at rest;
  while one channel played at 720p with the on-screen logo, about 140 MiB and 0.9 of a processor core.
  With animation (0.3.0, 19 November 2026, the plug-in's image with 2 cores and 768 MB, one 720p piece at real time,
  two runs each): a programme with the logo, clock, label and straps animating used 0.92 to 0.97 of a core against
  1.03 to 1.09 with none, so no measurable increase, and about 4 MiB more memory; a card animating used 0.43 of a
  core against 0.79 to 0.82, as its darkening is worked out in YUV, with about 25 MiB more memory while it plays.

## What it may do

- It uses Jellyfin's key, which Starboard keeps, to read your films and series, play them, and add its channels and
  guide to Jellyfin's Live TV.
- It reaches your home network, and has its own web page on it, at a port Starboard chooses. Jellyfin reads the
  channel list, the guide and the streams there, at addresses with a random word in them that only Jellyfin is given.
- With a language other than English, it asks Jellyfin's remote search (which asks the film database, TMDB) for the
  titles of programmes about to be shown, and keeps them in its folder. Nothing in Jellyfin is changed.
- It runs one container with 768 MB of memory and 2 processor cores at most.
- It keeps its channels, idents, clips, logos, broadcast packs and promos in its own folder. Nothing in a pack is run:
  its pictures and sounds are only read by FFmpeg. It never changes your films, series or Jellyfin's
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
- The example pack, Example TV: made in code by `example_pack.py`, its logo, pictures and music included. Free to use.
- FFmpeg, LGPL and GPL, from Alpine Linux.
