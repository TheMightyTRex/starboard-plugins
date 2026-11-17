[Help centre](../README.md) · Fix a problem · troubleshooting
<!-- help: fix / problems -->

# A plug-in is not working

Find out why a plug-in from the collection has stopped or will not start, from what its tab in Starboard says. Each
plug-in also has its own Problems page, with the messages only it shows.

```flow
title: Find your answer
start: A plug-in is not working
step: Open its tab | Settings, then Plug-ins, then its name
q: What does its state say?
  Needs setting up -> 1
  Did not start or Failed -> q2
  Not supported -> 3
  Active, but a card is wrong -> a-card-says-no-answer.md
q2: Did it stop soon after an update?
  Yes -> 4
  No -> 2
1: Finish setting it up #1-finish-setting-it-up
2: Start it again #2-start-it-again
3: Update it or update Starboard #3-update-it-or-update-starboard
4: Roll it back #4-roll-it-back
```

## 1. Finish setting it up

A setting it needs is empty, or it has never been set up.

1. On its tab, select **Finish setting up**. The first setting it needs has the focus.
2. Fill it in and save.
3. Select **Activate**.

## 2. Start it again

1. Read the message under its state: it says why it stopped.
2. Select **Try again**.
3. If it stops again, go to **System**, then **Logs**, and find its name.
4. Read the plug-in's own Problems page, such as [Direct play's](../plugins/direct-play/problems.md).

## 3. Update it or update Starboard

Your Starboard's plug-in API is outside what this version works with, so Starboard stopped it.

1. Select **Check for an update** on its tab.
2. If there is none, update Starboard. Every plug-in here needs plug-in API 1.14, in Starboard 0.18.0 or later, and Library clean-up
   needs plug-in API 1.15, in Starboard 0.19.0 or later.

## 4. Roll it back

1. On its tab, in **Versions**, select **Roll back to** and the version you had.
2. Enter your Starboard password and select **Roll back**.
3. Tell its maker what happened, at the [plug-ins' issues on GitHub](https://github.com/TheMightyTRex/starboard-plugins/issues).

## Find out more

- [A card says No answer](a-card-says-no-answer.md)
- [A plug-in will not add](a-plug-in-will-not-add.md)
- [Update a plug-in and roll it back](../use/update-and-roll-back.md)
