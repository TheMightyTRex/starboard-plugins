# Kavita

Kavita, a reader for comics, manga and books in the browser and in e-reader apps (OPDS). It reads your books and comics folders and never changes them.

An app plug-in for Starboard (plug-in API 1.14 or later). Kavita runs outside the main install, in Starboard's locked-down containers. It has its own page on your home network. Starboard chooses the port (5000 when it is free) and shows the address
on the plug-in's page with **Open**.

## Who it is for

People who read comics, manga and books, in the browser or in an e-reader app that speaks OPDS. The main install can also add Kavita (Install apps, Ebooks); use one or the other.

## Set it up

1. Activate it, choose **Open Kavita** and make the first account. The first account made is its admin, so choose a strong password.
2. Add libraries for `/media/books` and `/media/comics`. It reads them only, so Kavita cannot change or delete a file. Its sign-in key is made for this install.

## Read on your phone

These apps work well with Kavita. Other people make them. We tested Kover with Kavita; we have not tested the others. Each one needs your Kavita address and your **Auth key**. Kavita shows both under your user settings, on the **3rd Party Clients** tab, with a copy button. Read [Kavita's page on the Auth key and OPDS address](https://wiki.kavitareader.com/guides/user-settings/3rdpartyclients/).

- **Android: KOReader.** Add an OPDS catalogue and paste the address from the **3rd Party Clients** tab. Get it from [KOReader's site](https://koreader.rocks/) or [F-Droid](https://f-droid.org/packages/org.koreader.launcher.fdroid/). [Kavita's KOReader guide](https://wiki.kavitareader.com/guides/3rdparty/koreader/) has the steps.
- **Android: Kover.** An unofficial app made for Kavita. We tested it with Kavita on 26 November 2026. Get it from [Google Play](https://play.google.com/store/apps/details?id=com.rodonisi.kover), [its project page](https://github.com/rodonisi/kover) or [its releases](https://github.com/rodonisi/kover/releases). It is also in open beta for iPhone and iPad on [TestFlight](https://testflight.apple.com/join/UsCtQUeY).
- **iPhone and iPad: [Sutra](https://apps.apple.com/app/id6780096864).** A free reader that uses OPDS and keeps your page in step with Kavita. It needs iOS 17.
- **iPhone and iPad, comics and manga: [Komic](https://apps.apple.com/dk/app/id6744676973).** It needs your Auth key. Away from home it needs an `https` address.

Kavita's wiki lists more apps under [other apps made for Kavita](https://wiki.kavitareader.com/guides/3rdparty/kavita-dedicated).

In Starboard, the same list is under **Read on your phone** on this plug-in's page and in **Settings**, **Apps**, **Manage apps**.

## What it may do

- It can read: Files in your media folder under books (read only).
- It can read: Files in your media folder under comics (read only).
- It can change: Its own folder in Starboard's data (data/plugins/kavita).
- It can reach: Other computers on your home network, and the internet.
- It can reach: Its own web page on your home network. Anyone on your home network can open it, at this computer's address and a port Starboard chooses.

It runs read only, as a user that is not root, with no extra rights, like every plug-in. Its images, pinned by digest:

- `app`: `docker.io/jvmilazz0/kavita@sha256:31181a32f0dda73cae68721867028a7253d57881b58bea5754cd9e578e75421a`

## At rest

What it uses when nobody is using it, measured with `tools/app_check.py` (median of 36 readings over 3 minutes, after
2 minutes to settle). A real library uses more.

| Reading | Memory | Processor (one core) |
|---|---|---|
| As Starboard runs it (hardened, empty library), 13 November 2026 | 339.1 MiB | 0.77% |
| 13 November benchmark (`bench-2026-11-13/RESULTS.md`, no limits) | 337.4 MiB | 0.99% |

## Removing it

**Settings**, **Plug-ins**, Kavita, **Remove**. Its containers stop and go and its key stops working. You choose
where its folder goes, with everything it kept (settings). It is either
kept in `data/plugins/.removed` or moved to the holding folder in **System**, **Clean up**.
From there you can put it back or delete it permanently. Starboard never deletes it. Your media folder is not touched.

## Licence

This plug-in is MIT, by TheMightyTRexUK. Kavita itself is under the GPL-3.0 licence, made by others: https://www.kavitareader.com
