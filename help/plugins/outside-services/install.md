# Uptime and status: Install

Add Uptime and status from Starboard's **Catalogue**, where it is listed under **Network**. Version 2.0.0 takes over Outside services: if you have Outside services, update it instead, and your addresses are kept. Read [Updates](updates.md).

## Before you begin

- Starboard with plug-in API 1.17 or later, for its **Response times** card and its alerts. An older Starboard is offered Outside services 1.1.4: read [Updates](updates.md).
- Your Starboard password. Adding and removing a plug-in ask for it.

## What it may do

Starboard lists these before you add it, each with its risk.

| Permission | Risk |
|---|---|
| Reach other computers on your home network, and the internet (`network:lan`) | Medium |
| Open its own web page on your home network, at a port Starboard chooses (`network:port`) | Medium |
| Send alerts through Starboard, to where it sends its own (`alerts:send`) | Low |

What it runs:

- **main:** reaches your home network and the internet, to run the checks. It also answers on a port of this computer for the status page and heartbeat addresses. It can use its own folder in Starboard's data (`data/plugins/outside-services`).

Like every plug-in, it runs read only, as a user that is not root, with no extra rights. Its image is pinned by digest, so what you approved is what runs.

## Memory and processor

- **main:** 48 MB of memory and 0.1 of a processor core at most.

Measured on 20 November 2026 with 7 checks: about 17 MB of memory and under 0.1% of a processor core.

## Add it

1. Go to **Settings**, then **Plug-ins**, then **Catalogue**.
2. Under **Network**, find **Uptime and status** and select **Install…**.
3. A slide-out opens with what it can read, change and reach. Read it all.
4. Enter your Starboard password and select **Install Uptime and status**. To stop, select **Cancel**: nothing is installed.
5. Its own tab opens under **Settings**, then **Plug-ins**, and Starboard turns it on.

### Add it by its address

On the **Catalogue** page, under **Add one from elsewhere**, paste this into **The plug-in's manifest address**. Then select **What it does** and carry on from step 3:

```text
https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/outside-services/starboard-plugin.json
```

Or run its installer, `install.py` in its folder, on any computer with Python, and give your Starboard's address.

## Set it up

1. Go to **Settings**, then **Plug-ins**, then **Uptime and status**, then **Checks**.
2. In **Add a check**, enter one line, such as `Router: ping 192.168.1.1 in Home`, and select **Add**. Read [Settings](settings.md) for every kind.
3. Add more, then put its cards on your dashboard. Read [Dashboard card](dashboard-card.md).
4. Open the status page from the plug-in's tab with **Open**.

## Remove it

1. Go to **Settings**, then **Plug-ins**, then **Uptime and status**.
2. Under **Remove**, select **Remove Uptime and status**.
3. Choose where its folder goes: **Keep it with Starboard's data** (in `data/plugins/.removed`) or **Move it to the holding folder**, listed in **System**, **Clean up**.
4. Enter your Starboard password and select **Remove**.

Its container stops, its API key stops working and its alerts are cleared. Nothing is deleted. To stop it for a while instead, select **Turn off** on its tab.

## Find out more

- [What Uptime and status does](../../../outside-services/README.md)
- [Settings](settings.md)
- [Problems](problems.md)
- [Add a plug-in, in Starboard's help](https://themightytrex.github.io/starboard/help/topics/add-a-plugin.html)
- [What a plug-in can change, in Starboard's help](https://themightytrex.github.io/starboard/help/basics/what-plugins-can-change.html)
