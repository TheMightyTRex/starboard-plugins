# Home Assistant: Dashboard card

Home Assistant adds 1 card you can put on your dashboard. It starts with a band: Home Assistant's logo and name, a status in words, and when it last changed.

## Home

Shows the things in **What to show** in one sentence: each one's name in Home Assistant, its state and any unit, such as "Front door: closed. Lounge: 20.5 °C". It shows the first 8.

- **How often it updates:** once a minute while the dashboard is open. Each time, it asks Home Assistant for the state of each one. Nothing is asked while the browser tab is hidden.
- **Example:** Front door: closed. Lounge: 20.5 °C

## What the status says

| Status | Means |
|---|---|
| **OK** | Home Assistant answered, and nothing is in a state from **Warn when any is**. The time in the band is when it last asked. |
| **Warning** | At least one thing is in a state from **Warn when any is**, such as a door that is open or unlocked. The card says **Warning**. |
| **Needs setting up** | The address, the token or **What to show** is empty. The card says "Add the address, a token and what to show in the plug-in's settings". |

If Home Assistant does not answer, refuses the token or does not know an entity id, the card shows **No answer from Home Assistant** instead. Read [Problems](problems.md).

## Add it to your dashboard

1. Select **Edit dashboard**.
2. In **Add a card**, choose **Home (Home Assistant)**.
3. Select **Save**.

Home Assistant must be added and active first. Read [Install](install.md).

## Find out more

- [Use and change the dashboard, in Starboard's help](https://themightytrex.github.io/starboard/help/topics/use-the-dashboard.html)
- [Settings](settings.md)
- [Problems](problems.md)
