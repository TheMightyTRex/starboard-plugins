# Outside services

Up or down for things that are not on this server: your router, a NAS, a website.

An example Starboard plug-in by TheMightyTRexUK, MIT licence.

## What it may do

- It reaches your home network and the internet.
- It runs one small container (48 MB of memory at most).

## On the dashboard

- **Outside services**: a status card.
- **Outside services**: a list card.

## Settings

- **Addresses to check**: One each, such as http://192.168.1.1 or https://example.org. Give a name first if you like: Router http://192.168.1.1
- **Check every**

## Add it

In Starboard, open **Settings**, **Plug-ins**, **Add a plug-in**, and give this address:

`https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/outside-services/starboard-plugin.json`

Or run `python3 install.py` in this folder.
