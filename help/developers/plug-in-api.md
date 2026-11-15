[Help centre](../README.md) · Developers · reference
<!-- help: dev / build -->
<!-- plugin-api: 1.14 -->

# Plug-in API 1.14 for the collection

Every plug-in in the collection uses plug-in API 1.14, in Starboard 0.18.0 or later. This page sums up what 1.14
added and how the plug-ins here use it. Starboard's help has the full references.

## When would you use it

- You want to change a plug-in here, or add one, and need to know what it must do.
- You are bringing a plug-in of your own up to 1.14.

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
older plug-in API is still offered one it can run. When a newer plug-in API comes, `tools/check_help.py` fails until
these pages are brought up to it.

## Find out more

- [Make a plug-in for the collection](make-a-plug-in-for-the-collection.md)
- [Plug-in manifest reference, in Starboard's help](https://themightytrex.github.io/starboard/help/developers/plugin-manifest-reference.html)
- [Plug-in API reference, in Starboard's help](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html)
- [API changelog, in Starboard's help](https://themightytrex.github.io/starboard/help/developers/api-changelog.html)
