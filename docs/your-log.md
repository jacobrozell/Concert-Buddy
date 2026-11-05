# Your shows: the CSV, settings and show files

[← ConcertBuddy README](../README.md) · What goes in `concerts.csv`, `config.json`, `artists.csv` and `shows/<id>.json`, and how shows, acts and genres work.

## `concerts.csv`: your shows

The first line must be the header row. Column order doesn't matter, and extra columns are ignored, so add your own (`rating`, `ticket_price`…) if you want them in the file.

| Column | Required | Example | Details |
|---|---|---|---|
| `artist` | **yes** | `Thundercat` | The headliner. For co-headliners, separate names with ` / ` (space, slash, space), **biggest name first** the way the poster bills them: `The Smashing Pumpkins / Interpol`. The first name is the headliner and is used for the show id. |
| `date` | **yes** | `2026-11-03` | Must be `YYYY-MM-DD`. The build stops with a clear message if it isn't. If you only know the year, pick a placeholder date and say so in `notes`. |
| `venue` | | `Avondale Brewing Company` | |
| `location` | | `Birmingham, AL` | City and region. **Everything after the last comma** is treated as the region: it picks the stub colour and the state filter. US state codes (`AL`, `TN`…) show their full names; anything else (`UK`, `Ontario`) is shown as written. Wrap the value in double quotes because it contains a comma. |
| `companions` | | `Samantha` | Who you went with. Separate people with ` / ` (or commas). Write `Solo` if you went on your own; leave it empty if you don't remember (it shows as *not logged*). Feeds the *With …* filter, the stats, and the people logging page. |
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
| `highlight_companion` | `"Samantha"` | Adds a *With Samantha* count to the top of the timeline (click it to filter). The name has to match how it's written in `companions` (case doesn't matter). Leave empty to hide it. |
| `media_base_url` | `""` or `"https://media.example.com"` | Where your own media files are served from. Empty (the default) means the files in `media/` are published with the site. Set a URL to host them somewhere else; see [Big videos](hosting-media.md#big-videos-and-storage-limits). |
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
