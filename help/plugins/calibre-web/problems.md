# Calibre-Web: Problems

Find what is wrong with Calibre-Web, then follow the numbered answer.

```flow
title: Find your answer
start: Calibre-Web is not working as it should
q: What does its tab say?
  Did not start -> 1
  Not supported -> 2
  Active, but something is wrong -> q2
q2: What is wrong?
  Its page does not open -> 3
  It finds no books -> 4
  I do not have its password -> 6
  It will not upload or edit books -> 5
1: Start it again #start-it-again
2: Update it or update Starboard #update-it-or-update-starboard
3: Open its page #open-its-page
4: Point it at your library #point-it-at-your-library
5: Add books with Calibre #add-books-with-calibre
6: Get a new password #get-a-new-password
```

## Start it again

Its tab says **Did not start** when Calibre-Web did not start, or stopped answering.

1. On Calibre-Web's tab, read the message under its state: it says why it stopped.
2. Select **Try again**.
3. If it stopped soon after an update, select **Roll back to** and the version you had. Read [Updates](updates.md).
4. Still failing: go to **System**, then **Logs**, and find its name.

## Update it or update Starboard

Your Starboard's plug-in API is outside what this version of Calibre-Web works with, so Starboard stopped it.

1. Select **Check for an update** on its tab.
2. If there is none, update Starboard. Read [Update Starboard](https://themightytrex.github.io/starboard/help/topics/update-starboard.html).

## Open its page

Calibre-Web's page is on your home network, at this computer's address and the port Starboard chose for it. The port is not always the usual one: Starboard takes the next free port when that one is in use.

1. Check Calibre-Web's tab says **Active**. Starboard gives it a port only once it is active.
2. Under **Its web page**, read the address, then select **Open Calibre-Web**.
3. Open it from a device on your home network. It does not open from away from home.
4. If it still does not open, deactivate it, activate it again and wait a minute for the app to start.

## Point it at your library

Calibre-Web finds books only in a Calibre library: a folder with `metadata.db` in it. A folder of book files is not one.

1. Check whether `books-library` in your media folder has `metadata.db`. If it does, deactivate Calibre-Web and activate it again: Starboard sets the library at its start.
2. If not, and `books` has no `metadata.db` either, make a library with [Calibre library maker](../calibre-library/install.md). Read [Your books](your-books.md).
3. If your own Calibre library is somewhere else, move it into `books` with Calibre. Or enter `/media/books` as **Location of Calibre database** in Calibre-Web's admin settings.

## Add books with Calibre

Starboard gives Calibre-Web the books folders read only, so it can never change your books. Uploading, editing details and deleting books in Calibre-Web are off, by design.

1. Add new books to your books folder, then run [Calibre library maker](../calibre-library/install.md) again: it adds only what is new.
2. Or add and change books with Calibre itself, in the same library.
3. Calibre-Web shows the changes when it next reads the library.

## Get a new password

Starboard shows Calibre-Web's first password once. If it is lost:

1. Go to **Settings**, then **Plug-ins**, then **Calibre-Web**, and select **Remove Calibre-Web**.
2. Choose **Move it to the holding folder**, enter your Starboard password and select **Remove**.
3. Add Calibre-Web again from the **Catalogue**. It makes a new password, which **Its first sign-in** shows once. Your books and your library are not touched.

## Report a problem

If none of these helps, tell its maker, with what its tab says: [the plug-ins' issues on GitHub](https://github.com/TheMightyTRex/starboard-plugins/issues).

## Find out more

- [Settings](settings.md)
- [Updates](updates.md)
- [If a plug-in will not add, in Starboard's help](https://themightytrex.github.io/starboard/help/topics/add-a-plugin.html#if-it-does-not-work)
