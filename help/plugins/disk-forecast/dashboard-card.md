# Disk forecast: Dashboard card

Disk forecast adds 1 card you can put on your dashboard. Each starts with a band: Disk forecast's logo and name and a status in words. A footer says when it last changed.

## Disk forecast

Shows one line for each disk Starboard finds, such as "Pool: full in about 140 days". A disk that has not grown since the first day it kept says how full it is instead, such as "Media: 62% full, not growing".

The forecast compares how full each disk is today with the oldest day it kept, up to 35 days back. It assumes the disk carries on filling at that rate. It measures once an hour.

- **How often it updates:** once a minute while the dashboard is open. Nothing is asked while the browser tab is hidden. The forecast itself changes once an hour at most.
- **When it last changed:** when it last measured the disks.
- **Example:** Pool full in about 140 days

## What the status says

| Status | Means |
|---|---|
| **OK** | Every disk has more than 60 days left at the rate it is filling, or is not growing. |
| **Waiting** | Shown as **Measuring**. It has not measured yet. The card says "Measuring: a forecast after two days". |
| **Warning** | A disk fills in less than 60 days. The band says "Filling fast", and the card says when, such as "Pool: full in about 41 days". |
| **Problem** | A disk fills in less than 14 days, or it could not measure at all. When it could not measure, the card shows what went wrong. |

The band always counts the disk that fills first.

## Add it to your dashboard

1. Select **Edit dashboard**.
2. In **Add a card**, choose the card. Its name ends with (Disk forecast), such as **Disk forecast (Disk forecast)**.
3. Select **Save**.

Disk forecast must be added and active first. Read [Install](install.md).

## Find out more

- [Use and change the dashboard, in Starboard's help](https://themightytrex.github.io/starboard/help/topics/use-the-dashboard.html)
- [Settings](settings.md)
- [Problems](problems.md)
