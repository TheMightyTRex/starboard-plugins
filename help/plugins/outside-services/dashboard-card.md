# Uptime and status: Dashboard card

Uptime and status adds 5 cards you can put on your dashboard. Each starts with a band: its logo and name and a status in words. A footer says when it last changed. Each is asked again once a minute while the dashboard is open, never while the browser tab is hidden.

## All checks

One line: whether every check is up, or which are down, such as "Down: Router, NAS". It also names any group in maintenance.

- **Example:** All 6 checks are up

## Checks

Each check by its name, the ones down first, with "Up" and its response time and uptime this week, or how long it has been down and why. Web addresses link to the address. Up to 10.

- **Example:** Router: Up, 4 ms, 99.98% this week

## Groups

One row for each group: how many of its checks are up, its uptime this week, and its maintenance window when one is on.

- **Example:** Home: Up. 3 of 3 up, 100% this week

## Response times

A small line for each check, the average each hour for the last 24 hours, up to 8, the ones down and the slowest first. Starboard writes the latest, lowest and highest in words beside each line, which is what a screen reader reads; the line is a picture of the same figures. A gap is an hour with no answer.

- **Example:** Router: Now 5 ms, lowest 4 ms, highest 6 ms. Up 99.98% of the last 24 hours

## Certificates

Each certificate, the soonest to run out first: the days left, the names it was issued for, and **Not trusted** with why for one your devices made themselves.

- **Example:** Website: 41 days left, for example.org

## What the status says

| Status | Means |
|---|---|
| **OK** | Every check is up, or every certificate has more than **Warn when a certificate has this long left**. |
| **Waiting** | Checks were added, but the first round has not finished. |
| **Needs setting up** | There are no checks yet. |
| **Down** | Shown as **Problem**: at least one check is down. |
| **Runs out soon** | Shown as **Warning** on Certificates: one runs out within the days you chose. |

## Add it to your dashboard

1. Select **Edit dashboard**.
2. In **Add a card**, choose one of **All checks**, **Checks**, **Groups**, **Response times** or **Certificates**, each with (Uptime and status) after it.
3. Select **Save**.

A dashboard that had Outside services' cards keeps them: they are now **All checks** and **Checks**.

## Find out more

- [Use and change the dashboard, in Starboard's help](https://themightytrex.github.io/starboard/help/topics/use-the-dashboard.html)
- [Settings](settings.md)
- [Problems](problems.md)
