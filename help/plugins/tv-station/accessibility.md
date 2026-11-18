# Create your own TV channel: Accessibility

Starboard draws everything Create your own TV channel shows in Starboard: its settings, its pages, buttons, card and messages, with the same parts as the rest of Starboard. They follow your **Display** choices: text size, spacing, theme, **High contrast**, underlined links and reduced motion.

## What was checked

- **The plug-in tester:** accessibility passed, checking settings, cards and actions. Starboard runs it before the plug-in is added, every time.
- **The guide** is a real table for each channel, with column headings and the time as each row's heading, so a screen reader names each programme by its time. Search, sorting and the New or repeat filter work by keyboard.
- **Channels** opens each channel as its own page, with a back link and focus on its heading. Every choice is a list, so nothing needs a mouse.
- **New or Repeat** is in words, in the guide, on the card and on the television, never by colour alone. Each channel's colour is decoration: its name and number always say which it is.
- **Its logo**, a television with an aerial, has the text description "Create your own TV channel logo" where it is shown without its name.

## On the television

- **Contrast on any picture.** Words on the television have a dark outline, and the backing plate, activated unless you change it, puts a dark box behind the on-screen logo, the clock and the labels. Coming up next cards darken their picture to a third of its brightness, so white words on them have at least 7 to 1 contrast whatever the picture.
- **The font** is Atkinson Hyperlegible Next, made to be clear to people with low vision, as in Starboard.
- **Inside the safe area** keeps the on-screen logo and the straps in the picture on every television.
- **Broadcast packs:** words drawn on a pack's backgrounds have the same dark outline. Choose backgrounds that are dark where the words go, or set the text colour in `pack.json`; the placement guides show the title safe area. The example pack's words are white and amber on dark navy, at least 7 to 1.
- **Not carried through yet:** audio description tracks and subtitles. A channel plays the programme's default sound track. These are planned for a later version.

## Find out more

- [Accessibility in Starboard](https://themightytrex.github.io/starboard/help/accessibility/overview.html)
- [Problems](problems.md)
