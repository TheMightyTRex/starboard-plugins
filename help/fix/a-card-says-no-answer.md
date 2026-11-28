[Help centre](../README.md) · Fix a problem · troubleshooting
<!-- help: fix / problems -->

# A card says No answer

When a plug-in's card on the dashboard says **No answer from** and the plug-in's name, Starboard asked the plug-in
and did not get a good answer in time. Find out why.

```flow
title: Find your answer
start: A card says No answer from a plug-in
q: Is the plug-in Active on its tab?
  No -> 1
  Yes -> q2
q2: Does the card come back in a minute?
  Yes -> 2
  No -> q3
q3: Does the card's band say Problem?
  Yes -> 3
  No -> 4
1: Turn it on #1-turn-it-on
2: Let it wake up #2-let-it-wake-up
3: Read what the card says #3-read-what-the-card-says
4: Start it again #4-start-it-again
```

## 1. Turn it on

A plug-in that is off cannot answer. Go to **Settings**, then **Plug-ins**, then its name, and select **Turn on** in **General**, **State**.

## 2. Let it wake up

Some plug-ins rest when nobody is using them, such as Notifications and Watch statistics. Starboard wakes one when a
card asks, and waits up to 20 seconds, so the first answer can be slow. Nothing is wrong.

## 3. Read what the card says

The words under **Problem** say what went wrong, such as "Starboard has no Jellyfin key to give yet: add Jellyfin in
Settings, Apps". Fix that, then wait for the next check. Each plug-in's Problems page lists its messages.

## 4. Start it again

A card must answer in 3 seconds, in 64 KB at most and in the right shape.

1. On the plug-in's tab, select **Turn off**, then **Turn on**.
2. If the card still says **No answer from**, go to **System**, then **Logs**, and find the plug-in's name.
3. Tell its maker, at the [plug-ins' issues on GitHub](https://github.com/TheMightyTRex/starboard-plugins/issues).

## Find out more

- [Every plug-in's dashboard cards](../use/dashboard-cards.md)
- [A plug-in is not working](a-plug-in-is-not-working.md)
