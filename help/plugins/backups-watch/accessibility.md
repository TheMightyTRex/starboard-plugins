# Backups watch: Accessibility

Starboard draws everything Backups watch shows in Starboard: its settings, buttons, cards and messages, with the same parts as the rest of Starboard. They follow your **Display** choices: text size, spacing, theme, **High contrast**, underlined links and reduced motion.

## What was checked

- **The plug-in tester:** accessibility passed, checking settings, cards and actions. Starboard runs it before the plug-in is added, every time.
- **Its logo**, two discs with a tick, has the text description "Backups watch logo" where it is shown without its name. Beside its name, screen readers skip it, so the name is read once.
- **Its cards** say their status in words with an icon, never by colour alone. A screen reader hears the card's heading, then its status and when it last changed. Nothing on a card interrupts a screen reader when it refreshes.
- **The size card** gives each backup's title and a sentence with the number of runs and the latest size. So the chart is never the only way to read it.
- **Its alerts** are plain sentences, such as "Backup overdue: documents".
- **Starboard's own parts** (settings, buttons, dialogs and cards) are checked with axe, a keyboard walk and the reading order in each Starboard release. Read [How Starboard is tested](https://themightytrex.github.io/starboard/help/accessibility/how-starboard-is-tested.html).

## Find out more

- [Accessibility in Starboard](https://themightytrex.github.io/starboard/help/accessibility/overview.html)
- [Problems](problems.md)
