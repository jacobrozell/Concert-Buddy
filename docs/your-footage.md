# Your photos and videos

[← ConcertBuddy README](../README.md) · Sorting your clips into shows, shrinking them, and tagging each one with its song.

## Adding your own footage

### Sorting a big batch automatically

Your phone saves the time (and usually the place) inside every photo and video, so you don't have to sort clips by hand. Needs ffmpeg (`brew install ffmpeg`).

**Files you've copied in** (exported from Photos, AirDropped…): put them in `media/inbox/` and run

```sh
python3 scripts/import_media.py                       # dry run: lists where each file would go
python3 scripts/import_media.py --apply --convert     # moves them into media/<show-id>/, shrinking videos to 1080p
```

**A folder or external drive** (years of old clips): the script reads them **where they are** and **copies** what matches. The originals are never moved or changed:

```sh
python3 scripts/import_media.py --from /Volumes/MyDrive/Videos                    # report only
python3 scripts/import_media.py --from /Volumes/MyDrive/Videos --apply --convert  # copy matches, shrunk
```

With `--convert`, only the small 1080p copy lands on your Mac, never the original. The report looks like this:

```
2026-11-03-thundercat  (14 to the show, 2 to review, 3 already there)
    8:38 PM  IMG_3967.MOV          52s
    8:44 PM  IMG_3968.MOV           4s  → review: only 4.0s long
    9:10 PM  IMG_3971 copy.MOV    101s  (already have it)
    …
Nights with clips but no show in your log (2). Probably shows to add to concerts.csv:
  Thu May 7, 2026     21 clips  6:03 PM–9:57 PM   near 36.1593,-86.7785  https://maps.google.com/?q=36.15930,-86.77850
  Mon Aug 23, 2021     1 clip   10:15 PM          near 39.7438,-104.9922  https://maps.google.com/?q=…
```

**How it decides:**
- **Which show:** the capture time inside the file. Anything after midnight and before 5 AM counts toward the previous night. A time saved without a timezone is tried against every zone (and borrows the zone from that show's other clips) and is only matched if exactly one show fits.
- **No capture time:** a date in the file name, then camera-roll neighbours (`IMG_5343` between two clips of the same show), then the file's own date. These are guesses, so those clips go to review.
- **Location check:** a clip whose GPS is far from that show's other clips goes to review.
- **Duplicates:** a clip you already have (same show, same capture time, same length, or the same file) is skipped, so you can re-run it on the same drive as often as you like.
- **Nights with no show:** listed with a map link. That's how forgotten shows turn up. Add the show to `concerts.csv` and run it again.
- The capture times are saved in each show folder (`media.json`), so clips stay in filming order.

### The review folder

Videos **under 10 seconds** (pocket videos, false starts) and clips whose **show is a guess** go to `media/_review/<show-id>/` instead of the show folder. Nothing there is put on the site or committed. `media/_review/README.txt` lists every clip and why it's there.

```sh
python3 scripts/import_media.py --restore IMG_1234.MOV              # keep one: moves it into its show
python3 scripts/import_media.py --restore 2026-11-03-thundercat     # keep all of a show's review clips
python3 scripts/import_media.py --review --apply                    # send short/unsure clips already in show folders to review
```

Don't want one? Delete it. Change the cut-off with `--min-seconds 5`.

### Shrinking videos

```sh
python3 scripts/import_media.py --convert        # videos already in show folders → 1080p H.264 MP4
python3 scripts/import_media.py --convert 720    # smaller still
```

A 52-second iPhone clip goes from 68 MB to about 22 MB at 1080p, or 10 MB at 720p, and plays in every browser. On a Mac, ffmpeg uses **Apple's hardware video encoder** automatically, which is several times faster than the default and converts several clips at once. `--encoder x264` gives slightly smaller files, more slowly. x264 already uses every CPU core for each clip, so keep `--jobs` at 1 or 2 with it (more can overload the machine); the Apple encoder runs on its own chip and barely touches the CPU. Originals of files converted in place are kept in `originals/` (never committed); delete them once you're happy, since the originals are still in Photos or on your drive.

It's safe to stop with Ctrl+C (or `--time-limit SECONDS`) and run it again: each clip is written to a temporary `.converting.mp4` and only swapped in once it's finished, so it picks up where it left off. Each clip keeps its real frame rate (iPhone files claim 120 fps, which used to make ffmpeg pad them with duplicate frames), and tags and Shazam results follow the new `.mp4` names.

The script can tell **which show** a clip is from, but not **which song**. For that, use the tagging screen.

### Tag clips with songs (the tagging screen)

With the preview running (`python3 scripts/build.py --serve`), open **http://localhost:8000/tag.html**, or click **Tag clips** on a show page. It only works in your local preview, because it saves to your files.

- Pick a show. Its photos and videos are listed **in the order you filmed them**, with the time and length of each and a player, so you can check what's in it.
- Choose a song for a clip from that night's setlist, grouped by act (openers first).
- Every clip after it gets a **suggested** song (dashed outline), worked out from the time between clips. A clip within about a minute and a half of the previous one is the same song; otherwise it moves on one song per ~4½ minutes. Fix the first wrong guess and everything after it updates.
- **Accept suggestions** keeps them all; **Save** writes your choices to `shows/<id>.json` and rebuilds the preview.
- **Not a song (Other moments)** is for the crowd, the venue, the merch line. **Hide** keeps a clip off the site entirely (accidental pocket videos).
- Clips you've already tagged by file name show up as tagged, and changing one here simply overrides the name.
- If you've run [Shazam](shazam.md#song-tagging-with-shazam) over the show, what it heard is written under each clip, and clips whose song is on the setlist are suggested from that (a solid green **Shazam match** chip) instead of from timing.

### The quick way: tag the file name

1. Create a folder in `media/` named with the [show id](your-log.md#show-ids): `media/2026-11-03-thundercat/`
2. Copy your photos and videos into it.
3. Add the song name after `--` (two dashes) in each file name:

```
media/2026-11-03-thundercat/
├── IMG_0412--Them-Changes.mp4        → slot for "Them Changes"
├── IMG_0415--Them-Changes-2.mp4      → a second clip of "Them Changes"
├── IMG_0420--candlelight.mp4         → "Candlelight" (capitals don't matter)
├── IMG_0431--A.D.D. Through the Roof.mp4   → punctuation and spaces don't matter
└── IMG_0399.jpg                      → no tag: goes in "Other moments"
```

4. Run `python3 scripts/build.py --serve` and check the show page.

**How the matching works**, in case a file lands somewhere unexpected:
- Only the part **after the first `--`** is compared with the song titles. Anything before it (camera file names, dates) is ignored.
- Both sides are simplified the same way as [show ids](your-log.md#show-ids): lowercase, accents dropped, `&` → `and`, punctuation → dashes. So `--Them_Changes`, `--them changes` and `--THEM-CHANGES` all match "Them Changes".
- A counter at the end (`-2`, `-3`, `-b`) is ignored, so you can have several clips of one song.
- Text after the song name also works: `--Them-Changes-encore-singalong` matches "Them Changes" (the longest matching song title wins).
- If a tagged file doesn't match any song, the build warns you and puts the file in *Other moments*.
- **Openers' songs:** the build looks for the song in the headliner's set first, then co-headliners', then openers'. To point a clip at a specific act (say an opener played a song with the same title), name the act first: `IMG_0398--Channel-Tres--Jet-Black.mp4`.

### The no-rename way: list it in the JSON

If you'd rather keep the original file names, reference them by name in `shows/<id>.json`:

```json
{ "title": "Them Changes", "media": [ { "src": "IMG_0412.mov", "caption": "Right at the drop" } ] }
```

A file listed like this isn't also tagged by its name, so you can mix both approaches freely. Listing a file is also how you give it a `caption`, `start` or `end`.

### Getting files out of your photo library

The build only sees files in `media/<show-id>/`, so first get your clips from the phone or photo app onto your computer:

- **Apple Photos (Mac):** search the show's date (e.g. "Nov 3, 2026") or scroll to it in *Library → Days*, select the photos and videos, then **File → Export → Export Unmodified Original For N Items…** and choose the show's media folder. You get the camera's original `.HEIC` photos and `.MOV` videos; convert them with the commands in [Big videos](hosting-media.md#big-videos-and-storage-limits).
- **iPhone, without a Mac library:** select the items in Photos and AirDrop them to your Mac, or save them to Files → a synced folder.
- **Google Photos:** select the items and choose **Download** (several at once arrive as a `.zip`). For a whole year at once, use [Google Takeout](https://takeout.google.com).
- **Anything else** (Android file transfer, a camera's SD card, Dropbox): just copy the files in.

Then rename each one with `--Song Name` (or list them in `shows/<id>.json`) and rebuild.

### Supported file types

| Type | Extensions | Notes |
|---|---|---|
| Video | `.mp4` `.m4v` `.mov` `.webm` | **`.mp4` with H.264 plays everywhere.** iPhone `.mov` files are usually HEVC (H.265), which some browsers on some computers can't play. See [Big videos](hosting-media.md#big-videos-and-storage-limits) to convert them. |
| Photo | `.jpg` `.jpeg` `.png` `.gif` `.webp` `.avif` `.heic` | `.heic` (the iPhone default) only displays in Safari; the build warns about it. Export as JPEG instead. On iPhone, **Settings → Camera → Formats → Most Compatible** makes the camera shoot JPEG and H.264 from then on. |
| Audio | `.mp3` `.m4a` `.aac` `.wav` `.ogg` | Gets an audio player. Good for voice memos of songs you didn't film. |

Other files in the folder (and anything starting with a `.`) are ignored.
