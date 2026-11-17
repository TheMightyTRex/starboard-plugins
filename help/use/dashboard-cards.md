[Help centre](../README.md) · Use it · reference
<!-- help: use / cards -->

# Every plug-in's dashboard cards

The cards each plug-in can add to your dashboard, and how often each one updates. Every card starts with a grey band:
the plug-in's logo and name, its status in words, and when it last changed.

## When would you use it

- You want to choose which cards to put on your dashboard.
- You need to know how often a card asks its plug-in, on a small server.

## The cards

| Plug-in | Card | Kind | How often it updates |
|---|---|---|---|
| [Watching now](../plugins/watching-now/dashboard-card.md) | Watching now | List | Every 30 seconds |
| [Most watched](../plugins/most-watched/dashboard-card.md) | Most watched | List | Once a minute |
| [Watch statistics](../plugins/watch-stats/dashboard-card.md) | Plays this week | Stat | Every 30 minutes |
| [Watch statistics](../plugins/watch-stats/dashboard-card.md) | Top titles | List | Every 30 minutes |
| [Watch statistics](../plugins/watch-stats/dashboard-card.md) | Who watched most | List | Every 30 minutes |
| [Watch statistics](../plugins/watch-stats/dashboard-card.md) | Watch statistics source | Status | Every 60 minutes |
| [Library health](../plugins/library-health/dashboard-card.md) | Library health | Stat | Once a minute |
| [Library health](../plugins/library-health/dashboard-card.md) | To fix in Jellyfin | List | Once a minute |
| [Audio description](../plugins/audio-description/dashboard-card.md) | Audio description | Stat | Every 60 minutes |
| [Audio description](../plugins/audio-description/dashboard-card.md) | Recently found with audio description | List | Every 60 minutes |
| [Audio description tracks](../plugins/audio-description-tracks/dashboard-card.md) | Description tracks to check | Stat | Every 60 minutes |
| [Direct play](../plugins/direct-play/dashboard-card.md) | Direct play | List | Every 30 seconds |
| [Direct play](../plugins/direct-play/dashboard-card.md) | Space saved by Direct play | Stat | Every 10 minutes |
| [Picture shrinker](../plugins/picture-shrinker/dashboard-card.md) | Space saved | Stat | Every 60 seconds |
| [Disk forecast](../plugins/disk-forecast/dashboard-card.md) | Disk forecast | Status | Once a minute |
| [Notifications](../plugins/notifications/dashboard-card.md) | Notifications | Status | Every 60 minutes |
| [Notifications](../plugins/notifications/dashboard-card.md) | Notifications sent | List | Every 60 minutes |
| [Download summary](../plugins/download-summary/dashboard-card.md) | Downloaded today | Stat | Once a minute |
| [VPN check](../plugins/vpn-check/dashboard-card.md) | VPN | Status | Once a minute |
| [Remote access](../plugins/remote-access/dashboard-card.md) | Away from home | Status | Once a minute |
| [Ad blocking](../plugins/dns-blocking/dashboard-card.md) | Blocked today | Stat | Once a minute |
| [Line speed](../plugins/line-speed/dashboard-card.md) | Line speed | Stat | Once a minute |
| [Line speed](../plugins/line-speed/dashboard-card.md) | Line speed this week | List | Once a minute |
| [Outside services](../plugins/outside-services/dashboard-card.md) | Outside services | Status | Once a minute |
| [Outside services](../plugins/outside-services/dashboard-card.md) | Outside services | List | Once a minute |
| [Home Assistant](../plugins/home-assistant/dashboard-card.md) | Home | Status | Once a minute |
| [Jellystat](../plugins/jellystat/dashboard-card.md) | Jellystat | Status | Every 10 minutes |

Styles and the apps you can add, apart from Jellystat, have no card.

## How a card is asked

- A card is asked only while a dashboard with it is open. Nothing is asked while the browser tab is hidden.
- No card is asked more often than every 10 seconds. A plug-in may set its own time in its answer: Direct play's card
  follows its **Card updates every** setting, and Picture shrinker's card updates more often while it is shrinking.
- Many people with the dashboard open at once still ask the plug-in once, because Starboard keeps the answer for that long.

## What the status says

| Status | Means |
|---|---|
| **OK**, **Done**, **Ready**, **Protected** | All is well |
| **Working**, **Converting**, **Scanning**, **Running** | It is doing something now |
| **Waiting**, **Idle**, **Scheduled** | Nothing to do now, or it waits for a set time |
| **Paused**, **Inactive** | Stopped by you |
| **Warning**, **Needs setting up** | Check it soon |
| **Problem**, **Failed**, **Stopped** | Something is wrong: the words under it say what |

Each status is words with an icon, never colour alone. Each plug-in's Dashboard card page says when it shows each one.

## Find out more

- [Use and change the dashboard, in Starboard's help](https://themightytrex.github.io/starboard/help/topics/use-the-dashboard.html)
- [A card says No answer](../fix/a-card-says-no-answer.md)
