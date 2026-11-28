# Create your own TV channel: Problems

Find what is wrong with Create your own TV channel, then follow the numbered answer.

```flow
title: Find your answer
start: Create your own TV channel is not working as it should
q: Where is the problem?
  Its tab says Failed or Not answering -> 1
  The channels are not in Jellyfin -> 2
  A channel will not play -> q2
  A channel has nothing on -> 4
  A broadcast pack was not used -> 6
  There are no promos -> 7
  The schedule grid does not open -> 8
  Jellyfin's Live TV has no programmes -> 9
  The holding slide or music was refused -> 10
  A series starts from an episode I have watched -> 11
q2: What happens?
  Jellyfin says no tuner is free -> 3
  It starts, then stops -> 5
  It shows only a card with the station's and channel's names -> 12
1: Start it again #start-it-again
2: Give Jellyfin its address #give-jellyfin-its-address
3: Let more channels play at once #let-more-channels-play-at-once
4: Add something to the channel #add-something-to-the-channel
5: Check the stream #check-the-stream
6: Fix the pack and upload it again #fix-the-pack-and-upload-it-again
7: Give promos what they need #give-promos-what-they-need
8: Open the schedule grid #open-the-schedule-grid
9: Check Jellyfin has the guide #check-jellyfin-has-the-guide
10: Choose a file it can use #choose-a-file-it-can-use
11: Count what you have watched #count-what-you-have-watched
12: Update the plug-in #update-the-plug-in
```

## Start it again

1. On Create your own TV channel's tab, read the message under its state: it says why it stopped.
2. Select **Try again**.
3. If it stopped soon after an update, select **Roll back to** and the version you had. Read [Updates](updates.md).
4. Still failing: go to **System**, then **Logs**, and find its name.

## Give Jellyfin its address

Jellyfin reads the channel list and the guide from Create your own TV channel's own web page. So Create your own TV channel needs the address that Jellyfin can reach it at.

1. Check Starboard is 0.23.0 or later, in **Settings**, **Updates**: it gives Create your own TV channel its address on your home network by itself. With an older Starboard, go to Create your own TV channel's tab and select **Open**, next to its web page's address. A page with the station's name opens.
2. Within a minute, Create your own TV channel adds its tuner and guide to Jellyfin and starts Jellyfin's guide refresh.
3. If Jellyfin runs on another computer, go to **Station**. In **Address Jellyfin uses to reach this plug-in**, enter the address it reaches this server at. Then select **Read the channels from Jellyfin again**.
4. In Jellyfin, go to **Dashboard**, then **Live TV**: the tuner has the station's name. Select **Refresh guide data** if the channels have no programmes.

## Let more channels play at once

Each channel being watched is one conversion, and **Most channels at once** is 2 unless you change it. People watching the same channel share one, so it is the number of different channels at once.

1. In **Streaming**, raise **Most channels at once**. Each one adds about 0.9 of a processor core at 720p.
2. Or choose **720p** in **Picture size**, which is lighter.

## Add something to the channel

A channel with nothing in **What it shows**, or whose series and films Jellyfin no longer has, has nothing to play.

1. Open the channel in **Channels** and add a series, film, collection or playlist.
2. Select **Read the channels from Jellyfin again**.
3. Check **Today and tomorrow** on the channel's page.

## Check the stream

1. Select **Preview a frame** on the channel's page. If it says what went wrong, such as Jellyfin not answering, fix that first.
2. A programme that will not play is replaced by a slate with the station's name for 20 seconds, then the channel goes on.
3. Check **System**, then **Logs**, for Create your own TV channel.
4. If the server is busy, choose **720p** in **Picture size**. Or turn off the on-screen logo and the straps for that channel, so it copies its programmes with no converting.

## Fix the pack and upload it again

The pack is checked before anything in it is used, and the pack in use stays when it does not pass.

1. In **Broadcast pack**, read **The last pack checked**. Each row names a file and what to change. For example, a logo may have no transparent parts, or a file name may not be one the pack uses.
2. Change those files. [Make a broadcast pack](../../use/make-a-broadcast-pack.md) has every name, size and length.
3. Zip the folder again and select **Upload a pack**.
4. Still refused: download the template, put your files in its folders with the same names, and upload that.

## Give promos what they need

1. Check the channel has something to make promos with: its **Holding slide and promos** card says how its promos are made. A broadcast pack with a promo works, and so does music. To add music, upload some in **Idents, clips and music**, under **Music for promos**, or on the channel's card. The channel then gets plain promos on its colour.
2. Check **Make promos in quiet hours** is on, in the plug-in's settings under **Promos**.
3. Promos are made in Starboard's quiet hours while nobody is watching anything in Jellyfin. To make them now, select **Make promos now** on the plug-in's tab, with nothing playing.
4. A channel needs programmes in the next 6 days that start at least 2 hours from now.

## Open the schedule grid

The grid is on the plug-in's own page on your home network, not inside Starboard, so it opens in a new tab.

1. In **Schedule grid**, select **Open the schedule grid** under the channel. Use a desktop browser: on a phone or tablet the page says to use a computer.
2. Check Starboard is 0.24.0 or later, in **Settings**, **Updates**: the link then uses the address you opened Starboard with. With an older Starboard it uses the server's home network address. A browser that reaches Starboard another way, such as by a name or from outside your home, may not reach that address.
3. If the grid says to add a channel first, add one in **Channels**.
4. Still nothing: on the plug-in's tab, under **Its web page**, select **Open**. If that page does not open either, the browser cannot reach the plug-in's port: open Starboard from a computer on your home network.

## Check Jellyfin has the guide

1. Open **Guide**: it starts by saying when Jellyfin last read the guide and how many programmes it had.
2. If Jellyfin has not read it, or not lately, select **Refresh Jellyfin's guide** in **Actions**, wait a minute, and open **Guide** again.
3. In Jellyfin, the channels are under **Live TV**, then **Channels** or **Guide**. Some Jellyfin apps keep the guide for a while; close the app and open it again.
4. Still nothing: [Give Jellyfin its address](#give-jellyfin-its-address).

## Choose a file it can use

Every file is checked with FFmpeg before it is used, and the message says what was wrong.

- **A holding slide:** a PNG or JPEG picture, or a video (MP4, MOV, WEBM or MKV) of 1 to 120 seconds. It can be up to 90 MB (with Starboard 0.24.1 or later; 60 MB before) and 4096 pixels across.
- **Music for promos:** an MP3, M4A, OGG or FLAC file with sound, of 5 seconds to 10 minutes and up to 60 MB. You can have up to 20 tracks for the station and 20 for each channel. Remove one first when there are 20.

## Count what you have watched

A series on the schedule grid can be set to **From the next episode not watched**. It then starts at the first episode, in the channel's order, that Jellyfin says was not played. The channel must also not have played it to someone watching. The channel never tells Jellyfin what it played, so an episode watched on the channel is not marked as played in Jellyfin.

1. Open the channel in **Channels**. On its **Played on this channel** card, check **Count what this channel has played as watched** is **Yes**.
2. Check the episode is listed as **Watched**. An episode counts once 70% or more of it was played to someone watching; **Part watched** means less was.
3. For an episode watched somewhere else, mark it as played in Jellyfin.
4. Open the schedule grid, select the series and choose **From the next episode not watched** again. Where it starts is worked out when you choose it.

## Update the plug-in

A channel that shows only a card with the station's and channel's names is replacing each programme it could not start.

1. Update Create your own TV channel to 0.5.4 or later. Before 0.5.4, a programme with a subtitle file beside it could
   not start, because the plug-in asked for the subtitle in place of its sound.
2. Select **Read the channels from Jellyfin again** on the plug-in's **General** tab, so each programme's sound is read
   again. This also happens every night.
3. If the card stays, follow [Check the stream](#check-the-stream).

## Find out more

- [Settings](settings.md)
- [A plug-in is not working](../../fix/a-plug-in-is-not-working.md)
