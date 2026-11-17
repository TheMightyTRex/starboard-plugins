# Audio description: Accessibility

Starboard draws everything Audio description shows in Starboard: its settings, buttons, cards and messages, with the same parts as the rest of Starboard. They follow your **Display** choices: text size, spacing, theme, **High contrast**, underlined links and reduced motion.

## What was checked

- **The plug-in tester:** accessibility passed, checking settings, cards and actions. Starboard runs it before the plug-in is added, every time.
- **Its logo**, a loudspeaker with sound waves, has the text description "Audio description logo" where it is shown without its name. Beside its name, screen readers skip it, so the name is read once.
- **Its cards** say their status in words with an icon, never by colour alone. A screen reader hears the card's heading, then its status and when it last changed. Nothing on a card interrupts a screen reader when it refreshes.
- **What it is for:** it helps blind and partially sighted people find films and series with a described sound track, and keep that track in Jellyfin.
- **Its words:** a test checks that what people read on its pages and cards, and its README, has no em dashes or contractions.
- **Its links** each say where they go, such as "Search AudioVault for" and the title, and open in a new tab.
- **Long lists** on **Search AudioVault** and **Search YouDescribe** open by first letter when Films or Series has more than 80 titles, so no page is too long to move through.
- **Not checked:** the sites and phone apps it links to, such as AudioVault, YouDescribe, MovieReading and Earcatch. They are not part of Starboard.
- **Starboard's own parts** (settings, buttons, dialogs and cards) are checked with axe, a keyboard walk and the reading order in each Starboard release. Read [How Starboard is tested](https://themightytrex.github.io/starboard/help/accessibility/how-starboard-is-tested.html).

## Find out more

- [Accessibility in Starboard](https://themightytrex.github.io/starboard/help/accessibility/overview.html)
- [Problems](problems.md)
