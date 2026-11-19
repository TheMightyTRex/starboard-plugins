# Create your own TV channel: Settings

Create your own TV channel's settings are on its tab in **Settings**, then **Plug-ins**. Choices save as soon as you make them. Its pages, **Channels**, **Guide**, **Schedule grid**, **Idents, clips and music** and **Broadcast pack**, open from the same tab. A change saves in place: the page stays where it was, with the channel open, and says what was saved beside what you changed.

## Channels

**Channels** lists your channels, each on a card with its number, its name, whether it is on air and what is on now. Select a channel to open it. An opened channel has a card for each part of it, each saying what it is for: **Name and number**, **What it shows**, **Breaks**, **On-screen logo and branding**, **Holding slide and promos**, and **Today and tomorrow**.

### Add a channel

1. In **Add a channel**, enter its name, such as Comedy, and select **Add a channel**.
2. Open it. On the **What it shows** card, select **Choose from your library**. A slide-out opens.
3. Select **Series**, **Films**, **Collections**, **Playlists**, **Genres** or **Decades**: each lists every one Jellyfin has, 100 at a time, with **Show more** for the rest. Enter words in **Search by name** to narrow the list.
4. Tick each one you want. Ticks are kept as you change kind or search, and the ones on the channel already show as added.
5. Select **Add the ticked ones**. The slide-out closes, focus goes back to **Choose from your library**, and the card says what was added.

With Starboard before 0.23.0 there is no slide-out: the card has **Add a series**, **Add a film** and the rest, each taking a name.

Its line-up is read from Jellyfin straight away. The programmes for today and tomorrow are listed at the end of the channel's page, under **Today and tomorrow**.

### Each channel's settings

| Card | Setting | What it does |
|---|---|---|
| Name and number | **On air** | Activate to put it in Jellyfin's Live TV. **Up** and **Down** move it in the list, which sets its number. **Remove** takes it off; its settings are kept in the plug-in's folder |
| Name and number | **Name** | Select **Rename**. Shown in Jellyfin, in the guide and on the television |
| Name and number | **Number** | Select **Change number**. Leave it empty to number it by its place in the list |
| Name and number | **Colour** | On its Coming up next cards, its made logo and its plain promos |
| On-screen logo and branding | **Broadcast pack** | **The station's pack**, **Its own pack** or **No pack**. The pack gives the on-screen logo, idents, the logo with music, transitions, the Coming up next card and promos |
| On-screen logo and branding | **Its own pack** | Select **Upload its own pack** and choose a zip made from the template. Then choose **Its own pack** |
| On-screen logo and branding | **Logo** | Select **Add logo** and choose a PNG with a clear background. It is used in place of the pack's logo. With neither, a logo with its number and name is made. The logo in use shows on the card as a small picture |
| What it shows | Each series, film, collection, playlist, genre or decade | **Up** and **Down** set the order; **Remove** takes it off |
| What it shows | **Order** | **In order** plays each series in aired order, taking turns. **Shuffled** plays them in a new order each time round |
| What it shows | **Episodes of a series in a row** | From 1 to 6 |
| Breaks | **Programmes start** | **Back to back**, or on the quarter, half or whole hour, with a break filling the time to it |
| Breaks | **Break between programmes** | Up to 5 minutes after each programme |
| Breaks | **Idents** | This channel's, the station's, both, or none |
| Breaks | **Idents play** | In order, or in a random order. A broadcast pack's idents always play in a random order |
| Breaks | **Trailers** | Jellyfin's own trailers of the films on this channel |
| Breaks | **Your clips** | This channel's, the station's, both, or none |
| Breaks | **Add an ident**, **Add a clip** | Choose a video of up to 60 MB, or enter the name of a Jellyfin collection or folder of them. A clip can be up to 10 minutes |
| On-screen logo and branding | Every on-screen logo setting | **Station default** uses the station's choice, which the option names |
| On-screen logo and branding | **Preview a frame** | Opens a frame of what is on now, drawn with the settings, in a new tab |
| On-screen logo and branding | **Preview a Coming up next card** | Opens the next card, in a new tab |
| Holding slide and promos | **Holding slide** | **The station's holding slide**, **Its own holding slide** or **No holding slide**. The slide loops at the end of each break, after the promos, until the next programme starts, so the channel never shows black. With none, breaks end on Coming up next cards |
| Holding slide and promos | **Its own holding slide** | Select **Upload a holding slide** and choose a PNG or JPEG picture, or a video of up to 60 seconds and 60 MB, which loops. It is checked with FFmpeg first |
| Holding slide and promos | **Words on the slide** | **A countdown to the next programme** (Next programme in 4:32, with the programme's name, reaching 0:00 as it starts), **Back soon** or **No words**. **Station default** uses the choice in Idents, clips and music |
| Holding slide and promos | **Preview the holding slide** | Opens a frame of the slide with its words, in a new tab |
| Holding slide and promos | **Promos** | How this channel's promos are made: with its pack's promo, or on its colour with your music, or none yet |
| Holding slide and promos | **Add music for its promos** | Select **Upload music** and choose an MP3, M4A, OGG or FLAC file of 5 seconds to 10 minutes. Used for this channel's promos in place of the station's music |

A change to what a channel shows, its order or its times starts after the programme on air ends, so nobody watching meets a jump.

## Guide

**Guide** starts by saying when Jellyfin last read the guide, and how many programmes on how many channels it had, so you can tell Jellyfin has it. It then has a table for each channel: what is on in the next 24 hours, with the time, the programme, the episode, New or Repeat, and what it is about. Jellyfin's own guide has 7 days.

## Schedule grid

**Schedule grid** lists your channels, each with an **Open the schedule grid** link that opens its grid in a new tab, on the plug-in's own page, in a desktop browser. From Starboard 0.23.0 the link uses the address you opened Starboard with. The grid is: a week, Monday to Sunday, in 15 minute steps. Films and series placed on it play at those times every week; the time between them keeps the channel's automatic line-up, whole programmes only, and the rest is a break. A channel with nothing on its grid is as it was. The guide in Jellyfin follows the grid.

| On the grid | What it does |
|---|---|
| **Channel**, **Show** and **Day** | Which channel, and the whole week or one day |
| **Add a programme**, or an empty time | Search Jellyfin, choose a film or series, its day and time and, for a series, where it starts: from the first episode, from the next episode not watched, or from a series and episode |
| Drag a programme to an empty time | Moves it. Everything a drag does can also be done without one: select a programme for **Move 15 minutes earlier**, **Move 15 minutes later**, **Move to** a day and time, or **Pick it up, then choose a time** and select an empty time |
| **Stripe across the week** | On a series: the same time on the weekdays you choose, 1 to 4 episodes each day, Saturday and Sunday too if you choose. Each slot plays the next episode in order, and the next week carries on |
| **Where the series starts** | The first episode, the next episode not watched, or an episode you choose, from this week |
| **Copy a day** | Copies one day to the days you choose, in place of what was on them |
| **Suggest a schedule** | Asks what to make the week from, then proposes it. **Watch history**: the channel's own series and films people have watched, as its settings say. **General watch history**: everything anyone has watched, whatever the channel shows. **All TV**: series from the whole library, every day. **All films**: a film from the whole library every evening. **TV and Films**: series on weekdays and films at the weekend, from the whole library. The most watched come first. The choice is remembered for each channel. Nothing is saved until you select **Save the suggestion**; **Discard the suggestion** keeps the grid as it was |
| **Undo** | Takes back the last change |

A programme takes the time of its longest episode, rounded up to 15 minutes, so programmes never run into each other. A change that would overlap another programme is refused, and the message names it. In the grid, the arrow keys move between times and days, Page Up and Page Down by an hour, and Enter opens a programme's actions or adds one at an empty time.

## Idents, clips and music

The station's own idents and clips, for every channel that chooses **The station's** or **Both**. Add a video of up to 60 MB, or the name of a Jellyfin collection or folder of them.

| Setting | What it does |
|---|---|
| **The station's holding slide** | Select **Upload a holding slide** and choose a PNG or JPEG picture, or a video of up to 60 seconds and 60 MB. Every channel without its own slide uses it |
| **Words on the slide** | A countdown to the next programme, Back soon, or no words. Each channel can choose its own |
| **Music the promos use** | **Your music and the pack's**, **Only your music** or **Only the pack's music**. A channel's own music comes first. With no music of the kind chosen, the other is used |
| **Add music for promos** | Select **Upload music** and choose an MP3, M4A, OGG or FLAC file of 5 seconds to 10 minutes and up to 60 MB, up to 20 tracks. Each is checked with FFmpeg and played at the same loudness as the rest. **Remove** in its More menu takes it off |

With music here, a channel whose pack has no promo, or that has no pack, gets plain promos: the programme's clips and words on the channel's colour.

## Broadcast pack

Your own branding for every channel: the on-screen logo, the logo with its music, idents, transitions, and backgrounds for the Coming up next card and the promos, with music for the promos. [Make a broadcast pack](../../use/make-a-broadcast-pack.md) has the specification.

| Row | What it does |
|---|---|
| **Station's pack** | Select **Upload a pack** and choose a zip of up to 60 MB made from the template. It is checked first; when it passes, every channel without a pack of its own uses it. **Remove** stops using it |
| **Try the example pack** | Activate to use Example TV, a made-up channel drawn in code, for every channel without a pack of its own. The first time, it takes about 2 minutes to make, while no channel is playing. Deactivate to go back to your own pack, or none |
| **The last pack checked** | What the check found: each problem with a pack that was not used, or notes on one that was, such as a picture scaled to fit |
| **Downloads** | The template (folders, `pack.json`, its schema and a README), the placement guides for the Coming up next card, the promo and the on-screen logo, and the example pack as a zip |
| **Promos kept** | Each promo, with its programme, its day and time and its channel |
| **Each channel's pack** | Which pack each channel uses. Change it on the channel's page |

## Station

| Setting | What it does |
|---|---|
| **Station name** | Shown in Jellyfin's Live TV, on the cards and with the on-screen logo. Home TV unless you change it. A new name is given to its tuner in Jellyfin's Live TV too |
| **First channel number** | 1 puts your channels first in Jellyfin's Live TV, before the free channels from 101 |
| **Address Jellyfin uses to reach this plug-in** | Filled in by itself: Starboard 0.23.0 and later give the plug-in its address on your home network. Enter one only if Jellyfin runs on another computer that reaches this one by another address |
| **Days in Jellyfin's guide** | 7 unless you change it, up to 14 |

## Streaming

| Setting | What it does |
|---|---|
| **Picture size** | 720p is lighter on the processor; 1080p is sharper |
| **Most channels at once** | Each channel being watched is one conversion. People watching the same channel share it. 2 unless you change it |
| **Stop a channel after the last viewer leaves** | 30 seconds unless you change it |
| **Copy programmes when nothing is drawn on them** | A channel with no on-screen logo and no straps plays its programmes as they are, with no converting |

## Promos

Promos are made only for channels whose broadcast pack has a promo background.

| Setting | What it does |
|---|---|
| **Make promos in quiet hours** | In Starboard's quiet hours, one at a time at the lowest priority, and never while anyone is watching: a few short clips of a programme coming up, a music bed from the pack, and its title, day and time and channel. Activated unless you change it |
| **Promos kept for each channel** | 3 unless you change it, up to 6 |
| **Replace each promo after** | 2 days unless you change it. A promo is also replaced once its programme has started, so they never pile up |
| **Show promos for your other channels** | Each channel's breaks show the promos of your other channels too. Activated unless you change it |

## On-screen logo

The station's choices, which every channel uses unless it has its own.

| Setting | What it does |
|---|---|
| **On-screen logo** | The channel's logo, the channel's name, the station's name, or none |
| **Corner** | Which corner of the picture it sits in |
| **Size** | Small, medium or large |
| **Distance from the edge** | **Inside the safe area** keeps it in the picture on every television |
| **Opacity** | From 30% to 100%. 80% unless you change it |
| **When it shows** | Always; only during programmes; or during programmes and cards, not in idents, trailers and clips |
| **Fades in after the opening** | Keeps a programme's opening titles clear |
| **Clock** | The time beside the logo |
| **Label** | New or Repeat, or Live, in words, for the first 2 minutes of each programme |
| **Backing plate** | A dark, partly transparent box behind the logo, the clock and the label, so they are clear on any picture. Activated unless you change it |

## Straps and cards

| Setting | What it does |
|---|---|
| **Programme name at the start** | For 8 seconds as each programme starts |
| **Up next during the end credits** | The next programme and its time |
| **Up next shows for** | 30 seconds unless you change it |
| **Coming up next and Later cards** | In the breaks: the programme's picture, its title, the date and time it is shown and a short synopsis. Deactivated, a break with no clips shows the station's name |

## Actions

- **Try the example pack:** makes Example TV, if it is not made yet, and uses it for every channel without a pack of its own.
- **Make promos now:** makes any promos that are due, one at a time at the lowest priority, unless someone is watching. They are also made each hour of Starboard's quiet hours.
- **Refresh Jellyfin's guide:** asks Jellyfin to read the channel list and the guide again now. The **Guide** page says when Jellyfin last read the guide and how many programmes it had.
- **Read the channels from Jellyfin again:** reads every channel's line-up now. It also runs each night at 04:40, so new episodes join.
- **Stop every channel playing:** stops every stream now. Anyone watching can choose the channel again.

## Find out more

- [Dashboard card](dashboard-card.md)
- [Problems](problems.md)
