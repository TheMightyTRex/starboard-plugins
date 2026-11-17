# Uptime Kuma: Accessibility

Starboard draws everything Uptime Kuma shows in Starboard: its tab, its buttons and its messages, with the same parts as the rest of Starboard. They follow your **Display** choices: text size, spacing, theme, **High contrast**, underlined links and reduced motion.

## What was checked

- **The plug-in tester:** accessibility passed. Starboard runs it before the plug-in is added, every time. Uptime Kuma has no settings, card or actions in Starboard, so there was little to check.
- **Its logo**, a heartbeat line, has the text description "Uptime Kuma logo" where it is shown without its name. Beside its name, screen readers skip it, so the name is read once.
- **Starboard's own parts** (settings, buttons, dialogs and cards) are checked with axe, a keyboard walk and the reading order in each Starboard release. Read [How Starboard is tested](https://themightytrex.github.io/starboard/help/accessibility/how-starboard-is-tested.html).

## Not checked

- **Uptime Kuma's own web page** is made by others. Starboard did not check it for accessibility: not checked. Its link, **Open Uptime Kuma**, says that it opens in a new tab, for screen reader users.

## Find out more

- [Accessibility in Starboard](https://themightytrex.github.io/starboard/help/accessibility/overview.html)
- [Problems](problems.md)
