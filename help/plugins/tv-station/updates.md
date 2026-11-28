# Create your own TV channel: Updates

Create your own TV channel 0.9.2 is the latest version. It needs Starboard with plug-in API 1.15 or later. Choose from your library, the cards and saving in place need Starboard 0.24.0.

## Versions

| Version | Needs plug-in API | Released |
|---|---|---|
| 0.9.2 | 1.15 or later; Starboard 0.24.0 for the slide-out, the cards and saving in place | Not released yet |
| 0.9.1 | 1.15 or later; Starboard 0.24.0 for the slide-out, the cards and saving in place | Not released yet |
| 0.9.0 | 1.15 or later; Starboard 0.24.0 for the slide-out, the cards and saving in place | Not released yet |
| 0.8.0 | 1.15 or later; Starboard 0.24.0 for the slide-out, the cards and saving in place | Not released yet |
| 0.7.0 | 1.15 or later; Starboard 0.24.0 for the slide-out, the cards and saving in place | 22 November 2026 |
| 0.6.0 | 1.15 or later; Starboard 0.24.0 for the slide-out, the cards and saving in place | 21 November 2026 |
| 0.5.7 | 1.15 or later; Starboard 0.24.0 for the slide-out, the cards and saving in place | 21 November 2026 |
| 0.5.6 | 1.15 or later; Starboard 0.24.0 for the slide-out, the cards and saving in place | 20 November 2026 |
| 0.5.5 | 1.15 or later; Starboard 0.24.0 for the slide-out, the cards and saving in place | 19 November 2026 |
| 0.5.4 | 1.15 or later; Starboard 0.24.0 for the slide-out, the cards and saving in place | 19 November 2026 |
| 0.5.3 | 1.15 or later; Starboard 0.24.0 for the slide-out, the cards and saving in place | 19 November 2026 |
| 0.5.2 | 1.15 or later; Starboard 0.24.0 for the slide-out, the cards and saving in place | 19 November 2026 |
| 0.5.1 | 1.15 or later; Starboard 0.24.0 for the slide-out, the cards and saving in place | 19 November 2026 |
| 0.5.0 | 1.15 or later; Starboard 0.24.0 for the slide-out, the cards and saving in place | 19 November 2026 |
| 0.4.0 | 1.15 or later; Starboard 0.24.0 for the slide-out, the cards and saving in place | 19 November 2026 |
| 0.3.2 | 1.15 or later; Starboard 0.24.0 for the slide-out, the cards and saving in place | 19 November 2026 |
| 0.3.1 | 1.15 or later; Starboard 0.24.0 for the slide-out, the cards and saving in place | 19 November 2026 |
| 0.3.0 | 1.15 or later; Starboard 0.24.0 for the slide-out, the cards and saving in place | 19 November 2026 |
| 0.2.1 | 1.15 or later; Starboard 0.24.0 for the slide-out, the cards and saving in place | 19 November 2026 |
| 0.2.0 | 1.15 or later; Starboard 0.24.0 for the slide-out, the cards and saving in place | 19 November 2026 |
| 0.1.1 | 1.15 or later | 19 November 2026 |
| 0.1.0 | 1.15 or later | 19 November 2026 |

The catalogue offers each Starboard the newest version it can run.

## What is new in 0.9.0

Not released yet.

Added:

- **Fit for Adverts:** in either grid, **Times shown** for **Adverts** can be **Fit**, which adds as many whole adverts as the break has room for. It never cuts an advert or another item short, and the holding countdown makes up the rest. [Fit, and a break length for each column](settings.md#fit-and-a-break-length-for-each-column) says how.
- **Break length for each column:** **Automatic**, or 2 to 30 minutes. A column whose items need more than that says so in words, and the programme still starts on time.

- **File lists:** one page for every ident, promo clip, advert and PSA. It has a search, sorting, filters and paging. You can add several files to a channel, or take them off it, together. [File lists](settings.md#file-lists) says how.
- **PSA:** a new kind of item for the grids, with its own files. [PSAs](settings.md#psas) says what it needs.

Fixed:

- **The holding countdown and Back soon count what comes after them.** That can be a bumper, a promo, an ident, an other channel promo or a Coming soon promo. The clock reaches 0:00 as the programme starts. The slide ends early by the length of what follows, in the classic breaks too. When a clip's length cannot be read, the plug-in uses the length it kept earlier. The log says so.

## What is new in 0.8.0

Not released yet.

Added:

- **Break grids:** two grids for each channel, **In between programmes** and **Breaks**, with up to 7 columns each. Choose **Random**, **Sequence**, **Day of week**, or **Morning, afternoon and evening**. Then drag **Bumper**, **Promo**, **Adverts**, **Ident**, **Other channel promo**, **Coming soon promo**, **Holding countdown** and **Back soon** into the columns. Say how many times each is shown. Everything also works from the keyboard and with buttons. [Break grids](settings.md#break-grids) says how.
- **Where breaks go inside a programme:** at silence, at set times or at the end of a scene. You choose how many in each 30 minutes and in a film. The plug-in finds them once for each programme in the quiet hours. [Where breaks go inside a programme](settings.md#where-breaks-go-inside-a-programme) says what each does.

Nothing you have set changes. A channel that has not changed its grids plays what it always has, and the grids start from that order.

## What is new in 0.7.0

Released on 22 November 2026.

Added:

- **Audio description on promos:** a setting in **Promos** that is not active unless you turn it on. A voice says
  each promo's words, so a blind viewer hears what is coming, on which channel, and when. The voice is made on your
  server, in the station's language, and nothing is sent anywhere. A programme that has a described sound track plays
  that track in its clips. [Audio description on promos](settings.md#audio-description-on-promos) says what is said
  and what it costs.

## What is new in 0.6.0

Added:

- **Language:** a station setting, English unless changed, with French, German, Spanish, Italian, Portuguese, Dutch,
  Swedish, Danish and Norwegian. The words drawn on the picture and in the guide are in that language. That covers
  **Coming up next**, the series and episode, and the day and time.
- **Sound track in your language:** a programme with more than one sound track plays the one in the station's
  language, else its default track.
- **Titles in your language:** the plug-in reads film and series titles, and film descriptions, in the station's language.
  It gets them from the film database for programmes about to be shown, a few each hour, and keeps them. Episode names and plots stay as
  Jellyfin has them; [Language](settings.md#language) says how to get those in your language too.

## What is new in 0.5.7

Fixed:

- **Moving a programme with the keyboard:** on the schedule grid, focus goes straight to the programme at its new time.
  This happens after **Move 15 minutes earlier**, **Move 15 minutes later** or **Move to**. The new time is said. A screen
  reader no longer reads the old time first. When a move cannot be made, focus goes back to the programme where it
  was and the reason is said.

## What is new in 0.5.6

Changed:

- **Busy buttons on the schedule grid:** a button that asks the plug-in for something shows a turning ring before its words while it works. That covers **Suggest a week**, **Save the suggestion** and **Undo**. With less motion asked for in **Display**, the ring fades instead of turning.

## What is new in 0.5.5

Added:

- **Leave out 3D films:** every channel leaves out a film that is 3D. The plug-in goes by what Jellyfin or the file name says, or by a check of the picture in quiet hours.

Changed:

- **Reading the channels again** updates each programme's details, such as which sound track it plays, even when the programmes are the same.

## What is new in 0.5.4

Fixed:

- **A programme with a subtitle file beside it** played only the fallback card with the station's and channel's names. Its sound track is now found among the file's own sound tracks. A line-up read before 0.5.4 is put right when it is read again.

## What is new in 0.5.2

Added:

- **The station's logo on promos:** promos for a channel with its own pack show the station's logo, small, in a corner. To leave it out, turn off **Show the station's logo on promos**.

## What is new in 0.5.0

Added:

- **Promos and clips in each break:** **Up to 2**, **Up to 3**, **Up to 4** or **Up to 6** on each channel's **Breaks** card. Each plays once at most in a break, in a random order.
- **Extra videos:** upload videos of up to 10 minutes for the station or for one channel. One plays at random after the promos in each break, when it fits.

Changed:

- **A break between programmes** is a bumper, the promos and clips, an extra video and the holding slide. It ends with the ident and its music, right before the next programme.

## What is new in 0.4.0

Added:

- **Bumpers:** a broadcast pack may have short bumpers, with no sound, to open and close a break.
- **Breaks inside programmes:** **Off** unless chosen on a channel's **Breaks** card. In quiet hours, **Find breaks inside programmes** finds where a programme fades to black for its adverts, and a short break plays there. The schedule never moves.

## What is new in 0.3.2

Added:

- **Create initial schedule:** on a channel's What it shows card, the plug-in makes a week from the channel's own series and films. It uses the hours you give. It waits in the schedule grid for you to change and save.
- **This channel's line-up** in Suggest a schedule does the same from the grid page.

## What is new in 0.3.0

Added:

- **Animation on and off:** each of these can come on and go off with an animation. That covers the Coming up next and Later cards, the straps, the on-screen logo and the clock. It also covers the New, Repeat or Live label and the words on the holding slide. The animation can fade, slide in from the left, the right or the bottom, wipe or grow. It can be quick, normal or slow. Choose them for every channel on the new **Animation** page, or for one channel on its **Animation** card. Each has a **Preview**: a few seconds of it, in a new tab.
- **A broadcast pack can choose its animation** in `pack.json`, under `animation`. A choice in the settings comes first.
- **Each channel remembers what it has played** to someone watching. **From the next episode not watched** counts an episode it played, 70% or more of it, as watched, as well as what Jellyfin says. Jellyfin's own watched marks are never changed.
- **Played on this channel:** a card on each channel lists the last 5 programmes it played. It has **Count what this channel has played as watched** and a way to forget them.

Changed:

- **From the next episode not watched** starts at the first episode, in the channel's order, that is not watched. Before, it took the first not played in Jellyfin's order.

## What is new in 0.2.1

Added:

- **Choose the hours a suggestion fills:** Suggest a schedule asks for the hours to fill on weekdays and at weekends, such as 18:00 to 23:00. It fills them one programme after another and leaves out one that would run past the end. The hours are remembered for each channel.

Changed:

- **Longer holding slides:** a holding slide's video may be up to 120 seconds and 90 MB. Starboard 0.24.1 or later takes files that big; an older Starboard stops at 60 MB.

## What is new in 0.2.0

Added:

- **Choose from your library:** a slide-out lists every series, film, collection, playlist, genre and decade in Jellyfin, with search. Tick several and add them to a channel at once. Needs Starboard 0.24.0.
- **A holding slide:** a picture or short video with Back soon or a countdown to the next programme. It loops at the end of each break until the next programme starts.
- **Music for promos:** upload music for the station or one channel. A channel with music but no pack promo gets plain promos on its colour.
- **Jellyfin's guide:** the Guide page says when Jellyfin last read the guide, and **Refresh Jellyfin's guide** asks it to read it again.
- **Suggest a schedule asks what to make it from:** Watch history, General watch history, All TV, All films or TV and Films.
- **Logos show on their rows** as a small picture once uploaded.

Changed:

- **Channels in cards**, and **changes save in place**, keeping the open channel, where you were and focus. Need Starboard 0.24.0.
- **Renaming the station renames its tuner** in Jellyfin's Live TV.

Fixed:

- **The schedule grid opens** from the address you opened Starboard with (Starboard 0.24.0), and says what to do when there are no channels.

## What is new in 0.1.0

Added:

- **Your own channels:** name the station and each channel, with its number, logo and colour. Fill it from series, films, collections, playlists, genres or decades, in order or shuffled, with episodes of a series in a row.
- **Schedule grid:** place films and series at set times on a week's grid, by dragging or with buttons and the keyboard. Copy a day, stripe a series across weekdays, choose where a series starts, or suggest a week from watch history.
- **In Jellyfin's Live TV, first:** numbered from 1 in your order, with a 7-day guide of titles, episode names, synopses, pictures and New or Repeat. Tuning in joins part way through, as on television.
- **Breaks:** idents, Jellyfin's trailers, your own clips, and Coming up next and Later cards. The cards show the programme's picture, title, date, time and a short synopsis.
- **Broadcast pack:** your own branding from a zip made from the template. It holds the on-screen logo, the logo with its music, idents in a random order, transitions, and Coming up next and promo backgrounds. Every file is checked first. Or try the example pack.
- **Promos:** the plug-in makes them in quiet hours from short clips of a programme coming up. They use a music bed from the pack and the day and time from the schedule. It keeps and replaces them as the settings say, and shows them on your other channels too.
- **Downloads:** the template, with pack.json, its schema and a README, and placement guides for the Coming up next card, the promo and the on-screen logo.
- **On-screen logo:** the channel's logo or name in a corner you choose. You set its size and opacity, and can add a clock, a New, Repeat or Live label and a backing plate. This works for the station or each channel, with a preview.
- **Light:** nothing runs until someone chooses a channel, viewers of a channel share one stream, and it stops 30 seconds after the last one leaves.

## How it updates

Before an update, Create your own TV channel stops any channel playing, so the update never cuts a conversion short. Anyone watching can choose the channel again afterwards. Your channels, idents, clips, logos, broadcast packs and promos stay in its folder. Select **Roll back to** on its tab to go back to the version before.

## Find out more

- [Update and roll back](../../use/update-and-roll-back.md)
- [Problems](problems.md)
