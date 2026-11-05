# Song tagging with Shazam

[← ConcertBuddy README](../README.md) · Let Shazam name the song in each clip (Mac only).

On a Mac, Apple's ShazamKit can listen to each clip and name the song, so most of the tagging does itself. It works best on studio-recorded songs by well-known artists; it matches against studio recordings, so loud, distorted phone audio and live arrangements often stump it. Expect it to recognise a minority of your clips; the [tagging screen](your-footage.md#tag-clips-with-songs-the-tagging-screen)'s timing suggestions carry on from the ones it gets.

It only needs the clips on your computer, and skips clips under 4 seconds (Shazam needs at least 3).

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
- Shazam's answer for each clip is sorted three ways:
  - **On the setlist:** tagged with `--apply`, and suggested in the tagging screen (a green *Shazam match* chip).
  - **By an act on the bill, but not on its setlist:** listed, left untagged. Usually the setlist is missing it: an opener with no setlist yet, or a [provisional setlist](setlists.md#provisional-setlists) borrowed from another night. Add the song to `shows/<id>.json` in the right place, then tag it.
  - **By somebody not on the bill:** almost always a wrong guess on crowd noise, or the music the venue played between sets. Never suggested; shown dimmed in the tagging screen so you can check.
