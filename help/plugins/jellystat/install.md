# Jellystat: Install

Add Jellystat from Starboard's **Catalogue**, where it is listed under **Apps you can add**. Starboard shows what it may do and tests it before anything is added. At the end, Jellystat is active, with its own page on your home network.

## Before you begin

- Starboard with plug-in API 1.14 or later. An older Starboard is offered an earlier version: read [Updates](updates.md).
- Jellyfin added to Starboard, in **Settings**, **Apps**. Jellystat works with it.
- Your Starboard password. Adding and removing a plug-in ask for it.

## What it may do

Starboard lists these before you add it, each with its risk.

| It asks to | Risk |
|---|---|
| Use Jellyfin's API key, kept by Starboard (`jellyfin:key`) | High |
| Reach other computers on your home network, and the internet (`network:lan`) | Medium |
| Open its own web page on your home network, at a port Starboard chooses (`network:port`) | Medium |

What it runs:

- **main:** reaches only Starboard, on its own network: it cannot reach your home network or the internet. It can use its own folder in Starboard's data (`data/plugins/jellystat`).
- **app:** reaches your home network and the internet, and this computer as `host.docker.internal`. It can use its own folder in Starboard's data (`data/plugins/jellystat`). Its web page is on your home network at port 3000 when that port is free, or the next free one.
- **db:** reaches only Starboard, on its own network: it cannot reach your home network or the internet. It can use its own folder in Starboard's data (`data/plugins/jellystat`).

Like every plug-in, it runs read only, as a user that is not root, with no extra rights, and its image is pinned by digest, so what you approved is what runs.

## Memory and processor

- **main:** 64 MB of memory and 0.25 of a processor core at most.
- **app:** 320 MB of memory and 0.5 of a processor core at most, and 128 processes.
- **db:** 256 MB of memory and 0.5 of a processor core at most, and 128 processes.

Measured:

- 126.4 MiB at rest as Starboard runs it, with an empty library: main 14.2 MiB, app 75.3 MiB and db 36.9 MiB (13 November 2026).

## Add it

1. Go to **Settings**, then **Plug-ins**, then **Catalogue**.
2. Under **Apps you can add**, find **Jellystat** and select **Install…**.
3. A slide-out opens with what it can see, change and reach. Read it all.
4. Enter your Starboard password and select **Install Jellystat**. To stop, select **Cancel**: nothing is installed.
5. Jellystat's own tab opens under **Settings**, then **Plug-ins**. Select **Activate**. Its state changes to **Active**.

### Add it by its address

On the **Catalogue** page, under **Add one from elsewhere**, paste this into **The plug-in's manifest address**, then select **See what it does** and carry on from step 3:

```text
https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/jellystat/starboard-plugin.json
```

Or run its installer, `install.py` in its folder, on any computer with Python, and give your Starboard's address.

### Open it

Jellystat's tab shows its address on your home network, with **Open**. Anyone on your home network can open that page, so set the app's own password straight away.

## Remove it

1. Go to **Settings**, then **Plug-ins**, then **Jellystat**.
2. Under **Remove**, select **Remove Jellystat**.
3. Choose where its folder goes: **Keep it with Starboard's data** (in `data/plugins/.removed`) or **Move it to the holding folder**, listed in **System**, **Clean up**, where you can put it back or delete it for good.
4. Enter your Starboard password and select **Remove**.

Its containers stop and go, and its API key stops working. Nothing is deleted.

To stop it for a while instead, select **Deactivate** on its tab: its settings and folder are kept.

## Find out more

- [What Jellystat does](../../../jellystat/README.md)
- [Settings](settings.md)
- [Problems](problems.md)
- [Add a plug-in, in Starboard's help](https://themightytrex.github.io/starboard/help/topics/add-a-plugin.html)
- [What a plug-in can change, in Starboard's help](https://themightytrex.github.io/starboard/help/basics/what-plugins-can-change.html)
