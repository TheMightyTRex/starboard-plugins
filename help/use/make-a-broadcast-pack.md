[Help centre](../README.md) · Use it · reference
<!-- help: use / tv -->

# Make a broadcast pack

A broadcast pack is your own branding for the channels in [Create your own TV channel](../../tv-station/README.md): the on-screen logo, the logo with its music, idents, the Coming up next card, promos, their music, and transitions. It is one folder of files with set names and a `pack.json`, uploaded as a zip. This page is its specification.

## When would you use it

- You want your channels to have their own logo, idents and cards, like a broadcast channel.
- You are making the pictures and sounds, or asking someone to, and need the sizes, names and lengths.
- A pack you uploaded was not used, and you want to know why.

## Start from the template or the example

In Starboard, go to **Settings**, then **Plug-ins**, then **Create your own TV channel**, then **Broadcast pack**. Under **Downloads**:

- **The template** has every folder, a `pack.json` to fill in, `pack.schema.json` (the machine-checked rules for `pack.json`) and a README with this specification in short.
- **Placement guides** for the Coming up next card, the promo and the on-screen logo are 1920 by 1080 pictures that mark the clip area, each text field with its size and place, and the safe areas. With a pack in use, the guides are drawn on its own backgrounds.
- **The example pack** is Example TV, a made-up channel drawn in code by the plug-in. Activate **Try the example pack** first, and it is made.

## The folder

| File | Needed | What it is |
|---|---|---|
| `pack.json` | Yes | The pack's name, and where the clip and each text field go |
| `logo/dog.png` | Yes | The on-screen logo (the DOG, or bug): a PNG with a transparent background, 256 pixels tall or more (under 64 is refused) and at most 1920 by 1080 |
| `logo/logo-with-music.mp4` or `.mov` | No | The logo animated, with its music baked into the file: 1 to 20 seconds, with sound. It opens each break, as a sting |
| `idents/ident01.mp4`, `ident02.mp4` and on | No | As many idents as you like, up to 99: `ident` and a number of 2 or 3 digits. 2 to 60 seconds each, also `.mov`, `.mkv` or `.webm`. They play in a random order |
| `coming-next/background.mp4` | No | The Coming up next card: a video of 2 to 60 seconds that loops, or a `.png` or `.jpg` still |
| `promo/background.mp4` | No | The promo, in the same way as the Coming up next card |
| `promo/music/music01.m4a` and on | No | Music beds for the promos, 5 to 300 seconds each, up to 20. Also `.mp3`, `.wav`, `.flac`, `.ogg` or `.opus`. Each promo has one, chosen at random |
| `transitions/wipe01.webm` and on | No | Wipes and stings between a programme and a break, up to 20: 0.2 to 5 seconds, with transparency, as WebM VP9 with alpha (`yuva420p`) or ProRes 4444 with alpha (`.mov`). Any name of letters, numbers, `-` and `_` |

A README, `pack.schema.json`, `placement.png` files and an `examples` folder may stay in the pack: they are not used. Any other file name is refused, so a misspelt name is found at once.

## Sizes, lengths and sound

- **Pictures** are 1920 by 1080 pixels at 25 frames a second. Another 16:9 size is scaled to fit; a picture that is not 16:9 is fitted inside with black bars, and the check says so. Under 320 by 180 or over 3840 by 2160 is refused.
- **Safe areas:** keep every word inside the title safe area, 5% in from each edge (96 pixels at the sides and 54 at the top and bottom). Keep anything that moves inside the action safe area, 3.5% in. Some televisions cut the edges of the picture.
- **Sound** plays at -23 LUFS (EBU R 128), with peaks under -1 dBTP. The plug-in measures each file when the pack is checked and brings it to -23 LUFS, by up to 12 dB, so a quiet ident is not lost after a loud programme.
- **Transitions** cut at their middle: at that moment the picture should be covered, so the change from programme to break is hidden. A transition plays its first half over the end of one and its second half over the start of the next.

## pack.json

Every position is a box, `[left, top, right, bottom]`, in pixels of 1920 by 1080, and is scaled with the picture.

```json
{
 "pack": 1,
 "name": "Your channel",
 "colours": {"text": "#FFFFFF", "accent": "#FFD54F"},
 "logo": {"dog": "logo/dog.png", "with_music": "logo/logo-with-music.mp4"},
 "idents": ["ident01.mp4", "ident02.mp4"],
 "coming_next": {
  "background": "coming-next/background.mp4",
  "clip": [980, 210, 1780, 660],
  "fields": {"Heading": [140, 200, 940, 280], "Title": [140, 330, 940, 470], "Episode": [140, 500, 940, 560],
             "Day and time": [140, 590, 940, 650], "Synopsis": [140, 680, 940, 840]}
 },
 "promo": {
  "background": "promo/background.mp4",
  "clip": [980, 210, 1780, 660],
  "music": ["promo/music/music01.m4a"],
  "seconds": 15,
  "fields": {"Heading": [140, 200, 940, 280], "Title": [140, 330, 940, 470], "Day and time": [140, 500, 940, 640],
             "Channel name": [140, 680, 940, 740]}
 },
 "transitions": ["wipe01.webm"]
}
```

| Key | What it says |
|---|---|
| `pack` | Always 1, the version of this specification |
| `name` | The pack's name in Starboard, up to 40 characters |
| `colours` | `text` for the words, `accent` for **Day and time**, as `#RRGGBB`. White unless you change them |
| `idents`, `transitions`, `logo`, `music` | The files, for a check that none is missing. Every ident and transition in the folder is used, listed or not |
| `clip` | Where the programme's picture (Coming up next) or its clips (promo) play. Keep it 16:9, such as 800 by 450 |
| `fields` | Where each text goes. Leave out the ones you do not want |
| `seconds` | How long each promo is: 10 to 30, 15 unless you change it |

### The text fields

| Field | What is drawn |
|---|---|
| **Heading** | Coming up next, or Later on and the channel's name. On a promo, Coming soon |
| **Title** | The programme's title, on up to 2 lines |
| **Episode** | Such as Series 2, episode 4: The crossing |
| **Day and time** | From the schedule. On a card, such as Today at 21:00; on a promo, such as Sunday at 21:00, as a promo is made days before it plays |
| **Synopsis** | A short synopsis, on up to 3 lines |
| **Channel name** | The channel it is on |

The words are made as large as the box allows, on as many lines as the field has, and smaller when they need more. For more control, give a field an object in place of the box: `{"box": [140, 330, 940, 470], "colour": "#FFFFFF", "align": "left", "lines": 2}`, where `align` is `left`, `centre` or `right` and `lines` is 1 to 4.

Leave the clip area and the text fields clear in your backgrounds: the plug-in draws into them. Put the heading in a **Heading** field, not in the background, so Later cards can say Later.

## What the plug-in does with it

- **The on-screen logo** is `logo/dog.png`, at the size and in the corner the on-screen logo settings say. A channel's own logo, added on its page, is used in its place.
- **Each break** opens with the logo with music, when the break has room, then an ident chosen at random, then trailers, clips and promos, then Later and Coming up next cards drawn on your background.
- **Transitions** play at each cut between a programme and a break, chosen at random, the same one on both sides of the cut.
- **Promos** are made in quiet hours, one at a time at the lowest priority and never while anyone is watching: a few short clips of a programme coming up in the clip area, a music bed from `promo/music`, and its title, day and time and channel. Each channel keeps the number the settings say; old ones are replaced. They play on their own channel and, unless you deactivate it, on your other channels.

## The upload, and what is checked

The station has one pack, which every channel uses, and each channel can have its own in its place, or none.

1. Zip the pack's folder. A zip with its files inside one folder is read from inside that folder.
2. In **Broadcast pack**, select **Upload a pack** and choose the zip. For one channel, open it in **Channels** and select **Upload its own pack**.
3. The plug-in checks it before anything in it is used. When it passes, it is in use at once, and anything to change is listed under **The last pack checked**. When it does not, the pack in use stays, and each problem is listed there.

The checks: the zip is at most 60 MB, the most Starboard takes, and at most 400 MB and 150 files unpacked; every name is one in the table; no file is a link or has a path outside the pack's folder; no file is packed far smaller than it is; `pack.json` passes `pack.schema.json`, and each box is inside the picture; every file is read with FFmpeg's `ffprobe` for its type, size, length and sound; the logo has transparent parts; each transition has transparency. Nothing in a pack is ever run.

## Things to note

- Making the example pack takes about 2 minutes, at the lowest priority, and up to about 500 MB of memory for that time. It is made once and kept, and only while no channel is playing; a channel chosen meanwhile is asked to wait.
- A pack's files stay in the plug-in's folder, in `packs`. Removing the station's pack keeps one copy until the next is removed.
- A promo is made at the picture size of the stream, 720p unless you change it.

## Find out more

- [Create your own TV channel: Settings](../plugins/tv-station/settings.md)
- [Create your own TV channel: Problems](../plugins/tv-station/problems.md)
- [pack.schema.json](../../tv-station/pack.schema.json)
