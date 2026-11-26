# Immich: Dashboard card

Immich adds 3 cards you can put on your dashboard. Each starts with a band: Immich's logo and name and a status in words. A footer says when it last changed.

## Immich library

Shows how many photos and videos Immich holds, with the split and the space they use.

- **How often it updates:** every 5 minutes while the dashboard is open. Nothing is asked while the browser tab is hidden.
- **Example:** 48,210 photos and videos. 44,870 photos, 3,340 videos, 412.6 GB.

![The Immich library card in the light theme: the band with Immich's logo and OK, and the number of photos and videos](../../images/immich/dashboard-card-2-light.png)

## Immich storage

Shows where the space goes, photos and videos. Then it shows the disk Immich is on: how much is used, how full it is and how much is free. It also shows the people who use the most space.

- **How often it updates:** every 5 minutes while the dashboard is open.
- **Status:** **Nearly full** from 90% and **Full** from 98%, the same limits as Starboard's own disk card.
- **Example:**
  - Photos: 44,870, 301.2 GB
  - The disk Immich is on: 1.2 TB used of 4.0 TB (30%), 2.8 TB free

![The Immich storage card: photos and videos with their space, and the disk](../../images/immich/dashboard-card-3-storage.png)

## Immich jobs

Shows what the job queues are doing: which are working, how many jobs are waiting, and how many have failed.

- **How often it updates:** every minute while the dashboard is open.
- **Example:** Working: Thumbnails, Smart search. 340 waiting.

## What the status says

| Status | Means |
|---|---|
| **OK** | The figures were read. |
| **Working** | A job queue is busy. |
| **Idle** | Nothing is waiting. |
| **Needs attention** | Jobs have failed, or the disk is nearly full. Open Immich, Administration, Jobs to retry failed jobs. |
| **Paused** | A queue with work waiting is paused. |
| **Full** | The disk is 98% full or more. |
| **Cannot read it** | Immich did not answer, or refused the key. The card says why. |
| **Needs setting up** | No address or key is saved yet. |

## Add it to your dashboard

1. Select **Edit dashboard**.
2. In **Add a card**, choose the card. Its name ends with (Immich), such as **Immich library (Immich)**.
3. Select **Save**.

![Edit dashboard, with Immich library (Immich) chosen in Add a card (step 2) and Save (step 3) outlined](../../images/immich/dashboard-card-1-add.png)

Immich's plug-in must be added and active first. Read [Install](install.md).

## Find out more

- [Use and change the dashboard, in Starboard's help](https://themightytrex.github.io/starboard/help/topics/use-the-dashboard.html)
- [Settings](settings.md)
- [Problems](problems.md)
