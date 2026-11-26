# Audio description: Accessibility

Starboard draws everything Audio description shows in Starboard: its settings, buttons, cards and messages, with the same parts as the rest of Starboard. They follow your **Display** choices: text size, spacing, theme, **High contrast**, underlined links and reduced motion.

## What was checked

- **The plug-in tester:** accessibility passed, checking settings, cards and actions. Starboard runs it before the plug-in is added, every time.
- **Its logo**, a film frame with a speech bubble holding a loudspeaker, has the text description "Audio description logo" where its name is not shown. Beside its name, screen readers skip it, so the name is read once.
- **Its cards** say their status in words with an icon, never by colour alone. A screen reader hears the card's heading, then its status and when it last changed. Nothing on a card interrupts a screen reader when it refreshes.
- **What it is for:** it helps blind and partially sighted people find films and series with a described sound track. It also helps them keep that track in Jellyfin.
- **Its words:** a test checks that what people read on its pages and cards, and its README, has no em dashes or contractions.
- **Its links** each say where they go, such as "Search AudioVault for" and the title, and open in a new tab.
- **Titles with audio description** is a list with headings: **Films** and **Series** first, each with its count, then each series, then its episodes. Each row's name is a heading, so a screen reader can move from title to title. Its status is in words, such as **Described** or "3 of 6 episodes described", never by colour alone. When a series opens, focus moves to its heading, and **Back to Titles with audio description** returns focus to the row it came from. Each link names its title, such as "Open Harbour Lights (2019) in Jellyfin", and says it opens in a new tab.
- **Long lists** on **Search AudioVault** and **Search YouDescribe** open by first letter when Films or Series has more than 80 titles. So no page is too long to move through.
- **Not checked:** the sites and phone apps it links to, such as AudioVault, YouDescribe, MovieReading and Earcatch. They are not part of Starboard.
- **Starboard's own parts** (settings, buttons, dialogs and cards) are checked with axe, a keyboard walk and the reading order in each Starboard release. Read [How Starboard is tested](https://themightytrex.github.io/starboard/help/accessibility/how-starboard-is-tested.html).

## Find out more

- [Accessibility in Starboard](https://themightytrex.github.io/starboard/help/accessibility/overview.html)
- [Problems](problems.md)
