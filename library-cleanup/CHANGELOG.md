# Changelog

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
