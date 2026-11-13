# Changelog

## 1.0.0 (13 November 2026)

### Added
- Three tables: recent plays by day, top titles and people, each to read only, with search and sorting.
- Four cards: plays this week, top titles, who watched most, and where the figures come from.
- Reads Jellyfin's Playback Reporting with one query, so a Full install can go without Jellystat and its PostgreSQL.
- Without Playback Reporting it says so and how to add it, and shows each person's last plays from Jellyfin itself.
- Rests when not in use, and keeps each answer for 15 minutes.
