# Home Assistant: Settings

Home Assistant's settings are on its own tab: go to **Settings**, then **Plug-ins**, then **Home Assistant**. Starboard draws them and keeps them; secrets are never shown again once saved.

## Settings

| Setting | What it does | Default |
|---|---|---|
| **Home Assistant's address** | Such as http://192.0.2.30:8123 A web address. | Empty |
| **Long-lived access token** | In Home Assistant: your profile, Security, Long-lived access tokens, Create token. Kept by Starboard. Kept secret by Starboard: it is never shown again. | Empty |
| **What to show** | One entity id each, such as binary_sensor.front_door or sensor.lounge_temperature. One a line. | Empty |
| **Warn when any is** | States that turn the card amber, separated by commas. Words. | on, open, unlocked |

## Things to note

- A setting you change is used straight away; you do not need to deactivate it first.
- Settings are kept when you update or deactivate it, and when you remove it they stay in its folder.

## Find out more

- [Install](install.md)
- [Dashboard card](dashboard-card.md)
- [Problems](problems.md)
