# The site

[← ConcertBuddy README](../README.md) · What each page shows, and how to change the look.

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
