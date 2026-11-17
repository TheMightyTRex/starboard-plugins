# Audio description: Settings

Audio description's settings are on its own tab: go to **Settings**, then **Plug-ins**, then **Audio description**. Starboard draws them and keeps them; secrets are never shown again once saved.

## Reelix searches

| Setting | What it does | Default |
|---|---|---|
| **Prefer releases with audio description** | Reelix chooses with its own Audio description format: set it to Prefer in **Settings**, **Reelix**, **Picture quality**. While this is activated, **Check the Reelix choice now** reminds you when Reelix does not prefer it. Activated or deactivated. | Activated |

## People

| Setting | What it does | Default |
|---|---|---|
| **Play the described track** | A page of its own that lists everyone in Jellyfin. Activate a person and, when they start a title with a described track while another plays, Starboard asks their app to change to the described track, within about half a minute. Not every Jellyfin app accepts this; the page says when one did not. | Nobody |
| **People who want audio description** | A page of its own that lists everyone in Jellyfin. Activate a person and Jellyfin remembers the sound track they choose, so they choose the described track once for each film and series. Deactivate them and Jellyfin goes back to what they had. | Nobody |

## Your library

| Setting | What it does | Default |
|---|---|---|
| **Add them to the Audio description collection** | The films and series with a described track go into one Jellyfin collection called Audio description, and the ones without are taken out. Every Jellyfin app shows it. Deactivated, the collection stays as it is. Activated or deactivated. | Activated |
| **Titles with audio description** | A page of its own that lists the films with a described sound track, with the track's name, and the series, with how many episodes are described, from the last check. It says when it last checked. | Not a setting |

## Elsewhere

| Setting | What it does | Default |
|---|---|---|
| **Audio description elsewhere** | A page of its own with links to places that offer audio description in their own apps, such as BBC iPlayer, ITVX, Channel 4, My5 and Netflix, and to RNIB, The Audio Description Project and AudioVault. Each link opens in a new tab. | Not a setting |

## Sources

| Setting | What it does | Default |
|---|---|---|
| **AudioVault search links** | A link to AudioVault's own search for each film and series without audio description. Starboard never downloads from AudioVault or reads its pages. Activated or deactivated. | Deactivated |
| **YouDescribe search links** | A link to YouDescribe's own search for each film and series, for described trailers and clips on YouTube. Nothing is fetched from YouDescribe. Activated or deactivated. | Activated |
| **MovieReading and Earcatch** | How to use these phone apps alongside Jellyfin, and where to get them. Neither publishes a list of titles, so Starboard cannot say which films they have. Activated or deactivated. | Activated |

## AudioVault

| Setting | What it does | Default |
|---|---|---|
| **Search AudioVault** | A page of its own, while **AudioVault search links** is activated, with a link to AudioVault's own search for each film and series without audio description. Films and series are listed apart, by first letter when there are more than 80. | Not a setting |

## YouDescribe

| Setting | What it does | Default |
|---|---|---|
| **Search YouDescribe** | A page of its own, while **YouDescribe search links** is activated, with a link to YouDescribe's own search for every film and series, each marked **Described here** or **No description here**. | Not a setting |

## MovieReading and Earcatch

| Setting | What it does | Default |
|---|---|---|
| **MovieReading and Earcatch** | A page of its own, while **MovieReading and Earcatch** under **Sources** is activated: what each app is, links to it in the App Store, on Google Play and on its website, and five steps to use one alongside Jellyfin. | Not a setting |

## Buttons

These are on Audio description's tab.

- **Check for described titles now** reads the sound tracks of every film and episode in Jellyfin straight away, in the background, instead of waiting for tonight's check. It says "Checking for described titles. The list updates in a minute or two".
- **Check the Reelix choice now** reads how Reelix treats releases with audio description and says so, such as "Reelix prefers releases with audio description in 4 quality levels". Where no level prefers them and **Prefer releases with audio description** is activated, it says "To prefer releases with audio description, set Audio description to Prefer in Settings, Reelix, Picture quality". It never changes Reelix: only an admin key may, and Starboard never gives plug-ins one.

## Things to note

- At each check, every film and episode with a described track, and each series with one, gets the tag **Audio description** in Jellyfin, and the tag comes off when the track goes. Other tags stay as they are. In any Jellyfin app, filter a library by that tag.
- When Jellyfin's own Audio description plug-in is installed, this one leaves the tag, the collection and **Play the described track** to it, and its card says **Idle**. The lists, the Reelix choice and the sources still work.
- The words, the tag and the collection's name come from the rules file it shares with the Jellyfin version, rules 1.0.
- The choice itself is made in Starboard: **Settings**, **Reelix**, **Picture quality**, where **Audio description** can be set to **Prefer**, **Neutral** or **Never**. It uses Reelix's own Audio description format, which comes with Reelix; an older Reelix has none, and the plug-in says so.
- The switches under **Sources** are used straight away: their pages show or hide their links the next time you open them.
- It checks the library once a night at 04:20, in quiet hours. The lists and cards change after each check.
- It finds a described track by its name, such as "English (Audio Description)", "AD" or "Descriptive audio". Commentary tracks never count. Jellyfin does not read the flag that marks a described track inside a file.
- It never downloads from, or reads the pages of, any website it links to, and never changes a media file.
- Settings are kept when you update or deactivate it, and when you remove it they stay in its folder.

## Find out more

- [Install](install.md)
- [Dashboard card](dashboard-card.md)
- [Problems](problems.md)
