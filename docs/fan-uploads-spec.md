# Spec: fan uploads ("Were you there? Add your clips")

**Status:** planned, not built. Written Nov 2026.
**Goal:** let people who were at a show upload their own photos and videos to the right song slots, so a show can be filled in by the crowd, starting with a Reddit post that links to one show.

---

## 1. Why this needs more than GitHub Pages

The site is static: GitHub Pages serves files and can't receive uploads. Today all media reaches the site by being committed to the repo (your own files in `media/<show-id>/`) or linked (YouTube, Instagram, TikTok). Taking uploads from strangers needs three things the static site doesn't have:

1. **Somewhere to put the files**, which can also hold large videos (GitHub's 100 MB limit rules out the repo).
2. **A small piece of server code** that hands out permission to upload, checks limits, and stops bots.
3. **A review step**, so nothing a stranger uploads shows up on the site until the owner approves it.

## 2. User stories

- **Owner:** "I open uploads for one show, post the link on the artist's subreddit, and over the next few days check an inbox of submitted clips, approving the good ones."
- **Fan:** "From the Reddit link I see the setlist for the night I was at, tap the song I filmed, attach the video from my phone, type my Reddit username for credit, and submit. No account."
- **Fan, later:** "I can see my clip on the show page with my name on it, and it plays in order in Play the show."
- **Fan who changed their mind:** "I can ask for my clip to be removed, and it is."
- **Someone forking the template:** "I can turn the same thing on for my own log by following setup steps, without writing code."

## 3. Recommended architecture: Cloudflare R2 + a Worker

Cloudflare was already planned for media hosting, has no download (egress) fees (which matters for video), and has a free tier that should comfortably cover a personal log.

```
 Fan's phone ──1. ask to upload──▶ Cloudflare Worker  (checks show is open, Turnstile, limits)
     │        ◀─2. signed URL ────        │
     └──3. upload file straight to R2 ───▶ R2: inbox/<show-id>/<upload-id>.<ext>   (private)
     └──4. "done" + details ────────────▶ Worker writes inbox/<show-id>/<upload-id>.json

 Owner's computer ── scripts/inbox.py ── list ▸ preview ▸ approve/reject
     approve: convert to 1080p H.264, strip location data, rename by song,
              copy to R2 public/<show-id>/, add entry to shows/<show-id>.json, git commit
     reject:  delete from inbox

 Site (GitHub Pages) ── media_base_url = public R2 address ── shows approved clips
```

### Pieces

| Piece | What it does | Notes |
|---|---|---|
| **R2 bucket** | Stores files. `inbox/` is private; `public/` is served to the site. | `public/` is the same layout as `media/` today, so the existing `media_base_url` setting already works with it. |
| **Worker** (`worker/` in this repo) | Two endpoints. `POST /api/uploads` checks the request and returns a short-lived signed upload URL. `POST /api/uploads/<id>/complete` saves the submission details. | About 200 lines. Deployed with Wrangler. Holds the R2 credentials, so the site never does. |
| **Turnstile** | Cloudflare's free, mostly invisible "are you human" check. | Verified by the Worker before it hands out an upload URL. |
| **`site/upload.html`** | The fan-facing upload page: `upload.html?id=<show-id>`. | Static, like the rest of the site. Reads the show's setlist from `data/shows/<id>.json`. |
| **`scripts/inbox.py`** | The owner's review tool. | Uses the R2 API with the owner's own keys, kept outside the repo. |

### Upload page (fan's view)

1. Header in the same ticket style: artist, venue, date. "Were you there? Add your photos and videos from this night."
2. **Pick files:** multiple allowed. Videos and photos straight from the camera roll.
3. **For each file, pick the song** from the setlist (a numbered list, so "the one after Them Changes" is easy to find), or "Not a song: crowd, venue, before/after".
4. **Credit:** "How should we credit you?" (e.g. a Reddit username). Optional; blank means "Anonymous fan".
5. **Contact (optional, private):** an email for removal requests. Never published.
6. **Consent checkbox (required):** "I filmed this myself and I'm happy for it to appear on this site with the credit above. I can ask for it to be removed at any time."
7. **Upload** with a progress bar per file; large videos upload in chunks so a phone on bad signal can resume.
8. **Confirmation:** "Thanks! Your clips will appear once they've been reviewed."

### Limits and abuse protection

| Rule | Starting value | Why |
|---|---|---|
| Uploads only for shows marked open | `"uploads": {"open": true, "until": "2026-12-31"}` in `shows/<id>.json` | Nothing is open by default; links stop working after the date. |
| File types | `.mp4 .mov .m4v .webm .jpg .jpeg .png .heic` | Checked in the Worker against both the extension and the content type. |
| File size | 1 GB per video, 30 MB per photo | Big enough for a few minutes of 4K phone video. |
| Per person | 20 files and 5 GB per day, keyed on a hashed IP | Stops one person filling the bucket. |
| Per show | 500 files waiting in the inbox | A hard stop if a link goes viral or gets abused. |
| Bot check | Turnstile on every upload request | |
| Nothing public without review | Files sit in private `inbox/` until approved | The core safeguard: no stranger's upload ever appears unreviewed. |

### What gets saved with each upload (`inbox/<show-id>/<upload-id>.json`)

```json
{
  "upload_id": "01JC3Y8Q…",
  "show_id": "2026-11-03-thundercat",
  "song_n": 16,
  "song_title": "Them Changes",
  "credit": "u/basslinebrenda",
  "contact": "fan@example.com",
  "original_name": "IMG_4412.MOV",
  "type": "video/quicktime",
  "bytes": 284113920,
  "uploaded_at": "2026-11-05T02:14:09Z",
  "ip_hash": "sha256:…",
  "consent": "v1"
}
```

`contact` and `ip_hash` never leave the inbox. `ip_hash` is only for rate limiting and is deleted along with the submission.

### Review tool (`scripts/inbox.py`)

```sh
python3 scripts/inbox.py list                       # waiting uploads, grouped by show
python3 scripts/inbox.py review 2026-11-03-thundercat   # one at a time: details + opens the file
python3 scripts/inbox.py approve <upload-id> [--song 12] [--start 0:20 --end 3:10]
python3 scripts/inbox.py reject <upload-id>
python3 scripts/inbox.py remove <public file>        # takedown request for an already-approved clip
```

**Approve** does the following:
1. Downloads the file.
2. Converts video to 1080p H.264 MP4 and photos to JPEG, using the same settings as the README.
3. Strips location and device metadata.
4. Uploads it as `public/<show-id>/<upload-id>--<Song-Name>.mp4`.
5. Adds `{ "src": "<that file>", "by": "fan", "credit": "u/…" }` under the song in `shows/<id>.json`.
6. Deletes the inbox copy.

The owner then commits and pushes as usual. Later this could commit and push for you.

### Changes to the existing site

- **Show page:** when a show's uploads are open, a **"Were you there? Add your clips →"** button in the header and in each empty song slot (the slot link preselects that song on the upload page).
- **`config.json`:** add `upload_api` (the Worker's address) and `contact_email` (for removal requests, shown on the upload page).
- **Build:** a show with open uploads includes the open/until fields in its data file so the page knows to show the button.
- **README:** a "Collecting clips from other fans" section with setup steps (create the bucket, deploy the Worker, add the Turnstile key), plus a Reddit post template.

### Reddit post template (draft)

> **[Thundercat — Avondale, Birmingham — Nov 3] Help me rebuild the whole show from fan footage**
>
> I'm putting together a song-by-song archive of this show. I got a few songs; if you filmed anything, you can add it here, no account needed: <link>
>
> Pick the song you filmed, add your username if you want credit, and that's it. I review everything before it goes up, and anything can be taken down on request.

## 4. Alternatives considered

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| **Dropbox File Request** link per show | No setup; uploaders don't need an account | No song picker, so the owner has to work out what each clip is; files go to Dropbox, not the site | Good stopgap if uploads are needed before this is built |
| **Google Photos shared album** | Familiar; phones upload easily | Uploaders need a Google account; no song picker; download step is manual | Same |
| **Google Form with file upload** | Has a song dropdown | Uploaders need a Google account; 10 GB form limit; files land in Drive | Possible stopgap |
| **Uploads as GitHub pull requests** | Stays in Git | Nobody on Reddit will do this; 100 MB limit | No |
| **A hosted backend (Supabase, Firebase)** | Comes with auth and a database | More moving parts; storage costs for video | Overkill for this |

## 5. Costs

At personal scale this should cost nothing, or close to it. Cloudflare's free tiers include 10 GB of R2 storage with free downloads, 100,000 Worker requests a day, and Turnstile. Past 10 GB, R2 is roughly $0.015 per GB per month (check current pricing before relying on these numbers). A few hundred converted 1080p clips is in the low tens of GB.

## 6. Privacy, consent and takedowns

- Uploaders agree to a short consent statement. Its version is saved with each upload.
- Contact emails are never published or committed to the repo.
- Location and device metadata are removed from everything published.
- A removal request is handled with `inbox.py remove`. The README should say how to ask (the `contact_email`).
- Uploads that show other people's faces prominently, or that aren't from that show, are rejected at review.

## 7. Plan

| Phase | Scope |
|---|---|
| **0. Media to R2** | Move the owner's own media to R2 behind `media_base_url` (useful on its own once videos outgrow GitHub). |
| **1. Uploads** | Worker, upload page, `inbox.py` (list/review/approve/reject/remove), per-show open/until, Turnstile, limits, README setup guide. |
| **2. Nicer review** | A password-protected review page in the browser instead of the CLI; approve straight from a phone. |
| **3. Smarter matching** | Suggest the song from the clip's recording time, compared with already-placed clips from the same night; "this song still needs footage" prompts on the upload page. |

## 8. Open questions

- Should approved fan clips be converted to a smaller size than the owner's own (e.g. 720p) to save space?
- Should fans be able to give a start/end time, or is "pick the song" enough?
- Should there be a per-show note on the upload page (e.g. "especially looking for the encore")?
- Push notifications or email to the owner when something new arrives?
