# Themearr: Settings

Themearr's settings are on its own tab: go to **Settings**, then **Plug-ins**, then **Themearr**. Starboard draws them and keeps them; secrets are never shown again once saved. Everything else is set in Themearr itself, on its own page.

## Fetching theme tunes

| Setting | What it does | Default |
|---|---|---|
| **RapidAPI key** | Themearr fetches each tune through the youtube-mp36 service on RapidAPI. Make a RapidAPI account, subscribe to youtube-mp36 (its free plan has a monthly limit) and enter the key it gives you. | Empty |
| **RapidAPI user name** | The user name of the same RapidAPI account. | Empty |
| **Fetch tunes for new films by itself** | Themearr finds a tune for each film and fetches it. Off, you choose each tune on Themearr's own page. | Active |

Starboard passes the key and user name to Themearr within 2 minutes of **Save**, and again each time you change them. Left empty, a key you entered in Themearr's own page stays.

## Settings

| Setting | What it does | Default |
|---|---|---|
| **Sign in to Themearr** | A page of its own with the access token Themearr's own page asks for once in each web browser. You can read it, but not change it. | None |

## Things to note

- **Nothing to enter for Reelix.** Starboard gives Themearr Reelix's address and key as its Radarr, because Reelix answers Radarr's API. Themearr reads every film Reelix has a file for, every 15 minutes.
- **Where the films are.** Themearr is given your `movies` folder at `/media/movies`, and told that Reelix's `/data/media/movies` is the same folder.
- **The access token** is made by Starboard for this install. Anyone with it can change Themearr's settings, so keep it private. It is shown only on Themearr's tab, to people who can open Starboard's settings.
- **Fetching by itself** Starboard gives this to Themearr when the plug-in first starts and each time you change the switch. A choice you make in Themearr's own page stays until then.
- **The tunes are full length** unless you choose trimming in Themearr's own settings. Read Themearr's own help for how much space they take: about 3.7 GB for every 1,000 films.
- Settings are kept when you update or turn it off, and when you remove it they stay in its folder.

## Find out more

- [Install](install.md)
- [Dashboard card](dashboard-card.md)
- [Problems](problems.md)
