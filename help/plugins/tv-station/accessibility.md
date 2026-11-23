# Create your own TV channel: Accessibility

Starboard draws everything Create your own TV channel shows in Starboard: its settings, its pages, buttons, card and messages, with the same parts as the rest of Starboard. They follow your **Display** choices: text size, spacing, theme, **High contrast**, underlined links and reduced motion.

## What was checked

- **The plug-in tester:** accessibility passed, checking settings, cards and actions. Starboard runs it before the plug-in is added, every time.
- **The guide** is a real table for each channel, with column headings and the time as each row's heading, so a screen reader names each programme by its time. Search, sorting and the New or repeat filter work by keyboard.
- **Channels** opens each channel as its own page, with a back link and focus on its heading. Each part of a channel is a card with its own heading, so a screen reader can move from card to card. Every choice is a list, so nothing needs a mouse.
- **A change saves in place** (0.2.0): focus stays on what you changed, the page does not move, and what was saved, such as "Corner: Bottom left. Saved for Comedy", is shown beside it and read out once.
- **Choose from your library** (0.2.0) is a slide-out: focus moves to its search box, each kind is a radio button, each item a tick box with its name as its label and what it is as its description, and how many are shown and ticked is read out as it changes. Escape or **Cancel** closes it, and focus goes back to **Choose from your library**.
- **A logo shown on its row** (0.2.0) has words with it, such as "Comedy's logo".
- **Suggest a schedule** (0.2.0) asks what to make the week from as radio buttons in a group, each with a sentence linked to it, and starts on the last choice for the channel.
- **Promos for viewers who cannot read the picture** (0.7.0): with **Audio description on promos** activated, a voice says each promo's words, the title, the channel, the day and the time. It is not active unless you activate it. [Audio description on promos](settings.md#audio-description-on-promos) says what is said.
- **New or Repeat** is in words, in the guide, on the card and on the television, never by colour alone. Each channel's colour is decoration: its name and number always say which it is.
- **Its logo**, a television with an aerial, has the text description "Create your own TV channel logo" where it is shown without its name.

## The schedule grid

The grid is the plug-in's own page, built to the same rules as Starboard's, and checked with axe (WCAG 2.2 AA) in light and dark, with a keyboard walk.

- **Nothing needs dragging** (WCAG 2.2, 2.5.7): each programme's actions have **Move 15 minutes earlier**, **Move 15 minutes later**, **Move to** a day and time, and **Pick it up, then choose a time**.
- **One Tab stop for the grid**, then the arrow keys between times and days, Page Up and Page Down by an hour, Home and End for the start and end of the day. Each time is read with its day and what is on.
- **Focus** goes to a dialog's heading when it opens, back to what opened it when it closes, and to the programme after each move.
- **Works in a desktop browser.** On a phone or tablet, the grid shows one notice: to use a computer. It checks the device, not the width of the window, so a desktop browser zoomed to 400% keeps the whole page (WCAG 1.4.4 and 1.4.10).
- **Messages** are read out: what changed, from a status region, and what could not be done, from an alert.

## The break grids

The grids are the plug-in's own page, checked with axe (WCAG 2.2 AA) in light, dark and high contrast, at desktop, phone and 175% text size, with the reading order, a Tab walk, where focus goes after each change and what is said after each.

- **Nothing needs dragging** (WCAG 2.2, 2.5.7). Dragging is one of three ways: pick an item up with Space or Enter, move it with the arrow keys, drop it with Space or Enter, cancel with Escape; or use the buttons: **Add to** a column, **Move up**, **Move down**, **Move to** and **Remove**.
- **Every step is said** in a status line: picked up, each column and place as it changes ("Column 2, position 1 of 3"), dropped, cancelled and removed. A refusal is an alert.
- **Lists and groups,** not a grid role: each column is a group named by its heading with an ordered list of its items, and the items you can add are a list.
- **Focus** stays on the control you used. After a move it is on the same button at the item's new place; after a drop it is on the item; after **Remove** it is on the next item or the column's heading.
- **Targets** are at least 44 by 44 pixels, focus is a clear outline in every theme, nothing depends on colour, the columns stack on a phone, text size and zoom to 200% need no sideways scrolling, motion is left out when your device asks, and forced colours use the browser's own.

## On the television

- **Contrast on any picture.** Words on the television have a dark outline, and the backing plate, activated unless you change it, puts a dark box behind the on-screen logo, the clock and the labels. Coming up next cards darken their picture to a third of its brightness, so white words on them have at least 7 to 1 contrast whatever the picture.
- **The font** is Atkinson Hyperlegible Next, made to be clear to people with low vision, as in Starboard.
- **Inside the safe area** keeps the on-screen logo and the straps in the picture on every television.
- **Broadcast packs:** words drawn on a pack's backgrounds have the same dark outline. Choose backgrounds that are dark where the words go, or set the text colour in `pack.json`; the placement guides show the title safe area. The example pack's words are white and amber on dark navy, at least 7 to 1.
- **Not carried through yet:** audio description tracks and subtitles. A channel plays the programme's default sound track. These are planned for a later version.

## Find out more

- [Accessibility in Starboard](https://themightytrex.github.io/starboard/help/accessibility/overview.html)
- [Problems](problems.md)
