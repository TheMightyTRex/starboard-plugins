# Changelog

## 0.2.0 (27 November 2026)

### Added
- Heavy jobs held on battery: while the UPS is on battery, Starboard holds its background jobs, scheduled backups and downloads, and starts them again when the mains power is back. A job you start yourself still runs. You can deactivate this in Settings.
- The card says so: the Power card says when Starboard's heavy jobs are held.

### Changed
- It needs Starboard 0.40.0 or later (plug-in API 1.23). It asks for one more permission: to hold Starboard's heavy jobs.

## 0.1.1 (26 November 2026)

### Changed
- Plainer wording in the text and help pages. How it works has not changed.

## 0.1.0 (25 November 2026)

### Added
- One card for your UPS: it says whether you are on mains power or battery, and shows the battery charge, the time left and the load. A list has the voltage and power used.
- Alerts: through Starboard, once when the mains power is lost, the battery is low, it needs replacing or the UPS cannot be reached. You get one more when each is over.
- NUT or PeaNUT: it reads NUT's own protocol, or PeaNUT's web address; you choose, and the UPS if there is more than one.
- Light: one small question a minute, about 32 MB of memory at most, and a short history kept for the sparkline.
