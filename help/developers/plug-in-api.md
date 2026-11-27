[Help centre](../README.md) · Developers · reference
<!-- help: dev / build -->
<!-- plugin-api: 1.24 -->

# Plug-in API 1.15 for the collection

The plug-ins in the collection use plug-in API 1.14, in Starboard 0.18.0 or later, and Library clean-up uses plug-in
API 1.15, in Starboard 0.19.0 or later. This page sums up what 1.15 and 1.14 added and how the plug-ins here use them.
Starboard's help has the full references.

## When would you use it

- You want to change a plug-in here, or add one, and need to know what it must do.
- You are bringing a plug-in of your own up to 1.14, 1.15, 1.16 or 1.17.

## What plug-in API 1.24 added

- `power:hold` and `POST /api/v1/plugin/hold`: a plug-in may ask Starboard to hold its heavy automatic jobs, scheduled backups and downloads, for example while the computer runs on battery. The hold ends by itself after 10 minutes unless the plug-in asks again, and what was held starts afterwards. UPS and power 0.2.0 uses it. Read [Holding heavy jobs](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html#holding-heavy-jobs-api-124).
- The `time` setting type: one time of day, such as `22:00`, in a time box.

## What plug-in API 1.22 added

- `starboard_tested` and `capabilities`: a plug-in names the newest plug-in API it was tested with, and the optional parts of Starboard it needs or uses. No plug-in here uses them yet.

## What plug-in API 1.21 added

- `needs_plugins` and `switch`: a plug-in may list the plug-ins it needs, and name its own main switch. Deactivating a plug-in, or saving its switch as inactive, asks first when other active plug-ins need it, names them in plain words, and deactivates them too on a yes. Single sign-on 0.1.0 uses `switch`. Read the [manifest reference](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html#plug-ins-that-need-another-plug-in-needs_plugins-and-switch).

## What plug-in API 1.20 added

- `first_sign_in`: Starboard makes a password for an app plug-in, the app sets it before it first starts, and the plug-in's page shows it once, after the Starboard password. Calibre-Web 1.2.0 uses it, so it does not start with the default sign-in everyone knows. A plug-in that needs it names `>=1.20` in `starboard_api`, so an older Starboard is offered the earlier version.

## What plug-in API 1.17 added

Plug-in API 1.17 comes with the Starboard release after 0.24. Nothing was taken away: a plug-in made for 1.16 works as before.

| Part | What it is | Used here by |
|---|---|---|
| The `sparkline` card | `{"series": [{"title", "points", "unit", "detail"}], "note"}`: up to 8 series of up to 96 numbers (`null` for a gap). Starboard draws a small line for each, hidden from screen readers, and writes the latest, lowest and highest in words | Uptime and status's **Response times** |
| `alerts:send` and `POST /api/v1/plugin/alerts` | A plug-in raises and clears alerts with its own key: `{"key", "state": "raised" or "cleared", "title", "message", "level"}`. Each key is sent once until it is cleared, through the same channel, events and log as Starboard's own, at most 30 new ones an hour. The permission is low risk | Uptime and status |

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
- **Starboard's API through `starboard()`.** The helper `_shared/sbplugin.py` sends each call to the socket
  `STARBOARD_API_SOCKET` when Starboard gives one, and to `STARBOARD_API` otherwise. A plug-in on its own network,
  such as Disk forecast, can reach Starboard only through that socket, because Starboard runs on the server's own
  network.
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
