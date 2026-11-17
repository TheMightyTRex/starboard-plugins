# Watching now: Dashboard card

Watching now adds 1 card you can put on your dashboard. Each starts with a band: Watching now's logo and name and a status in words. A footer says when it last changed.

## Watching now

Shows a short list, up to 10 lines: one line for each person playing something in Jellyfin, from the sessions Jellyfin saw in the last 2 minutes. Each line has the film or episode, then who is watching, on which device, how far through they are, and "paused" when they have paused it. An episode shows its series, season and episode number, such as "S01E02".

- **How often it updates:** every 30 seconds while the dashboard is open and in view. Nothing is asked while the browser tab is hidden.
- **Example:**
  - Dune: Part Two: Sam, living room TV, 40%

## What the status says

| Status | Means |
|---|---|
| **Running** | One person or more is watching. The band says "Watching", and the card lists each person. |
| **Idle** | Nobody is watching. The band says "Nobody watching" and the card says "Nobody is watching" and "Jellyfin is quiet". |

Someone who has paused is still counted as watching: their line ends with "paused".

If Watching now cannot ask Jellyfin, the card shows what went wrong instead of a list, such as "Starboard has no Jellyfin key to give yet: add Jellyfin in Settings, Apps". Read [Problems](problems.md).

## Add it to your dashboard

1. Select **Edit dashboard**.
2. In **Add a card**, choose the card. Its name ends with (Watching now), such as **Watching now (Watching now)**.
3. Select **Save**.

Watching now must be added and active first. Read [Install](install.md).

## Find out more

- [Use and change the dashboard, in Starboard's help](https://themightytrex.github.io/starboard/help/topics/use-the-dashboard.html)
- [Settings](settings.md)
- [Problems](problems.md)
