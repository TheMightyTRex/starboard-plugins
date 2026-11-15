[Help centre](../README.md) · Get started · guide
<!-- help: start / first -->

# Add your first plug-in

For anyone who has Starboard running and wants to add something from the collection. At the end, the plug-in is
active and its card is on your dashboard. It takes about five minutes.

## Before you begin

- Starboard 0.18.0 or later, with plug-in API 1.14. An older Starboard is offered each plug-in's version before.
- Your Starboard password.
- For a plug-in that works with Jellyfin, Jellyfin added in **Settings**, then **Apps**.

## The steps at a glance

1. Choose a plug-in.
2. Read what it may do.
3. Install it.
4. Set it up and activate it.
5. Add its card to your dashboard.

```flow
title: Add your first plug-in
start: Choose a plug-in | In the catalogue or this help
step: Read what it may do | Its permissions and memory
q: Happy with what it may do?
  Yes -> stepinstall
  No -> endstop
stepinstall: Install it | Enter your Starboard password
q2: Does its tab say Needs setting up?
  Yes -> stepsetup
  No -> stepactivate
stepsetup: Fill in its settings
stepactivate: Activate it
endcard: Add its card to your dashboard
endstop: Leave it out | Nothing is installed
```

## Step 1: Choose a plug-in

Read [Choose the plug-ins for your server](choose-plug-ins.md), or go to **Settings**, then **Plug-ins**, then
**Catalogue** in Starboard. A first plug-in that asks for little is Disk forecast: it only reads your disks.

## Step 2: Read what it may do

Each plug-in's Install page lists what it may do and the most memory it may use, such as
[Disk forecast's](../plugins/disk-forecast/install.md). Starboard shows the same list before you add it.

## Step 3: Install it

In the **Catalogue**, select **Install…** next to the plug-in, read the slide-out, enter your Starboard password and
select **Install** and its name. Its own tab opens. You know it worked when the tab shows its state.

## Step 4: Set it up and activate it

If the tab says **Needs setting up**, select **Finish setting up** and fill in what it asks for. Then select
**Activate**. You know it worked when its state says **Active**.

## Step 5: Add its card to your dashboard

Select **Edit dashboard**, choose its card in **Add a card**, then select **Save**. Not every plug-in has a card:
each plug-in's Dashboard card page says.

## What next

- [Use its dashboard card](../use/dashboard-cards.md)
- [Update a plug-in and roll it back](../use/update-and-roll-back.md)
- [A plug-in is not working](../fix/a-plug-in-is-not-working.md)
