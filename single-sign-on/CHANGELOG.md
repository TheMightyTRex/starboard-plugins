# Changelog

## 0.1.0 (27 November 2026)

### Added
- An on and off switch: off means nothing runs for single sign-on.
- The provider's address: the Tailscale name of your server, checked, and kept the first time it is valid, because passkeys are tied to it for ever.
- A warning if the name changes: the card says passkeys made at the old name will not work, and Use the new address asks before it changes.
- No provider yet: this version only holds the settings. It makes no network call and starts only when a card asks.
