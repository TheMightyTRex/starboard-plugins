# Library clean-up

A small server's disks fill up with films and series that everyone has watched, or that nobody watches any more.
Library clean-up finds them by the rules you choose and moves them to a holding folder. It never deletes anything:
each item can be put back, and you delete what is in the holding folder yourself when you are sure.

Starboard never adds it by itself: you choose to add it from the catalogue. Nothing moves until you have looked at
**Preview** and activated **Move items each day**.

## What it moves

Three rules, each activated when you add it. You can deactivate any of them in **Rules**.

- **Films watched by everyone:** every person who uses Jellyfin has watched it, and the last time anyone watched it
  was more than 90 days ago (**Last watched more than**).
- **Series that ended, every episode watched:** Jellyfin says the series has ended, everyone has watched every
  episode, and the last episode anyone watched was more than the same 90 days ago.
- **Films and series nobody watches:** nobody has watched it for 12 months (**Not watched for**), and it was added
  longer ago than that, so nothing new is moved.

"Everyone" means each person who can sign in to Jellyfin. If someone never watches, such as a guest account, add
their Jellyfin user name to **People to leave out**, or the first rule never finds anything.

In **Libraries**, each film and series library in Jellyfin is listed. Choose **Deactivate** for a library the rules
should leave alone, such as a children's library.

## What it always keeps

In **Always keep**, each activated when you add it:

- **Favourites:** anything anyone has marked as a favourite in Jellyfin.
- **Something someone is part way through:** anything in anyone's **Continue watching**, and a series someone has
  started but not finished.
- **Films in a collection:** anything in one of Jellyfin's collections.
- **Keep tag:** anything with the tag `keep` in Jellyfin. To keep a film for good, add the tag to it in Jellyfin:
  open the film, choose **Edit metadata**, and add `keep` under **Tags**. Change the word, or leave it empty to use no
  tag.

## Preview

Open **Preview** before you activate anything. It lists every film and series the rules would move now, with why and
how much space each frees, and the total at the top. It is worked out in the background when you open it, which takes
a few seconds on a large library; the page updates by itself. It is worked out again when you change a setting, after
six hours, or when you choose **Preview again** in **Actions**.

Nothing moves from **Preview**. If something is listed that you want to keep, tag it `keep` in Jellyfin, or change
the rules, and look again.

## Start moving

When **Preview** lists only what you are happy to move, activate **Move items each day** in **Rules**. Once a day, in
Starboard's quiet hours, it works out the list again and moves each item:

- The item's folder goes to `media/.holding/library-cleanup`, keeping the folders it was in. A film in
  `media/movies/A Film (2001)` goes to `media/.holding/library-cleanup/movies/A Film (2001)`. A film with no folder
  of its own moves with its subtitles and the other files that share its name.
- Reelix stops following it, so it is not downloaded again.
- Jellyfin is told, so it leaves your library.

The move is instant and needs no free space: the holding folder is on the same disk, inside your media folder. If a
move would have to copy the files, it is not made. A run moves up to 200 items; the next carries on.

To run it straight away, open **System**, **Jobs** and choose **Run now** beside **Move items to the holding folder**.

## Put something back

Open **Holding folder**. It lists everything Library clean-up moved, newest first, with when, why and its size. Choose
**Put back** beside an item: it goes back to the same folder, Reelix follows it again exactly as before (the same
episodes), and Jellyfin is told, so it is back in your library within a minute. If something else is in its place
now, it stays in the holding folder and the page says so.

Jellyfin usually remembers who watched it, so it is not shown as new.

## Free the space for good

Library clean-up never deletes. When you are sure you do not want something, delete its folder in
`media/.holding/library-cleanup` yourself, with your computer's file manager or a terminal. Until then the space is
still used.

## The card on your dashboard

Add the **Holding folder** card in **Edit dashboard**. It shows how much is in the holding folder. The grey band at the
top shows the Library clean-up logo, its name and a status: **Deactivated** with what Preview would move, **Next in
quiet hours** once it is moving items each day, or **Working** while it works out Preview or moves items.

## What it may do

Before you add it, Starboard shows what it may do and asks for your password. Its risk is high.

- It reads and changes your media folder, to move films and series into the holding folder there and back. It is
  given the whole folder, so add it only if you trust it. Its code has no way to delete a file, and the collection's
  tests check that.
- It uses Jellyfin's key, to read what each person watched, their favourites and collections, and to tell Jellyfin
  what moved.
- It uses Reelix's key, to stop following what moves and follow it again when you put it back.
- It reaches your home network, where Jellyfin and Reelix are, and no other folder.
- It rests when not in use. It uses 128 MB of memory and half a processor at most.

## Updating it

When a new version is ready, the plug-in's page offers **Update** with what is new. Before the update, Library clean-up
finishes the item it is moving, so nothing is left half moved. If the new version does not start, Starboard goes back
to the version you had, with your settings as they were.

## Stop it or remove it

- **Stop it for a while:** deactivate **Move items each day**, or choose **Deactivate** for the plug-in. What is in
  the holding folder stays there.
- **Remove it:** first put back anything you want with **Put back**. After it is removed, what it moved stays in
  `media/.holding/library-cleanup`; move a folder back to where it was yourself, and Reelix will not follow it again
  until you choose **Follow** for it in Starboard's **Library**.
