#!/usr/bin/env python3
"""Fill in setlists for every act on a show's bill: shows/<show-id>.json.

From setlist.fm (free API key: https://www.setlist.fm/settings/api):
    export SETLISTFM_API_KEY=your-key
    python3 scripts/setlist.py 2026-11-03-thundercat     # every act on that bill
    python3 scripts/setlist.py --all                     # every show, every act still missing a setlist

By hand (one song per line; a line like "[Encore]" starts a new set):
    python3 scripts/setlist.py 2026-11-03-thundercat --from-file songs.txt                       # the headliner
    python3 scripts/setlist.py 2026-11-03-thundercat --act "Channel Tres" --from-file songs.txt  # an opener
    pbpaste | python3 scripts/setlist.py 2026-11-03-thundercat --from-file -

See what's there and what's missing:
    python3 scripts/setlist.py --list

Media you've already attached to songs is kept. If a song disappears from a
new setlist, its clips move to "Other moments" so nothing is lost.
"""
import argparse
import datetime
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
from common import bill, clean_set_name, load_show, read_concerts, save_show, show_acts, slugify  # noqa: E402

API = "https://api.setlist.fm/rest/1.0"


# ---------- setlist.fm ----------

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


def parse_setlistfm(data):
    sets = []
    for i, s in enumerate(data.get("sets", {}).get("set", [])):
        name = clean_set_name(s.get("name") or (f"Encore {s['encore']}" if s.get("encore", 0) > 1 else "Encore" if s.get("encore") else ""), i)
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
    return sets


def fetch_act(artist, row, key, setlist_id=None, search_name=None):
    """Returns (sets, url, message). Uses an exact setlist id when given, else
    searches setlist.fm for the artist on that date (preferring the right city)."""
    if setlist_id:
        data = api_get(f"/setlist/{setlist_id}", key)
        if data and data.get("sets", {}).get("set"):
            return parse_setlistfm(data), data.get("url", ""), ""
    name = search_name or artist
    y, mo, d = row["date"].split("-")
    res = api_get("/search/setlists?" + urllib.parse.urlencode({"artistName": name, "date": f"{d}-{mo}-{y}"}), key) or {}
    hits = [s for s in res.get("setlist", []) if s.get("sets", {}).get("set")]
    if not hits:
        return None, None, "nothing on setlist.fm yet"
    want = slugify(name)
    exact = [s for s in hits if slugify(s.get("artist", {}).get("name", "")) == want]
    if not exact:
        found = hits[0].get("artist", {}).get("name", "?")
        return None, None, f"setlist.fm only had '{found}' that day; if that's them, add --search \"{found}\""
    city = (row.get("location") or "").split(",")[0].strip().lower()
    exact.sort(key=lambda s: s.get("venue", {}).get("city", {}).get("name", "").lower() != city)
    return parse_setlistfm(exact[0]), exact[0].get("url", ""), ""


# ---------- by hand ----------

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


# ---------- saving ----------

def merge_act(old, new_sets, extras):
    """New setlist for one act; carry media over from the old one by song title.
    Media on songs that disappeared is moved to the show's extras."""
    by_slug = {}
    for s in (old or {}).get("sets", []):
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
    for leftovers in by_slug.values():
        for p in leftovers:
            for m in p.get("media", []):
                m = {"src": m} if isinstance(m, str) else dict(m)
                m.setdefault("caption", f"Was tagged “{p['title']}”")
                extras.append(m)
    return new_sets


def save(row, show, acts_by_slug, extras):
    """Write the show file with acts in stage order."""
    order = bill(row, show.get("order"))
    acts = []
    for a in order:
        act = acts_by_slug.pop(slugify(a["artist"]), None)
        if act and (act.get("sets") or act.get("checked")):
            acts.append({"artist": a["artist"], **{k: v for k, v in act.items() if k != "artist"}})
    acts += [a for a in acts_by_slug.values() if a.get("sets")]  # acts not on the CSV bill: keep them
    out = {k: v for k, v in show.items() if k not in ("acts", "sets", "source", "provisional", "extras")}
    out["acts"] = acts
    if extras:
        out["extras"] = extras
    save_show(row["id"], out)


def has_setlist(act):
    return bool(act and act.get("sets") and not act.get("provisional"))


# ---------- commands ----------

def cmd_list(rows):
    for r in rows:
        show = load_show(r["id"]) or {}
        acts = {slugify(a.get("artist", "")): a for a in show_acts(show, r)}
        marks = []
        for a in bill(r, show.get("order")):
            act = acts.get(slugify(a["artist"]))
            mark = "✓" if has_setlist(act) else "~" if act and act.get("sets") else "·" if act and act.get("checked") else "✗"
            marks.append(f"{mark} {a['artist']}")
        print(f"{r['id']:40} {'   '.join(marks)}")
    print("\n✓ setlist   ~ provisional   ✗ missing   · not on setlist.fm when last checked (--retry to check again)")


def cmd_fetch(rows, args):
    key = os.environ.get("SETLISTFM_API_KEY")
    if not key:
        raise SystemExit("Set SETLISTFM_API_KEY first (free at https://www.setlist.fm/settings/api), or use --from-file.")
    today = datetime.date.today().isoformat()
    for row in rows:
        show = load_show(row["id"]) or {}
        acts = {slugify(a.get("artist", "")): a for a in show_acts(show, row)}
        extras = list(show.get("extras", []))
        changed = False
        for a in bill(row, show.get("order")):
            if args.act and slugify(args.act) != slugify(a["artist"]):
                continue
            slug, old = slugify(a["artist"]), acts.get(slugify(a["artist"]))
            if has_setlist(old) and not args.refresh:
                continue
            if old and old.get("checked") and not old.get("sets") and not (args.retry or args.act or not args.all):
                continue
            setlist_id = None
            if a["role"] == "headliner":
                m = re.search(r"setlist\.fm/.*-([0-9a-f]{6,10})\.html", row.get("setlist_url", ""))
                setlist_id = m.group(1) if m else None
            sets, url, msg = fetch_act(a["artist"], row, key, setlist_id, args.search if args.act else None)
            if sets:
                acts[slug] = {"artist": a["artist"], "source": url, "sets": merge_act(old, sets, extras)}
                print(f"  ✓ {row['id']} · {a['artist']}: {sum(len(s['songs']) for s in sets)} songs")
            else:
                if not (old and old.get("sets")):
                    acts[slug] = {"artist": a["artist"], "checked": today}
                print(f"  – {row['id']} · {a['artist']}: {msg}")
            changed = True
            time.sleep(0.6)  # setlist.fm allows ~2 requests/second
        if changed:
            save(row, show, acts, extras)


def cmd_from_file(row, args):
    text = sys.stdin.read() if args.from_file == "-" else Path(args.from_file).read_text(encoding="utf-8")
    sets = parse_text(text)
    if not sets:
        raise SystemExit("No songs found in that input.")
    show = load_show(row["id"]) or {}
    acts = {slugify(a.get("artist", "")): a for a in show_acts(show, row)}
    on_bill = bill(row, show.get("order"))
    if args.act:
        target = next((a for a in on_bill if slugify(a["artist"]) == slugify(args.act)), None)
        if not target:
            raise SystemExit(f"'{args.act}' isn't on this show's bill: {', '.join(a['artist'] for a in on_bill)}")
    else:
        target = next(a for a in on_bill if a["role"] == "headliner")
    extras = list(show.get("extras", []))
    slug = slugify(target["artist"])
    acts[slug] = {"artist": target["artist"], "sets": merge_act(acts.get(slug), sets, extras)}
    save(row, show, acts, extras)
    print(f"Saved {sum(len(s['songs']) for s in sets)} songs for {target['artist']} → shows/{row['id']}.json")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("show_id", nargs="?")
    ap.add_argument("--act", help="only this artist on the bill (default: every act, or the headliner with --from-file)")
    ap.add_argument("--from-file", metavar="PATH", help="songs one per line ('-' for stdin)")
    ap.add_argument("--search", metavar="NAME", help="with --act: the artist's name as setlist.fm spells it")
    ap.add_argument("--all", action="store_true", help="every show")
    ap.add_argument("--refresh", action="store_true", help="fetch again even where a setlist exists (keeps media)")
    ap.add_argument("--retry", action="store_true", help="with --all: re-check acts that weren't on setlist.fm last time")
    ap.add_argument("--list", action="store_true", help="show every show's acts and which have setlists")
    args = ap.parse_args()

    rows = read_concerts()
    if args.list:
        return cmd_list(rows)
    targets = rows if args.all else [r for r in rows if r["id"] == args.show_id]
    if not targets:
        raise SystemExit(f"No show with id {args.show_id!r}. Run with --list to see ids." if args.show_id else "Give a show id, or --all.")
    if args.from_file:
        if len(targets) != 1:
            raise SystemExit("--from-file needs exactly one show id")
        return cmd_from_file(targets[0], args)
    cmd_fetch(targets, args)


if __name__ == "__main__":
    main()
