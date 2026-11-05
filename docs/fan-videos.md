# Other fans' videos

[← ConcertBuddy README](../README.md) · Filling the songs you didn't film with YouTube, Instagram and TikTok clips.

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
