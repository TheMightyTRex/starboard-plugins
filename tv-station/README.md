# Create your own TV channel

Your own TV channels in Jellyfin's Live TV, made from your films and series.

Each channel runs to a schedule, like broadcast television. When you choose a channel, you join it at the point it has
reached, which may be part way through a programme. Between programmes, the breaks have short title clips, trailers, coming-up trailers, your
own clips and Coming up next cards. Branding gives the channels your own branding: the corner logo, the logo
with its music, short title clips, transitions and the card and coming-up trailer backgrounds. Try the example pack, Example TV, to find out
how it works.

Its id and folder stay `tv-station`, so nothing that already uses it changes.

**Works in a desktop browser.** Use a computer to set up channels, the schedule grid and the branding. This page is for a
computer screen. It is not made for phones. The plug-in's own pages say so on a narrow screen. The dashboard card works anywhere.

Starboard never adds it by itself. You choose to add it from the catalogue.

## What it needs, and what it leaves alone

- **It needs [Starboard](https://github.com/TheMightyTRex/starboard).** It is a Starboard plug-in. You add it from
  Starboard's plug-in catalogue, and you add Jellyfin in Starboard in **Settings**, then **Apps**. It does not run on
  its own.
- **It works alongside the \*arr stack.** Sonarr, Radarr and the rest go on adding films and series as they do. The
  plug-in reads films and series from Jellyfin only, so whatever reaches Jellyfin can be on a channel.
- **It never changes other apps or your library.** Your films, series, their files, Jellyfin's library, watched marks
  and **Continue watching** stay as they are. Its only change to Jellyfin is to add its channels and their guide to
  Live TV.

## Help

- [Its pages in the help centre](https://themightytrex.github.io/starboard/help/plugins/tv-station/index.html): install, every setting with an example of its result, the dashboard card and problems.
- [Use branding](../help/use/use-a-broadcast-pack.md): add a pack to the station or a channel, replace or remove it, and try the example pack.
- [Make branding](../help/use/make-a-broadcast-pack.md): step by step, with the template, the placement guides, every file, `pack.json` and what each problem means.

## What it does

- **A station and its channels.** You name the station and each channel. A channel has a name, number, logo and colour.
- **What each channel shows.** You tick series, films, collections, playlists, genres or decades from Jellyfin in a
  slide-out that lists every one (**Choose from your library**, Starboard 0.23.0 and later). Programmes play in order
  or shuffled, with up to 6 episodes of a series in a row. They run back to back, or start on the quarter, half or
  whole hour with a break filling the time to it. New episodes join the line-up at the end of the programme on air.
- **Break layouts** (0.8.0). Each channel has two grids, In between programmes and Breaks, with up to 7 columns each.
  The modes are Random, Sequence, Day of week, and Morning, afternoon and evening. You drag these items into the
  columns, and say how many times each is shown: Very short title clip, Coming-up trailer, Your own short videos, Short title clip, Other channel coming-up trailer, Coming soon coming-up trailer,
  Waiting screen countdown and Back soon. The grids also work from the keyboard and with buttons. A channel that has not
  changed its grids plays as before.
- **Where breaks go inside a programme** (0.8.0). Breaks can go at silence, at set times or at the end of a scene, with
  your choice of how many in each 30 minutes and in a film. The plug-in finds the places once for each programme in the
  quiet hours and keeps them in a small file. It searches for nothing while a channel streams.
- **Breaks.** A break can have these:
  - Short title clips for each channel or for the whole station, in order or in a random order.
  - Jellyfin's own trailers of the films on the channel.
  - Your own clips.
  - Coming up next and Later cards, with the programme's picture, title, the date and time it is shown and a short
    synopsis.

  At the end of each programme, Up next shows during the end credits.
- **The corner logo (the DOG).** It shows the channel's logo or name, or the station's name, in the corner you
  choose. You set its size, distance from the edge and opacity. It can show always, only during programmes, or during
  programmes and cards. It can fade in after the opening and have a clock beside it. It can also have a New, Repeat or
  Live label in words. A dark box behind the logo keeps it clear on any picture. The station sets it for every channel, and each
  channel can have its own. **Preview a frame** opens a frame drawn with your settings.
- **Animation on and off.** These can fade in, slide in from the left, the right or the bottom, wipe or grow, and go
  off the same ways, quick, normal or slow:
  - the Coming up next and Later cards
  - the title bars
  - the corner logo
  - the clock
  - the label
  - the waiting screen's words

  You set this for every channel on the **Animation** page, for one channel, or as its branding says. Each has a
  **Preview**, a few seconds long. Timing stays exact: nothing runs past its end.
- **Branding.** This is one zip with set names:
  - `logo/dog.png` for the corner logo
  - `logo/logo-with-music.mp4` as a sting
  - `idents/identNN.mp4`, played in a random order
  - `coming-next/background.mp4` and `promo/background.mp4`, with a clip area and text fields placed in `pack.json`
  - music beds in `promo/music`
  - transitions with transparency in `transitions`

  The station has one pack, and each channel can have its own. The plug-in checks every file before it uses it. Its
  page offers the template, placement guides that mark where the clip, each text field and the safe areas go, and the
  example pack. [Use branding](../help/use/use-a-broadcast-pack.md) says how to add one, and
  [Make branding](../help/use/make-a-broadcast-pack.md) says how to make one.
- **Coming-up trailers.** The plug-in makes them in quiet hours. Each uses a few short clips of a programme coming up, a background music
  you upload or take from the pack, and the title, channel, day and time from the schedule. Each channel keeps 3 unless
  you change it, and replaces old ones after 2 days. They play on their own channel and on your other channels.
- **A waiting screen.** This is a picture or short video with a countdown to the next programme or Back soon. It loops at
  the end of each break until the next programme starts, so the channel never shows black.
- **A schedule grid.** The grid shows a week for each channel in 15 minute steps. You can:
  - drag films and series onto it, or use buttons and the keyboard
  - copy a day
  - stripe a series across weekdays, with a number of episodes a day
  - choose where a series starts
  - suggest a week from watch history, everyone's history, all TV, all films or both (`suggest.py`, also a script)

  Empty times keep the automatic line-up.
- **It remembers what it has played.** Each channel keeps what it played to someone watching. So **From the next
  episode not watched** passes over an episode that someone watched on the channel, 70% or more of it. The plug-in
  never changes Jellyfin's own watched marks.
- **In your language.** The language is English unless you change it. You can choose French, German, Spanish,
  Italian, Portuguese, Dutch, Swedish, Danish or Norwegian. The language covers three things:
  - the words drawn on the picture and in the guide
  - the sound track, where a programme has one in that language
  - film and series titles and descriptions, which come from the film database through Jellyfin for programmes about to
    be shown, at most 60 an hour, and are kept
- **Audio description on coming-up trailers**, when you turn it on. A voice says each coming-up trailer's words, the title, the channel, the
  day and the time, so a blind viewer hears more than music. A small speech program in the image makes it on your
  server. Nothing is sent anywhere.
- **In Jellyfin's Live TV, first.** Its channels are numbered from 1 in your order, before the free channels from 101.
  The 7-day guide has titles, episode names, synopses, pictures, and New or Repeat.

## How it stays light

- **Nothing runs while nobody watches.** The plug-in works out the schedule from the time, the line-up and a fixed seed.
  The idea comes from [Clickarr](https://github.com/thegregstengel/clickarr), MIT, an Android TV app. No code is
  copied. It works out the guide when Jellyfin asks for it, about once a day.
- **A stream starts only when a channel is chosen,** at the right point. It stops 30 seconds after the last viewer
  leaves. People watching the same channel share one stream.
- **Coming-up trailers are made one at a time,** by one FFmpeg at the lowest priority with one thread, in Starboard's quiet
  hours. Nothing is made while anyone is watching: a channel starting stops it at once.
- **One server work for each channel being watched,** at 720p unless you choose 1080p. At most 2 channels convert at
  once unless you change it. A channel with no corner logo and no title bars copies its programmes with no converting.
- **Measured** (17 November 2026, as Starboard runs it): 16.4 MiB of memory and no measurable processor (0.00%) at
  rest. While one channel played at 720p with the corner logo, it used about 140 MiB and 0.9 of a processor core.
- **Measured with animation** (0.3.0, 19 November 2026, the plug-in's image with 2 cores and 768 MB, one 720p piece at
  real time, two runs each):
  - A programme with the logo, clock, label and title bars animating used 0.92 to 0.97 of a core. With none animating it
    used 1.03 to 1.09. So there was no measurable increase, and about 4 MiB more memory.
  - A card animating used 0.43 of a core, against 0.79 to 0.82 with none. The plug-in works out its darkening in YUV.
    It used about 25 MiB more memory while the card plays.

## What it may do

- It uses Jellyfin's key, which Starboard keeps, to read your films and series, play them, and add its channels and
  guide to Jellyfin's Live TV.
- It reaches your home network, and has its own web page on it, at a port Starboard chooses. Jellyfin reads the
  channel list, the guide and the streams there. The addresses have a random word in them, and only Jellyfin is given
  them.
- With a language other than English, it asks Jellyfin's remote search for the titles of programmes about to be shown,
  and keeps them in its folder. Jellyfin's remote search asks the film database, TMDB. Nothing in Jellyfin is changed.
- It runs one container with 768 MB of memory and 2 processor cores at most.
- It keeps its channels, short title clips, clips, logos, branding and coming-up trailers in its own folder. Nothing in a pack is run:
  FFmpeg only reads its pictures and sounds. It never changes your films, series or Jellyfin's library.

## Add it

You need Starboard with plug-in API 1.15 or later, and Jellyfin added in **Settings**, then **Apps**. In Starboard, go
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
channels stay in Jellyfin's Live TV list with nothing to play. To clear them, remove the tuner named after the station
in Jellyfin's **Live TV** settings.

## Credits

- The idea of a channel as a function of time, and of line-ups that change at a programme's end: Clickarr, by
  thegregstengel, MIT.
- The font on the television: Atkinson Hyperlegible Next, SIL Open Font License 1.1 (`LICENSE-OFL.txt`).
- The example pack, Example TV: made in code by `example_pack.py`, its logo, pictures and music included. Free to use.
- FFmpeg, LGPL and GPL, from Alpine Linux.
