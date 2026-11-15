[Help centre](../README.md) · Developers · reference
<!-- help: dev / build -->

# Direct play's card, worked through

How Direct play's dashboard card uses plug-in API 1.14, from its manifest to its answer, as an example to copy for a
card that shows work in progress.

## When would you use it

- You are making a card for a plug-in that works in the background, such as a converter.
- You want to see the card band, `refresh_seconds` and `updated` used together.

## In the manifest

```json
{"id": "now", "title": "Direct play", "type": "list", "path": "/card", "refresh_seconds": 30}
```

A list card, asked every 30 seconds while a dashboard with it is open and in view. A second card, `saved`, is a
`stat` card with `"format": "bytes"`, asked every 10 minutes (`refresh_minutes`).

## Its answer

```json
{"items": [
  {"title": "Converting now: Dune (2021)", "detail": "Shrink, 34% done, about 1 hour 5 minutes left"},
  {"title": "Next: Slow Horses, series 1 episode 3", "detail": "Add a playable sound track"},
  {"title": "Totals", "detail": "1,173 files fixed, 1.03 TB saved, 40 files still to do"}],
 "refresh_seconds": 30, "status": "converting", "updated": 1794694110}
```

- **`items`:** what it is converting now, up to four files next, and the totals. A list shows 10 lines at most.
- **`refresh_seconds`:** from its **Card updates every** setting (10 seconds, 30 seconds, 1 minute or 5 minutes), so
  the answer wins over the manifest and people choose how lively the card is.
- **`status`:** `converting` while a file is converted, `paused` after **Pause fixing**, `done` when nothing is left,
  `needs_setup` when no device is chosen, and `waiting` otherwise. Starboard shows each as words and an icon.
- **`updated`:** when the status file last changed, never in the future, so the band says "Updated 30 seconds ago".

## Keep the answer cheap

The card reads only a small status file the worker writes, and the facts it already found about each file. Nothing
is probed or asked for when the card is asked, so a dashboard left open costs almost nothing. The worker writes the
status file only as often as the card is asked.

## Updates

Its `update.before` step stops the file being converted and starts no new one, and `update.after` lets it carry on.
The stopped file is converted again afterwards, so an update never leaves a half-written file.

## Find out more

- [Direct play: For developers](../plugins/direct-play/for-developers.md)
- [Direct play's app.py](../../direct-play/app.py)
- [The card band, in Starboard's help](https://themightytrex.github.io/starboard/help/developers/plugin-api-reference.html#the-card-band-api-114)
