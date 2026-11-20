[Help centre](../README.md) · Use it · reference
<!-- help: use / everyday -->

# Plug-ins that change your files

Four plug-ins change files on your server: Direct play, Audio description tracks and Picture shrinker change them,
and Library clean-up moves them. Each checks its work before it replaces anything, and leaves a file as it was when
the check fails. Two apps you can add change files too: Tdarr converts them by its own rules, and Themearr adds a
theme tune to each film's folder.

## When would you use it

- You want to know what can change your films, series and pictures before you add a plug-in.
- You need to know whether you can get an original back.

## Each one

| Plug-in | What it changes | How it checks | Can you keep the originals |
|---|---|---|---|
| [Direct play](../plugins/direct-play/install.md) | Films and series in `movies` and `tv`, so your devices play them directly | The length, the picture, the first sound track and where sound and picture start | Yes: **Keep the originals** moves each one to a `.direct-play-originals` folder |
| [Audio description tracks](../plugins/audio-description-tracks/install.md) | Adds a description track as a separate file next to the film, such as `Dune (2021).Audio Description.eng.mka` | The lengths of the track and the film must agree, within 5 seconds unless you change it | The film itself is never changed; a track you say does not play in step moves to **Taken off** |
| [Picture shrinker](../plugins/picture-shrinker/install.md) | Posters, backdrops, thumbnails, logos, banners, disc art, clear art and photos of people in Jellyfin's metadata folder, as **What to shrink** says | Each picture is shrunk into a hidden copy, opened again and checked; it replaces the original only when it is the right size and smaller | Yes, if **Original pictures** is **Keep a backup copy of each original**: **Restore original pictures** puts them back. Without a backup, **Start again** has Jellyfin download them again |
| [Library clean-up](../plugins/library-cleanup/install.md) | Moves whole films and series to the holding folder, `media/.holding/library-cleanup`, by the rules you set | **Preview** lists what would move first. Nothing moves until you activate **Move items each day**, then only once a day in quiet hours. Its code has no call that deletes | Yes: **Put back** in **Holding folder** returns each one where it was |
| [Tdarr](../plugins/tdarr/install.md) | Films and series, by the rules you choose in Tdarr | Tdarr's own checks | Read [Tdarr's settings](../plugins/tdarr/settings.md) |
| [Themearr](../plugins/themearr/install.md) | Adds `theme.mp3` to each film's folder | Themearr's own checks | Your films are never changed: it only adds a file |

## Things to note

- Direct play and Picture shrinker work at the lowest priority, in the hours you choose, so watching comes first.
- Before an update, each of the four stops or finishes what it is doing, so an update never leaves a half-written file.
- Removing one of them does not undo what it already changed. What Library clean-up moved stays in the holding folder.

## Find out more

- [What each plug-in may do](what-each-plug-in-may-do.md)
- [Direct play's overview](../../direct-play/README.md)
- [Picture shrinker's overview](../../picture-shrinker/README.md)
