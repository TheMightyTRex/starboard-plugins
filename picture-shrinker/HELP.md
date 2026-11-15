# Picture shrinker

Jellyfin keeps a copy of every poster and every photo of an actor or crew member it shows, often much larger than
any screen needs. On a large library they can take tens of gigabytes. Picture shrinker makes them smaller, so they
take less space, and checks each one before it replaces the original.

Starboard never adds it by itself: you choose to add it from the catalogue.

## What it does

- **Posters** are shrunk to 900 pixels tall. That is still sharp on a television.
- **Photos of cast and crew** are shrunk to 400 pixels wide.
- Pictures that are already that small are left alone. So are backdrops, logos and every other picture.

Each picture is shrunk into a hidden copy beside it. The copy is opened again and checked, and it replaces the
original only when it is the right size and smaller. If anything is wrong, the original stays as it was.

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

- **Posters no taller than:** 900 pixels when you add it, from 300 to 3,000.
- **Photos of people no wider than:** 400 pixels when you add it, from 100 to 2,000.

A smaller number saves more space. A picture already shrunk is not made larger again if you choose a larger number.

## Space saved

**Space saved** in its section of **Settings**, **Plug-ins** says how much space it has saved, how many pictures it
has shrunk, and when it runs next. Below is a table of each run: when, what started it, how many pictures were shrunk,
left as they were or could not be read, and the space saved. Pictures it could not read are listed under **Could not
read**, with the reason.

## The card on your dashboard

Add the **Space saved** card in **Edit dashboard**. It shows the space saved and how many pictures are shrunk. The grey
band at the top shows the Picture shrinker logo, its name and a status: **Running** with how many are shrunk so far,
or **Scheduled** with when it runs next. Beside it is when the card last changed.

## What it may do

Before you add it, Starboard shows what it may do and asks for your password.

- It reads and changes Jellyfin's metadata folder: the posters, photos and details Jellyfin saved. It changes only
  posters and photos of people. Jellyfin can download any picture again.
- It reaches nothing else: no network, no key and none of your films, series or music.
- It uses 128 MB of memory and half a processor at most.

## Updating it

When a new version is ready, the plug-in's page offers **Update** with what is new. Before the update, Picture
shrinker stops after the picture it is on, so nothing is left half done. If the new version does not start, Starboard
goes back to the version you had, with your settings as they were.

## Stop it or remove it

- **Stop it for a while:** choose **Deactivate**. Its settings and what it has saved are kept.
- **Remove it:** choose **Remove**. The pictures it shrank stay shrunk. Jellyfin downloads a larger copy again if you
  choose **Refresh metadata** and **Replace existing images** for a film or series in Jellyfin.
