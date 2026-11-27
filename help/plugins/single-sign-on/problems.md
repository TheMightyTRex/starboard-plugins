# Single sign-on: Problems

Find what is wrong with the Single sign-on plug-in, then follow the numbered answer.

```flow
title: Find your answer
start: The Single sign-on plug-in is not working as it should
q: What does its card say?
  Needs a name -> 1
  Name changed -> 2
  Off -> 3
  Waiting for provider -> 4
1: Choose the Tailscale name #choose-the-tailscale-name
2: Decide which name to keep #decide-which-name-to-keep
3: Activate it or leave it off #activate-it-or-leave-it-off
4: Wait for the provider #wait-for-the-provider
```

## Choose the Tailscale name

1. Go to **Settings**, then **Plug-ins**, then **Single sign-on**.
2. In **This server's Tailscale name**, enter the full name that ends in `.ts.net`, such as `starboard.tail1234.ts.net`.
3. Find the name in Tailscale's admin page under **Machines**, or run `tailscale status` on the server.
4. A `100.` address, a port such as `:8443`, a path or a space is refused. Use only the name.
5. Select **Save**, then **Check the name** under **Actions**.

## Decide which name to keep

The card says the name now in the settings differs from the one the plug-in kept. Passkeys made at one address do not work at another.

1. If the change was a mistake, enter the kept name in the setting again. The card goes back to **Waiting for provider**.
2. If you really want a new name, select **Use the new address** under **Actions**, read what it says and confirm. Every passkey made at the old name stops working and has to be made again.

## Activate it or leave it off

Single sign-on is off. Nothing runs for it, which is right on a server only you use.

1. To use it, go to **Settings**, then **Plug-ins**, then **Single sign-on**.
2. Activate **Use single sign-on** and enter the Tailscale name. Read [Settings](settings.md).

## Wait for the provider

The name is good and kept. This first version holds the settings and has no provider in it yet, so nothing can sign in through it. A later version adds the provider and says so in its release notes.

## Find out more

- [Settings](settings.md)
- [Dashboard card](dashboard-card.md)
