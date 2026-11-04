# Your own photos and clips

Make one folder per show, named with the show id (`<date>-<first-artist>`), e.g. `media/2026-11-03-thundercat/`.
Run `python3 scripts/setlist.py --list` to see every id.

Tag a clip with its song by putting the song name after `--` in the file name:

```
media/2026-11-03-thundercat/IMG_0412--Them-Changes.mp4
media/2026-11-03-thundercat/IMG_0415--Them-Changes-2.mp4   ← a second clip of the same song
media/2026-11-03-thundercat/IMG_0399.jpg                   ← no tag: goes under "Other moments"
```

Capitalization and punctuation don't matter (`--them-changes`, `--Them_Changes` both work).
If you'd rather not rename files, list them under a song in `shows/<id>.json` instead: `{ "src": "IMG_0412.mov" }`.
