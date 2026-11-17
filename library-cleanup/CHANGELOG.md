# Changelog

## 1.0.3 (17 November 2026)

### Changed
- Clearer words: Libraries says Checked for each library the rules check, the card says "Next check in quiet hours", and its hints name the setting they mean.
- Logo description: where its logo stands on its own, a screen reader says "Library clean-up logo", the plug-in's name, instead of a description of the symbol.

## 1.0.2 (17 November 2026)

### Fixed
- Jellyfin 12: it sends Jellyfin's key the way Jellyfin 12 asks for it, so Jellyfin no longer refuses its requests where legacy authorisation is off. Older Jellyfin still works.


## 1.0.1 (16 November 2026)

### Changed
- Lighter at rest: it wakes about once a minute while nothing asks it anything, not twice a second.
- Starts faster: its image comes with Python's modules already compiled, so a start takes about a quarter of the processor time.


## 1.0.0 (15 November 2026)

### Added
- Rules: films watched by everyone, last watched more than 90 days ago; series that ended with every episode watched; films and series nobody has watched for 12 months. Each a setting, for the libraries you choose.
- Always kept: favourites, anything someone is part way through, films in a collection, and anything tagged keep.
- Preview lists what would move and the space it frees. Nothing moves until you activate Move items each day.
- Never deletes: it moves each item to media/.holding, keeping its folders, and Put back returns it.
- Reelix and Jellyfin are told: Reelix stops following what moves, so it is not downloaded again, and follows it again when it is put back.
