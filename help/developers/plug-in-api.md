[Help centre](../README.md) · Developers · reference
<!-- help: dev / build -->
<!-- plugin-api: 1.16 -->

# Plug-in API 1.15 for the collection

The plug-ins in the collection use plug-in API 1.14, in Starboard 0.18.0 or later, and Library clean-up uses plug-in
API 1.15, in Starboard 0.19.0 or later. This page sums up what 1.15 and 1.14 added and how the plug-ins here use them.
Starboard's help has the full references.

## When would you use it

- You want to change a plug-in here, or add one, and need to know what it must do.
- You are bringing a plug-in of your own up to 1.14, 1.15 or 1.16.

## What plug-in API 1.16 added

Plug-in API 1.16 comes with Starboard 0.23.0. Nothing was taken away: a plug-in made for 1.15 works as before.

| Part | What it is | Used here by |
|---|---|---|
| The `disk.changed` event, with `system:read` | Sent when Starboard's disk pool helper finishes a job, however it was asked for: `action` (`add`, `remove` or `balance`), `state`, `disk`, `erased` (the disks it erased) and `result` | Notifications 1.2.0 |
| `STARBOARD_HOME_ADDRESS` | For a container with `publish` on the `lan` network: its own address on the home network, such as `http://192.0.2.20:8790` | Create your own TV channel 0.1.1 |
| Plain text boxes | A custom setting's `add` box and an item's `attach` form take plain text, not only a web address: check what you are sent | Create your own TV channel |
| Activated when installed | Starboard activates a plug-in as soon as it is installed, unless it needs settings first or an app it brings in is on the computer | Every plug-in |

## What plug-in API 1.15 added

Plug-in API 1.15 came with Starboard 0.19.0. Nothing was taken away: a plug-in made for 1.14 works as before.

| Part | What it is | Used here by |
|---|---|---|
| `build` on a container | Its image is built by Starboard from the `Dockerfile` in the plug-in's zip file and tagged `local/<id>:<version>`. It installs only with **Settings**, **Plug-ins**, **Add a plug-in**, **Upload a zip file**, and updates with **Update from a zip file**. A manifest with `build` from an address or a catalogue is refused | None: every plug-in here is published with an image pinned by digest |
| `jellyfin_libraries` and `jellyfin:libraries` | Jellyfin libraries for folders the plug-in fills, which Starboard adds on each activation with real-time monitoring deactivated unless the plug-in sets `realtime_monitor`. The permission is medium risk | None yet |
| `library:holding` and the volume `media:holding` | The media folder, read and write, at `/media`, so a plug-in can move films and series into its holding folder, `media/.holding/<id>/`, keeping the folders each was in, and put them back. The permission is high risk. A container that mounts it may run as `"user": "media"` | Library clean-up |
| `restore` on a custom setting's item | An action on a row of a custom setting's list, drawn as a **Put back** button and sent as `{"action": "restore", "id"}` | Library clean-up's **Holding folder** |

## What plug-in API 1.14 added

| Part | What it is | Used here by |
|---|---|---|
| `logo` | A small SVG or PNG and its text description, shown in **Settings**, **Plug-ins**, the catalogue and on its cards | Every plug-in: a rounded tile, from `tools/make_logos.py` |
| The card band | Every card starts with a grey band: logo, name, a status chip and when it last changed. A card's answer adds `status`, `status_label` and `updated` | Every plug-in with a card, through `band()` in `_shared/sbplugin.py` |
| `refresh_seconds` | How often a card is asked, 10 to 3600 seconds, in the manifest or in its answer | Watching now, Direct play, Picture shrinker |
| `recommended` | A catalogue entry shown first, with a **Recommended** chip | Direct play, Notifications, Disk forecast |
| A `schedule` setting | Every day, week or month at a time, named by a job's `schedule` | Picture shrinker |
| `jellyfin:metadata` | Jellyfin's metadata folder, mounted as `jellyfin-metadata` | Picture shrinker |
| `update` | A `before` and an `after` step, a health wait with an automatic Roll back, and settings migrations | Every plug-in that works in the background |
| **What is new** before an update | From the new version's `changes` | Every plug-in |

## The rules every plug-in here follows

- **Fewest permissions.** Ask only for what it uses, and say why in its README.
- **Never delete media.** A plug-in with `library:holding` moves items into its holding folder and back, and has no
  call that deletes a file or a folder; its tests check that.
- **Pinned images.** Every image is pinned by digest (`@sha256:`) before it is published.
- **Small and quiet.** The smallest memory limit that works (48 to 128 MB for a card plug-in), `when_needed` when
  Starboard is the only way it is reached, and cards that read a small file rather than doing work when asked.
- **Safe updates.** A plug-in that works in the background answers `/update/before` by starting nothing new and
  finishing or stopping its work, and `/update/after` by carrying on.
- **Accessible words.** Labels under 60 characters in sentence case, a hint on every switch and choice, a title on
  every card. Starboard's plug-in tester checks them, and every plug-in here passes it.
- **The content rules:** British English, sentence case, no em dashes, no contractions; settings are activated or
  deactivated.

## Older Starboards

The catalogue keeps each plug-in's version before 1.14, at the commit it was published from, so a Starboard with an
older plug-in API is still offered one it can run. Library clean-up has no version before 1.15, so a Starboard with
plug-in API 1.14 or earlier is not offered it. When a newer plug-in API comes, `tools/check_help.py` fails until
these pages are brought up to it.

## Find out more

- [Make a plug-in for the collection](make-a-plug-in-for-the-collection.md)
- [Plug-in manifest reference, in Starboard's help](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference, in Starboard's help](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
- [API changelog, in Starboard's help](https://themightytrex.github.io/starboard/help/developers/api-changelog.html)
