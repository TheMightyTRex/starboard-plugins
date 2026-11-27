# Single sign-on: Accessibility

Starboard draws everything Single sign-on shows in Starboard: its settings, buttons, cards and messages, with the same parts as the rest of Starboard. They follow your **Display** choices: text size, spacing, theme, **High contrast**, underlined links and reduced motion.

## What was checked

- **The plug-in tester:** accessibility passed, checking settings, cards and actions. Starboard runs it before the plug-in is added, every time.
- **Its logo**, a key, has the text description "Single sign-on logo" where it is shown without its name. Beside its name, screen readers skip it, so the name is read once.
- **Its card** says its status in words with an icon, never by colour alone. A screen reader hears the card's heading, then its status and when it last changed. Nothing on the card interrupts a screen reader when it refreshes.
- **Its settings and buttons** are Starboard's own switch, text box and buttons. **Use the new address** asks first in a dialog that starts on Cancel.
- **Starboard's own parts** (settings, buttons, dialogs and cards) are checked with axe, a keyboard walk and the reading order in each Starboard release. Read [How Starboard is tested](https://themightytrex.github.io/starboard/help/accessibility/how-starboard-is-tested.html).

## What is not covered yet

The sign-in provider is not in this version. Its own pages, such as the page where a passkey is made, will be checked the same way and any gap written here before it is released.

## Find out more

- [Accessibility in Starboard](https://themightytrex.github.io/starboard/help/accessibility/overview.html)
- [Problems](problems.md)
