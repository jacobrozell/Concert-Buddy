#!/usr/bin/env python3
"""Fill in a show's setlist: shows/<show-id>.json.

From setlist.fm (free API key: https://www.setlist.fm/settings/api):
    export SETLISTFM_API_KEY=your-key
    python3 scripts/setlist.py 2026-11-03-thundercat
    python3 scripts/setlist.py --all            # every show that doesn't have a setlist yet

By hand (one song per line; a line like "[Encore]" starts a new set):
    python3 scripts/setlist.py 2026-11-03-thundercat --from-file songs.txt
    pbpaste | python3 scripts/setlist.py 2026-11-03-thundercat --from-file -

Media you've already attached to songs is kept. If a song disappears from
the new setlist, its clips move to "Other moments" so nothing is lost.
Show ids are <date>-<first-artist>, e.g. 2022-08-27-jack-white
(run with --list to see them all).
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_show, read_concerts, save_show, slugify  # noqa: E402

API = "https://api.setlist.fm/rest/1.0"


def api_get(path, key):
    req = urllib.request.Request(
        f"{API}{path}",
        headers={"x-api-key": key, "Accept": "application/json", "User-Agent": "ConcertBuddy/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        if e.code == 429:
            time.sleep(2)
            return api_get(path, key)
        raise SystemExit(f"setlist.fm said {e.code}: {e.read()[:200]!r}")


def fetch_from_setlistfm(row, key, artist_override=None):
    """Use the setlist_url id when the CSV has one, else search by artist + date."""
    m = re.search(r"-([0-9a-f]{6,10})\.html", row.get("setlist_url", ""))
    data = api_get(f"/setlist/{m.group(1)}", key) if m else None
    if not data:
        y, mo, d = row["date"].split("-")
        artists = [artist_override] if artist_override else re.split(r"\s+/\s+", row["artist"])
        for artist in artists:
            q = urllib.parse.urlencode({"artistName": artist, "date": f"{d}-{mo}-{y}"})
            res = api_get(f"/search/setlists?{q}", key) or {}
            hits = [s for s in res.get("setlist", []) if s.get("sets", {}).get("set")]
            if hits:
                data = hits[0]
                break
    if not data or not data.get("sets", {}).get("set"):
        return None, None
    sets = []
    for i, s in enumerate(data["sets"]["set"]):
        name = s.get("name") or (f"Encore {s['encore']}" if s.get("encore", 0) > 1 else "Encore" if s.get("encore") else "Main set" if i == 0 else f"Set {i + 1}")
        songs = []
        for song in s.get("song", []):
            if song.get("tape") or not song.get("name"):
                continue  # intro tapes / walk-on music
            note = []
            if song.get("info"):
                note.append(song["info"])
            if song.get("cover"):
                note.append(f"{song['cover']['name']} cover")
            if song.get("with"):
                note.append(f"with {song['with']['name']}")
            songs.append({"title": song["name"], **({"note": "; ".join(note)} if note else {})})
        if songs:
            sets.append({"name": name, "songs": songs})
    return sets, data.get("url", "")


def parse_text(text):
    sets, current = [], {"name": "Main set", "songs": []}
    for raw in text.splitlines():
        line = re.sub(r"^\s*\d+[.)]\s*", "", raw).strip()  # drop "1. " numbering
        if not line or line.startswith("#"):
            continue
        if m := re.fullmatch(r"\[(.+)\]", line):
            if current["songs"]:
                sets.append(current)
            current = {"name": m.group(1).strip(), "songs": []}
            continue
        title, _, note = line.partition(" -- ")
        current["songs"].append({"title": title.strip(), **({"note": note.strip()} if note else {})})
    if current["songs"]:
        sets.append(current)
    return sets


def merge(old, new_sets, source):
    """Carry media from the old setlist onto matching songs in the new one."""
    old = old or {}
    by_slug = {}
    for s in old.get("sets", []):
        for song in s.get("songs", []):
            by_slug.setdefault(slugify(song.get("title", "")), []).append(song)
    for s in new_sets:
        for song in s["songs"]:
            prev = by_slug.get(slugify(song["title"]))
            if prev:
                p = prev.pop(0)
                if p.get("media"):
                    song["media"] = p["media"]
                if p.get("note") and not song.get("note"):
                    song["note"] = p["note"]
    extras = list(old.get("extras", []))
    for leftovers in by_slug.values():
        for p in leftovers:
            for m in p.get("media", []):
                m = {"src": m} if isinstance(m, str) else dict(m)
                m.setdefault("caption", f"Was tagged “{p['title']}”")
                extras.append(m)
    out = {"sets": new_sets, "extras": extras}
    if source:
        out["source"] = source
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("show_id", nargs="?")
    ap.add_argument("--from-file", metavar="PATH", help="songs one per line ('-' for stdin)")
    ap.add_argument("--artist", help="artist name to search setlist.fm with (for multi-artist bills)")
    ap.add_argument("--all", action="store_true", help="fetch every show without a setlist")
    ap.add_argument("--list", action="store_true", help="print every show id")
    args = ap.parse_args()

    rows = read_concerts()
    if args.list:
        for r in rows:
            have = load_show(r["id"])
            mark = "✓" if have and have.get("sets") and not have.get("provisional") else "~" if have and have.get("sets") else " "
            print(f"{mark} {r['id']}")
        print("\n✓ has setlist   ~ provisional")
        return

    targets = rows if args.all else [r for r in rows if r["id"] == args.show_id]
    if not targets:
        raise SystemExit(f"No show with id {args.show_id!r}. Run with --list to see ids.")

    if args.from_file:
        if len(targets) != 1:
            raise SystemExit("--from-file needs exactly one show id")
        text = sys.stdin.read() if args.from_file == "-" else Path(args.from_file).read_text(encoding="utf-8")
        sets = parse_text(text)
        if not sets:
            raise SystemExit("No songs found in that input.")
        row = targets[0]
        save_show(row["id"], merge(load_show(row["id"]), sets, ""))
        print(f"Saved {sum(len(s['songs']) for s in sets)} songs → shows/{row['id']}.json")
        return

    key = os.environ.get("SETLISTFM_API_KEY")
    if not key:
        raise SystemExit("Set SETLISTFM_API_KEY first (free at https://www.setlist.fm/settings/api), or use --from-file.")

    for row in targets:
        existing = load_show(row["id"])
        if args.all and existing and existing.get("sets") and not existing.get("provisional"):
            continue
        sets, url = fetch_from_setlistfm(row, key, args.artist)
        if not sets:
            print(f"  – {row['id']}: nothing on setlist.fm yet")
        else:
            save_show(row["id"], merge(existing, sets, url))
            print(f"  ✓ {row['id']}: {sum(len(s['songs']) for s in sets)} songs")
        if args.all:
            time.sleep(0.6)  # setlist.fm allows ~2 requests/second


if __name__ == "__main__":
    main()
