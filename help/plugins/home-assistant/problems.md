# Home Assistant: Problems

Find what is wrong with Home Assistant, then follow the numbered answer.

```flow
title: Find your answer
start: Home Assistant is not working as it should
q: What does its tab say?
  Failed or Not answering -> 1
  Not supported -> 2
  Active, but a card is wrong -> 3
1: Start it again #start-it-again
2: Update it or update Starboard #update-it-or-update-starboard
3: Read what the card says #read-what-the-card-says
```

## Start it again

1. On Home Assistant's tab, read the message under its state: it says why it stopped.
2. Select **Try again**.
3. If it stopped soon after an update, select **Roll back to** and the version you had. Read [Updates](updates.md).
4. Still failing: go to **System**, then **Logs**, and look for its name.

## Update it or update Starboard

Your Starboard's plug-in API is outside what this version of Home Assistant works with, so Starboard stopped it.

1. Select **Look for an update** on its tab.
2. If there is none, update Starboard. Read [Update Starboard](https://themightytrex.github.io/starboard/help/topics/update-starboard.html).

## Read what the card says

- **No answer from** and its name: it did not answer in 3 seconds. Check that it is **Active** on its tab, then wait a minute.
- **Problem** on the card: the words under it say what went wrong. Fix that, then wait for the next check.

## Report a problem

If none of these helps, tell its maker, with what its tab and the card say: [the plug-ins' issues on GitHub](https://github.com/TheMightyTRex/starboard-plugins/issues).

## Find out more

- [Settings](settings.md)
- [Updates](updates.md)
- [If a plug-in will not add, in Starboard's help](https://themightytrex.github.io/starboard/help/topics/add-a-plugin.html#if-it-does-not-work)
