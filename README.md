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
- [Acts: openers and co-headliners](#acts-openers-and-co-headliners)
- [Genres](#genres)
- [Setlists](#setlists)
- [`shows/<id>.json`: setlists and media for one show](#showsidjson-setlists-and-media-for-one-show)
- [Adding your own footage](#adding-your-own-footage)
- [Adding other fans' videos](#adding-other-fans-videos)
- [Big videos and storage limits](#big-videos-and-storage-limits)
- [The timeline page](#the-timeline-page)
- [The show page and Play the show](#the-show-page-and-play-the-show)
- [Stats, artist pages and memories](#stats-artist-pages-and-memories)
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
- Stats at the top: total shows, most-seen artist, most-visited venue, number of cities, top genre, and a chart that switches between shows per year (click to jump to a year) and shows by genre (click to filter)
- Search across artists, venues, openers and notes; filter by state, by the person you go to shows with most, or by shows that have footage
- A small coverage bar on each stub showing how much of the setlist has footage
- A red **TONIGHT** stamp on the stub for a show happening today
- Download links in the footer for the whole log as a CSV and for a blank template

**Show page**
- **The bill:** every act (openers, co-headliners, headliner) as a tab in the order they played, each with its own setlist and genres
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
├── artists.csv                  ← genres for each artist (you edit this)
├── shows/
│   └── 2026-11-03-thundercat.json   ← setlist + fan-video links for one show (you edit these)
├── media/
│   ├── README.md                ← naming cheat sheet
│   └── 2026-11-03-thundercat/   ← your own photos/clips for that show (you add these)
│       ├── IMG_0412--Them-Changes.mp4
│       ├── media.json           ← every file with when it was filmed (written by import_media.py)
│       └── originals/           ← optional: full-size originals, ignored by git
├── templates/
│   ├── concerts_template.csv    ← blank CSV with the right columns
│   └── show_template.json       ← example show file using every feature
├── scripts/
│   ├── build.py                 ← builds the site into _site/
│   ├── setlist.py               ← fetches or imports setlists
│   ├── import_media.py          ← sorts photos/videos into shows by capture time; shrinks videos
│   ├── upload_media.py          ← uploads media to Cloudflare R2
│   ├── shazam_tag.py            ← tags clips with the song Shazam hears in them
│   └── common.py                ← shared helpers
├── tools/shazam/
│   ├── main.swift               ← the Mac helper that asks ShazamKit what's playing
│   └── build.sh                 ← builds and signs it (tools/shazam/cb-shazam, not committed)
├── site/
│   ├── index.html               ← the timeline page
│   ├── show.html                ← the show page and player
│   ├── stats.html               ← stats: most-heard songs, venues, who you go with
│   ├── artist.html              ← every time you've seen one artist
│   ├── tag.html                 ← tag clips with songs (local preview only)
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
| `artist` | **yes** | `Thundercat` | The headliner. For co-headliners, separate names with ` / ` (space, slash, space), **biggest name first** the way the poster bills them: `The Smashing Pumpkins / Interpol`. The first name is the headliner and is used for the show id. |
| `date` | **yes** | `2026-11-03` | Must be `YYYY-MM-DD`. The build stops with a clear message if it isn't. If you only know the year, pick a placeholder date and say so in `notes`. |
| `venue` | | `Avondale Brewing Company` | |
| `location` | | `Birmingham, AL` | City and region. **Everything after the last comma** is treated as the region: it picks the stub colour and the state filter. US state codes (`AL`, `TN`…) show their full names; anything else (`UK`, `Ontario`) is shown as written. Wrap the value in double quotes because it contains a comma. |
| `companions` | | `Samantha` | Who you went with, in any format. Searchable, and used by the `highlight_companion` filter. |
| `opener` | | `The Shins / Silversun Pickups` | Openers and support acts, **biggest name first** (main support, then the first act on). Every opener becomes its own act on the show page, with its own setlist and footage slots. See [Acts](#acts-openers-and-co-headliners). |
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

## Acts: openers and co-headliners

Every artist on a show's bill, from the `artist` and `opener` columns, is an **act** with its own setlist and its own footage slots. The show page lists them as tabs in the order they played, and **Play the show** runs the whole night from the first opener to the headliner's encore.

**Playing order.** Write both columns the way a poster bills them, biggest name first. The site plays them in reverse: openers from the last-listed up, then co-headliners, then the headliner.

```
artist:  A Day To Remember / Yellowcard
opener:  The Wonder Years / Dinosaur Pile-Up

stage order → 1 Dinosaur Pile-Up · 2 The Wonder Years · 3 Yellowcard (co-headliner) · 4 A Day To Remember (headliner)
```

If a night ran differently, put the order in that show's file:

```json
{ "order": ["Escape the Fate", "Hollywood Undead", "Falling in Reverse", "Papa Roach"], "acts": [ … ] }
```

`python3 scripts/setlist.py --list` prints every show's acts in playing order, so you can check them:

```
2026-05-23-godsmack            ✓ Dorothy   · Stone Temple Pilots   ✓ Godsmack
2026-11-03-thundercat          ✗ Channel Tres   ✓ Thundercat

✓ setlist   ~ provisional   ✗ missing   · not on setlist.fm when last checked
```

---

## Genres

`artists.csv` gives each artist one or more genres, separated by `;`. The first one is the main genre:

```csv
artist,genres
Thundercat,R&B & soul; Electronic
Tyler Childers,Country; Folk & Americana
```

- A **show's genres** are its headliner's and co-headliners' genres. Openers' genres appear on their own tab but don't change the show's.
- The timeline gets a **genre filter**, a **By genre** chart (click a bar to filter), and a *Top genre* stat. Genres are searchable too.
- The build lists any artist that has no genre yet: `! No genre in artists.csv for: Glove`.
- Use whatever genre names you like. Fewer, broader genres make a more useful chart than many narrow ones.

---

## Setlists

An act needs a setlist before it has song slots. There are three ways to add one.

### Option A: from setlist.fm (recommended)

1. Create a free account at [setlist.fm](https://www.setlist.fm) and request an API key at **https://www.setlist.fm/settings/api** (it's free for non-commercial use).
2. Make the key available to the script for this terminal session:
   ```sh
   export SETLISTFM_API_KEY=your-key-here
   ```
   (To set it permanently, add that line to `~/.zshrc` or `~/.bashrc`. **Never commit your key to the repo.**)
3. Fetch every act on one show's bill:
   ```sh
   python3 scripts/setlist.py 2026-11-03-thundercat
   python3 scripts/setlist.py 2026-11-03-thundercat --act "Channel Tres"   # just one act
   ```
   or every act on every show that doesn't have a setlist yet (plus any marked provisional):
   ```sh
   python3 scripts/setlist.py --all
   ```

**How it finds the setlist:**
- For the headliner, if the CSV row has a `setlist_url`, it fetches that exact setlist.
- Otherwise it searches setlist.fm for each act's name on that date, preferring a result in the same city.
- It only accepts a result whose artist name matches. If setlist.fm spells the name differently (`BØRNS` vs `Borns`), it tells you what it found; run it again with `--act "Borns" --search "BØRNS"`.
- If nothing turns up, it says so and remembers, so `--all` won't ask about that act again. Use `--all --retry` to check those again later. Setlists for last night's show often take a day or two to appear; openers' sets are often never posted, which is what Option B is for.

**What gets saved:**
- Sets keep their setlist.fm names; otherwise they're named *Main set*, *Encore*, *Encore 2*, or *Set 2*…
- Intro tapes and walk-on music are skipped.
- Extra details go into the song's `note`: setlist.fm's own notes (*"acoustic"*), covers (*"David Bowie cover"*), and guests (*"with Channel Tres"*).
- The setlist.fm page is saved as the setlist source and linked from the show page.

`--all` waits a moment between requests to stay under setlist.fm's rate limit, so a few hundred acts take a few minutes. `--refresh` fetches again even where a setlist exists (your media is kept).

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
python3 scripts/setlist.py 2026-11-03-thundercat --from-file songs.txt                       # the headliner
python3 scripts/setlist.py 2026-11-03-thundercat --act "Channel Tres" --from-file songs.txt  # an opener
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

Create or edit `shows/<id>.json` by hand. See the [next section](#showsidjson-setlists-and-media-for-one-show) for the format, and `templates/show_template.json` for an example.

### Re-running is safe

Running `setlist.py` on a show that already has a setlist **replaces the song list but keeps your media**:
- Media is carried over to the new list by song title. Matching ignores capitals and punctuation, so `Them Changes!` still matches `them changes`.
- A song's note carries over too, unless the new setlist supplies its own.
- If a song is gone from the new list (because the old one was a guess, or a title was spelled differently), its media isn't deleted. It moves to *Other moments* with a caption like *Was tagged "Black Qualls"*, so you can reassign it.
- The `provisional` marker is removed, because the new setlist is the real one.

### Provisional setlists

Want song slots before the real setlist is posted? Copy the setlist from another night on the same tour and add a `provisional` note to the show's JSON:

```json
{ "acts": [ { "artist": "Thundercat", "provisional": "Copied from the Oct 6 Jacksonville show. Replace when Birmingham is posted.", "sets": [ … ] } ] }
```

The show page displays the note as a banner, the timeline counts the show as provisional, and `setlist.py --all` fetches it again until a real setlist exists.

---

## `shows/<id>.json`: setlists and media for one show

The full structure, with every optional field:

```jsonc
{
  "order": ["Channel Tres", "Thundercat"],    // optional: playing order, if the CSV billing order is wrong

  "acts": [                                   // one entry per act that has a setlist (any order; the site sorts them)
    {
      "artist": "Channel Tres",               // must match a name in the CSV's artist or opener column
      "sets": [ { "name": "Main set", "songs": [ { "title": "Topless" }, { "title": "Jet Black" } ] } ]
    },
    {
      "artist": "Thundercat",
      "source": "https://www.setlist.fm/…",   // optional: where the setlist came from (set by setlist.py)
      "provisional": "…",                     // optional: banner text; marks the setlist as a stand-in
      "sets": [
        {
          "name": "Main set",                 // shown above the songs; "Main set" alone shows as "Setlist"
          "songs": [
            {
              "title": "Them Changes",        // required
              "note": "extended outro",       // optional, shown next to the title
              "media": [                      // optional, list of media items (below)
                { "src": "IMG_0412.mov" },
                { "src": "https://youtu.be/VIDEO_ID", "start": "1:02:15", "end": "1:06:40", "credit": "@fan" }
              ]
            }
          ]
        },
        { "name": "Encore", "songs": [ { "title": "Friend Zone" } ] }
      ]
    }
  ],

  "extras": [                                 // optional: media that isn't a song ("Other moments")
    { "src": "IMG_0399.jpg", "caption": "Line outside before doors" }
  ]
}
```

(`//` comments are only here to explain; real JSON files can't contain comments.) An older file with a single top-level `"sets"` list still works; it's read as the headliner's setlist.

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
- If you've run [Shazam](#song-tagging-with-shazam) over the show, what it heard is written under each clip, and clips whose song is on the setlist are suggested from that (a solid green **Shazam match** chip) instead of from timing.

### Song tagging with Shazam

On a Mac, Apple's ShazamKit can listen to each clip and name the song, so most of the tagging does itself. It works best on studio-recorded songs by well-known artists; crowd noise, a stripped-down live arrangement or a brand-new song can stump it, and then the timing suggestions above fill in.

**One-time setup** (needs Xcode, macOS 14 or later, and an Apple developer account):

1. In [developer.apple.com](https://developer.apple.com/account/resources/identifiers/list) › *Certificates, IDs & Profiles* › *Identifiers*, click **+**, choose **App IDs** › **App**, and give it an explicit bundle ID such as `com.yourname.concertbuddy.shazam`. On the **App Services** tab, tick **ShazamKit**, then register it. (Shazam only answers apps whose bundle ID has ShazamKit turned on.)
2. Make sure Xcode has a signing certificate: *Xcode › Settings › Accounts*, sign in, *Manage Certificates* › **+** › *Apple Development*.
3. Build the helper, signed with that bundle ID:
   ```bash
   tools/shazam/build.sh com.yourname.concertbuddy.shazam
   ```
   That compiles `tools/shazam/main.swift` into `tools/shazam/cb-shazam`, embeds the bundle ID, and signs it. **The certificate must come from the same developer team as the bundle ID.** If your Mac has certificates for more than one team (a work account, say), the script lists them with their team IDs and asks you to pick: `tools/shazam/build.sh com.yourname.concertbuddy.shazam --sign "Your Name"` (or `--sign` and the team ID). Both choices are remembered, so later builds are just `tools/shazam/build.sh`.
4. Try it on one clip: `tools/shazam/cb-shazam media/<show-id>/IMG_1234.MOV`. It prints one line of JSON with what it heard. If every window has an `error` saying *check that you have enabled the ShazamKit App Service for this app identifier* (HTTP 401), either it was signed with another team's certificate (rebuild with `--sign`), or ShazamKit was only just ticked for that bundle ID (give it a few minutes). If Apple won't serve a plain command-line tool at all, wrap the same `main.swift` in a minimal macOS app target in Xcode with that bundle ID, and point `CB_SHAZAM` at the binary inside the built `.app`.

**Run it:**

```bash
python3 scripts/shazam_tag.py                       # listen to every untagged clip and report
python3 scripts/shazam_tag.py --apply               # ...and tag the ones whose song is on the setlist
python3 scripts/shazam_tag.py --show 2023-04-22-shakey-graves --apply
python3 scripts/shazam_tag.py --retry               # listen again to clips it didn't recognise
```

- It listens to up to four 10-second windows spread through each clip and stops as soon as two agree. A few hundred clips take a while; stop any time (Ctrl+C or `--time-limit 600`) and run it again to carry on.
- What it heard is saved in `media/.shazam.json` (not committed), so re-runs only listen to new clips.
- Matching to the setlist ignores case, punctuation, *(Live)*, *- Remastered 2009*, *(feat. …)* and the like. Covers match on the title even though Shazam names the original artist ("Where Is My Mind?" by Pixies lands on Shakey Graves's cover).
- **It never touches a clip you've tagged**, hidden or put under Other moments. With `--apply`, review the result in the tagging screen.
- A clip whose song **isn't on the setlist** is reported and left untagged. That's common with a provisional setlist: it's a sign the real night was different. Add the song to `shows/<id>.json` in the right place, then tag it.

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
- **Openers' songs:** the build looks for the song in the headliner's set first, then co-headliners', then openers'. To point a clip at a specific act (say an opener played a song with the same title), name the act first: `IMG_0398--Channel-Tres--Jet-Black.mp4`.

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

### Just for you: no hosting at all

You don't need to host your videos anywhere to enjoy them. The local preview (`python3 scripts/build.py --serve`) plays every clip straight from your disk, so on your own computer the site is complete: song slots, Play the show, all of it. The public GitHub Pages site keeps working with setlists only and leaves out clips it can't serve.

### 3. Host your media on Cloudflare R2 (for lots of video)

For more than a few dozen clips, keep the files in cloud storage and only the *list* of files in Git. Cloudflare R2 has a free tier (10 GB) and no download fees, which matters for video. The site works exactly the same; only where the files come from changes.

**One-time setup** (about 10 minutes, in the Cloudflare dashboard):

1. **R2 → Create bucket**, e.g. `concert-media`.
2. In the bucket's **Settings → Public access**, turn on the **r2.dev development URL** (or connect your own domain). Copy the address, e.g. `https://pub-1a2b3c….r2.dev`.
3. **R2 → Manage API tokens → Create API token** with **Object Read & Write** permission on that bucket. Copy the **Access Key ID** and **Secret Access Key** (the secret is shown once), plus your **Account ID** from the R2 overview page.
4. Create a file called `.env` next to `concerts.csv` (it's git-ignored, so it never leaves your computer):
   ```sh
   R2_ACCOUNT_ID=your-account-id
   R2_ACCESS_KEY_ID=your-access-key-id
   R2_SECRET_ACCESS_KEY=your-secret
   R2_BUCKET=concert-media
   R2_PUBLIC_URL=https://pub-1a2b3c….r2.dev
   ```

**Then, whenever you add media:**

```sh
python3 scripts/import_media.py --apply      # sort new files into shows
python3 scripts/import_media.py --convert    # optional: smaller, plays everywhere
python3 scripts/upload_media.py              # upload anything not in the bucket yet
git add media/*/media.json shows/ config.json
git commit -m "Add footage" && git push
```

- **Staying free:** R2 includes 10 GB a month. `upload_media.py` shows the bucket's size before and after each upload, and **stops before going past 10 GB** unless you add `--allow-paid` (beyond that it's about $0.015 per GB per month; downloads are free). At 1080p, 10 GB is roughly 6 hours of video.
- The free `r2.dev` address is rate-limited and meant for testing; it's fine for personal use. For a site other people will visit, connect a domain you own to the bucket and use that as `R2_PUBLIC_URL`.
- `upload_media.py` uploads to `<bucket>/<show-id>/<file>` (the same layout as `media/`), skips anything already there with the same size, and never uploads `originals/`, `inbox/` or `media.json`. Add `--dry-run` to see what it would do, or `--show <show-id>` for one show. The first time it runs it sets `media_base_url` in `config.json` to your `R2_PUBLIC_URL`.
- The `.gitignore` in this repo already keeps media files out of Git and commits only each show's `media.json`, the list of files with when they were filmed. That list is how GitHub's build knows the clips exist without having the files.
- Your local preview still plays files from your own disk, so you can tag clips before uploading them.
- Once a file is uploaded, you can delete your local copy to free space; its `media.json` entry keeps it on the site. Keep the `originals/` somewhere safe; they aren't uploaded.
- **Keeping media in the repo instead** (a small log, no R2)? Delete the four lines starting at `media/**` near the end of `.gitignore`.

Any S3-compatible storage works the same way (Backblaze B2, Amazon S3); `upload_media.py` speaks R2's flavour of the S3 API, and tools like [rclone](https://rclone.org) can sync the folder to the others.

---

## The timeline page

`index.html` is the home page.

- **Headline and stats.** Total shows; *Most seen* (the artist you've seen most, by the `artist` column); *Home venue* (most visits); *Cities* (distinct `location` values); *With …* (if `highlight_companion` is set); *Shows with footage* (once there is any).
- **Shows-per-year chart.** Click a bar to jump to that year. Years with no shows appear as empty bars, and on the timeline a line like *"2019–2020 · no shows"* marks the gap.
- **Sort.** *Newest first* / *Oldest first*.
- **Memories.** Shows from this time of year in past years (see [Stats, artist pages and memories](#stats-artist-pages-and-memories)).
- **Search.** Matches artist, venue, location, opener, who you went with and notes as you type. `./?q=Bridgestone` opens the page already searched.
- **Filters.** One chip per state or region (the dot shows its stub colour), *With …*, and *Has footage* (appears once any show has media). Click a chip again to turn it off.
- **Stubs.** Date, artist, venue, opener, and the show number in date order. Shows with a setlist say how long it was (*17-song setlist*); once a show has footage, that becomes a bar of ticks (filled = song has footage) and a count like *4/16 filmed*. A show dated today gets a **TONIGHT** stamp. Click a stub to open its show page.

---

## The show page and Play the show

`show.html?id=<show-id>` is the page for one show. Links are shareable.

### Page sections

1. **Ticket header.** Full date, region, artist, venue, genres, who you went with, notes, the show number, and **▶ Play the show**.
2. **The bill** (shows with openers or co-headliners). One tab per act in playing order (*1 · Opener*, *2 · Headliner*…), with its song count, how many songs are filmed, and its main genre. Click a tab, or use the arrow keys, to show that act's setlist below. The headliner is shown first; other acts get a shareable link like `show.html?id=…#act-1`. Shows with a single act skip the tabs.
3. **The night, song by song.** The coverage strip for the whole night, grouped by act: one block per song, **orange** = you have footage, **teal** = only fans' footage, **grey** = nothing yet. Hover to see the song name, click to jump to it (switching acts if needed). Appears once the show has any footage.
4. **The selected act.** Its name, role and genres, **▶ Play this set**, and a link to its setlist source.
5. **Provisional banner** (if the setlist is a stand-in).
6. **The setlist.** Each song numbered through the act's set (encores continue the count), with its note, a clip count, a **▶ Play from here** button, and its media. Each piece of media is labelled **MINE** or **FAN** (plus the credit), with its time range and caption. YouTube, Instagram and TikTok embeds load only when clicked, so a page with fifty clips still opens quickly.
7. **Other moments.** Untagged files, `extras`, and the `media_links` from the CSV.
8. **Add footage to this show.** A collapsed how-to with this show's exact folder name and an example, for when you come back to it months later. **Only shown in your local preview** (`build.py --serve`), never on the public site.

Until a show has any footage, the page stays compact: no coverage strip or play button, and songs show as a simple numbered list. Songs with clips get the full-size treatment.

A show with no setlist shows a *No setlist yet* box, plus any media in *Photos & clips*. In your local preview it also shows the command to fetch the setlist.

### The player

**▶ Play the show** opens a full-screen player that runs through the whole night in order: every act from the first opener to the headliner's encore. **▶ Play this set** starts at the selected act, and **▶ Play from here** at a song.

- **Which clip plays for each song:** by default, the single best one. That's the first video, YouTube clip or audio file (your own before fans'), then a photo if there's none of those, then anything else.
- **Every clip** (the checkbox at the bottom right) plays all the media for each song in turn instead.
- **Songs with no footage** show a title card for about two seconds, then it moves on.
- **An act with no footage at all** gets a single card for its whole set instead of one per song.
- **Photos** stay up for 5 seconds.
- **Videos and YouTube** move on when the clip ends, or when the `end` time is reached.
- **Instagram, TikTok and other links** wait for you to press **Next**.
- A clip that can't play (missing file, embedding disabled, unsupported format) shows a short notice and is skipped.
- At the end you get a *That's the show* card.

**Controls:** **◀ Prev** / **Next ▶**, click any segment in the progress strip to jump to it, **Close ✕**.

**Keyboard:** `→` next, `←` previous, `Esc` close. When the video itself has focus, the arrow keys seek within it as usual.

**On phones:** browsers only autoplay video after you've tapped something. Tapping *Play the show* counts, so it normally runs without further taps. If a phone pauses between clips, tap play on the video.

---

## Stats, artist pages and memories

Everything here is worked out by `build.py` from your CSV and setlists (into `_site/data/stats.json`); there's nothing to maintain.

- **Stats page** (`stats.html`, linked as *All the stats* on the home page): the totals (shows, artists, songs heard, venues, cities, hours of footage); **Songs you keep hearing**, every song you've heard live more than once, with a chip per night (outlined in your accent colour if you filmed it, dashed if it came from a provisional setlist); the artists you've seen most and your venues, cities and companions (click one to search the timeline for it); the nights of the week and months you go out; a few odds and ends (first show, busiest year, longest wait between shows, most songs in a night, biggest bill, most filmed night); and everyone you've seen, A–Z.
- **Artist pages** (`artist.html?a=<artist-slug>`, e.g. `artist.html?a=shakey-graves`): every time you saw them as a row of ticket stubs (headlining or opening, with whom, how much you filmed), every song you've heard them play with how often and on which nights, and the other acts on those bills.
- **On the show page**, an act you've seen before says which time this was (*4th of 6 times →*, linking to the artist page), and each song you've heard more than once says which time it was (*2nd of 3 times live*).
- **Memories** on the home page: shows from a week before to two weeks after today's date in past years (*Tomorrow · 5 years ago*), and *On this day* when there's an anniversary today.
- Songs are matched across nights by title, ignoring case, punctuation and things like *(Live)*. Songs from provisional setlists count, but are marked.

---

## What the build does (and its warnings)

`python3 scripts/build.py`:

1. Deletes and recreates `_site/`.
2. Copies everything in `site/` into it.
3. Reads `concerts.csv` and `config.json`. It stops with an error if a date isn't `YYYY-MM-DD` or two shows share an id.
4. For each show: reads `shows/<id>.json` if it exists, works out what kind each media item is (file, YouTube, Instagram…), matches files in `media/<id>/` to songs by name, and puts your own media first.
5. Writes `_site/data/shows/<id>.json` for each show, and `_site/data/concerts.json` with every show's summary (including counts of songs, filmed songs and clips).
6. Copies `media/` into `_site/media/` (skipped when `media_base_url` is set).
7. Copies `concerts.csv` and the blank template into `_site/` so visitors can download them.
8. Prints a summary:

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
- [x] Openers and co-headliners as full acts, with their own setlists, in playing order
- [x] Genres: filter, by-genre chart, per-act genres
- [ ] **Finding fan footage:** a list of ready-made YouTube/TikTok searches for every empty song slot
- [x] **Song stats across shows:** songs you've heard live most often, and on which nights
- [x] **Artist pages:** every time you've seen an artist, side by side
- [x] **Memories:** shows from this time of year, years ago
- [ ] **Fan uploads:** a per-show upload page you can share (e.g. on Reddit) where people pick the song they filmed and upload it to a review inbox. See the [spec](docs/fan-uploads-spec.md).
- [x] **Media import:** sort clips into shows by capture time, shrink videos, tag songs on a screen, upload to Cloudflare R2
- [x] **Song recognition:** Shazam names the song in each clip (Mac, ShazamKit)
- [ ] **Ticket stub images:** attach a photo of the real ticket to each show
- [ ] **Map view:** venues on a map, sized by number of visits

Ideas and pull requests welcome. Open an issue on the repo.

---

## License

[MIT](LICENSE). Use it, fork it, change it, share it. Your own concert data, photos and videos are yours; the license covers the code and templates.
