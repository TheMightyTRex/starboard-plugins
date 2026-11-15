# Audio description tracks: Accessibility

Starboard draws everything Audio description tracks shows in Starboard: its settings, buttons, cards and messages, with the same parts as the rest of Starboard. They follow your **Display** choices: text size, spacing, theme, **High contrast**, underlined links and reduced motion.

## What was checked

- **The plug-in tester:** accessibility passed, checking settings, cards and actions. Starboard runs it before the plug-in is added, every time.
- **Its logo** has a text description, "A loudspeaker with a plus sign", for where it is shown without its name.
- **Its cards** say their status in words with an icon, never by colour alone. A screen reader hears the card's heading, then its status and when it last changed. Nothing on a card interrupts a screen reader when it refreshes.
- **What it is for:** it adds a described sound track for blind and partially sighted people, marked with the flag for audio description so players that read the flag can find it.
- **Its page** says each file's state in words, such as **Lengths differ** or **Added**, and says how much longer or shorter a track is in words, such as "2 minutes 4 seconds".
- **Not checked:** how each Jellyfin app lists the added track.
- **Starboard's own parts** (settings, buttons, dialogs and cards) are checked with axe, a keyboard walk and the reading order in each Starboard release. Read [How Starboard is tested](https://themightytrex.github.io/starboard/help/accessibility/how-starboard-is-tested.html).

## Find out more

- [Accessibility in Starboard](https://themightytrex.github.io/starboard/help/accessibility/overview.html)
- [Problems](problems.md)
