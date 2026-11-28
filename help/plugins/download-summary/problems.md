# Download summary: Problems

Find what is wrong with Download summary, then follow the numbered answer.

```flow
title: Find your answer
start: Download summary is not working as it should
q: What does its tab say?
  Failed or Not answering -> 1
  Needs an update -> 2
  Active, but the card is wrong -> q2
q2: What does the card say?
  0 bytes today -> 3
  Problem -> 4
  Less than I expected -> 5
1: Start it again #start-it-again
2: Update it or update Starboard #update-it-or-update-starboard
3: Check something is downloading #check-something-is-downloading
4: Read the words under the number #read-the-words-under-the-number
5: Know what it counts #know-what-it-counts
```

## Start it again

1. On Download summary's tab, read the message under its state: it says why it stopped.
2. Select **Try again**.
3. If it stopped soon after an update, select **Roll back to** and the version you had. Read [Updates](updates.md).
4. Still failing: go to **System**, then **Logs**, and find its name.

## Update it or update Starboard

Your Starboard's plug-in API is outside what this version of Download summary works with, so Starboard stopped it.

1. Select **Check for an update** on its tab.
2. If there is none, update Starboard. Read [Update Starboard](https://themightytrex.github.io/starboard/help/topics/update-starboard.html).

## Check something is downloading

It counts only what moves in Starboard's download queue.

1. Go to **Activity**, then **Downloads**, then **Queue**.
2. Check that something there is downloading, not waiting or paused.
3. If the queue is empty when you know something is downloading, add that app to Starboard in **Settings**, then **Apps**. Read [Add an app, in Starboard's help](https://themightytrex.github.io/starboard/help/topics/add-an-app.html).
4. Wait a minute or two for the next readings.

## Read the words under the number

**Problem** means it could not read the queue the last time it tried. The words under the number say what went wrong, in place of the week's total.

1. Check that **Activity**, then **Downloads** opens and shows the queue.
2. Wait a minute: the words go when a reading works again.
3. If they stay, select **Turn off**, then **Turn on**, on its tab.
4. Still there: go to **System**, then **Logs**, and find its name.

## Know what it counts

The totals are what it saw move, so they can be lower than what your apps say.

- It counts from when it first finds a download, not what was done before.
- It reads once a minute, so the last minute of a download that finishes and leaves the queue may be missed.
- While it is off or stopped, it reads nothing. When it starts again, it counts a download still in the queue for the day it starts again. It does not count one that finished in between.
- The day starts at midnight on your server's clock, and this week means today and the 6 days before it.

## Report a problem

If none of these helps, tell its maker, with what its tab and the card say: [the plug-ins' issues on GitHub](https://github.com/TheMightyTRex/starboard-plugins/issues).

## Find out more

- [Settings](settings.md)
- [Updates](updates.md)
- [If a plug-in will not add, in Starboard's help](https://themightytrex.github.io/starboard/help/topics/add-a-plugin.html#if-it-does-not-work)
