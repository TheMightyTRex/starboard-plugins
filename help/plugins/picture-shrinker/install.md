# Picture shrinker: Install

Add Picture shrinker from Starboard's **Catalogue**, where it is listed under **Jellyfin**. Starboard shows what it may do and tests it before anything is added. At the end, Picture shrinker is active and its card is ready for your dashboard.

## Before you begin

- Starboard with plug-in API 1.14 or later. An older Starboard is offered an earlier version: read [Updates](updates.md).
- Jellyfin installed in Starboard, in **Settings**, then **Apps**. Picture shrinker works on Jellyfin's metadata folder.
- Your Starboard password. Adding and removing a plug-in ask for it.

## What it may do

Starboard lists these before you add it, each with its risk.

| Permission | Risk |
|---|---|
| Read and change Jellyfin's metadata folder: the posters, photos and details Jellyfin saved (`jellyfin:metadata`) | Medium |
| Use Jellyfin's API key, kept by Starboard (`jellyfin:key`) | High |
| Reach other computers on your home network, and the internet (`network:lan`) | Medium |

It uses Jellyfin's key to read Jellyfin's libraries and list of plug-ins. This lets it stay idle when Jellyfin's own Picture shrinker is installed. It also uses the key for **Start again**, to have Jellyfin download pictures again.

What it runs:

- **main:** reaches your home network, where Jellyfin answers. It runs all the time, at the lowest priority while it shrinks. It can use its own folder in Starboard's data (`data/plugins/picture-shrinker`), Jellyfin's metadata folder, to read and change.

Like every plug-in, it runs read only, as a user that is not root, with no extra rights. Its image is pinned by digest, so what you approved is what runs.

## Memory and processor

- **main:** 128 MB of memory and 0.5 of a processor core at most.

Measured:

- 12.1 MiB at rest, and 28.0 MiB at its busiest while it shrank a sample of 540 pictures. We measured this on 14 November 2026. The sample went from 1.17 GB down to 91 MB in 93 seconds, at half a processor.

## Add it

1. Go to **Settings**, then **Plug-ins**, then **Catalogue**.
2. Under **Jellyfin**, find **Picture shrinker** and select **Install…**.
3. A slide-out opens with what it can read, change and reach. Read it all.
4. Enter your Starboard password and select **Install Picture shrinker**. To stop, select **Cancel**: nothing is installed.
5. Picture shrinker's own tab opens under **Settings**, then **Plug-ins**. In **Original pictures**, choose **Keep a backup copy of each original** or **Shrink without a backup**. Until you choose, it says it needs setting up.
6. Select **Activate** in **General**, **State**. Its state changes to **Active**.
7. Check **When to shrink**. It runs every Sunday at 03:30 unless you change it. Read [Settings](settings.md).
8. If you want new pictures shrunk each night, activate **Shrink new pictures in quiet hours**.
9. Add its card to your dashboard. Read [Dashboard card](dashboard-card.md).

To shrink straight away, select **Shrink now** on its tab.

### Add it by its address

On the **Catalogue** page, under **Add one from elsewhere**, paste this into **The plug-in's manifest address**. Then select **What it does** and carry on from step 3:

```text
https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/picture-shrinker/starboard-plugin.json
```

Or run its installer, `install.py` in its folder, on any computer with Python, and give your Starboard's address.

## Remove it

1. Go to **Settings**, then **Plug-ins**, then **Picture shrinker**.
2. Under **Remove**, select **Remove Picture shrinker**.
3. Choose where its folder goes. Either **Keep it with Starboard's data** (in `data/plugins/.removed`) or **Move it to the holding folder**. The holding folder is listed in **System**, **Clean up**, where you can put it back or delete it for good.
4. Enter your Starboard password and select **Remove**.

Its containers stop and go, and its API key stops working. Nothing is deleted. Pictures it already shrank stay as they are.

To stop it for a while instead, select **Deactivate** on its tab: its settings and folder are kept.

## Find out more

- [What Picture shrinker does](../../../picture-shrinker/README.md)
- [Settings](settings.md)
- [Problems](problems.md)
- [Add a plug-in, in Starboard's help](https://themightytrex.github.io/starboard/help/topics/add-a-plugin.html)
- [What a plug-in can change, in Starboard's help](https://themightytrex.github.io/starboard/help/basics/what-plugins-can-change.html)
