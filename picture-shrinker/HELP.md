# Picture shrinker

Jellyfin keeps a copy of every poster and every photo of an actor or crew member it shows, often much larger than
any television or computer needs. On a large library they can take tens of gigabytes. Picture shrinker makes them smaller, so they
take less space, and checks each one before it replaces the original.

Starboard never adds it by itself: you choose to add it from the catalogue.

## What it does

It shrinks every type of picture Jellyfin saves, each to its own size:

| Picture | Shrunk to |
|---|---|
| Posters | 900 pixels tall. Still sharp on a television |
| Photos of cast and crew | 400 pixels wide |
| Backdrops, the wide picture behind each film and series | 1920 pixels wide |
| Thumbnails, the landscape picture some apps show | 1280 pixels wide |
| Logos | 800 pixels wide |
| Banners | 1000 pixels wide |
| Disc art | 500 pixels wide |
| Clear art | 800 pixels wide |

Pictures that are already that small are left alone. Every type is shrunk when you add it; you can leave types out in
**What to shrink**.

Each picture is shrunk into a hidden copy beside it. The copy is opened again and checked, and it replaces the
original only when it is the right size and smaller. If anything is wrong, the original stays as it was.

You choose whether to keep a backup copy of each original, or shrink without a backup. With a backup, each original is copied to
the plug-in's own folder before its first shrink, and if the copy cannot be made the picture is not shrunk.

It works at the lowest priority, so your server stays quick for everything else, and people can watch while it runs.

## When it runs

In **Settings**, **Plug-ins**, **Picture shrinker**:

- **When to shrink:** choose **Every day**, **Every week** and the day, or **Every month** and the date, then the
  time. When you add it, it runs every Sunday at 03:30. In a month without the date you chose, such as the 31st in
  April, it runs on the last day.
- **Shrink now:** in **Actions**, starts a run straight away. **Stop shrinking** stops it after the picture it is on.
- **Shrink new pictures in quiet hours:** deactivated when you add it. Activate it to shrink the pictures Jellyfin
  saves for new films and series each night, in Starboard's quiet hours, so they never build up.

A run stops itself after about two hours. The next run carries on where it stopped.

## Settings

- **Shrink all picture types:** activated when you add it, so every type is shrunk in one setting. Deactivate it to
  choose types one by one with the ticks under it: **Posters**, **Photos of cast and crew**, **Backdrops**,
  **Thumbnails**, **Logos**, **Banners**, **Disc art** and **Clear art**, all activated when you add it.

In **Sizes and quality**:

- **Posters no taller than:** 900 pixels when you add it, from 300 to 3,000.
- **Photos of people no wider than:** 400 pixels when you add it, from 100 to 2,000.
- **Quality:** 85 when you add it, from 50 to 100, for JPEG and WebP pictures. PNG pictures stay lossless.
- **Backdrops no wider than:** 1920 pixels, from 640 to 3,840. Sharp on a 1080p television and a little softer
  across the whole of a 4K television.
- **Thumbnails no wider than** 1280, **Logos** 800, **Banners** 1000, **Disc art** 500 and **Clear art** 800 pixels
  when you add it, each with its own range.
Its settings are in three sections. **What to shrink** comes first, so it is the first thing you set up:

- **Original pictures:** **Keep a backup copy of each original**, or **Shrink without a backup**. Nothing is
  chosen when you add it, and after the update to 1.2.0 you choose again. Nothing is shrunk until you choose, and the
  card says **Choose a backup**. With no backup, pictures shrunk from then on cannot be put back from a backup, but
  **Start again** has Jellyfin download them again.

A smaller number saves more space. A picture already shrunk is not made larger again if you choose a larger number.

## The backup

- **Restore original pictures**, in **Actions**, puts every original back where it came from. The backup is kept.
  Change **When to shrink** first, or the next run shrinks them again.
- **Delete backup**, in **Actions**, removes the backup for good after asking you, and frees its space. **Restore
  original pictures** can then no longer put those pictures back; the shrunk pictures stay. It is refused while a run
  is going.

The first run may need almost as much free space as the pictures take now. **Space saved** shows the size of the
backup.

## Start again

**Start again** clears everything and has Jellyfin download the pictures again at full size. There are two, in
**Actions**, and each asks you first:

- **Start again: the pictures it shrinks** downloads again every picture of every type it shrinks, whatever you
  ticked in **What to shrink**. Each one is moved aside while Jellyfin downloads a new one. A picture Jellyfin cannot download again within a day, such as a poster
  you added yourself, is put back as it was.
- **Start again: every picture** has Jellyfin replace every picture of every film, series and person, backdrops and
  logos included. Pictures you added yourself in Jellyfin are replaced. It downloads much more and can take many
  hours.

Both delete the backup and the plug-in's records of what it has shrunk. Your choice in **Original pictures** is kept,
and the next run shrinks the new pictures, backing them up first if you keep a backup. Jellyfin downloads at its own
pace; **Space saved** shows how many new pictures have come so far. Start again is refused while a run is going, and
nothing is changed if Jellyfin does not answer.

## Space saved

**Space saved** in its section of **Settings**, **Plug-ins** shows the pictures now (their size and number), the
backup of the originals, the space saved and how many pictures it has shrunk, measured when you open it, and when it
runs next. Then comes a table of each run: when, what started it, how many pictures were shrunk,
left as they were or could not be read, and the space saved. Pictures it could not read are listed under **Could not
read**, with the reason.

## The card on your dashboard

Add the **Space saved** card in **Edit dashboard**. It shows the space saved, how many pictures are shrunk and the size
of the backup. The card's band shows the Picture shrinker logo, its name and its status. The card says when it runs next. A finished
run changes only these figures: it sends no notification and raises no alert.

## Jellyfin's own version

Picture shrinker is also a plug-in for Jellyfin itself, which Starboard offers in **Settings**, **Apps**, **Jellyfin**.
When it is installed, this plug-in stays idle and its card says **Idle**, so the two never shrink the same pictures.
Remove one of them.

## What it may do

Before you add it, Starboard shows what it may do and asks for your password.

- It reads and changes Jellyfin's metadata folder: the posters, photos and details Jellyfin saved. It changes only
  posters and photos of people. Jellyfin can download any picture again.
- It uses Jellyfin's key for two things: reading Jellyfin's list of plug-ins, to stay idle when Jellyfin's own version
  is installed, and, when you choose **Start again**, asking Jellyfin to download pictures again. It touches none of
  your films, series or music.
- It uses 128 MB of memory and half a processor at most.

## Updating it

When a new version is ready, the plug-in's page offers **Update** with what is new. Before the update, Picture
shrinker stops after the picture it is on, so nothing is left half done. If the new version does not start, Starboard
goes back to the version you had, with your settings as they were.

## Stop it or remove it

- **Stop it for a while:** choose **Deactivate**. Its settings and what it has saved are kept.
- **Remove it:** choose **Remove**. The pictures it shrank stay shrunk. To put them back first, choose **Restore
  original pictures**, or **Start again** to have Jellyfin download them again; to free the backup's space, choose
  **Delete backup**.
