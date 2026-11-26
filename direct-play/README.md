# Direct play

Makes your films and series play directly on the devices you choose, so Jellyfin does not have to convert them while
they play. It fixes one file at a time, at the lowest priority, in the hours you choose. It checks each new file
before it replaces the old one.

A Starboard plug-in by TheMightyTRexUK, MIT licence. Its rules come from a script that converted 1,173 files and
saved 1.03 TB on the server it was written for.

Read [HELP.md](HELP.md) for how to use it.

## What it does to a file

Cheapest first, one at a time:

| Fix | When | How |
|---|---|---|
| Repackage as MKV | The wrong container, such as AVI, M2TS or TS | The streams are copied into MKV; nothing is converted |
| Add a playable sound track | No sound track every chosen device plays, such as DTS, TrueHD or FLAC only | A Dolby Digital 5.1 track (or AAC stereo when a chosen device lacks Dolby Digital) is added first; the original track is kept |
| Shrink | H.264 over the bitrate you set: 15 Mbps for 1080p, 8 for 720p, 5 for smaller | H.264 at CRF 20, capped at 10 Mbps; kept as it was unless it gets at least a tenth smaller |
| Convert to H.264 | DivX, Xvid, MPEG-2, WMV, VC-1, 10-bit H.264, larger than a chosen device shows, or HEVC when you ask and no chosen device plays it | H.264 at CRF 20 |

It leaves HEVC alone unless you activate **Convert HEVC to H.264**. That costs space, and Jellyfin converts HEVC as it
plays. It keeps subtitles, chapters and fonts.

## Each new file is checked

Before it replaces the original, Direct play checks that the new file passes all of these:

- Its length is within 2 seconds (or 0.5%) of the original's.
- It has a picture of the right kind.
- Its first sound track is one your devices play.
- Sound and picture start within half a second of each other.
- It has every subtitle track.

If a file fails, Direct play leaves it as it was and lists it under **Not fixed** with the reason.
Then Reelix rescans the film or series, and Jellyfin is told the file changed.

## What it may do

- It uses Jellyfin's key and Reelix's key, which Starboard keeps, only to tell them a file changed.
- It reaches your home network, where Jellyfin and Reelix are.
- It can read and change files in your media folder under movies and tv, as the owner of your media folder.
- It runs one container, with 512 MB of memory and one processor at most. ffmpeg runs only while a file is fixed.
  It uses the lowest processor and disk priority and two threads at most.

## Add it

Needs Starboard with plug-in API 1.14 or later, and Jellyfin. In Starboard, open **Settings**, **Plug-ins**,
**Catalogue**: it is under **Jellyfin**, marked **Recommended**. Or give this address under **Add one from elsewhere**:

`https://raw.githubusercontent.com/TheMightyTRex/starboard-plugins/main/direct-play/starboard-plugin.json`

Or run `python3 install.py` in this folder.
