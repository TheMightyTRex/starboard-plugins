# Create your own TV channel: Accessibility

Starboard draws everything that Create your own TV channel shows in Starboard. That covers its settings, pages, buttons, card and messages. They use the same parts as the rest of Starboard. They follow your **Display** choices: text size, spacing, theme, **High contrast**, underlined links and reduced motion.

## What was checked

- **The plug-in tester:** accessibility passed, checking settings, cards and actions. Starboard runs it before the plug-in is added, every time.
- **The guide** is a real table for each channel. It has column headings, and the time is each row's heading, so a screen reader names each programme by its time. Search, sorting and the New or repeat filter work by keyboard.
- **Channels** opens each channel as its own page, with a back link and focus on its heading. Each part of a channel is a card with its own heading, so a screen reader can move from card to card. Every choice is a list, so nothing needs a mouse.
- **A change saves in place** (0.2.0). Focus stays on what you changed and the page does not move. A note beside it shows what was saved, such as "Corner: Bottom left. Saved for Comedy", and a screen reader reads it out once.
- **Choose from your library** (0.2.0) is a slide-out. Focus moves to its search box. Each kind is a radio button. Each item is a tick box, with its name as the label and what it is as the description. A screen reader reads out how many are shown and ticked as it changes. Escape or **Cancel** closes it, and focus goes back to **Choose from your library**.
- **A logo shown on its row** (0.2.0) has words with it, such as "Comedy's logo".
- **Suggest a schedule** (0.2.0) asks what to make the week from. The choices are radio buttons in a group, each with a linked sentence of help. It starts on the last choice for the channel.
- **Promos for viewers who cannot read the picture** (0.7.0): with **Audio description on promos** turned on, a voice says each promo's words. It also says the title, channel, day and time. It is not active unless you turn it on. [Audio description on promos](settings.md#audio-description-on-promos) says what is said.
- **New or Repeat** is in words, in the guide, on the card and on the television, never by colour alone. Each channel's colour is decoration: its name and number always say which it is.
- **Its logo**, a television with an aerial, has the text description "Create your own TV channel logo" where it is shown without its name.

## The schedule grid

The grid is the plug-in's own page. We built it to the same rules as Starboard's pages. We checked it with axe (WCAG 2.2 AA) in light and dark, and with a keyboard walk.

- **Nothing needs dragging** (WCAG 2.2, 2.5.7). Each programme has four actions: **Move 15 minutes earlier**, **Move 15 minutes later**, **Move to** a day and time, and **Pick it up, then choose a time**.
- **One Tab stop for the grid.** Use the arrow keys between times and days. Page Up and Page Down move by an hour. Home and End go to the start and end of the day. Each time is read with its day and what is on.
- **Focus** goes to a dialog's heading when it opens, back to what opened it when it closes, and to the programme after each move.
- **Works in a desktop browser.** On a phone or tablet, the grid shows one notice: to use a computer. It checks the device, not the width of the window, so a desktop browser zoomed to 400% keeps the whole page (WCAG 1.4.4 and 1.4.10).
- **Messages** are read out: what changed, from a status region, and what could not be done, from an alert.

## The break grids

The grids are the plug-in's own page. We checked them with axe (WCAG 2.2 AA) in light, dark and high contrast, at desktop, phone and 175% text size. We also checked the reading order, a Tab walk, where focus goes after each change, and what a screen reader says after each.

- **Nothing needs dragging** (WCAG 2.2, 2.5.7). Dragging is one of three ways. You can pick an item up with Space or Enter. Move it with the arrow keys. Drop it with Space or Enter, or cancel with Escape. Or you can use the buttons: **Add to** a column, **Move up**, **Move down**, **Move to** and **Remove**.
- **Every step is said** in a status line. It says when you pick an item up. It says each column and place as it changes ("Column 2, position 1 of 3"). It says when you drop, cancel or remove. A refusal is an alert.
- **Lists and groups,** not a grid role. Each column is a group named by its heading, with an ordered list of its items. The items you can add are also a list.
- **Focus** stays on the control you used. After a move, it is on the same button at the item's new place. After a drop, it is on the item. After **Remove**, it is on the next item or the column's heading.
- **Targets** are at least 44 by 44 pixels. Focus is a clear outline in every theme. Nothing depends on colour. The columns stack on a phone. Text size and zoom to 200% need no sideways scrolling. Motion is left out when your device asks. Forced colours use the browser's own.

## On the television

- **Contrast on any picture.** Words on the television have a dark outline. The backing plate puts a dark box behind the on-screen logo, the clock and the labels, and it is on unless you change it. Coming up next cards darken their picture to a third of its brightness. White words on them then have at least 7 to 1 contrast, whatever the picture.
- **The font** is Atkinson Hyperlegible Next, made to be clear to people with low vision, as in Starboard.
- **Inside the safe area** keeps the on-screen logo and the straps in the picture on every television.
- **Broadcast packs:** words drawn on a pack's backgrounds have the same dark outline. Choose backgrounds that are dark where the words go, or set the text colour in `pack.json`; the placement guides show the title safe area. The example pack's words are white and amber on dark navy, at least 7 to 1.
- **Not carried through yet:** audio description tracks and subtitles. A channel plays the programme's default sound track. These are planned for a later version.

## Find out more

- [Accessibility in Starboard](https://themightytrex.github.io/starboard/help/accessibility/overview.html)
- [Problems](problems.md)
- **Fit and Break length (0.9.0):** **Times shown** for Adverts has **Fit** as a choice, with a line of help under the list of items. Each column has a labelled **Break length** choice with its own help line. After a change, a column's warning, when it has one, is text in the column and a screen reader reads it out with what changed. Both are keyboard choices in the same order as the rest of the column.

## The file lists (0.9.0)

The page is the plug-in's own, built the same way as the break grids. We checked it with axe, the reading order, a Tab walk, where focus goes after each change, and what a screen reader says after each.

- **A search form,** with a label on each choice. The files are in a real table with column headings. The file's name is each row's heading, so a screen reader says the name with each cell.
- **A tick box on each file** is named "Tick" and the file's name; the heading's box ticks the page. How many are ticked is text beside the buttons, and read out as it changes.
- **Pages** are two buttons, **Previous page** and **Next page**, with "Page 2 of 5" between them. A screen reader says the number of files and the page when they change. Focus stays on the button you used.
- 44 pixel targets, visible focus, the same three themes, reduced motion, forced colours and phone width with the table scrolling sideways inside its own region.

