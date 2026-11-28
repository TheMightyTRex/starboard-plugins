# Style library

A list of styles (broadcast packs for Create your own TV channel) that other people made, for the Online sources plug-in's page
**Styles from the library**. **It is empty, and it stays a private draft until the owner of Starboard's plug-ins has read each style and
chosen to list it.**

## What may be listed

- Only styles under the **MIT licence**, with **credits** that say who made each part.
- A pack must be a creative work, not a folder of unchanged stock pictures or music.
- A style made by someone else is a **link** entry (a name, the maker and a link to the maker's page) when it is not MIT or not ours to host.
  A link entry is never downloaded.
- Each entry carries who read it and when (`reviewed`).

## An entry

```json
{"id": "evening-news", "kind": "pack", "name": "Evening news", "maker": "A. Maker", "licence": "MIT",
 "credits": "Pictures and music by A. Maker", "size": 123456, "sha256": "<64 letters and numbers>",
 "file": "packs/evening-news.zip", "preview": "previews/evening-news.png", "reviewed": {"by": "TheMightyTRex", "on": "2026-11-30"}}
```

`python3 tools/check_style_library.py` checks the file: MIT only, credits, the zip exists and its size and sha256 match, the zip is a
pack (a `pack.json`, a `LICENCE.txt`, no path outside it), the preview exists, and nothing is bigger than 25 MB.
