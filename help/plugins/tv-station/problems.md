# TV station: Problems

Find what is wrong with TV station, then follow the numbered answer.

```flow
title: Find your answer
start: TV station is not working as it should
q: Where is the problem?
  Its tab says Failed or Not answering -> 1
  The channels are not in Jellyfin -> 2
  A channel will not play -> q2
  A channel has nothing on -> 4
q2: What happens?
  Jellyfin says no tuner is free -> 3
  It starts, then stops -> 5
1: Start it again #start-it-again
2: Give Jellyfin its address #give-jellyfin-its-address
3: Let more channels play at once #let-more-channels-play-at-once
4: Add something to the channel #add-something-to-the-channel
5: Check the stream #check-the-stream
```

## Start it again

1. On TV station's tab, read the message under its state: it says why it stopped.
2. Select **Try again**.
3. If it stopped soon after an update, select **Roll back to** and the version you had. Read [Updates](updates.md).
4. Still failing: go to **System**, then **Logs**, and find its name.

## Give Jellyfin its address

Jellyfin reads the channel list and the guide from TV station's own web page, so TV station needs to know the address Jellyfin can reach it at.

1. On TV station's tab, next to its web page's address, select **Open**. A page with the station's name opens.
2. Within a minute, TV station adds its tuner and guide to Jellyfin and starts Jellyfin's guide refresh.
3. If Jellyfin runs on another computer, enter the address it reaches this server at in **Address Jellyfin uses to reach this plug-in**, in **Station**, then select **Read the channels from Jellyfin again**.
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
3. Check **System**, then **Logs**, for TV station.
4. If the server is busy, choose **720p** in **Picture size**, or deactivate the on-screen logo and the straps for that channel, so it copies its programmes with no converting.

## Find out more

- [Settings](settings.md)
- [A plug-in is not working](../../fix/a-plug-in-is-not-working.md)
