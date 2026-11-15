# VPN check

Shows the address and country your downloads use through the VPN, and warns if it is your home address.

An example Starboard plug-in by TheMightyTRexUK, MIT licence.

## What it may do

- It runs inside your VPN, in the network of your VPN's Gluetun container, and asks ipinfo.io which address the internet sees.
- It runs one small container (48 MB of memory at most).

## On the dashboard

- **VPN**: a status card.

## Settings

- **Your home's public address**: Optional, such as 81.2.69.160. If the VPN ever shows this address, the card turns red.
- **Check every**: how often it checks, from 5 to 240 minutes, 15 unless you change it. A new value is used after it starts again.

## Add it

Needs Starboard with plug-in API 1.14 or later. An older Starboard keeps version 1.0.0. In Starboard, go to **Settings**, then **Plug-ins**, then **Catalogue**, and find it there. Or, under **Add one from elsewhere**, give this address:

`https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/vpn-check/starboard-plugin.json`

Or run `python3 install.py` in this folder.
