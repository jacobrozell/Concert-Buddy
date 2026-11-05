# Troubleshooting

[← ConcertBuddy README](../README.md) · Common problems and their fixes.

**"Couldn't load data/concerts.json"**
You opened the HTML file directly. Run `python3 scripts/build.py --serve` and use http://localhost:8000.

**A show page says "Couldn't find that show"**
The id in the address doesn't exist. This usually means the date or artist was edited in the CSV and the id changed. See [Show ids](your-log.md#show-ids).

**My clip is under "Other moments" instead of its song**
Check the build output for a *didn't match* warning. Common causes: no `--` in the file name, a typo in the song name, or the setlist uses a different title (`How Sway / Uh Uh` vs `How Sway`). Rename the file, or reference it in the JSON.

**A video shows a black box or won't play**
It's probably HEVC/H.265 (most iPhone `.mov` files). Convert it to H.264 `.mp4` (see [Big videos](hosting-media.md#1-shrink-clips-before-committing-start-here)).

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
