# Home Assistant

Your house in one sentence on the dashboard: the things you choose from Home Assistant.

An example Starboard plug-in by TheMightyTRexUK, MIT licence.

## What it may do

- It reaches your home network and the internet.
- It runs one small container (48 MB of memory at most).

## On the dashboard

- **Home**: a status card.

## Settings

- **Home Assistant's address**: Such as http://192.0.2.30:8123
- **Long-lived access token**: In Home Assistant: your profile, Security, Long-lived access tokens, Create token. Kept by Starboard.
- **What to show**: One entity id each, such as binary_sensor.front_door or sensor.lounge_temperature.
- **Warn when any is**: States that turn the card amber, separated by commas.

## Add it

Needs Starboard with plug-in API 1.14 or later; a Starboard with an older plug-in API is offered the version before. In Starboard, go to **Settings**, then **Plug-ins**, then **Catalogue**, and find it under **Home**. Or, under **Add one from elsewhere**, give this address:

`https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/home-assistant/starboard-plugin.json`

Or run `python3 install.py` in this folder.
