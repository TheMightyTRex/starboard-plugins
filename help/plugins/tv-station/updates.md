# Create your own TV channel: Updates

Create your own TV channel 0.3.0 is the latest version. It needs Starboard with plug-in API 1.15 or later; Choose from your library, the cards and saving in place need Starboard 0.24.0.

## Versions

| Version | Needs plug-in API | Released |
|---|---|---|
| 0.3.0 | 1.15 or later; Starboard 0.24.0 for the slide-out, the cards and saving in place | Not yet released |
| 0.2.1 | 1.15 or later; Starboard 0.24.0 for the slide-out, the cards and saving in place | 19 November 2026 |
| 0.2.0 | 1.15 or later; Starboard 0.24.0 for the slide-out, the cards and saving in place | 19 November 2026 |
| 0.1.1 | 1.15 or later | 19 November 2026 |
| 0.1.0 | 1.15 or later | 19 November 2026 |

The catalogue offers each Starboard the newest version it can run.

## What is new in 0.5.5

Added:

- **Leave out 3D films:** a film that is 3D, by what Jellyfin or its file name says or by a check of its picture in quiet hours, is left out of every channel.

Changed:

- **Reading the channels again** updates each programme's details, such as which sound track it plays, even when the programmes are the same.

## What is new in 0.5.2

Added:

- **The station's logo on promos:** promos for a channel with its own pack show the station's logo, small, in a corner. To leave it out, deactivate **Show the station's logo on promos**.

## What is new in 0.3.2

Added:

- **Create initial schedule:** on a channel's What it shows card, a week made from the channel's own series and films in the hours you give, waiting in the schedule grid for you to change and save.
- **This channel's line-up** in Suggest a schedule does the same from the grid page.

## What is new in 0.3.0

Added:

- **Animation on and off:** the Coming up next and Later cards, the straps, the on-screen logo, the clock, the New, Repeat or Live label and the words on the holding slide can each fade, slide in from the left, the right or the bottom, wipe or grow, and go off the same ways, quick, normal or slow. Choose them for every channel on the new **Animation** page, or for one channel on its **Animation** card. Each has a **Preview**: a few seconds of it, in a new tab.
- **A broadcast pack can choose its animation** in `pack.json`, under `animation`. A choice in the settings comes first.
- **Each channel remembers what it has played** to someone watching. **From the next episode not watched** counts an episode it played, 70% or more of it, as watched, as well as what Jellyfin says. Jellyfin's own watched marks are never changed.
- **Played on this channel:** a card on each channel lists the last 5 programmes it played, with **Count what this channel has played as watched** and a way to forget them.

Changed:

- **From the next episode not watched** starts at the first episode, in the channel's order, that is not watched; before, it took the first not played in Jellyfin's order.

## What is new in 0.2.1

Added:

- **Choose the hours a suggestion fills:** Suggest a schedule asks for the hours to fill on weekdays and at the weekend, such as 18:00 to 23:00, and fills them one programme after another, leaving out one that would run past the end. The hours are remembered for each channel.

Changed:

- **Longer holding slides:** a holding slide's video may be up to 120 seconds and 90 MB. Starboard 0.24.1 or later takes files that big; an older Starboard stops at 60 MB.

## What is new in 0.2.0

Added:

- **Choose from your library:** a slide-out lists every series, film, collection, playlist, genre and decade in Jellyfin, with search; tick several and add them to a channel at once. Needs Starboard 0.24.0.
- **A holding slide:** a picture or short video with Back soon or a countdown to the next programme, looping at the end of each break until the next programme starts.
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

- **Your own channels:** name the station and each channel, with its number, logo and colour, and fill it from series, films, collections, playlists, genres or decades, in order or shuffled, with episodes of a series in a row.
- **Schedule grid:** place films and series at set times on a week's grid, by dragging or with buttons and the keyboard; copy a day; stripe a series across weekdays; choose where a series starts; suggest a week from watch history.
- **In Jellyfin's Live TV, first:** numbered from 1 in your order, with a 7-day guide of titles, episode names, synopses, pictures and New or Repeat. Tuning in joins part way through, as on television.
- **Breaks:** idents, Jellyfin's trailers, your own clips, and Coming up next and Later cards with the programme's picture, title, date and time and a short synopsis.
- **Broadcast pack:** your own branding from a zip made from the template: the on-screen logo, the logo with its music, idents in a random order, transitions, and Coming up next and promo backgrounds. Every file is checked first. Or try the example pack.
- **Promos:** made in quiet hours from short clips of a programme coming up, a music bed from the pack and its day and time from the schedule, kept and replaced as the settings say, and shown on your other channels too.
- **Downloads:** the template, with pack.json, its schema and a README, and placement guides for the Coming up next card, the promo and the on-screen logo.
- **On-screen logo:** the channel's logo or name in a corner you choose, with its size, opacity, a clock, a New, Repeat or Live label and a backing plate, for the station or each channel, with a preview.
- **Light:** nothing runs until someone chooses a channel, viewers of a channel share one stream, and it stops 30 seconds after the last one leaves.

## How it updates

Before an update, Create your own TV channel stops any channel playing, so the update never cuts a conversion short; anyone watching can choose the channel again after it. Your channels, idents, clips, logos, broadcast packs and promos stay in its folder. Select **Roll back to** on its tab to go back to the version before.

## Find out more

- [Update and roll back](../../use/update-and-roll-back.md)
- [Problems](problems.md)
