# Themearr: Dashboard card

Themearr adds 1 card you can put on your dashboard. It starts with a band: Themearr's logo and name and a status in words. A footer says when it last changed.

## Film theme tunes

Shows how many of your films have a theme tune, and how many are still without one.

- **How often it updates:** every 10 minutes while the dashboard is open. Nothing is asked while the browser tab is hidden.
- **Example:** 412 films with a theme. 38 of 450 films still without a theme.

## What the status says

| Status | Means |
|---|---|
| **OK** | Themearr reads your films from Reelix and has a RapidAPI key, so it fetches their tunes. |
| **Needs setting up** | The band says "Needs a RapidAPI key". Themearr reads your films but fetches no tune until you enter a RapidAPI key and user name. Read [Settings](settings.md). |
| **Waiting** | It started moments ago and Themearr is not answering yet. The band says "Starting". |
| **Warning** | Something stops it. The band says "No Reelix", "Not connected", "Not set up" or "Problem", and the card says why, such as "Starboard has no Reelix key to give yet: add Reelix in Settings, Apps." |

It asks Themearr every 2 minutes, starting 15 seconds after it starts.

## Add it to your dashboard

1. Select **Edit dashboard**.
2. In **Add a card**, choose the card. Its name ends with (Themearr), such as **Film theme tunes (Themearr)**.
3. Select **Save**.

Themearr must be added and active first. Read [Install](install.md).

## Find out more

- [Use and change the dashboard, in Starboard's help](https://themightytrex.github.io/starboard/help/topics/use-the-dashboard.html)
- [Settings](settings.md)
- [Problems](problems.md)
