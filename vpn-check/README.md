# VPN check

Shows the address and country your downloads use through the VPN, and warns if it is your home address.

An example Starboard plug-in by TheMightyTRexUK, MIT licence.

## What it may do

- It runs inside your VPN.
- It runs one small container (48 MB of memory at most).

## On the dashboard

- **VPN**: a status card.

## Settings

- **Your home's public address**: Optional, such as 81.2.69.160. If the VPN ever shows this address, the card turns red.
- **Check every**

## Add it

In Starboard, open **Settings**, **Plug-ins**, **Add a plug-in**, and give this address:

`https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/vpn-check/starboard-plugin.json`

Or run `python3 install.py` in this folder.
