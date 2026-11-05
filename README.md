# ConcertBuddy 🎟️

**A concert log you can relive.** ConcertBuddy turns a spreadsheet of every show you've been to into a website, hosted free on GitHub Pages. Every concert is a ticket stub on a timeline. Open one and its setlist becomes a row of slots, one per song, for your own clips and other fans' videos. Press **▶ Play the show** to watch the night back in order.

**See one:** https://jacobrozell.github.io/Concert-Buddy/

No server, no database, no accounts, no monthly bill. Your log is a CSV file plus a few folders in a GitHub repo you own; a Python script (standard library only) builds the site, and GitHub publishes it every time you push.

---

## Start your own

You need a GitHub account, `git`, and Python 3.9 or newer (`python3 --version`; macOS and Linux have it).

**1. Make your copy.** On this repo's GitHub page, click **Use this template → Create a new repository**. The name you pick becomes part of your address: `https://<you>.github.io/<repo-name>/`. Then:

```sh
git clone https://github.com/<you>/<repo-name>.git
cd <repo-name>
```

**2. Clear out the example and make it yours.**

```sh
python3 scripts/start_fresh.py
```

It removes the example shows, then asks for your name, a site title, who you usually go to shows with (optional) and, if you like, your first show.

**3. Add your shows** to `concerts.csv`, one row each. Only `artist` and `date` are required; use a spreadsheet app or a text editor:

```csv
artist,date,venue,location,companions,opener,setlist_url,media_links,notes
Phoebe Bridgers,2024-06-01,Ryman Auditorium,"Nashville, TN",Alex,MUNA,,,Front row
```

**4. Look at it** on your computer: `python3 scripts/build.py --serve`, then open http://localhost:8000.

**5. Publish.** On GitHub: **Settings → Pages → Source → GitHub Actions**. Then push:

```sh
git add -A && git commit -m "My concert log" && git push
```

The **Actions** tab shows the build; when it's green (about a minute), your site is live.

---

## Then, whenever you like

| To… | Run | Guide |
|---|---|---|
| Fill in setlists from setlist.fm | `python3 scripts/setlist.py --all` | [Setlists](docs/setlists.md) |
| Sort a folder of phone videos into shows and shrink them | `python3 scripts/import_media.py --from ~/Desktop/Export --apply --convert` | [Your photos and videos](docs/your-footage.md) |
| Tag each clip with its song | `python3 scripts/build.py --serve`, then open `/tag.html` | [Tagging screen](docs/your-footage.md#tag-clips-with-songs-the-tagging-screen) |
| Let Shazam name the songs (Mac) | `python3 scripts/shazam_tag.py --apply` | [Shazam](docs/shazam.md) |
| Put your videos online (free up to 10 GB) | `python3 scripts/upload_media.py` | [Hosting](docs/hosting-media.md) |
| Add other fans' YouTube / TikTok clips | edit `shows/<id>.json` | [Fan videos](docs/fan-videos.md) |

After any change: commit and push, and the site rebuilds.

---

## What you get

- **Timeline:** every show as a ticket stub, coloured by state, with search, filters, a shows-per-year (or per-genre) chart, and memories of shows from this time of year.
- **Show page:** the whole bill (openers to headliner) as tabs, each act's setlist with a slot per song, a strip showing which songs have footage, and an "Other moments" section for everything else.
- **Play the show:** a full-screen player that runs through the night in setlist order, your footage first, fans' as a fallback, and a title card for songs nobody filmed.
- **Stats and artist pages:** the songs you've heard live most, the artists you've seen most, venues, who you go with, and every time you've seen each artist.
- **Tools:** setlists from setlist.fm, sorting phone videos into shows by when and where they were filmed, shrinking them, a tagging screen, Shazam song recognition, and uploading to Cloudflare R2.

---

## The guides

- [Your shows: the CSV, settings and show files](docs/your-log.md): every column, `config.json`, openers and co-headliners, genres
- [Setlists](docs/setlists.md): from setlist.fm, pasted in, or borrowed from a nearby night ("provisional")
- [Your photos and videos](docs/your-footage.md): importing, the review folder, shrinking, the tagging screen, tagging by file name
- [Song tagging with Shazam](docs/shazam.md): Mac setup and how matches are judged
- [Other fans' videos](docs/fan-videos.md): YouTube, Instagram and TikTok, with start and end times
- [Big videos and hosting](docs/hosting-media.md): GitHub's size limits, and free hosting on Cloudflare R2
- [The site](docs/the-site.md): what each page shows, and changing the look
- [Building, previewing and publishing](docs/publishing.md): how it works, project layout, GitHub Pages, privacy
- [Troubleshooting](docs/troubleshooting.md)

**Everything you publish is public**, including who you went with and any notes, so leave out anything you wouldn't post. See [Privacy](docs/publishing.md#privacy-everything-is-public).

---

## Roadmap

- [x] Ticket-stub timeline, show pages, Play the show
- [x] Openers and co-headliners as full acts; genres
- [x] Setlists from setlist.fm or pasted in
- [x] Importing, shrinking and tagging your own videos; Shazam; Cloudflare R2
- [x] Stats, artist pages and memories
- [ ] **Finding fan footage:** ready-made YouTube/TikTok searches for every empty song slot
- [ ] **Fan uploads:** a per-show page where other fans can upload the songs they filmed ([spec](docs/fan-uploads-spec.md))
- [ ] **Ticket stub images:** a photo of the real ticket on each show
- [ ] **Map view:** venues on a map, sized by number of visits

Ideas and pull requests welcome: open an issue.

## License

[MIT](LICENSE). Use it, fork it, change it, share it. Your concert data, photos and videos are yours; the license covers the code and templates.
