#!/usr/bin/env python3
"""Start your own concert log: clears the example shows that came with the template and
asks a few questions. Run it once, right after you make your copy of the repo.

    python3 scripts/start_fresh.py

It shows what it's about to remove and asks before changing anything:
  concerts.csv   -> just the column headers, plus your first show if you type one in
  artists.csv    -> just the column headers
  shows/         -> emptied (the example shows' setlists and tags)
  media/         -> the example shows' folders removed (media/README.md stays)
  config.json    -> your site title, name, tagline, who you usually go with, time zone;
                    the media address is cleared (the example's videos aren't yours)
The code, templates and docs aren't touched. Afterwards: commit, push, and your
(empty) site is live; add shows to concerts.csv and push again.

No questions asked (for scripts):
    python3 scripts/start_fresh.py --yes --title "Sam's Shows" --owner "Sam" \\
        [--tagline "..."] [--companion "Alex"] [--timezone America/New_York]
Standard library only.
"""
import argparse
import csv
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CONFIG_PATH, CSV_PATH, MEDIA_DIR, ROOT, SHOWS_DIR, read_concerts  # noqa: E402

COLUMNS = ["artist", "date", "venue", "location", "companions", "opener", "setlist_url", "media_links", "notes"]
DEFAULT_TAGLINE = "Every concert I've been to, one ticket stub at a time. Open a show to relive it song by song."


def this_computers_timezone():
    """'America/Chicago' from the system clock settings, or '' if it can't tell."""
    try:
        target = str(Path("/etc/localtime").resolve())
        m = re.search(r"zoneinfo/(.+)$", target)
        if m:
            return m.group(1)
    except OSError:
        pass
    tz = Path("/etc/timezone")
    return tz.read_text().strip() if tz.exists() else ""


def ask(prompt, default=""):
    shown = f" [{default}]" if default else ""
    try:
        answer = input(f"{prompt}{shown}: ").strip()
    except EOFError:
        answer = ""
    return answer or default


def ask_first_show():
    print("\nYour first show (optional: press Enter to skip and add shows to concerts.csv later).")
    artist = ask("  Artist")
    if not artist:
        return None
    while True:
        date = ask("  Date (YYYY-MM-DD)")
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            break
        print("    Please use the form 2024-06-14.")
    return {"artist": artist, "date": date, "venue": ask("  Venue"), "location": ask("  City, state (e.g. Nashville, TN)"),
            "companions": ask("  Who you went with"), "opener": ask("  Opener(s), separated by ' / '")}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--yes", action="store_true", help="don't ask; use the options below")
    ap.add_argument("--title", help='site title, e.g. "Sam\'s Shows"')
    ap.add_argument("--owner", help="your name, shown at the top of the site")
    ap.add_argument("--tagline")
    ap.add_argument("--companion", help="someone you go to shows with: adds a 'With …' filter and count")
    ap.add_argument("--timezone", help="e.g. America/New_York (used when sorting phone videos into shows)")
    args = ap.parse_args()

    shows = read_concerts() if CSV_PATH.exists() else []
    show_files = sorted(SHOWS_DIR.glob("*.json")) if SHOWS_DIR.is_dir() else []
    media_folders = sorted(p for p in MEDIA_DIR.iterdir() if p.is_dir()) if MEDIA_DIR.is_dir() else []
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8")) if CONFIG_PATH.exists() else {}

    print("This clears the example concert log so you can start your own:")
    print(f"  concerts.csv: {len(shows)} show(s) removed")
    print(f"  shows/: {len(show_files)} setlist file(s) removed")
    print(f"  media/: {len(media_folders)} show folder(s) removed (with any photos or videos in them)")
    print(f"  config.json: \"{cfg.get('site_title', '')}\" becomes your title and name")
    local_media = sum(1 for d in media_folders for f in d.rglob("*") if f.is_file() and f.name != "media.json")
    if local_media:
        print(f"\n  ! {local_media} photo/video file(s) are in those folders on this computer. They'll be deleted too.")
    if not args.yes:
        if ask("\nGo ahead? (yes/no)", "no").lower() not in ("y", "yes"):
            print("Nothing changed.")
            return

    # 1. You
    if args.yes:
        title = args.title or "My Concert Log"
        owner = args.owner or ""
        tagline = args.tagline or DEFAULT_TAGLINE
        companion = args.companion or ""
        timezone = args.timezone or this_computers_timezone()
        first = None
    else:
        print("\nA few questions (press Enter to accept the suggestion in brackets).")
        owner = ask("Your name (shown at the top of the site)", args.owner or "")
        title = ask("Site title", args.title or (f"{owner.split()[0]}'s Concert Log" if owner else "My Concert Log"))
        tagline = ask("One line under the title", args.tagline or DEFAULT_TAGLINE)
        companion = ask("Someone you often go with (adds a 'With …' filter; Enter to skip)", args.companion or "")
        timezone = ask("Your time zone", args.timezone or this_computers_timezone())
        first = ask_first_show()

    # 2. Clear the example
    for f in show_files:
        f.unlink()
    for d in media_folders:
        shutil.rmtree(d)
    for cache in (MEDIA_DIR / ".shazam.json", MEDIA_DIR / ".meta-cache.json"):
        if cache.exists():
            cache.unlink()
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        if first:
            w.writerow({k: first.get(k, "") for k in COLUMNS})
    with open(ROOT / "artists.csv", "w", newline="", encoding="utf-8") as f:
        f.write("artist,genres\n")

    # 3. Settings. repo_url keeps pointing at the template, for the "Made with ConcertBuddy" link.
    cfg.update({"site_title": title, "owner": owner, "tagline": tagline, "highlight_companion": companion,
                "media_base_url": "", "site_url": "", "timezone": timezone})
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"\nDone. \"{title}\" is ready{' with your first show' if first else ''}.")
    print("Next:")
    print("  python3 scripts/build.py --serve     # look at it on this computer (http://localhost:8000)")
    print("  git add -A && git commit -m \"Start my concert log\" && git push")
    print("Then add shows to concerts.csv (one row each) and push again. The README's quick start has the rest.")


if __name__ == "__main__":
    main()
