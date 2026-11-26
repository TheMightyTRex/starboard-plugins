# Styles: Accessibility

Starboard draws everything Styles shows in Starboard: its settings, buttons and messages, with the same parts as the rest of Starboard. They follow your **Display** choices: text size, spacing, theme, **High contrast**, underlined links and reduced motion.

## What was checked

- **The plug-in tester:** accessibility passed, checking 22 styles in light and dark, settings, cards and actions. Starboard runs it before the plug-in is added, every time.
- **Its logo**, a painter's palette, has the text description "Styles logo" where it is shown without its name. Beside its name, screen readers skip it, so the name is read once.
- **Contrast:** Before you can add a style, Starboard checks every colour pair of every style, in light and dark, against WCAG 2.2. It needs 4.5:1 for text, and 3:1 for edges and the focus ring.
- **Your Display choices win:** **High contrast**, text size, wider spacing, underlined links and reduced motion always win over a style.
- **Large and clear** is made for reading with low vision: strong contrast, heavy headings, wide focus rings and no glass or texture.
- **Not checked:** how each style works with every font on your device, since a style may use fonts already there.
- **Starboard's own parts** (settings, buttons, dialogs and cards) are checked with axe, a keyboard walk and the reading order in each Starboard release. Read [How Starboard is tested](https://themightytrex.github.io/starboard/help/accessibility/how-starboard-is-tested.html).

## Find out more

- [Accessibility in Starboard](https://themightytrex.github.io/starboard/help/accessibility/overview.html)
- [Problems](problems.md)
