# Calibre-Web: Accessibility

Starboard draws everything Calibre-Web shows in Starboard: its tab, its buttons and its messages, with the same parts as the rest of Starboard. They follow your **Display** choices: text size, spacing, theme, **High contrast**, underlined links and reduced motion.

## What was checked

- **The plug-in tester:** accessibility passed. Starboard runs it before the plug-in is added, every time. The one thing Calibre-Web adds is **Its first sign-in**: its button, the password box and the copy button were checked (read next).
- **Its logo**, a book in a browser window, has the text description "Calibre-Web logo" where it is shown without its name. Beside its name, screen readers skip it, so the name is read once.
- **Starboard's own parts** (settings, buttons, dialogs and cards) are checked with axe, a keyboard walk and the reading order in each Starboard release. Read [How Starboard is tested](https://themightytrex.github.io/starboard/help/accessibility/how-starboard-is-tested.html).

## Its first sign-in

- **Show the password…** is a button with a clear name. It opens Starboard's own dialog, which starts on **Cancel**, keeps focus inside and closes with Escape.
- The password appears in a read-only box with its own label. Focus moves to it and selects it, so a screen reader reads it and you can copy it by keyboard. **Copy the password for admin** is a button with that name.
- The result is announced in a live region, and nothing depends on colour.

## Not checked

- **Calibre-Web's own web page** is made by others. Starboard did not check it for accessibility: not checked. Its link, **Open Calibre-Web**, says that it opens in a new tab, for screen reader users.

## Find out more

- [Accessibility in Starboard](https://themightytrex.github.io/starboard/help/accessibility/overview.html)
- [Problems](problems.md)
