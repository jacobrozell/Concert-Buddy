# Setlists

[← ConcertBuddy README](../README.md) · Getting each show's setlist in, from setlist.fm or by hand.

An act needs a setlist before it has song slots. There are three ways to add one.

## Option A: from setlist.fm (recommended)

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

## Option B: type or paste it

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

## Option C: edit the JSON yourself

Create or edit `shows/<id>.json` by hand. See the [next section](your-log.md#showsidjson-setlists-and-media-for-one-show) for the format, and `templates/show_template.json` for an example.

## Re-running is safe

Running `setlist.py` on a show that already has a setlist **replaces the song list but keeps your media**:
- Media is carried over to the new list by song title. Matching ignores capitals and punctuation, so `Them Changes!` still matches `them changes`.
- A song's note carries over too, unless the new setlist supplies its own.
- If a song is gone from the new list (because the old one was a guess, or a title was spelled differently), its media isn't deleted. It moves to *Other moments* with a caption like *Was tagged "Black Qualls"*, so you can reassign it.
- The `provisional` marker is removed, because the new setlist is the real one.

## Provisional setlists

Want song slots before the real setlist is posted? Copy the setlist from another night on the same tour and add a `provisional` note to the show's JSON:

```json
{ "acts": [ { "artist": "Thundercat", "provisional": "Copied from the Oct 6 Jacksonville show. Replace when Birmingham is posted.", "sets": [ … ] } ] }
```

The show page displays the note as a banner, the timeline counts the show as provisional, and `setlist.py --all` fetches it again until a real setlist exists.
