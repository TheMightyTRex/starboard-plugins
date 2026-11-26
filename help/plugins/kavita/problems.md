# Kavita: Problems

Find what is wrong with Kavita from what its tab says or what happens, then follow the numbered answer.

```flow
title: Find your answer
start: Kavita is not working as it should
q: What does its tab say?
  Failed or Not answering -> 1
  Not supported -> 2
  Active -> q2
q2: What is wrong?
  Its page will not open -> 3
  Books or comics are missing -> 4
  An e-reader app cannot connect -> 5
  Making the first account fails with a 400 error -> 7
  There are two Kavitas -> 6
1: Start it again #start-it-again
2: Update it or update Starboard #update-it-or-update-starboard
3: Open its web page #open-its-web-page
4: Add the libraries #add-the-libraries
5: Connect a reading app #connect-a-reading-app
6: Keep one Kavita #keep-one-kavita
7: Repair the first account #repair-the-first-account
```

## Start it again

1. On Kavita's tab, read the message under its state: it says why it stopped.
2. Select **Try again**.
3. If it stopped soon after an update, select **Roll back to** and the version you had. Read [Updates](updates.md).
4. Still failing: go to **System**, then **Logs**, and find its name.

## Update it or update Starboard

Your Starboard's plug-in API is outside what this version of Kavita works with, so Starboard stopped it.

1. Select **Check for an update** on its tab.
2. If there is none, update Starboard. Read [Update Starboard](https://themightytrex.github.io/starboard/help/topics/update-starboard.html).

## Open its web page

1. Go to **Settings**, then **Plug-ins**, then **Kavita**.
2. Check its state is **Active**. If not, select **Activate**.
3. In **Its web page**, select **Open Kavita**. Use the address shown there: Starboard chooses the port, 5000 when it is free, so it may be a different one.
4. Open it from a device on your home network. The page is not on the internet.

## Add the libraries

Kavita can read only `books` and `comics` in your media folder, as `/media/books` and `/media/comics`, and shows nothing until you add a library.

1. Open Kavita and sign in with its admin account.
2. Add a library for `/media/books`.
3. Add a library for `/media/comics`.
4. Put your files in those two folders. Files anywhere else are not shown.

It reads the folders only, so it cannot change, move or delete a file.

## Connect a reading app

1. In an app that speaks OPDS, use the address in **Its web page**, with `http://` and the port.
2. Sign in with an account you made in Kavita, not your Starboard account.
3. Use the app on your home network. Remote access shares only Starboard, Jellyfin and Audiobookshelf, so Kavita does not answer away from home through it.

## Keep one Kavita

The main install can also add Kavita, in **Install apps**, **Ebooks**. With both, the plug-in takes another port when 5000 is in use, and each has its own accounts and libraries.

1. Choose the one you want to keep.
2. Remove the other. For the plug-in, read [Install](install.md).

## Repair the first account

Kavita 1.1.1 and earlier made a sign-in key that was too short for Kavita, so making the first account ended with "400 Error, Something went wrong when registering user". Version 1.1.2 makes a long enough key for a new install. An install made before it keeps the short key, because Starboard never writes over a file Kavita keeps in its own folder, so it needs one repair.

1. Update Kavita to 1.1.2. Read [Updates](updates.md).
2. On Kavita's tab, select **Deactivate**.
3. In Starboard's data folder, open `plugins/kavita/app` and move `appsettings.json` out of it, to a folder of your own. Starboard writes a new one with a long key the next time it starts.
4. Select **Activate** and make the first account again.

No account or library was made by the failed attempt, so nothing else needs to be reset. If you had already made accounts, they stay: only people signed in at the time are signed out.

## Report a problem

If none of these helps, tell its maker, with what its tab says: [the plug-ins' issues on GitHub](https://github.com/TheMightyTRex/starboard-plugins/issues). For a problem inside Kavita itself, read [Kavita's own help](https://www.kavitareader.com).

## Find out more

- [Settings](settings.md)
- [Updates](updates.md)
- [If a plug-in will not add, in Starboard's help](https://themightytrex.github.io/starboard/help/topics/add-a-plugin.html#if-it-does-not-work)
