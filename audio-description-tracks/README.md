# Audio description tracks

Adds a description track you already have, such as one from AudioVault, to the film or episode in Jellyfin it belongs
to. It checks first that the track and the film are the same length. So it never adds a track made for another cut of
the film by mistake.

A Starboard plug-in by TheMightyTRexUK, MIT licence. It goes with the [Audio description](../audio-description/)
plug-in, whose **Search AudioVault** list links to AudioVault's own search for each title without audio description.

## How to use it

1. Get the track yourself, for example from AudioVault after signing in there. Keep to its rules: 25 downloads a day
   for each account.
2. Put the file in the **audio-description** folder in your media folder, next to the movies and tv folders. Or upload
   it on the plug-in's **Description tracks to add** page (up to 60 MB). MP3, M4A and the like work. So does a
   zip of them, as AudioVault gives series.
3. Name it as the film and its year, such as `Dune (2021).mp3`, or a series with its episode, such as
   `Slow Horses S01E03.mp3`. When more than one title could match, choose the right one on the page.
4. The plug-in checks the lengths. When they agree, within 5 seconds unless you change it, it adds the track next to
   the film as `Dune (2021).Audio Description.eng.mka`, named **English (Audio Description)**. Then it asks Jellyfin
   to read the film again.
5. Play the film in Jellyfin, choose the English (Audio Description) sound track, and say on the page whether it
   plays in step. Yes moves the original to the **Confirmed** folder. No moves the added track to **Taken off**.

## When the lengths differ

A description track is made for one cut of a film. A different length, by more than a few seconds, almost always means
your copy is another cut. It may be an extended edition, a director's cut, a version with different studio logos at the
start, or a broadcast with its own credits. The plug-in says how much longer or shorter the track is. It does not add it.
Find a track for your cut, or line the track up yourself with describealign
(<https://pypi.org/project/describealign/>), then put the result in the folder.

## Beside Jellyfin's own Audio description plug-in

The names, the languages and how close the lengths must be follow `rules.json`. Jellyfin's own Audio description
plug-in shares this file, and adds tracks in the same way with Jellyfin's ffmpeg. When that plug-in is installed, this
one stays idle and its card says **Idle**. So the two never add the same track.

## What it may do

- It uses Jellyfin's key, which Starboard keeps: to search for the title and to ask Jellyfin to read it again.
- It reaches your home network, where Jellyfin is.
- It can add files in your media folder under movies and tv (the new sound tracks, next to their films). It can also
  add files under audio-description (its own folder). It runs as the owner of your media folder, so those files are yours.
- It runs one container (96 MB of memory at most). The container rests when it is not needed. mkvmerge, from MKVToolNix, runs
  only while a track is checked or added. It takes a few seconds each time and copies the sound as it is, without converting it.

## What it never does

- Download from, or read pages of, any website, AudioVault included.
- Change the film's own file.
- Delete anything. It moves files to **Confirmed**, **Taken off** and **Unzipped** inside the audio-description folder,
  and you delete them there when you like.

## Settings

- **Description tracks to add**: each file in the folder, what it was matched to, and what happened.
- **Language of the description tracks**: English unless you change it. The track is named after it.
- **How close the lengths must be**: 5 seconds unless you change it, from 1 to 30.
- **Check the folder now**: it also checks when its page opens, and once a night in quiet hours.

## Add it

Needs Starboard with plug-in API 1.14 or later. An older Starboard keeps version 1.0.0. In Starboard, go to **Settings**, then **Plug-ins**, then **Catalogue**, and find it there. Or, under **Add one from elsewhere**, give this address:

`https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/audio-description-tracks/starboard-plugin.json`

Or run `python3 install.py` in this folder.
