# ConcertBuddy 🎟️

**A concert log you can relive.** ConcertBuddy turns a spreadsheet of every show you've been to into a website hosted free on GitHub Pages. Every concert becomes a ticket stub on a timeline. Open one and its setlist becomes a row of slots, one per song. Fill each slot with your own clips, or with other fans' videos for the songs you didn't film, then press **▶ Play the show** to watch the whole night back in the order it happened.

**Live example:** https://jacobrozell.github.io/Concert-Buddy/

No server, no database, no accounts, no monthly bill. Your log is a CSV file, one JSON file per show, and a folder of media, all in a Git repo you own. A small Python script (standard library only, nothing to install) turns those into a static site, and GitHub publishes it every time you push.

---

## Contents

- [Features](#features)
- [How it works](#how-it-works)
- [Make your own in 10 minutes](#make-your-own-in-10-minutes)
- [Preview on your computer](#preview-on-your-computer)
- [Project layout](#project-layout)
- [`concerts.csv`: your shows](#concertscsv-your-shows)
- [`config.json`: site settings](#configjson-site-settings)
- [Show ids](#show-ids)
- [Setlists](#setlists)
- [`shows/<id>.json`: setlist and media for one show](#showsidjson-setlist-and-media-for-one-show)
- [Adding your own footage](#adding-your-own-footage)
- [Adding other fans' videos](#adding-other-fans-videos)
- [Big videos and storage limits](#big-videos-and-storage-limits)
- [The timeline page](#the-timeline-page)
- [The show page and Play the show](#the-show-page-and-play-the-show)
- [What the build does (and its warnings)](#what-the-build-does-and-its-warnings)
- [Publishing on GitHub Pages](#publishing-on-github-pages)
- [Privacy: everything is public](#privacy-everything-is-public)
- [Changing the look](#changing-the-look)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)

---

## Features

**Timeline**
- Every show as a ticket stub, grouped by year, newest or oldest first
- Stub colour shows the state (or country) the show was in
- Stats at the top: total shows, most-seen artist, most-visited venue, number of cities, and a shows-per-year chart you can click to jump to a year
- Search across artists, venues, openers and notes; filter by state, by the person you go to shows with most, or by shows that have footage
- A small coverage bar on each stub showing how much of the setlist has footage
- A red **TONIGHT** stamp on the stub for a show happening today

**Show page**
- Date, venue, opener, who you went with, and notes
- The setlist, split into sets (main set, encores), with each song as a slot for media
- A coverage strip showing at a glance which songs you filmed, which only fans filmed, and which nobody has yet (appears once a show has any footage)
- Your own videos, photos and audio, plus embedded YouTube, Instagram and TikTok posts, with credit to whoever posted them
- YouTube clips with start and end times, so one fan's full-show upload can fill every song you missed
- An "Other moments" section for anything that isn't a song: the line outside, the merch table, the crowd before doors

**Play the show**
- A full-screen player that plays the night in setlist order
- Your footage first, fan footage as a fallback
- Moves to the next song on its own when a clip ends (your files, direct video links, YouTube, photos)
- Songs with no footage get a short title card, then it moves on, so you still feel the shape of the set
- Start from any song, jump around using the strip of songs, or switch to "every clip" mode

**Tooling**
- `scripts/setlist.py` pulls setlists from setlist.fm, or takes a pasted list of songs
- `scripts/build.py` builds the site and warns you about mismatched file names, oversized files and formats browsers can't show
- A GitHub Actions workflow that rebuilds and publishes on every push

---

## How it works

```
                    you edit these                          the build makes this          GitHub serves it
┌───────────────────────────────────────────────┐
│ concerts.csv     one row per show             │
│ config.json      site title, your name, …     │       ┌──────────────────────┐
│ shows/<id>.json  setlist + video links        │──────▶│  scripts/build.py    │──▶ _site/ ──▶ https://you.github.io/repo/
│ media/<id>/      your own photos and clips    │       └──────────────────────┘     ├─ index.html
│ site/            the HTML, CSS and JavaScript │                                    ├─ show.html
└───────────────────────────────────────────────┘                                    ├─ assets/
                                                                                     ├─ data/concerts.json
                                                                                     ├─ data/shows/<id>.json
                                                                                     └─ media/<id>/…
```

- **`concerts.csv`** is the master list. It knows *when and where*, but nothing about songs.
- **`shows/<id>.json`** exists only for shows you've added a setlist to. It holds the songs, plus links to fan videos (and, optionally, which of your files belongs to which song).
- **`media/<id>/`** holds your own files. You tag them with a song through the file name, so most of the time you never have to touch JSON.
- **`build.py`** combines all of that into two kinds of data file, a summary of every show (`data/concerts.json`) and one detail file per show (`data/shows/<id>.json`), and copies the website and your media next to them in `_site/`.
- **The website** (`site/index.html`, `site/show.html`) is plain HTML and JavaScript with no framework. It reads those data files when it loads.

GitHub Pages can only serve files; it can't run code or accept uploads. So "adding a video" always means putting the file (or link) in the repo and pushing. The upside: there's nothing to keep running, nothing to hack, nothing that breaks if you ignore it for two years.

---

## Make your own in 10 minutes

### 1. Get a copy of the repo

On GitHub, click **Use this template → Create a new repository** (or **Fork**). Name it whatever you like; the name becomes part of your site's address (`https://<your-username>.github.io/<repo-name>/`).

Then clone it to your computer:

```sh
git clone https://github.com/<your-username>/<repo-name>.git
cd <repo-name>
```

### 2. Clear out my shows

These files belong to the example log. Remove them:

```sh
rm -f shows/*.json                                            # my setlists
find media -mindepth 1 -maxdepth 1 -type d -exec rm -rf {} +  # my media folders
cp templates/concerts_template.csv concerts.csv
```

(Keep `media/README.md`; it's a cheat sheet and the build ignores it.)

### 3. Fill in `concerts.csv`

One row per show. Only `artist` and `date` are required; see the [full column reference](#concertscsv-your-shows). You can edit it in any spreadsheet app or a text editor:

```csv
artist,date,venue,location,companions,opener,setlist_url,media_links,notes
The Example Band,2022-06-11,Big Room,"Nashville, TN",Alex,Opening Act,,,Front row
Another Artist / Co-Headliner,2023-03-04,The Theater,"Atlanta, GA",,,,,
```

### 4. Edit `config.json`

```json
{
  "site_title": "Alex's Concert Log",
  "owner": "Alex Rivera",
  "tagline": "Every show I've been to, one ticket stub at a time.",
  "highlight_companion": "Sam",
  "media_base_url": "",
  "repo_url": "https://github.com/<your-username>/<repo-name>"
}
```

See [`config.json` reference](#configjson-site-settings) for what each field does.

### 5. Turn on GitHub Pages

In your repo on GitHub: **Settings → Pages → Build and deployment → Source → GitHub Actions**. That's the only setting you need.

### 6. Push

```sh
git add -A
git commit -m "My concert log"
git push
```

Open the **Actions** tab to watch the build. When it goes green (usually under a minute), your site is live at `https://<your-username>.github.io/<repo-name>/`.

### Starting from an empty folder instead

If you downloaded the files rather than forking (or you're the person who made the repo and it's empty):

```sh
cd ConcertBuddy
git init -b main
git add -A
git commit -m "First commit"
git remote add origin https://github.com/<your-username>/<repo-name>.git
git push -u origin main
```

Then do step 5.

---

## Preview on your computer

You need **Python 3.9 or newer**. macOS and most Linux systems already have it (`python3 --version` to check). Nothing else needs installing.

```sh
python3 scripts/build.py --serve
```

Open **http://localhost:8000**. Press `Ctrl+C` to stop. Use `--port 9000` if 8000 is taken.

After changing anything (CSV, JSON, media, site files), stop the server and run the command again. The build is fast, a second or two even with hundreds of shows.

> **Why not just double-click `site/index.html`?** Browsers block web pages opened straight from disk (`file://`) from loading the data files, so you'd see "Couldn't load data/concerts.json". Always preview through the command above.

To build without serving (this is what GitHub does):

```sh
python3 scripts/build.py
```

---

## Project layout

```
ConcertBuddy/
├── concerts.csv                 ← your shows, one row each (you edit this)
├── config.json                  ← site title, your name, options (you edit this)
├── shows/
│   └── 2026-11-03-thundercat.json   ← setlist + fan-video links for one show (you edit these)
├── media/
│   ├── README.md                ← naming cheat sheet
│   └── 2026-11-03-thundercat/   ← your own photos/clips for that show (you add these)
│       ├── IMG_0412--Them-Changes.mp4
│       └── originals/           ← optional: full-size originals, ignored by git
├── templates/
│   ├── concerts_template.csv    ← blank CSV with the right columns
│   └── show_template.json       ← example show file using every feature
├── scripts/
│   ├── build.py                 ← builds the site into _site/
│   ├── setlist.py               ← fetches or imports setlists
│   └── common.py                ← shared helpers used by both scripts
├── site/
│   ├── index.html               ← the timeline page
│   ├── show.html                ← the show page and player
│   └── assets/
│       ├── base.css             ← colours, fonts, shared styles
│       ├── common.js            ← shared helpers (dates, state colours)
│       ├── icon.svg, apple-touch-icon.png   ← browser tab / home-screen icon
│       └── og.png               ← preview image for shared links
├── docs/
│   └── fan-uploads-spec.md      ← design for the planned fan-upload feature
├── .github/workflows/pages.yml  ← builds and publishes on every push
├── .gitignore
└── _site/                       ← build output (generated, never committed)
```

---

## `concerts.csv`: your shows

The first line must be the header row. Column order doesn't matter, and extra columns are ignored, so add your own (`rating`, `ticket_price`…) if you want them in the file.

| Column | Required | Example | Details |
|---|---|---|---|
| `artist` | **yes** | `Thundercat` | The headliner. For co-headliners or a festival-style bill, separate names with ` / ` (space, slash, space): `The Smashing Pumpkins / Interpol`. The first name is used for the show id and for the setlist.fm search. |
| `date` | **yes** | `2026-11-03` | Must be `YYYY-MM-DD`. The build stops with a clear message if it isn't. If you only know the year, pick a placeholder date and say so in `notes`. |
| `venue` | | `Avondale Brewing Company` | |
| `location` | | `Birmingham, AL` | City and region. **Everything after the last comma** is treated as the region: it picks the stub colour and the state filter. US state codes (`AL`, `TN`…) show their full names; anything else (`UK`, `Ontario`) is shown as written. Wrap the value in double quotes because it contains a comma. |
| `companions` | | `Samantha` | Who you went with, in any format. Searchable, and used by the `highlight_companion` filter. |
| `opener` | | `Channel Tres` | Openers or support acts. Separate several with ` / `. |
| `setlist_url` | | `https://www.setlist.fm/setlist/jack-white/2022/…-73b36ec1.html` | A setlist.fm link. `setlist.py` uses the id at the end of it to fetch the exact setlist, and the show page links to it. Any other URL works as a plain link. |
| `media_links` | | `https://youtu.be/abc https://youtu.be/def` | Links for the show as a whole (a full-show upload, a photo album). Separate with spaces or `\|`. These appear under "Other moments". To attach a link to a *song*, use `shows/<id>.json` instead. |
| `notes` | | `Distracted AF Tour` | Anything: tour name, where you sat, what happened. Shown on the show page and searchable. |
| `id` | | `2023-08-17-interpol` | Optional override for the [show id](#show-ids). Only needed when two shows would otherwise get the same one. |

**Editing tips**
- **Excel and Numbers** like to reformat dates (`11/3/26`) when they save. Format the `date` column as text before typing, or check the file in a text editor after saving. Save as **CSV UTF-8**.
- **Commas inside a value** (`"Nashville, TN"`) need the whole value in double quotes. Spreadsheet apps do this for you.
- **Order doesn't matter.** The site sorts by date, and show numbers (*No. 01*, *No. 02*…) follow date order.

---

## `config.json`: site settings

| Key | Example | What it does |
|---|---|---|
| `site_title` | `"Jacob's Concert Log"` | Browser tab title. |
| `owner` | `"Jacob Rozell"` | Shown above the headline: *Jacob Rozell · live music since 2016*. The year is worked out from your earliest show. Leave empty to show only the year. |
| `tagline` | `"Every concert I've been to…"` | The sentence under the headline. |
| `highlight_companion` | `"Samantha"` | Adds a *With Samantha* count to the stats and a filter chip. Matching is case-insensitive and partial, so `"Sam"` also matches `"Samantha"` and `"Sam & Holly"`. Leave empty to hide both. |
| `media_base_url` | `""` or `"https://media.example.com"` | Where your own media files are served from. Empty (the default) means the files in `media/` are published with the site. Set a URL to host them somewhere else; see [Big videos](#big-videos-and-storage-limits). |
| `repo_url` | `"https://github.com/you/repo"` | Adds a *"grab the template and log your own shows"* link in the footer. Leave empty to hide it. |
| `site_url` | `"https://you.github.io/repo/"` | Your site's public address, used for the preview card when someone shares a link (iMessage, Slack, Reddit…). Leave empty and the GitHub build works it out from your repo name. **If you forked this repo, empty it or change it**, or your previews will point at mine. |

Missing keys fall back to sensible defaults, so a config file with only `site_title` in it works.

---

## Show ids

Every show gets an id that links its row in the CSV to its setlist file and its media folder:

```
<date>-<first artist, lowercased, punctuation replaced with dashes>

Thundercat on 2026-11-03                       → 2026-11-03-thundercat
The Smashing Pumpkins / Interpol on 2023-08-17 → 2023-08-17-the-smashing-pumpkins
Mumford & Sons on 2025-08-01                   → 2025-08-01-mumford-and-sons
Black Jacket Symphony — Beatles                → 2017-09-22-black-jacket-symphony-beatles
```

`&` becomes `and`, accents are dropped (`Beyoncé` → `beyonce`), and everything that isn't a letter or digit becomes a single dash.

To see every id along with which shows already have setlists:

```sh
python3 scripts/setlist.py --list
```

```
  2026-10-09-weezer
~ 2026-11-03-thundercat
✓ 2022-08-27-jack-white

✓ has setlist   ~ provisional
```

> **Careful when editing the CSV:** the id comes from the date and the first artist. If you fix a typo in either, the id changes and the show loses track of its `shows/<id>.json` and `media/<id>/`. Rename that file and folder to match, or pin the old id with the `id` column.

---

## Setlists

A show page needs a setlist before it has song slots. There are three ways to add one.

### Option A: from setlist.fm (recommended)

1. Create a free account at [setlist.fm](https://www.setlist.fm) and request an API key at **https://www.setlist.fm/settings/api** (it's free for non-commercial use).
2. Make the key available to the script for this terminal session:
   ```sh
   export SETLISTFM_API_KEY=your-key-here
   ```
   (To set it permanently, add that line to `~/.zshrc` or `~/.bashrc`. **Never commit your key to the repo.**)
3. Fetch one show:
   ```sh
   python3 scripts/setlist.py 2026-11-03-thundercat
   ```
   or every show that doesn't have a setlist yet (plus any marked provisional):
   ```sh
   python3 scripts/setlist.py --all
   ```

**How it finds the setlist:**
- If the CSV row has a `setlist_url`, it fetches that exact setlist.
- Otherwise it searches setlist.fm for the artist on that date. On a ` / ` bill it tries each artist in turn. To search for a specific name instead, use `--artist "Interpol"`.
- If nothing turns up (setlists for last night's show often take a day or two to appear), it says so and changes nothing.

**What gets saved:**
- Sets keep their setlist.fm names; otherwise they're named *Main set*, *Encore*, *Encore 2*, or *Set 2*…
- Intro tapes and walk-on music are skipped.
- Extra details go into the song's `note`: setlist.fm's own notes (*"acoustic"*), covers (*"David Bowie cover"*), and guests (*"with Channel Tres"*).
- The setlist.fm page is saved as the setlist source and linked from the show page.

`--all` waits a moment between requests to stay under setlist.fm's rate limit, so a few hundred shows take a few minutes.

### Option B: type or paste it

Write the songs one per line in a text file:

```text
# Thundercat — Birmingham — 2026-11-03
Children of the Baked Potato
Candlelight
No More Lies -- with Channel Tres
Them Changes

[Encore]
Funny Thing
```

```sh
python3 scripts/setlist.py 2026-11-03-thundercat --from-file songs.txt
```

or straight from the clipboard on a Mac:

```sh
pbpaste | python3 scripts/setlist.py 2026-11-03-thundercat --from-file -
```

Format rules:
- One song per line. Blank lines and lines starting with `#` are ignored.
- Numbering like `1.` or `12)` at the start of a line is removed, so you can paste a numbered list as is.
- A line in square brackets (`[Encore]`, `[Set 2]`, `[Acoustic set]`) starts a new set with that name. Songs before the first one go in *Main set*.
- ` -- ` (space, two dashes, space) separates a song from a note: `No More Lies -- with Channel Tres`.

### Option C: edit the JSON yourself

Create or edit `shows/<id>.json` by hand. See the [next section](#showsidjson-setlist-and-media-for-one-show) for the format, and `templates/show_template.json` for an example.

### Re-running is safe

Running `setlist.py` on a show that already has a setlist **replaces the song list but keeps your media**:
- Media is carried over to the new list by song title. Matching ignores capitals and punctuation, so `Them Changes!` still matches `them changes`.
- A song's note carries over too, unless the new setlist supplies its own.
- If a song is gone from the new list (because the old one was a guess, or a title was spelled differently), its media isn't deleted. It moves to *Other moments* with a caption like *Was tagged "Black Qualls"*, so you can reassign it.
- The `provisional` marker is removed, because the new setlist is the real one.

### Provisional setlists

Want song slots before the real setlist is posted? Copy the setlist from another night on the same tour and add a `provisional` note to the show's JSON:

```json
{ "provisional": "Copied from the Oct 6 Jacksonville show. Replace when Birmingham is posted.", "sets": [ … ] }
```

The show page displays the note as a banner, the timeline counts the show as provisional, and `setlist.py --all` fetches it again until a real setlist exists.

---

## `shows/<id>.json`: setlist and media for one show

The full structure, with every optional field:

```jsonc
{
  "provisional": "Optional. A banner shown on the page; marks the setlist as a stand-in.",
  "source": "Optional. Link to where the setlist came from (set automatically by setlist.py).",

  "sets": [
    {
      "name": "Main set",                     // shown above the songs; "Main set" alone shows as "Setlist"
      "songs": [
        {
          "title": "Them Changes",            // required
          "note": "extended outro",           // optional, shown next to the title
          "media": [                          // optional, list of media items (below)
            { "src": "IMG_0412.mov" },
            { "src": "https://youtu.be/VIDEO_ID", "start": "1:02:15", "end": "1:06:40", "credit": "@fan" }
          ]
        }
      ]
    },
    { "name": "Encore", "songs": [ { "title": "Funny Thing" } ] }
  ],

  "extras": [                                 // optional: media that isn't a song ("Other moments")
    { "src": "IMG_0399.jpg", "caption": "Line outside before doors" }
  ]
}
```

(`//` comments are only here to explain; real JSON files can't contain comments.)

### Media item fields

| Field | Example | Details |
|---|---|---|
| `src` | `"IMG_0412.mov"` or `"https://youtu.be/…"` | **Required.** A file name means a file in `media/<id>/`; a URL means anything on the web. (`url` and `file` also work as the key name.) A bare string, `"IMG_0412.mov"`, is short for `{ "src": "IMG_0412.mov" }`. |
| `start` | `"1:02:15"`, `"62:15"`, `"1h2m15s"`, `3735` | Where to start playing. Works for YouTube and video files. A `?t=` in a YouTube link counts as the start too. |
| `end` | `"1:06:40"` | Where to stop. In the player, reaching it moves on to the next song. |
| `credit` | `"@concertfan99"` | Who filmed or posted it. Shown on fan media. |
| `caption` | `"From the balcony"` | A short description shown under the clip. |
| `by` | `"me"` or `"fan"` | Whose footage it is. **Files default to `me`, links to `fan`.** Set `"by": "me"` on a link to your own YouTube upload. |

**Order:** within each song, your own media always comes before fans' media, whatever order you list it in. Otherwise the order you write is kept.

---

## Adding your own footage

### The quick way: tag the file name

1. Create a folder in `media/` named with the [show id](#show-ids): `media/2026-11-03-thundercat/`
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
- Both sides are simplified the same way as [show ids](#show-ids): lowercase, accents dropped, `&` → `and`, punctuation → dashes. So `--Them_Changes`, `--them changes` and `--THEM-CHANGES` all match "Them Changes".
- A counter at the end (`-2`, `-3`, `-b`) is ignored, so you can have several clips of one song.
- Text after the song name also works: `--Them-Changes-encore-singalong` matches "Them Changes" (the longest matching song title wins).
- If a tagged file doesn't match any song, the build warns you and puts the file in *Other moments*.

### The no-rename way: list it in the JSON

If you'd rather keep the original file names, reference them by name in `shows/<id>.json`:

```json
{ "title": "Them Changes", "media": [ { "src": "IMG_0412.mov", "caption": "Right at the drop" } ] }
```

A file listed like this isn't also tagged by its name, so you can mix both approaches freely. Listing a file is also how you give it a `caption`, `start` or `end`.

### Getting files out of your photo library

The build only sees files in `media/<show-id>/`, so first get your clips from the phone or photo app onto your computer:

- **Apple Photos (Mac):** search the show's date (e.g. "Nov 3, 2026") or scroll to it in *Library → Days*, select the photos and videos, then **File → Export → Export Unmodified Original For N Items…** and choose the show's media folder. You get the camera's original `.HEIC` photos and `.MOV` videos; convert them with the commands in [Big videos](#big-videos-and-storage-limits).
- **iPhone, without a Mac library:** select the items in Photos and AirDrop them to your Mac, or save them to Files → a synced folder.
- **Google Photos:** select the items and choose **Download** (several at once arrive as a `.zip`). For a whole year at once, use [Google Takeout](https://takeout.google.com).
- **Anything else** (Android file transfer, a camera's SD card, Dropbox): just copy the files in.

Then rename each one with `--Song Name` (or list them in `shows/<id>.json`) and rebuild.

### Supported file types

| Type | Extensions | Notes |
|---|---|---|
| Video | `.mp4` `.m4v` `.mov` `.webm` | **`.mp4` with H.264 plays everywhere.** iPhone `.mov` files are usually HEVC (H.265), which some browsers on some computers can't play. See [Big videos](#big-videos-and-storage-limits) to convert them. |
| Photo | `.jpg` `.jpeg` `.png` `.gif` `.webp` `.avif` `.heic` | `.heic` (the iPhone default) only displays in Safari; the build warns about it. Export as JPEG instead. On iPhone, **Settings → Camera → Formats → Most Compatible** makes the camera shoot JPEG and H.264 from then on. |
| Audio | `.mp3` `.m4a` `.aac` `.wav` `.ogg` | Gets an audio player. Good for voice memos of songs you didn't film. |

Other files in the folder (and anything starting with a `.`) are ignored.

---

## Adding other fans' videos

This is how you fill in the songs you didn't film. Find a video, copy its link, and add it to the song in `shows/<id>.json`:

```json
{
  "title": "Them Changes",
  "media": [
    { "src": "https://www.youtube.com/watch?v=VIDEO_ID", "credit": "@thundercatfan" }
  ]
}
```

### Supported links

| Platform | Link formats | How it appears | Moves on by itself in the player? |
|---|---|---|---|
| **YouTube** | `youtube.com/watch?v=…`, `youtu.be/…`, `youtube.com/shorts/…`, `youtube.com/live/…`, `m.youtube.com/…` | Thumbnail with a play button; loads the player when clicked. Supports `start`/`end`. | ✅ Yes |
| **Instagram** | `instagram.com/p/…`, `instagram.com/reel/…`, `instagram.com/reels/…`, `instagram.com/tv/…` | Embedded post (loads when clicked) | ❌ Press **Next** |
| **TikTok** | `tiktok.com/@user/video/…` | Embedded post (loads when clicked) | ❌ Press **Next** |
| **Direct video/photo/audio URL** | Any link ending in a supported extension, e.g. `https://cdn.example.com/clip.mp4` | Played like your own files | ✅ Yes |
| **Anything else** | Facebook, Twitter/X, Google Photos, Vimeo… | A plain link | ❌ Press **Next** |

Instagram and TikTok don't tell the page when a video has finished, so the player waits for you to press **Next** on those.

### One full-show video, many songs

Fans often upload a whole concert as one long video. Use it for every song you're missing by repeating the link with different start and end times:

```json
{ "title": "Candlelight",  "media": [ { "src": "https://youtu.be/FULLSHOW", "start": "4:10",  "end": "9:02",  "credit": "@whoever" } ] },
{ "title": "No More Lies", "media": [ { "src": "https://youtu.be/FULLSHOW", "start": "9:02",  "end": "13:45", "credit": "@whoever" } ] },
{ "title": "Them Changes", "media": [ { "src": "https://youtu.be/FULLSHOW", "start": "1:21:30", "end": "1:27:10", "credit": "@whoever" } ] }
```

Tip: the description or comments of a full-show upload often list timestamps for each song. If it's your own whole-show recording, upload it to YouTube as *Unlisted* and do the same with `"by": "me"`.

### Where to look

- **YouTube:** search `<artist> <city> <date>` or `<artist> <venue> <year>`, and sort by upload date.
- **setlist.fm:** a show's page sometimes links to videos in its comments.
- **Instagram:** the venue's location tag and the tour's hashtag.
- **TikTok:** search `<artist> <city>`. TikTok is very good at surfacing videos from the same night.
- **Reddit:** the artist's subreddit often has a "post your clips" thread after each show.

### Good manners

Fan videos are **embedded from where they were posted, never copied into your repo**. The person who posted it stays in control: if they delete it or turn off embedding, it disappears from your page too (in the player, it's skipped). Always fill in `credit`. Don't download other people's videos and re-upload them as your own files.

---

## Big videos and storage limits

GitHub's limits:
- **100 MB per file** (hard limit; the push is rejected). GitHub warns from 50 MB.
- **About 1 GB per repo** is the comfortable maximum. Bigger repos get slow to clone and push.
- **1 GB for a published Pages site.**

A minute of 4K iPhone video is roughly 300–400 MB. Here are the options, from simplest to most capable.

### 1. Shrink clips before committing (start here)

1080p H.264 looks great on a phone or laptop, plays in every browser, and is typically a tenth the size of the original. With [ffmpeg](https://ffmpeg.org) (`brew install ffmpeg` on a Mac):

```sh
ffmpeg -i IMG_0412.MOV \
  -vf "scale=-2:1080" -c:v libx264 -crf 26 -preset veryfast \
  -c:a aac -b:a 128k -movflags +faststart \
  "IMG_0412--Them-Changes.mp4"
```

- `scale=-2:1080`: 1080 pixels tall (use `720` for even smaller files).
- `-crf 26`: quality; lower means better and bigger (`23` is near-transparent, `28` is noticeably soft).
- `-movflags +faststart`: lets the video start playing before it has fully downloaded.

**Trim while converting** (keep only 0:15 to 3:40):

```sh
ffmpeg -ss 0:15 -to 3:40 -i IMG_0412.MOV -vf "scale=-2:1080" -c:v libx264 -crf 26 -preset veryfast -c:a aac -b:a 128k -movflags +faststart out.mp4
```

**Convert a whole folder** (originals moved to `originals/`, which git ignores):

```sh
cd media/2026-11-03-thundercat
mkdir -p originals
for f in *.MOV *.mov; do
  [ -e "$f" ] || continue
  ffmpeg -n -i "$f" -vf "scale=-2:1080" -c:v libx264 -crf 26 -preset veryfast \
         -c:a aac -b:a 128k -movflags +faststart "${f%.*}.mp4" && mv "$f" originals/
done
```

**Convert HEIC photos to JPEG** on a Mac, without installing anything:

```sh
for f in *.HEIC *.heic; do [ -e "$f" ] && sips -s format jpeg "$f" --out "${f%.*}.jpg" && mv "$f" originals/; done
```

### 2. Upload long videos to YouTube as Unlisted

Unlisted videos don't show up in search but can be embedded. Link them like a fan video and add `"by": "me"`. This works well for full sets and long clips, and costs nothing.

### 3. Host your media folder somewhere else

When your media outgrows GitHub, put it in cloud storage and point the site at it. Your clips keep their file-name tags and the site works exactly the same; only where the files come from changes.

1. Create a storage bucket with public read access. **Cloudflare R2** is a good fit: it has a free tier and no download (egress) fees, which matters for video. Backblaze B2 and Amazon S3 also work.
2. Upload your `media/` folder to the bucket with **the same layout** (`<bucket>/2026-11-03-thundercat/IMG_0412--Them-Changes.mp4`). Tools like [rclone](https://rclone.org) can sync a folder to any of these: `rclone sync media r2:my-bucket --exclude "README.md" --exclude "**/originals/**"`.
3. Set the bucket's public address in `config.json`:
   ```json
   "media_base_url": "https://media.example.com"
   ```
4. Add `media/*/` to `.gitignore` so files stop going to GitHub (keep them on your computer, where the build still reads them to match songs).

With `media_base_url` set, the build reads the file names in `media/` on your computer (to match them to songs) but doesn't copy the files into the site; it links to the bucket instead. Because GitHub Actions only sees what's committed, run `python3 scripts/build.py` locally to confirm everything matched, then **list cloud-hosted files explicitly in `shows/<id>.json`** (`{ "src": "IMG_0412--Them-Changes.mp4" }`) so the build on GitHub knows about them too.

---

## The timeline page

`index.html` is the home page.

- **Headline and stats.** Total shows; *Most seen* (the artist you've seen most, by the `artist` column); *Home venue* (most visits); *Cities* (distinct `location` values); *With …* (if `highlight_companion` is set); *Shows with footage* (once there is any).
- **Shows-per-year chart.** Click a bar to jump to that year. Years with no shows appear as empty bars, and on the timeline a line like *"2019–2020 · no shows"* marks the gap.
- **Sort.** *Newest first* / *Oldest first*.
- **Search.** Matches artist, venue, location, opener and notes as you type.
- **Filters.** One chip per state or region (the dot shows its stub colour), *With …*, and *Has footage* (appears once any show has media). Click a chip again to turn it off.
- **Stubs.** Date, artist, venue, opener, and the show number in date order. Shows with a setlist say how long it was (*17-song setlist*); once a show has footage, that becomes a bar of ticks (filled = song has footage) and a count like *4/16 filmed*. A show dated today gets a **TONIGHT** stamp. Click a stub to open its show page.

---

## The show page and Play the show

`show.html?id=<show-id>` is the page for one show. Links are shareable.

### Page sections

1. **Ticket header.** Full date, region, artist, venue, opener, who you went with, notes, the show number, and buttons for **▶ Play the show** and the setlist source (or a setlist.fm search if there's no link).
2. **The night, song by song.** The coverage strip: one block per song, **orange** = you have footage, **teal** = only fans' footage, **grey** = nothing yet. Hover to see the song name, click to jump to it. The count on the right says how many songs have footage and how many of those were filled in by fans.
3. **Provisional banner** (if the setlist is a stand-in).
4. **The setlist.** Each song numbered through the whole show (encores continue the count), with its note, a clip count, a **▶ Play from here** button, and its media. Each piece of media is labelled **MINE** or **FAN** (plus the credit), with its time range and caption. YouTube, Instagram and TikTok embeds load only when clicked, so a page with fifty clips still opens quickly.
5. **Other moments.** Untagged files, `extras`, and the `media_links` from the CSV.
6. **Add footage to this show.** A collapsed how-to with this show's exact folder name and an example, for when you come back to it months later. **Only shown in your local preview** (`build.py --serve`), never on the public site.

Until a show has any footage, the page stays compact: no coverage strip or play button, and songs show as a simple numbered list. Songs with clips get the full-size treatment.

A show with no setlist shows a *No setlist yet* box, plus any media in *Photos & clips*. In your local preview it also shows the command to fetch the setlist.

### The player

**▶ Play the show** opens a full-screen player that runs through the setlist in order.

- **Which clip plays for each song:** by default, the single best one. That's the first video, YouTube clip or audio file (your own before fans'), then a photo if there's none of those, then anything else.
- **Every clip** (the checkbox at the bottom right) plays all the media for each song in turn instead.
- **Songs with no footage** show a title card for about two seconds, then it moves on.
- **Photos** stay up for 5 seconds.
- **Videos and YouTube** move on when the clip ends, or when the `end` time is reached.
- **Instagram, TikTok and other links** wait for you to press **Next**.
- A clip that can't play (missing file, embedding disabled, unsupported format) shows a short notice and is skipped.
- At the end you get a *That's the show* card.

**Controls:** **◀ Prev** / **Next ▶**, click any segment in the progress strip to jump to it, **Close ✕**.

**Keyboard:** `→` next, `←` previous, `Esc` close. When the video itself has focus, the arrow keys seek within it as usual.

**On phones:** browsers only autoplay video after you've tapped something. Tapping *Play the show* counts, so it normally runs without further taps. If a phone pauses between clips, tap play on the video.

---

## What the build does (and its warnings)

`python3 scripts/build.py`:

1. Deletes and recreates `_site/`.
2. Copies everything in `site/` into it.
3. Reads `concerts.csv` and `config.json`. It stops with an error if a date isn't `YYYY-MM-DD` or two shows share an id.
4. For each show: reads `shows/<id>.json` if it exists, works out what kind each media item is (file, YouTube, Instagram…), matches files in `media/<id>/` to songs by name, and puts your own media first.
5. Writes `_site/data/shows/<id>.json` for each show, and `_site/data/concerts.json` with every show's summary (including counts of songs, filmed songs and clips).
6. Copies `media/` into `_site/media/` (skipped when `media_base_url` is set).
7. Prints a summary:

```
Built 41 shows → _site/
  3 with a setlist, 27 media items
  2026-11-03-thundercat: 12/16 songs have footage
  2022-08-27-jack-white: 3/19 songs have footage
  ! 2026-11-03-thundercat: 'IMG_0420--Not-A-Song.mp4' didn't match a song on the setlist, so it went under Other moments
```

**Warnings** (lines starting with `!`) never stop the build, but they're worth fixing:

| Warning | Meaning | Fix |
|---|---|---|
| `didn't match a song on the setlist` | The text after `--` isn't close to any song title. | Fix the spelling in the file name, or list the file under the right song in the JSON. |
| `is HEIC, which only Safari shows` | iPhone photo format. | Convert to JPEG (see [above](#1-shrink-clips-before-committing-start-here)). |
| `is over 95 MB` | GitHub will reject the push. | Shrink it, move it to `originals/`, or host it elsewhere. |
| `mentions 'X' but it isn't in media/<id>/` | The JSON references a file that doesn't exist. | Check the file name (it's case-sensitive) and the folder name. |

Your source files are never modified by the build. Only `setlist.py` writes to `shows/`.

---

## Publishing on GitHub Pages

The workflow in `.github/workflows/pages.yml` runs on every push to `main` (and whenever you click **Run workflow** on the Actions tab). It:

1. checks out the repo,
2. sets up Python,
3. runs `python3 scripts/build.py`,
4. uploads `_site/` and publishes it to Pages.

**One-time setup:** **Settings → Pages → Source → GitHub Actions**. If the first run fails with a message about Pages not being enabled, set this and re-run it from the Actions tab.

**Your address:** `https://<username>.github.io/<repo-name>/`. All links in the site are relative, so it works under any repo name, or at the root if your repo is named `<username>.github.io`.

**Custom domain:** in **Settings → Pages → Custom domain**, enter e.g. `shows.example.com` and add the DNS record GitHub tells you to. Tick **Enforce HTTPS** once it's available.

**`_site/` is never committed** (it's in `.gitignore`); GitHub builds its own.

**Private repos:** publishing Pages from a private repo requires a paid GitHub plan, and even then the *site* is public to anyone with the link. See the next section.

---

## Privacy: everything is public

Anything in a public repo can be read by anyone, including its full history. Before you push, think about:

- **`companions`**: the names of the people you go to shows with. Use first names or nicknames, or leave the column blank.
- **`notes`**: details like seat numbers, order numbers or ticket sellers.
- **Photos and videos**: faces of friends and strangers; location data saved inside photo files (on iPhone, tap **Options → Location** off before sharing, or strip it with `exiftool -gps:all= *.jpg`).
- **A full timeline of where you've been, on which dates.**

Removing something in a later commit doesn't remove it from the history. If you push something you shouldn't have, GitHub's guide on [removing sensitive data](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository) explains how to purge it.

**Never commit your setlist.fm API key.** `setlist.py` reads it from the environment for exactly this reason, and `.env` files are in `.gitignore`.

---

## Changing the look

Everything is plain HTML, CSS and JavaScript, with no build tools.

| What | Where |
|---|---|
| Colours (background, text, accent, fan teal), fonts, light/dark mode | `site/assets/base.css`, the `:root` blocks at the top |
| Stub colour per state | `site/assets/common.js`, `KNOWN` (fixed colours for specific states) and `EXTRA` (palette for everything else) |
| Timeline layout, stubs, chart | `site/index.html`, `<style>` at the top |
| Show page, coverage strip, player | `site/show.html`, `<style>` at the top |
| Headline wording ("shows and counting") | `site/index.html`, the `<h1>` |

The site follows the device's light or dark setting. Fonts are [Big Shoulders Display](https://fonts.google.com/specimen/Big+Shoulders+Display), [Instrument Sans](https://fonts.google.com/specimen/Instrument+Sans) and [DM Mono](https://fonts.google.com/specimen/DM+Mono), from Google Fonts.

After any change: `python3 scripts/build.py --serve` and reload.

---

## Troubleshooting

**"Couldn't load data/concerts.json"**
You opened the HTML file directly. Run `python3 scripts/build.py --serve` and use http://localhost:8000.

**A show page says "Couldn't find that show"**
The id in the address doesn't exist. This usually means the date or artist was edited in the CSV and the id changed. See [Show ids](#show-ids).

**My clip is under "Other moments" instead of its song**
Check the build output for a *didn't match* warning. Common causes: no `--` in the file name, a typo in the song name, or the setlist uses a different title (`How Sway / Uh Uh` vs `How Sway`). Rename the file, or reference it in the JSON.

**A video shows a black box or won't play**
It's probably HEVC/H.265 (most iPhone `.mov` files). Convert it to H.264 `.mp4` (see [Big videos](#1-shrink-clips-before-committing-start-here)).

**A YouTube clip says it's unavailable**
The uploader turned off embedding, made it private, or deleted it. Find another video for that song.

**An Instagram or TikTok embed is blank**
The post is private or deleted, or the account blocks embeds. Use the *Open on …* link, or find another post.

**Push rejected: file exceeds 100 MB**
Remove the file from the commit (`git rm --cached path/to/file`), shrink it or move it to `originals/`, then commit again. If the big file is in an earlier commit, `git reset --soft origin/main` and recommit without it.

**`setlist.py` says "nothing on setlist.fm yet"**
Nobody has posted that setlist yet (it often takes a day or two), or the artist name in your CSV doesn't match setlist.fm's spelling. Try `--artist "Exact Name"`, add a `setlist_url`, or use `--from-file`.

**`setlist.py` says 401 or 403**
The API key is missing, mistyped, or not approved yet. Check with `echo $SETLISTFM_API_KEY`.

**The GitHub Action fails**
Open the failed run in the Actions tab. If the *build* step failed, it's the same error you'd get locally, so run `python3 scripts/build.py` on your computer to see it. If the *deploy* step failed, check that Pages is set to **GitHub Actions** in Settings.

**The site didn't update after pushing**
Wait for the Action to finish, then hard-refresh (`Cmd+Shift+R` / `Ctrl+Shift+R`). Browsers and GitHub's CDN can cache for a few minutes.

---

## Roadmap

- [x] Ticket-stub timeline with search, filters and stats
- [x] Setlists from setlist.fm or pasted by hand, with safe re-runs
- [x] Per-song media slots: your files and fan videos, with start/end times
- [x] Play the show in setlist order
- [ ] **Finding fan footage:** a list of ready-made YouTube/TikTok searches for every empty song slot
- [ ] **Song stats across shows:** songs you've heard live most often, first and last time you heard each, rarities
- [ ] **Artist pages:** every time you've seen an artist, side by side
- [ ] **Fan uploads:** a per-show upload page you can share (e.g. on Reddit) where people pick the song they filmed and upload it to a review inbox. See the [spec](docs/fan-uploads-spec.md).
- [ ] **Media import helper:** convert, rename by song, and (optionally) upload to cloud storage in one command
- [ ] **Ticket stub images:** attach a photo of the real ticket to each show
- [ ] **Map view:** venues on a map, sized by number of visits

Ideas and pull requests welcome. Open an issue on the repo.

---

## License

[MIT](LICENSE). Use it, fork it, change it, share it. Your own concert data, photos and videos are yours; the license covers the code and templates.
