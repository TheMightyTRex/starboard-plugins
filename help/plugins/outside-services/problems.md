# Uptime and status: Problems

Find what is wrong with Uptime and status from what its tab, its lists or its cards say, then follow the numbered answer.

```flow
title: Find your answer
start: Uptime and status is not working as it should
q: What does its tab say?
  Failed or Not answering -> 1
  Not supported -> 2
  Active, but something is wrong -> q2
q2: What is wrong?
  Add a check says what to change -> 3
  A check is Down -> 4
  Ping says a port was tried -> 5
  A heartbeat is Down -> 6
  No alerts arrive -> 7
  The status page does not open -> 8
1: Start it again #start-it-again
2: Update it or update Starboard #update-it-or-update-starboard
3: Write the check again #write-the-check-again
4: Check what is down #check-what-is-down
5: Ping is not allowed #ping-is-not-allowed
6: Check the heartbeat #check-the-heartbeat
7: Check the alerts #check-the-alerts
8: Open the status page #open-the-status-page
```

## Start it again

1. On its tab, read the message under its state: it says why it stopped.
2. Select **Try again**.
3. If it stopped soon after an update, select **Roll back to** and the version you had. Read [Updates](updates.md).
4. Still failing: go to **System**, then **Logs**, and find its name.

## Update it or update Starboard

Your Starboard's plug-in API is outside what this version works with, so Starboard stopped it. Uptime and status needs plug-in API 1.17.

1. Select **Check for an update** on its tab.
2. If there is none, update Starboard. Read [Update Starboard](https://themightytrex.github.io/starboard/help/topics/update-starboard.html).

## Write the check again

**Add a check** says what it could not read, such as "Write it as 192.168.1.5:445". Each check is a name, a colon, a kind and what to check: `NAS: tcp 192.168.1.5:445`. Words with spaces go between quote marks. Read [Settings](settings.md) for every kind.

## Check what is down

Its row and the Checks card say why, such as "The connection was refused" or "No answer in 8 seconds".

1. Select **Test** on its row to check it now.
2. Open the address in your browser, or check the device is on and on your network.
3. Check the line with **Change**: the address, port and any words must be exactly right.
4. A device that answers only some of the time: raise **Failed checks in a row before an alert**.

## Ping is not allowed

The row says "It answers on port 80 (ping is not allowed here, so a port was tried)". The server does not let the plug-in send ping, so it knocks on ports 443, 80, 22 and 53 instead, and any answer counts. If the device answers none of them, use a `tcp` check on a port it has open.

## Check the heartbeat

A heartbeat is down when nothing called its address within its grace time, or the last call said `status=down`.

1. Copy the address from its row in **Checks**: it starts with this computer's address and ends with `/push/` and its secret.
2. Check the job calls it at its end, from a computer on your home network.
3. If the job runs less often than the grace time, change it with **Change**, such as `grace 25h` for a job each day.

## Check the alerts

1. Check **Send alerts through Starboard** is active, in **Alerts**.
2. Check the check's group is active and not in a maintenance window, in **Groups and maintenance**.
3. Check Starboard's own alerts arrive: in Starboard's alert settings, select **Send a test alert**.
4. If **All checks** says "This Starboard does not take alerts from plug-ins yet", update Starboard.

## Open the status page

1. Check **Status page on your home network** is active, in **Status page**.
2. Open it from the plug-in's tab with **Open**, from a computer or phone on your home network. It is not reachable from outside your home.

## Report a problem

If none of these helps, tell its maker, with what its tab and the cards say: [the plug-ins' issues on GitHub](https://github.com/TheMightyTRex/starboard-plugins/issues).

## Find out more

- [Settings](settings.md)
- [Updates](updates.md)
- [If a plug-in will not add, in Starboard's help](https://themightytrex.github.io/starboard/help/topics/add-a-plugin.html#if-it-does-not-work)
