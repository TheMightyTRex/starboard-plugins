# Immich: Accessibility

Starboard draws everything Immich shows in Starboard: its settings, buttons, cards and messages, with the same parts as the rest of Starboard. They follow your **Display** choices: text size, spacing, theme, **High contrast**, underlined links and reduced motion.

## What was checked

- **The plug-in tester:** accessibility passed, checking settings, cards and actions. Starboard runs it before the plug-in is added, every time.
- **Its logo**, a photograph with a sun and hills, has the text description "Immich logo" where it is shown without its name. Beside its name, screen readers skip it, so the name is read once.
- **Its cards** say their status in words with an icon, never by colour alone. A screen reader hears the card's heading, then its status and when it last changed. Nothing on a card interrupts a screen reader when it refreshes.
- **The storage card** is a list: each line names what it is and says its figures in words.
- **The Job queues page** is drawn by Starboard as a list: each row names the queue, says how many jobs are working, waiting and failed, and says its state in words (Working, Idle, Paused or Failed jobs). Its switch and its choice have names, work with the keyboard, and Starboard says what it did. It exists because Immich's own queue pages are hard to use with a keyboard or a screen reader. Starboard's parts are checked; this page has not yet had a screen reader pass with a real Immich.
- **The jobs card** says what is working and how many are waiting in a sentence, with its status in words.
- **Starboard's own parts** (settings, buttons, dialogs and cards) are checked with axe, a keyboard walk and the reading order in each Starboard release. Read [How Starboard is tested](https://themightytrex.github.io/starboard/help/accessibility/how-starboard-is-tested.html).

## Find out more

- [Accessibility in Starboard](https://themightytrex.github.io/starboard/help/accessibility/overview.html)
- [Problems](problems.md)
