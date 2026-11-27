# Single sign-on

One sign-in for your apps and the people who use them. This first version holds the on and off switch and the Tailscale name the provider will live at.

An example Starboard plug-in by TheMightyTRexUK, MIT licence.

## What it may do

- Nothing beyond its own folder.
- It runs one small container (32 MB of memory at most).

## On the dashboard

- **Single sign-on**: a status card.

## Settings

- **Use single sign-on**: Leave it off on a server only you use. Off means nothing runs for it. To stop the plug-in completely, deactivate it in Settings, Plug-ins, Manage.
- **This server's Tailscale name**: Such as starboard.tail1234.ts.net, found in Tailscale's admin page under Machines. Set it once. Passkeys are tied to this address for ever: if it changes, every passkey stops working and has to be made again. Tailscale needs MagicDNS and HTTPS certificates activated.

## What this version does

It holds the settings that the sign-in provider will use, and nothing else. There is no provider in it yet, so nothing signs in
through it, and it makes no network call.

- **Use single sign-on** is off until you activate it. Leave it off on a server only you use.
- **This server's Tailscale name** is the address the provider will live at, such as `starboard.tail1234.ts.net`. Set it once.
  **Passkeys are tied to this address for ever.** A passkey made at one address does not work at another, so changing the
  name later means making every passkey again.
- The first valid name is kept in the plug-in's own folder. If the setting later differs, the card says so and keeps the first
  name until you choose **Use the new address**.

Starboard stays the one page you use and the one list of people (Settings, People). The provider will work behind it.

## Add it

Needs Starboard with plug-in API 1.21 or later. A Starboard with an older plug-in API is offered the version before. In Starboard, go to **Settings**, then **Plug-ins**, then **Catalogue**, and find it under **System**. Or, under **Add one from elsewhere**, give this address:

`https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/single-sign-on/starboard-plugin.json`

Or run `python3 install.py` in this folder.
