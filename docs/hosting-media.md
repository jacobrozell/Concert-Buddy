# Big videos and hosting

[← ConcertBuddy README](../README.md) · Keeping video out of GitHub's limits, and hosting it free on Cloudflare R2.

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
