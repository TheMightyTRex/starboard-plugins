# Changelog

## 0.2.0 (27 November 2026)

### Added
- A page for the job queues: in Settings, Plug-ins, Immich, each queue has a switch to pause or resume it and a choice to clear its failed jobs, so you do not need Immich's own pages, which are hard to use with a keyboard or a screen reader.
- Only when open: Starboard asks Immich for the queues only while the page is open.

### Changed
- To pause, resume or clear a queue, give the API key the permission queue.update (job.create on an older Immich). The cards work as before without it.

## 0.1.1 (26 November 2026)

### Changed
- Plainer wording in the text and help pages. How it works has not changed.

## 0.1.0 (25 November 2026)

### Added
- Three cards for Immich: the photos and videos, where the space goes, how full the disk is, and what the job queues are doing.
- Failed jobs are said on the jobs card, so a stuck queue does not hide.
- Light: it runs only when a card asks, keeps each answer for a minute, and rests five minutes after; nothing at rest.
- You choose the address and an API key with only the permissions it needs.
