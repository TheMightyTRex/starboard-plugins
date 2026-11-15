# Notifications: Install

Add Notifications from Starboard's **Catalogue**, where it is listed under **System**. Starboard shows what it may do and tests it before anything is added. At the end, Notifications is active and its card is ready for your dashboard.

## Before you begin

- Starboard with plug-in API 1.14 or later. An older Starboard is offered an earlier version: read [Updates](updates.md).
- Your Starboard password. Adding and removing a plug-in ask for it.

## What it may do

Starboard lists these before you add it, each with its risk.

| It asks to | Risk |
|---|---|
| See your apps and whether they answer (`apps:read`) | Low |
| See what is downloading (`downloads:read`) | Low |
| See your films, series and books (the media folder, read only, and the library) (`media:read`) | Medium |
| See processor, memory and disks (`system:read`) | Low |
| Reach other computers on your home network, and the internet (`network:lan`) | Medium |

What it runs:

- **main:** reaches your home network and the internet, and this computer as `host.docker.internal`. It can use its own folder in Starboard's data (`data/plugins/notifications`). It rests after 5 minutes with nothing to do, and Starboard wakes it when it is needed.

Like every plug-in, it runs read only, as a user that is not root, with no extra rights, and its image is pinned by digest, so what you approved is what runs.

## Memory and processor

- **main:** 48 MB of memory and 0.1 of a processor core at most.

Measured:

- About 14 MB for about a second while it sends a message; it rests the rest of the time.

## Add it

1. Go to **Settings**, then **Plug-ins**, then **Catalogue**.
2. Under **System**, find **Notifications** and select **Install…**.
3. A slide-out opens with what it can see, change and reach. Read it all.
4. Enter your Starboard password and select **Install Notifications**. To stop, select **Cancel**: nothing is installed.
5. Notifications's own tab opens under **Settings**, then **Plug-ins**. Select **Activate**. Its state changes to **Active**.

Tip: Notifications is marked **Recommended** in the catalogue.

### Add it by its address

On the **Catalogue** page, under **Add one from elsewhere**, paste this into **The plug-in's manifest address**, then select **See what it does** and carry on from step 3:

```text
https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/notifications/starboard-plugin.json
```

Or run its installer, `install.py` in its folder, on any computer with Python, and give your Starboard's address.

## Remove it

1. Go to **Settings**, then **Plug-ins**, then **Notifications**.
2. Under **Remove**, select **Remove Notifications**.
3. Choose where its folder goes: **Keep it with Starboard's data** (in `data/plugins/.removed`) or **Move it to the holding folder**, listed in **System**, **Clean up**, where you can put it back or delete it for good.
4. Enter your Starboard password and select **Remove**.

Its containers stop and go, and its API key stops working. Nothing is deleted.

To stop it for a while instead, select **Deactivate** on its tab: its settings and folder are kept.

## Find out more

- [What Notifications does](../../../notifications/README.md)
- [Settings](settings.md)
- [Problems](problems.md)
- [Add a plug-in, in Starboard's help](https://themightytrex.github.io/starboard/help/topics/add-a-plugin.html)
- [What a plug-in can change, in Starboard's help](https://themightytrex.github.io/starboard/help/basics/what-plugins-can-change.html)
