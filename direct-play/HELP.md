# Direct play

Direct play makes your films and series play directly on the devices you watch on. When a device cannot play a file
as it is, Jellyfin has to convert it while you watch. This uses much of your server's processor and can make the
picture stop and start. Direct play fixes those files once, one at a time, at quiet times, so they play directly
from then on.

It is a recommended plug-in in Starboard's catalogue. Starboard never adds it by itself: you choose to add it.

## What it does

Direct play checks the films in your movies folder and the series in your tv folder. For each file a device you
chose cannot play directly, it does one of these:

- **Repackage as MKV:** the file is in an old kind of container, such as AVI. It copies the picture and sound into
  an MKV file, without converting them.
- **Add a playable sound track:** none of the file's sound tracks plays on all your devices. An example is a film with DTS
  sound and a Roku. It adds a Dolby Digital or AAC track and keeps the original track beside it.
- **Shrink:** the file is H.264 at a very high bitrate. It converts the file again at the same picture quality, so it
  takes less space. It keeps the file as it was when the new file would not be at least a tenth smaller.
- **Convert to H.264:** the picture is in an old format, such as DivX, Xvid, MPEG-2 or WMV, or it is larger than
  your devices show. It converts the file to H.264, which every device plays.

Each new file is checked before it replaces the original: its length, its picture, its first sound track and that
sound and picture start together. If anything is wrong, the original stays as it was, and the file is listed under
**Not fixed** with the reason. Then Reelix and Jellyfin are told the file changed.

It works on one file at a time, at the lowest priority, so your server stays quick for everything else.

## Which devices

In **Devices**, turn on each kind of device anyone in your home watches on:

- **Roku Express and older Rokus**
- **Roku 4K:** Roku Express 4K, Streaming Stick 4K and Ultra
- **Fire TV Sticks**
- **Chromecast**
- **Smart TV apps:** Jellyfin on Samsung and LG televisions
- **Web browsers**
- **Apple TV**
- **Nvidia Shield**

The rules follow from your choice. A file is fixed only when one of the devices you chose cannot play it. For
example, with only an Nvidia Shield, a film with DTS sound is left alone, because the Shield plays DTS. Add a Fire TV
Stick, and a playable sound track is added to that film.

Roku Express and older Rokus is on when you add it. Choose your own devices before you turn on the plug-in.

Web browsers do not play Dolby Digital sound. If you turn on **Web browsers**, files with only Dolby Digital sound
get an extra stereo track.

## Settings

### When it works

- **At weekends:** all day on Saturday and Sunday. This is the setting when you add it.
- **In Starboard's quiet hours:** your download hours, if you set them, or from 01:00 to 06:00.
- **Any time.**

The file being converted always finishes, so work can run past the end of the hours.

### Shrink

- **Shrink very large H.264 files:** turned on when you add it.
- **Shrink 1080p files over:** 15 Mbps.
- **Shrink 720p files over:** 8 Mbps.
- **Shrink smaller files over:** 5 Mbps.

### More

- **Convert HEVC to H.264:** turned off when you add it. It leaves HEVC files alone unless you turn it on, and then
  only when none of your devices plays HEVC. H.264 files are larger, so this uses more space.
- **Keep the originals:** turned off when you add it. When turned on, each original moves to a
  `.direct-play-originals` folder in your movies or tv folder instead of being replaced. Delete them there yourself
  when you are happy with the new files. No space is saved until you do.
- **Card updates every:** how often the Direct play card on your dashboard shows progress while a file is
  converted. The choices are 10 seconds, 30 seconds, 1 minute or 5 minutes. 30 seconds when you add it. The card does not update
  while the browser tab is in the background.

## The card on your dashboard

Add the **Direct play** card in **Edit dashboard**. It shows:

- **Converting now:** the film or episode, what is being done, how far it is as a percentage, and about how long is
  left.
- **Next:** the next four files and what will be done to each.
- **Totals:** how many files are fixed, how much space is saved and how many are still to do.

When nothing is being converted, it says why, such as **Waiting for the weekend**, **Paused** or **Nothing left to
do**, and when it next runs. The card shows only while the plug-in is active.

The **Space saved by Direct play** card shows only the space saved.

Each card's band shows the Direct play logo, the plug-in's name and a status. The status is **Converting**,
**Waiting**, **Paused**, **Done** or, when no device is chosen, **Needs setting up**. Beside it is when the card last
changed, such as **2 minutes ago**.

## The Files page

In **Settings**, **Plug-ins**, **Direct play**, **Files** lists every file in tables. The tables are **Converting now**, **Still to
do**, **Not fixed** with the reason, and **Left alone**, such as HEVC files. The top of the page says how many files
are fixed, how much space is saved and which file was fixed last.

## What it may do

Before you add it, Starboard shows what it may do and asks for your password.

- It reads and changes files in your media folder, in the movies and tv folders only. It runs as the owner of your
  media folder, so the new files are yours.
- It uses Jellyfin's key and Reelix's key, only to tell them a file changed.
- It reaches your home network, where Jellyfin and Reelix are.
- It uses 512 MB of memory and one processor at most.

It never downloads anything, and it never changes any folder but movies and tv.

## Updating it

When a new version of Direct play is ready, the plug-in's page offers **Update** with what is new. Before the update,
Direct play stops the file being converted, removes its unfinished copy and starts no new file, so nothing is left
half done. After the update it carries on, and converts that file again. If the new version does not start, Starboard
goes back to the version you had, with your settings as they were.

## Pause it or remove it

- **Pause:** in **Settings**, **Plug-ins**, **Direct play**, choose **Pause fixing**. The file being converted stops
  at once, its unfinished copy is removed, and the original stays as it was. Choose **Resume fixing** to carry on.
- **Check again now:** **Check the library now** checks for new or changed files straight away. Only those are read.
- **Stop it for a while:** choose **Turn off**. Its settings and what it has done are kept.
- **Remove it:** choose **Remove**. The files it already fixed stay as they are. If you used **Keep the originals**,
  the `.direct-play-originals` folders stay too, for you to delete.
