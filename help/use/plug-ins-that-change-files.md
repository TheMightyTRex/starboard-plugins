[Help centre](../README.md) · Use it · reference
<!-- help: use / everyday -->

# Plug-ins that change your files

Three plug-ins change files on your server: Direct play, Audio description tracks and Picture shrinker. Each checks
its work before it replaces anything, and leaves a file as it was when the check fails. Tdarr, an app you can add,
converts files too, by its own rules.

## When would you use it

- You want to know what can change your films, series and pictures before you add a plug-in.
- You need to know whether you can get an original back.

## Each one

| Plug-in | What it changes | How it checks | Can you keep the originals |
|---|---|---|---|
| [Direct play](../plugins/direct-play/install.md) | Films and series in `movies` and `tv`, so your devices play them directly | The length, the picture, the first sound track and where sound and picture start | Yes: **Keep the originals** moves each one to a `.direct-play-originals` folder |
| [Audio description tracks](../plugins/audio-description-tracks/install.md) | Adds a description track as a separate file next to the film, such as `Dune (2021).Audio Description.eng.mka` | The lengths of the track and the film must agree, within 5 seconds unless you change it | The film itself is never changed; a track you say does not play in step moves to **Taken off** |
| [Picture shrinker](../plugins/picture-shrinker/install.md) | Posters and photos of people in Jellyfin's metadata folder | Each picture is shrunk into a hidden copy, opened again and checked; it replaces the original only when it is the right size and smaller | No: once a copy passes its check it replaces the original. Jellyfin can download pictures again with **Refresh metadata** |
| [Tdarr](../plugins/tdarr/install.md) | Films and series, by the rules you choose in Tdarr | Tdarr's own checks | Read [Tdarr's settings](../plugins/tdarr/settings.md) |

## Things to note

- Direct play and Picture shrinker work at the lowest priority, in the hours you choose, so watching comes first.
- Before an update, each of the three stops or finishes what it is doing, so an update never leaves a half-written file.
- Removing one of them does not undo what it already changed.

## Find out more

- [What each plug-in may do](what-each-plug-in-may-do.md)
- [Direct play's overview](../../direct-play/README.md)
- [Picture shrinker's overview](../../picture-shrinker/README.md)
