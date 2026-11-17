# VPN check: Problems

Find what is wrong with VPN check, then follow the numbered answer.

```flow
title: Find your answer
start: VPN check is not working as it should
q: What does its tab say?
  Failed or Not answering -> 1
  Not supported -> 2
  Active, but the card is wrong -> q2
q2: What does the card say?
  Home address showing -> 3
  No answer -> 4
  Problem with an error -> 4
  Checking soon for a long time -> 5
1: Start it again #start-it-again
2: Update it or update Starboard #update-it-or-update-starboard
3: Stop downloads and fix the VPN #stop-downloads-and-fix-the-vpn
4: Check the VPN is connected #check-the-vpn-is-connected
5: Wait for the first check #wait-for-the-first-check
```

## Start it again

1. On VPN check's tab, read the message under its state: it says why it stopped.
2. Check that your VPN's Gluetun container is running: VPN check runs inside its network and cannot start without it.
3. Select **Try again**.
4. If it stopped soon after an update, select **Roll back to** and the version you had. Read [Updates](updates.md).
5. Still failing: go to **System**, then **Logs**, and find its name.

## Update it or update Starboard

Your Starboard's plug-in API is outside what this version of VPN check works with, so Starboard stopped it.

1. Select **Check for an update** on its tab.
2. If there is none, update Starboard. Read [Update Starboard](https://themightytrex.github.io/starboard/help/topics/update-starboard.html).

## Stop downloads and fix the VPN

"The VPN shows your home address" means your downloads come from your home address, not from the VPN. Downloads are not hidden.

1. Pause your downloads: go to **Activity**, then **Downloads**. Read [Pause, resume and remove downloads, in Starboard's help](https://themightytrex.github.io/starboard/help/topics/manage-downloads.html).
2. Check your VPN's settings and that its subscription is still active.
3. Go to **Settings**, then **Plug-ins**, then **VPN check**, and select **Check now**.
4. When the card says **Protected** again, resume your downloads.

If your home's public address has changed, so the card is wrong, update **Your home's public address** on its tab.

## Check the VPN is connected

**No answer** means no check has worked for more than 3 times **Check every**. **Problem** with an error before the first check means none has worked yet. Either way, nothing reached the internet through the VPN.

1. Check that your VPN's Gluetun container is running and connected.
2. Select **Check now** on VPN check's tab. Starboard shows the address it found, or what went wrong.
3. If the VPN works but ipinfo.io does not answer, wait for the next check.

## Wait for the first check

"Not checked yet" with **Checking soon** means it has started but not checked yet. The first check is a few seconds after it starts.

1. Select **Check now** on its tab.
2. If Starboard shows an error, read [Check the VPN is connected](#check-the-vpn-is-connected).

## Report a problem

If none of these helps, tell its maker, with what its tab and the card say: [the plug-ins' issues on GitHub](https://github.com/TheMightyTRex/starboard-plugins/issues).

## Find out more

- [Settings](settings.md)
- [Updates](updates.md)
- [If a plug-in will not add, in Starboard's help](https://themightytrex.github.io/starboard/help/topics/add-a-plugin.html#if-it-does-not-work)
