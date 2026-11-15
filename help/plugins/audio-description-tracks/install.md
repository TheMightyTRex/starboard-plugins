# Audio description tracks: Install

Add Audio description tracks from Starboard's **Catalogue**, where it is listed under **Accessibility**. Starboard shows what it may do and tests it before anything is added. At the end, Audio description tracks is active and its card is ready for your dashboard.

## Before you begin

- Starboard with plug-in API 1.14 or later. An older Starboard is offered an earlier version: read [Updates](updates.md).
- Jellyfin added to Starboard, in **Settings**, **Apps**. Audio description tracks works with it.
- Your Starboard password. Adding and removing a plug-in ask for it.

## What it may do

Starboard lists these before you add it, each with its risk.

| It asks to | Risk |
|---|---|
| Use Jellyfin's API key, kept by Starboard (`jellyfin:key`) | High |
| Reach other computers on your home network, and the internet (`network:lan`) | Medium |

What it runs:

- **main:** reaches your home network and the internet, and this computer as `host.docker.internal`. It can use its own folder in Starboard's data (`data/plugins/audio-description-tracks`), the `movies` folder in your media folder, to read and change, the `tv` folder in your media folder, to read and change, the `audio-description` folder in your media folder, to read and change. It rests after 10 minutes with nothing to do, and Starboard wakes it when it is needed.

Like every plug-in, it runs read only, as a user that is not root, with no extra rights, and its image is pinned by digest, so what you approved is what runs.

## Memory and processor

- **main:** 96 MB of memory and 0.5 of a processor core at most.

Measured: not measured yet. The figures above are the most it may use.

## Add it

1. Go to **Settings**, then **Plug-ins**, then **Catalogue**.
2. Under **Accessibility**, find **Audio description tracks** and select **Install…**.
3. A slide-out opens with what it can see, change and reach. Read it all.
4. Enter your Starboard password and select **Install Audio description tracks**. To stop, select **Cancel**: nothing is installed.
5. Audio description tracks's own tab opens under **Settings**, then **Plug-ins**. Select **Activate**. Its state changes to **Active**.

### Add it by its address

On the **Catalogue** page, under **Add one from elsewhere**, paste this into **The plug-in's manifest address**, then select **See what it does** and carry on from step 3:

```text
https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/audio-description-tracks/starboard-plugin.json
```

Or run its installer, `install.py` in its folder, on any computer with Python, and give your Starboard's address.

## Remove it

1. Go to **Settings**, then **Plug-ins**, then **Audio description tracks**.
2. Under **Remove**, select **Remove Audio description tracks**.
3. Choose where its folder goes: **Keep it with Starboard's data** (in `data/plugins/.removed`) or **Move it to the holding folder**, listed in **System**, **Clean up**, where you can put it back or delete it for good.
4. Enter your Starboard password and select **Remove**.

Its containers stop and go, and its API key stops working. Nothing is deleted. Files it already changed in your media folder stay as they are.

To stop it for a while instead, select **Deactivate** on its tab: its settings and folder are kept.

## Find out more

- [What Audio description tracks does](../../../audio-description-tracks/README.md)
- [Settings](settings.md)
- [Problems](problems.md)
- [Add a plug-in, in Starboard's help](https://themightytrex.github.io/starboard/help/topics/add-a-plugin.html)
- [What a plug-in can change, in Starboard's help](https://themightytrex.github.io/starboard/help/basics/what-plugins-can-change.html)
