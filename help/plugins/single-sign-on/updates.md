# Single sign-on: Updates

Single sign-on 0.1.0 is the first version. It needs Starboard with plug-in API 1.21 or later.

## Versions

| Version | Needs plug-in API | Released |
|---|---|---|
| 0.1.1 | 1.21 or later | Not released yet |
| 0.1.0 | 1.21 or later | Not released yet |

## What is new in 0.1.0

Added:

- **An on and off switch:** off means nothing runs for single sign-on. If other plug-ins need it, Starboard names them and asks before it turns them off too (plug-in API 1.21).
- **The provider's address:** the Tailscale name of your server, checked, and kept the first time it is valid, because passkeys are tied to it for ever.
- **A warning if the name changes:** the card says passkeys made at the old name will not work, and Use the new address asks before it changes.
- **No provider yet:** this version only holds the settings. It makes no network call and starts only when a card asks.

## How an update is kept safe

- **Before the update** Starboard asks the plug-in to get ready: it starts nothing new and lets anything running finish, for up to 60 seconds. If it is not ready, nothing changes and Starboard says why.
- **After the update,** or after a Roll back, it carries on with its work.
- Starboard waits for the new version to answer. If it does not, Starboard goes back to the version you had by itself, with your settings as they were.
- Your settings and its folder are kept, including the Tailscale name it kept.

## Update it

1. Go to **Settings**, then **Plug-ins**. When a newer version is known, Single sign-on has an **Update** chip in **Manage**.
2. Select **Single sign-on** to open its tab.
3. In **Versions**, select **Update to** and the new version.
4. Read **What is new since** your version and **How the update is kept safe**, enter your Starboard password, and select **Update Single sign-on**.
5. When the dialog says it is updated, select **Done**.

## Find out more

- [Settings](settings.md)
- [Problems](problems.md)
