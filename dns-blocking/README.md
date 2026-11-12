# Ad blocking

How many adverts and trackers Pi-hole or AdGuard Home blocked today.

An example Starboard plug-in by TheMightyTRexUK, MIT licence.

## What it may do

- It reaches your home network and the internet.
- It runs one small container (48 MB of memory at most).

## On the dashboard

- **Blocked today**: a stat card.

## Settings

- **Which one**
- **Its address**: Such as http://192.168.1.2 for Pi-hole, or http://192.168.1.2:3000 for AdGuard Home.
- **User name**: AdGuard Home only.
- **Password**: Pi-hole's web password, or AdGuard Home's. Kept by Starboard.

## Add it

In Starboard, open **Settings**, **Plug-ins**, **Add a plug-in**, and give this address:

`https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/dns-blocking/starboard-plugin.json`

Or run `python3 install.py` in this folder.
