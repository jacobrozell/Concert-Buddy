# Building, previewing and publishing

[← ConcertBuddy README](../README.md) · How the build works, previewing on your computer, GitHub Pages, and privacy.

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
│   ├── start_fresh.py           ← clears the example log so you can start your own
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
│   ├── your-log.md, setlists.md, your-footage.md, shazam.md, …   ← the detailed guides
│   └── fan-uploads-spec.md      ← design for the planned fan-upload feature
├── .github/workflows/pages.yml  ← builds and publishes on every push
├── .gitignore
└── _site/                       ← build output (generated, never committed)
```

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
| `is HEIC, which only Safari shows` | iPhone photo format. | Convert to JPEG (see [above](hosting-media.md#1-shrink-clips-before-committing-start-here)). |
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
