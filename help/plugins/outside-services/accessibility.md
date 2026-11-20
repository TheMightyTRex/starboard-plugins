# Uptime and status: Accessibility

Starboard draws everything Uptime and status shows in Starboard: its settings, its Checks and Groups lists, buttons, cards and messages, with the same parts as the rest of Starboard. They follow your **Display** choices: text size, spacing, theme, **High contrast**, underlined links and reduced motion.

## What was checked

- **The plug-in tester:** accessibility passed, checking settings, cards and actions.
- **Its logo**, a heartbeat line across a circle, has the text description "Uptime and status logo" where it is shown without its name.
- **Its cards** say their status in words with an icon, never by colour alone. The Response times card gives each line's latest, lowest and highest in words; the line itself is hidden from screen readers. Nothing on a card interrupts a screen reader when it refreshes.
- **The status page** is made with the TRex Design System: a skip link, one main heading, a heading for each group, a table for each with a caption and the check's name as each row's header, and status chips with words, shape and colour. It follows the device's light or dark choice. It does not refresh by itself, so a screen reader keeps its place; it says when it was written. It was checked with axe (WCAG 2.2 AA), a keyboard walk and its reading order.

## Find out more

- [Accessibility in Starboard](https://themightytrex.github.io/starboard/help/accessibility/overview.html)
- [Problems](problems.md)
