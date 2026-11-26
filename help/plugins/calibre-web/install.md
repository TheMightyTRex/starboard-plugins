# Calibre-Web: Install

Add Calibre-Web from Starboard's **Catalogue**, where it is listed under **Apps you can add**. Starboard shows what it may do and tests it before anything is added. At the end, Calibre-Web is active, with its own page on your home network, and set up.

## Before you begin

- Starboard with plug-in API 1.20 or later. An older Starboard is offered an earlier version: read [Updates](updates.md).
- Your Starboard password. Adding and removing a plug-in ask for it, and so does showing Calibre-Web's first sign-in.
- Books in the `books` folder of your media folder. Calibre-Web needs a Calibre library (a folder with `metadata.db` in it). If your books are not one yet, Starboard can make one for you: read [Your books](your-books.md).

## What it may do

Starboard lists these before you add it, each with its risk.

| Permission | Risk |
|---|---|
| Reach other computers on your home network, and the internet (`network:lan`) | Medium |
| Open its own web page on your home network, at a port Starboard chooses (`network:port`) | Medium |

What it runs:

- **app:** reaches your home network and the internet, and this computer as `host.docker.internal`. It can use its own folder in Starboard's data (`data/plugins/calibre-web`), and the `books` and `books-library` folders in your media folder, to read only. Its web page is on your home network at port 8083 when that port is free, or the next free one.

Like every plug-in, it runs read only, as a user that is not root, with no extra rights. Its image is pinned by digest, so what you approved is what runs.

## Memory and processor

- **app:** 384 MB of memory and 0.5 of a processor core at most, and 128 processes.

Measured:

- 182.2 MiB at rest as Starboard runs it, with an empty library (13 November 2026).
- 171.9 MiB at rest with version 1.2.0 and a library of 12 books, and 0.01% of one processor core (26 November 2026).

## Add it

1. Go to **Settings**, then **Plug-ins**, then **Catalogue**.
2. Under **Apps you can add**, find **Calibre-Web** and select **Install…**.
3. A slide-out opens with what it can read, change and reach. Read it all.
4. Enter your Starboard password and select **Install Calibre-Web**. To stop, select **Cancel**: nothing is installed.
5. Calibre-Web's own tab opens under **Settings**, then **Plug-ins**, and Starboard activates it: its **State**, in **General**, says **Active**. If it needs settings first, it says what to enter: save them, then select **Activate**.

### Add it by its address

On the **Catalogue** page, under **Add one from elsewhere**, paste this into **The plug-in's manifest address**, then select **What it does** and carry on from step 3:

```text
https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/calibre-web/starboard-plugin.json
```

Or run its installer, `install.py` in its folder, on any computer with Python, and give your Starboard's address.

## Set it up

Starboard sets Calibre-Web up before it first starts, so there is nothing to change in Calibre-Web's admin pages:

- **A password only you know.** Calibre-Web normally starts with the sign-in `admin` and `admin123`, which everyone knows. Starboard replaces that password with a long random one before Calibre-Web first runs.
- **Its library.** If a Calibre library is in `books-library` (made by [Calibre library maker](../calibre-library/install.md)) or in `books`, Calibre-Web is set to it at its start.
- **Closed doors.** Uploads, public sign-up, anonymous browsing and remote sign-in are off, and the admin cannot edit or delete books, because your books are read only.
- **E-reader apps.** OPDS, the way e-reader apps list your books, works with your sign-in at `/opds` on its page.

Then:

1. Go to **Settings**, then **Plug-ins**, then **Calibre-Web**, and find **Its first sign-in**.
2. Select **Show the password…**, enter your Starboard password and select **Show it once**. Starboard shows the password once, with a button to copy it. Keep it in a password manager.
3. Select **Open Calibre-Web** under **Its web page**, and sign in as `admin` with that password.
4. If it finds no books, read [Your books](your-books.md).

If you lose the password, remove Calibre-Web, choose **Move it to the holding folder**, and add it again: it makes a new one. Your books and library are not touched.

An install made before version 1.2.0 keeps the password it has. Starboard shows nothing for it, and changing that password is done in Calibre-Web, under **Admin**, then **Edit user**.

## Remove it

1. Go to **Settings**, then **Plug-ins**, then **Calibre-Web**.
2. Under **Remove**, select **Remove Calibre-Web**.
3. Choose where its folder goes: **Keep it with Starboard's data** (in `data/plugins/.removed`) or **Move it to the holding folder**, listed in **System**, **Clean up**, where you can put it back or delete it for good.
4. Enter your Starboard password and select **Remove**.

Its containers stop and go, and its API key stops working. Nothing is deleted.

To stop it for a while instead, select **Deactivate** on its tab: its settings and folder are kept.

## Find out more

- [What Calibre-Web does](../../../calibre-web/README.md)
- [Settings](settings.md)
- [Problems](problems.md)
- [Add a plug-in, in Starboard's help](https://themightytrex.github.io/starboard/help/topics/add-a-plugin.html)
- [What a plug-in can change, in Starboard's help](https://themightytrex.github.io/starboard/help/basics/what-plugins-can-change.html)
