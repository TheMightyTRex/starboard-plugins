# Calibre-Web

Calibre-Web, a browser page for a Calibre library: read, search and send books to an e-reader. It reads your books and never changes them. Starboard sets it up for you.

An app plug-in for Starboard (plug-in API 1.20 or later): Calibre-Web runs outside the main install, in Starboard's locked-down
containers, with its own page on your home network. Starboard chooses the port (8083 when it is free) and shows the address
on the plug-in's page with **Open**.

## Who it is for

People who keep their books in a Calibre library (a folder with metadata.db) and want to read, search and send them to an e-reader from a browser.

## Set it up

Starboard sets it up before it first starts, so there is nothing to change in Calibre-Web itself:

1. Activate it. Its library is found by itself: `books-library` in your media folder (made by the Calibre library maker plug-in) or `books`, when it holds a Calibre library (a folder with `metadata.db`).
2. Its first password is made by Starboard, not the default `admin123`. On its tab, **Its first sign-in** has **Show the password…**: it asks for your Starboard password and shows it once.
3. Choose **Open Calibre-Web** and sign in as `admin`.

Uploads, public sign-up, anonymous browsing and remote sign-in are off, and the admin cannot edit or delete books: your books are read only. OPDS, for e-reader apps, is at `/opds` on its page, with your sign-in.

If your books are only files in folders, with no `metadata.db`, add the **Calibre library maker** plug-in: it makes a library beside them, never changing them.

## Read on your phone

Starboard names three phone apps that work well with Calibre-Web. They are made by others, and neither Starboard nor this plug-in runs them.

- **Android:** [KOReader](https://koreader.rocks/) opens your library over OPDS: add a catalogue with the address of Calibre-Web followed by `/opds`, and your Calibre-Web user name and password. [Calibre-Web-Companion](https://f-droid.org/en/packages/de.doen1el.calibreWebCompanion/) is made for Calibre-Web: enter its address and sign in.
- **iPhone and iPad:** [Readest](https://apps.apple.com/app/id6738622779) connects to Calibre-Web and to OPDS catalogues.

Use the address on this plug-in's page, from your home network. In Starboard the same list is under **Read on your phone**, on this plug-in's page and in **Settings**, **Apps**, **Manage apps**.

## What it may do

- It can read: Files in your media folder under books and books-library (read only).
- It can change: Its own folder in Starboard's data (data/plugins/calibre-web).
- It can reach: Other computers on your home network, and the internet.
- It can reach: Its own web page is opened on your home network: anyone on your home network can open it, at this computer's address and a port Starboard chooses.

It runs read only, as a user that is not root, with no extra rights, like every plug-in. Its images, pinned by digest:

- `app`: `lscr.io/linuxserver/calibre-web@sha256:8eabbc9ac4d7fcbc252434493078ba22e4e8c3aa461e11b102020b040c5fc3e6`

## At rest

What it uses when nobody is using it, measured with `tools/app_check.py` (median of 36 readings over 3 minutes, after
2 minutes to settle). A real library uses more.

| Reading | Memory | Processor (one core) |
|---|---|---|
| As Starboard runs it (hardened, empty library), 13 November 2026 | 182.2 MiB | 0.01% |
| Version 1.2.0 with its start-up, a library of 12 books, 26 November 2026 | 171.9 MiB | 0.01% |

## Removing it

**Settings**, **Plug-ins**, Calibre-Web, **Remove**. Its containers stop and go and its key stops working. You choose
where its folder goes, with everything it kept (settings):
kept in `data/plugins/.removed`, or moved to the holding folder in **System**, **Clean up**.
From there you can put it back or delete it permanently. Starboard never deletes it. Your media folder is not touched.

## Licence

This plug-in is MIT, by TheMightyTRexUK. Calibre-Web itself is under the GPL-3.0 licence, made by others: https://github.com/janeczku/calibre-web
