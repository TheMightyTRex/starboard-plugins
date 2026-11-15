# Tdarr: Accessibility

Starboard draws everything Tdarr shows in Starboard: its tab, its buttons and its messages, with the same parts as the rest of Starboard. They follow your **Display** choices: text size, spacing, theme, **High contrast**, underlined links and reduced motion.

## What was checked

- **The plug-in tester:** accessibility passed. Starboard runs it before the plug-in is added, every time. Tdarr has no settings, card or actions in its manifest, so there was little to check.
- **Its Settings section** is Starboard's own Tdarr settings, drawn with Starboard's parts: each choice is a labelled control and says beside itself when it is saved. It was not checked on its own for this plug-in: not checked.
- **Its logo** has a text description, "Two arrows in a circle", for where it is shown without its name.
- **Starboard's own parts** (settings, buttons, dialogs and cards) are checked with axe, a keyboard walk and the reading order in each Starboard release. Read [How Starboard is tested](https://themightytrex.github.io/starboard/help/accessibility/how-starboard-is-tested.html).

## Not checked

- **Tdarr's own web page** is made by others. Starboard did not check it for accessibility: not checked. Its link, **Open Tdarr**, says that it opens in a new tab, for screen reader users.

## Find out more

- [Accessibility in Starboard](https://themightytrex.github.io/starboard/help/accessibility/overview.html)
- [Problems](problems.md)
