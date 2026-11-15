# Styles: Problems

Find what is wrong with Styles, then follow the numbered answer. Styles runs nothing of its own, so most problems are about where a style shows.

```flow
title: Find your answer
start: A style is not showing as it should
q: What does its tab say?
  Not active -> 1
  Not supported -> 2
  Active -> q2
q2: What do you see?
  No Style in Display -> 3
  The style does not change the look -> 4
  Another device has no style -> 5
1: Activate it #activate-it
2: Update it or update Starboard #update-it-or-update-starboard
3: Open Display again #open-display-again
4: Check High contrast #check-high-contrast
5: Choose it in each browser #choose-it-in-each-browser
```

## Activate it

Its styles are offered in **Display** only while Styles is active.

1. Go to **Settings**, then **Plug-ins**, then **Styles**.
2. Select **Activate**. Its state changes to **Active**.
3. Select **Display** in the header, and choose a style under **Style**.

## Update it or update Starboard

Your Starboard's plug-in API is outside what this version of Styles works with, so Starboard stopped it.

1. Select **Look for an update** on its tab.
2. If there is none, update Starboard. Read [Update Starboard](https://themightytrex.github.io/starboard/help/topics/update-starboard.html).

## Open Display again

**Style** shows in the Display panel only when an active plug-in has styles.

1. Check that Styles says **Active** on its tab.
2. Reload the page in your browser.
3. Select **Display** in the header and look for **Style**.

## Check high contrast

**High contrast** in **Display** always wins over a style, and so do text size, wider spacing, underlined links and reduced motion.

1. Select **Display** in the header.
2. Deactivate **High contrast** to see the style's own colours.
3. Select **Done**.

If you need high contrast, keep it: it is made for that. **Large and clear** is the style made for easy reading.

## Choose it in each browser

Your choice of style is kept in the browser you use, not with your sign-in. A private window may forget it when it closes.

1. On the other device, select **Display** in the header.
2. Under **Style**, choose the style.
3. Select **Done**.

## Report a problem

If none of these helps, tell its maker, with what its tab and **Display** say: [the plug-ins' issues on GitHub](https://github.com/TheMightyTRex/starboard-plugins/issues).

## Find out more

- [Settings](settings.md)
- [Updates](updates.md)
- [Choose a style from a plug-in, in Starboard's help](https://themightytrex.github.io/starboard/help/topics/display-and-accessibility.html#choose-a-style-from-a-plug-in)
