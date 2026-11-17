# TV station: Settings

TV station's settings are on its tab in **Settings**, then **Plug-ins**. Choices save as soon as you make them. Its pages, **Channels**, **Guide** and **Idents and clips**, open from the same tab.

## Channels

**Channels** lists your channels, each with its number, its name and what is on now. Select a channel to open it.

### Add a channel

1. In **Add a channel**, enter its name, such as Comedy, and select **Add**.
2. Open it. Under **What it shows**, select **Add a series**, **Add a film**, **Add a collection**, **Add a playlist**, **Add a genre** or **Add a decade**.
3. Enter the name, or the start of it, and select **Add**. TV station finds it in Jellyfin and says what it added, and any other matches.

Its line-up is read from Jellyfin straight away. The programmes for today and tomorrow are listed at the end of the channel's page, under **Today and tomorrow**.

### Each channel's settings

| Section | Setting | What it does |
|---|---|---|
| Channel | **On air** | Activate to put it in Jellyfin's Live TV. **Up** and **Down** move it in the list, which sets its number. **Remove** takes it off; its settings are kept in the plug-in's folder |
| Channel | **Name** | Select **Rename**. Shown in Jellyfin, in the guide and on the television |
| Channel | **Number** | Select **Change number**. Leave it empty to number it by its place in the list |
| Channel | **Colour** | On its Coming up next cards and its made logo |
| Channel | **Logo** | Select **Add logo** and choose a PNG with a clear background. With none, a logo with its number and name is made |
| What it shows | Each series, film or collection | **Up** and **Down** set the order; **Remove** takes it off |
| Order and times | **Order** | **In order** plays each series in aired order, taking turns. **Shuffled** plays them in a new order each time round |
| Order and times | **Episodes of a series in a row** | From 1 to 6 |
| Order and times | **Programmes start** | **Back to back**, or on the quarter, half or whole hour, with a break filling the time to it |
| Order and times | **Break between programmes** | Up to 5 minutes after each programme |
| Breaks | **Idents** | This channel's, the station's, both, or none |
| Breaks | **Idents play** | In order, or in a random order |
| Breaks | **Trailers** | Jellyfin's own trailers of the films on this channel |
| Breaks | **Your clips** | This channel's, the station's, both, or none |
| Breaks | **Add an ident**, **Add a clip** | Choose a video of up to 60 MB, or enter the name of a Jellyfin collection or folder of them. A clip can be up to 10 minutes |
| On-screen logo and straps | Every on-screen logo setting | **Station default** uses the station's choice, which the option names |
| On-screen logo and straps | **Preview a frame** | Opens a frame of what is on now, drawn with the settings, in a new tab |
| On-screen logo and straps | **Preview a Coming up next card** | Opens the next card, in a new tab |

A change to what a channel shows, its order or its times starts after the programme on air ends, so nobody watching meets a jump.

## Guide

**Guide** has a table for each channel: what is on in the next 24 hours, with the time, the programme, the episode, New or Repeat, and what it is about. Jellyfin's own guide has 7 days.

## Idents and clips

The station's own idents and clips, for every channel that chooses **The station's** or **Both**. Add a video of up to 60 MB, or the name of a Jellyfin collection or folder of them.

## Station

| Setting | What it does |
|---|---|
| **Station name** | Shown in Jellyfin's Live TV, on the cards and with the on-screen logo. Home TV unless you change it |
| **First channel number** | 1 puts your channels first in Jellyfin's Live TV, before the free channels from 101 |
| **Address Jellyfin uses to reach this plug-in** | Filled in when you select **Open** on its tab. Enter it yourself only if Jellyfin runs on another computer that reaches this one by another address |
| **Days in Jellyfin's guide** | 7 unless you change it, up to 14 |

## Streaming

| Setting | What it does |
|---|---|
| **Picture size** | 720p is lighter on the processor; 1080p is sharper |
| **Most channels at once** | Each channel being watched is one conversion. People watching the same channel share it. 2 unless you change it |
| **Stop a channel after the last viewer leaves** | 30 seconds unless you change it |
| **Copy programmes when nothing is drawn on them** | A channel with no on-screen logo and no straps plays its programmes as they are, with no converting |

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

- **Read the channels from Jellyfin again:** reads every channel's line-up now. It also runs each night at 04:40, so new episodes join.
- **Stop every channel playing:** stops every stream now. Anyone watching can choose the channel again.

## Find out more

- [Dashboard card](dashboard-card.md)
- [Problems](problems.md)
