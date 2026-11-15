# Notifications: Accessibility

Starboard draws everything Notifications shows in Starboard: its settings, buttons, cards and messages, with the same parts as the rest of Starboard. They follow your **Display** choices: text size, spacing, theme, **High contrast**, underlined links and reduced motion.

## What was checked

- **The plug-in tester:** accessibility passed, checking settings, cards and actions. Starboard runs it before the plug-in is added, every time.
- **Its logo** has a text description, "A bell", for where it is shown without its name.
- **Its cards** say their status in words with an icon, never by colour alone. A screen reader hears the card's heading, then its status and when it last changed. Nothing on a card interrupts a screen reader when it refreshes.
- **Its messages** are plain sentences. The meaning is always in the words, never in a symbol or a colour, and a link has words before it: "Open Starboard:" and the address.
- **Its tests** check that every message has a title and a sentence in plain text, and that a link has words before it.
- **Not checked:** how each service, such as Telegram or Discord, shows the messages.
- **Starboard's own parts** (settings, buttons, dialogs and cards) are checked with axe, a keyboard walk and the reading order in each Starboard release. Read [How Starboard is tested](https://themightytrex.github.io/starboard/help/accessibility/how-starboard-is-tested.html).

## Find out more

- [Accessibility in Starboard](https://themightytrex.github.io/starboard/help/accessibility/overview.html)
- [Problems](problems.md)
