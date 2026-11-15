# Remote access: Settings

Remote access's settings are on its own tab: go to **Settings**, then **Plug-ins**, then **Remote access**. Starboard draws them and keeps them; secrets are never shown again once saved.

## Settings

| Setting | What it does | Default |
|---|---|---|
| **Connect with** | Tailscale joins your phone to home privately. Cloudflare Tunnel gives a web address of your own, behind Cloudflare Access. One of: Nothing yet, Tailscale (recommended), Cloudflare Tunnel. | Nothing yet |
| **Addresses away from home** | A page of its own on Remote access's tab. | None |

## Tailscale

| Setting | What it does | Default |
|---|---|---|
| **Sign in with** | With a link, the address to open shows in Addresses away from home. One of: An auth key you paste, A sign-in link. | An auth key you paste |
| **Tailscale auth key** | Make one in your own Tailscale admin page, Settings, Keys. It starts with tskey-auth-. Kept secret by Starboard: it is never shown again. | Empty |
| **Name on your tailnet** | Letters, numbers and hyphens, such as starboard. Words. | starboard |

## Cloudflare Tunnel

| Setting | What it does | Default |
|---|---|---|
| **Cloudflare tunnel token** | From Cloudflare's dashboard, Networks, Tunnels. Point each public hostname at http://localhost:8095, 8096 or 13378. Kept secret by Starboard: it is never shown again. | Empty |

## What to share

| Setting | What it does | Default |
|---|---|---|
| **Share Starboard** | Starboard's own pages, away from home. Activated or deactivated. | Activated |
| **Share Jellyfin** | Jellyfin, so the apps on phones and televisions work away from home. Activated or deactivated. | Activated |
| **Share Audiobookshelf** | Shared only when Audiobookshelf is in Starboard's apps. Download apps are never shared. Activated or deactivated. | Activated |

## Buttons

These are on Remote access's tab.

- **Test remote access**
- **Start remote access again**

## Things to note

- A setting you change is used straight away; you do not need to deactivate it first.
- Settings are kept when you update or deactivate it, and when you remove it they stay in its folder.

## Find out more

- [Install](install.md)
- [Dashboard card](dashboard-card.md)
- [Problems](problems.md)
