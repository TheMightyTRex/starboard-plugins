# Direct play: Problems

Find what is wrong with Direct play, then follow the numbered answer.

```flow
title: Find your answer
start: Direct play is not working as it should
q: What does its tab say?
  Needs setting up -> 1
  Failed or Not answering -> 2
  Not supported -> 3
  Active, but nothing is converted -> q2
q2: What does the Direct play card say?
  No devices chosen -> 1
  Waiting or Paused -> 4
  Nothing left to do -> 5
  A file is listed under Not fixed -> 6
1: Finish setting it up #finish-setting-it-up
2: Start it again #start-it-again
3: Update it or update Starboard #update-it-or-update-starboard
4: Check when it works #check-when-it-works
5: Check your devices #check-your-devices
6: Read why it was not fixed #read-why-it-was-not-fixed
```

## Finish setting it up

1. Go to **Settings**, then **Plug-ins**, then **Direct play**.
2. Select **Finish setting up**.
3. In **Devices**, activate each kind of device anyone in your home watches on. The card says "No devices chosen" until at least one is activated.
4. Select **Activate**.

## Start it again

1. On Direct play's tab, read the message under its state: it says why it stopped.
2. Select **Try again**.
3. If it stopped soon after an update, select **Roll back to** and the version you had. Read [Updates](updates.md).
4. Still failing: go to **System**, then **Logs**, and look for its name.

If a card says **No answer from** and its name, it did not answer in 3 seconds. Check that it is **Active** on its tab, then wait a minute.

## Update it or update Starboard

Your Starboard's plug-in API is outside what this version of Direct play works with, so Starboard stopped it.

1. Select **Look for an update** on its tab.
2. If there is none, update Starboard. Read [Update Starboard](https://themightytrex.github.io/starboard/help/topics/update-starboard.html).

## Check when it works

- **Waiting for the weekend** or **Waiting for quiet hours**: it works only in the hours set in **When it works**. Choose **Any time** to let it work now.
- **Paused**: select **Resume fixing** on its tab.
- **Looking at the library**: it is reading new or changed files. Wait for it to finish.
- **Waiting for an update**: an update is about to start. It carries on after the update.

## Check your devices

The card says "Nothing left to do", but a file still does not play directly.

- A file is fixed only when one of the devices chosen in **Devices** cannot play it. Activate every kind of device anyone watches on.
- HEVC files are left alone unless you activate **Convert HEVC to H.264**, and then only when none of your devices plays HEVC.
- A new file is found at the next look at the library. Select **Look at the library now** to look straight away.

## Read why it was not fixed

1. On Direct play's tab, open **Files**.
2. Look in **Not fixed**: **Why** says what went wrong, such as the new file's length or sound not matching the original. The original was left as it was.
3. Fix the file another way, or replace it. A file that failed is not tried again until it changes.

If **Files** says "The last pass did not finish", the words under it say what went wrong. Fix that, then wait for the next pass, within a minute in its hours.

## Report a problem

If none of these helps, tell its maker, with what its tab, the card and the **Files** page say: [the plug-ins' issues on GitHub](https://github.com/TheMightyTRex/starboard-plugins/issues).

## Find out more

- [Settings](settings.md)
- [Updates](updates.md)
- [If a plug-in will not add, in Starboard's help](https://themightytrex.github.io/starboard/help/topics/add-a-plugin.html#if-it-does-not-work)
