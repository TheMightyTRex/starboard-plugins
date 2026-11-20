# Uptime and status: Updates

Uptime and status 2.0.0 is the latest version. It takes over Outside services and needs Starboard with plug-in API 1.17 or later.

## Versions

| Version | Name | Needs plug-in API | Released |
|---|---|---|---|
| 2.0.0 | Uptime and status | 1.17 or later | Not yet released |
| 1.1.4 | Outside services | 1.14 or later | 19 November 2026 |
| 1.1.3 | Outside services | 1.14 or later | 17 November 2026 |
| 1.1.2 | Outside services | 1.14 or later | 17 November 2026 |
| 1.1.1 | Outside services | 1.14 or later | 16 November 2026 |
| 1.1.0 | Outside services | 1.14 or later | 15 November 2026 |
| 1.0.0 | Outside services | 1.1 or later | 12 November 2026 |

The catalogue offers each Starboard the newest version it can run, so a Starboard with plug-in API 1.14 to 1.16 keeps Outside services 1.1.4.

## From Outside services to Uptime and status

- **Your settings stay:** **Addresses to check** and **Check every** keep their names and values, so no setting moves. Each address is a web address check, as before, in the group Outside services, and its history starts at the update.
- **Your cards stay:** the one-line card is now **All checks** and the list is **Checks**.
- **It asks for two more permissions**, marked as new before you update: its own page on your home network (`network:port`), and sending alerts through Starboard (`alerts:send`).
- **Its own image:** the update downloads it once, about 25 MB.

## What is new in 2.0.0

Added:

- **More kinds of check:** a port (tcp), ping (with a knock on common ports where ping is not allowed), a DNS record, and words on a web page (keyword), beside web addresses.
- **Heartbeats:** a push check gives an address for a backup or a script to call; no call within its grace time means down.
- **90 days of history:** response times and uptime an hour and a day, about 43 KB a check, with no database.
- **Certificates** for every https address and every port checked with tls: the days left and the names it was issued for.
- **Groups, tags and maintenance windows:** write in Home after a check; a group's alerts pause in its maintenance windows.
- **Alerts through Starboard,** to where it sends its own, once when a check is down and once when it is up again.
- **A status page** on your home network, which only shows names, up or down, response times and uptime.
- **Three more cards:** Groups, Response times (a small line for each check) and Certificates.

Changed:

- **Outside services is now Uptime and status.** Your **Addresses to check** and **Check every** stay as they were and are checked as before, in the group Outside services.
- Needs Starboard with plug-in API 1.17 or later, for the Response times card and the alerts. A Starboard with an older plug-in API keeps version 1.1.4.
- **Its own image,** with the status page's files, in place of the image the examples share.

## What is new in 1.1.4

Changed:

- **Reaches Starboard on any network:** with Starboard 0.23.0 or later it calls Starboard through a socket in its own folder, so it works on its own closed network too. An older Starboard works as before.

## What is new in 1.1.3

Changed:

- **Clearer words:** the band says **Not answering**, and the card names each one. Its description spells out NAS.
- **Logo description:** where its logo stands on its own, a screen reader says "Outside services logo", the plug-in's name, instead of a description of the symbol.

## What is new in 1.1.2

Changed:

- **Shared helper:** the helper every example shares sends Jellyfin's key the way Jellyfin 12 asks for it. This plug-in does not ask Jellyfin anything, so it works as before.

## What is new in 1.1.1

Changed:

- **Lighter at rest:** it wakes about once a minute while nothing asks it anything, not twice a second, and writes nothing to its folder when a run goes well.
- **Starts faster:** its image comes with Python's modules already compiled, so a start takes about a quarter of the processor time.

## What is new in 1.1.0

Added:

- **A logo** in Settings, Plug-ins, in the Catalogue and on its dashboard cards.
- **Its cards say how things are:** a status and when they last changed, in the grey band at the top of each card.

Changed:

- Needs Starboard with plug-in API 1.14 or later. A Starboard with an older plug-in API keeps version 1.0.0.

## What is new in 1.0.0

Added:

- Up or down for things that are not on this server: your router, a NAS, a website.

## How an update is kept safe

- Before an update, it writes its history and finishes the round it is part way through, and starts no new one.
- Starboard waits up to 30 seconds for the new version to answer. If it does not, Starboard goes back to the version you had by itself, with your settings as they were.
- Your settings, checks, groups and history are kept.

## Update it

1. Go to **Settings**, then **Plug-ins**. When a newer version is known, it has an **Update** chip in **Manage**.
2. Select it to open its tab.
3. In **Versions**, select **Update to** and the new version.
4. Read **What is new since** your version, the new permissions and **How the update is kept safe**, enter your Starboard password, and select **Update**.
5. When the dialog says it is updated, select **Done**.

## Roll it back

1. On its tab, in **Versions**, select **Roll back to** and the version you had.
2. Enter your Starboard password and select **Roll back**.
3. When the dialog says it is back on that version, select **Done**.

Rolling back needs no download, and only one earlier version is kept. Back on Outside services, the checks you added stay in its folder, unused, until you update again.

## Find out more

- [Update a plug-in and roll it back, in Starboard's help](https://themightytrex.github.io/starboard/help/topics/update-a-plugin.html)
- [The changes, in full](../../../outside-services/CHANGELOG.md)
- [Problems](problems.md)
