# Calibre library maker: Accessibility

Starboard draws everything Calibre library maker shows in Starboard: its page, its buttons and its messages, with the same parts as the rest of Starboard. They follow your **Display** choices: text size, spacing, theme, **High contrast**, underlined links and reduced motion.

## What was checked

- **The plug-in tester:** accessibility passed. Starboard runs it before the plug-in is added, every time.
- **Its page** is a list. Each row has a title, a state in words (**Ready**, **Working**, **Done**, **Left out**) with a shape beside the colour, and a sentence of detail. Nothing depends on colour alone.
- **Progress** is a sentence on its own row, such as "Making your library: 120 of 836 books". It is words, not a moving bar.
- **Its buttons** have names that say what they do. **Make the library** asks first in Starboard's own dialog, which starts on **Cancel** and closes with Escape.
- **Its logo**, two books with a plus sign, has the text description "Calibre library maker logo" where it is shown without its name.
- **Starboard's own parts** are checked with axe, a keyboard walk and the reading order in each Starboard release. Read [How Starboard is tested](https://themightytrex.github.io/starboard/help/accessibility/how-starboard-is-tested.html).

## Find out more

- [Accessibility in Starboard](https://themightytrex.github.io/starboard/help/accessibility/overview.html)
- [Problems](problems.md)
