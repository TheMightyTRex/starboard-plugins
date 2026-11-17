# Outside services: Problems

Find what is wrong with Outside services from what its tab or its cards say, then follow the numbered answer.

```flow
title: Find your answer
start: Outside services is not working as it should
q: What does its tab say?
  Failed or Not answering -> 1
  Not supported -> 2
  Active, but a card is wrong -> q2
q2: What does the card say?
  Add addresses in the settings -> 3
  Not checked yet -> 4
  Not answering and a name -> 5
  Checks at the old interval -> 6
1: Start it again #start-it-again
2: Update it or update Starboard #update-it-or-update-starboard
3: Add the addresses #add-the-addresses
4: Wait for the first check #wait-for-the-first-check
5: Check what is not answering #check-what-is-not-answering
6: Start it again after a change #start-it-again-after-a-change
```

## Start it again

1. On Outside services' tab, read the message under its state: it says why it stopped.
2. Select **Try again**.
3. If it stopped soon after an update, select **Roll back to** and the version you had. Read [Updates](updates.md).
4. Still failing: go to **System**, then **Logs**, and find its name.

## Update it or update Starboard

Your Starboard's plug-in API is outside what this version of Outside services works with, so Starboard stopped it.

1. Select **Check for an update** on its tab.
2. If there is none, update Starboard. Read [Update Starboard](https://themightytrex.github.io/starboard/help/topics/update-starboard.html).

## Add the addresses

The card says "Add addresses in the plug-in's settings" and **Needs setting up**: there is nothing to check yet.

1. Go to **Settings**, then **Plug-ins**, then **Outside services**.
2. In **Addresses to check**, enter each address, such as `Router http://192.0.2.1`.
3. Select **Save**.

## Wait for the first check

The card says "Not checked yet" and **Waiting**. The first check starts a few seconds after Outside services starts, and each address can take up to 8 seconds, so wait a minute or two. After that, it checks at **Check every**.

## Check what is not answering

The card says "Not answering" and the names, such as "Not answering: NAS". At the last check, those addresses gave no answer within 8 seconds, or answered with a server error.

1. Open the address from the list card in your browser.
2. If it does not open there either, check the device is on and on your network.
3. If it opens in your browser, check the address in **Addresses to check** is exactly the same, including `http://` or `https://` and any port.
4. Wait for the next check: the card changes by itself.

## Start it again after a change

A new **Check every** is used only when Outside services starts.

1. Go to **Settings**, then **Plug-ins**, then **Outside services**.
2. Select **Deactivate**.
3. Select **Activate**.

## Report a problem

If none of these helps, tell its maker, with what its tab and the cards say: [the plug-ins' issues on GitHub](https://github.com/TheMightyTRex/starboard-plugins/issues).

## Find out more

- [Settings](settings.md)
- [Updates](updates.md)
- [If a plug-in will not add, in Starboard's help](https://themightytrex.github.io/starboard/help/topics/add-a-plugin.html#if-it-does-not-work)
