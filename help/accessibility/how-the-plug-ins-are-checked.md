[Help centre](../README.md) · Accessibility · reference
<!-- help: a11y / checks -->

# How the plug-ins are checked for accessibility

Every plug-in in the collection is checked for accessibility before it is published, and again by Starboard before
you add it. What a plug-in shows in Starboard is drawn by Starboard itself, so it follows your **Display** choices.

## When would you use it

- You use a screen reader, only a keyboard, large text or high contrast, and want to know what to expect.
- You want to know what was not checked.

## What every plug-in gets

- **Starboard draws it.** A plug-in sends words and numbers, never its own page code. Its settings, buttons, tables
  and cards are Starboard's own parts, checked with axe, a keyboard walk and the reading order in every Starboard
  release.
- **Your Display choices win.** Text size, spacing, theme, **High contrast**, underlined links and reduced motion
  apply to everything a plug-in shows.
- **Cards say their status in words,** with an icon, never by colour alone. A screen reader hears the card's heading,
  then its status and when it last changed. A card refreshing does not interrupt a screen reader.
- **Logos have text descriptions,** and a logo is always shown with the plug-in's name.

## What was checked

| Check | What it covers | Result |
|---|---|---|
| Starboard's plug-in tester | The words people read: labels, hints, card titles, button names; every style in light and dark | Passed for all 27 plug-ins on 15 November 2026 |
| Logo check | Each logo's colour has at least 4.5 to 1 contrast with its white symbol, and a text description | Passed for all 27 logos (`tools/make_logos.py`) |
| Styles | Every one of the 21 styles, in light and dark: text at least 4.5 to 1, edges and the focus ring 3 to 1 | Passed: a style that fails cannot be added |

## Not checked

- **The apps you can add,** such as Seerr or Kavita, have their own web pages, made by others. Starboard did not check
  those pages: not checked. Each app's Accessibility page says so.
- **Outside services a plug-in sends to,** such as Telegram or Discord for Notifications: not checked.

## Find out more

- [Plug-ins that help with accessibility](plug-ins-for-accessibility.md)
- [How Starboard is tested, in Starboard's help](https://themightytrex.github.io/starboard/help/accessibility/how-starboard-is-tested.html)
- [Accessibility in Starboard](https://themightytrex.github.io/starboard/help/accessibility/overview.html)
