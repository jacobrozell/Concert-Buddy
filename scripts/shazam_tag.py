#!/usr/bin/env python3
"""Let Shazam work out which song is playing in each clip, and tag it.

One-time setup (a Mac with Xcode, macOS 14+, and an Apple developer account):
see docs/shazam.md, then build the helper:

    tools/shazam/build.sh com.yourname.concertbuddy.shazam

Then:
    python3 scripts/shazam_tag.py                      # listen to every untagged clip, report what it heard
    python3 scripts/shazam_tag.py --apply              # ...and tag the clips whose song is on the setlist
    python3 scripts/shazam_tag.py --show 2026-11-03-thundercat --apply
    python3 scripts/shazam_tag.py --retry              # listen again to clips Shazam didn't recognise

Only clips you haven't tagged are touched; your own tags always win. What Shazam
heard is kept in media/.shazam.json, so re-runs only listen to new clips, and the
tagging screen (build.py --serve, then /tag.html) shows it next to every clip,
including songs that aren't on the setlist (covers, a provisional setlist that
was wrong). Standard library only.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402
from common import MEDIA_DIR, ROOT, judge_heard, read_concerts, read_config, read_genres  # noqa: E402

BIN = Path(os.environ.get("CB_SHAZAM", ROOT / "tools" / "shazam" / "cb-shazam"))
CACHE = MEDIA_DIR / ".shazam.json"
LISTEN_EXT = {".mov", ".mp4", ".m4v", ".webm", ".m4a", ".mp3", ".wav", ".aac"}
BATCH = 8
MIN_SECONDS = 4  # Shazam needs at least 3 s of audio; shorter clips are left for you to tag


def read_cache():
    return json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}


def write_cache(cache):
    tmp = CACHE.with_suffix(".tmp")
    tmp.write_text(json.dumps(cache, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(CACHE)


def summarize(windows):
    """Windows Shazam listened to -> [{title, artist, votes}], most-heard first."""
    votes, info = Counter(), {}
    for w in windows:
        if w.get("title"):
            k = w.get("shazamID") or f"{w['title']}|{w.get('artist', '')}"
            votes[k] += 1
            info.setdefault(k, {"title": w["title"], "artist": w.get("artist") or ""})
    return [{**info[k], "votes": n} for k, n in votes.most_common()]


def heard_for(cache, sid, name):
    """What Shazam heard in one clip, or None if it hasn't listened yet."""
    return (cache.get(sid) or {}).get(name)


def untagged(show):
    """Clips the build found in the folder but nobody has placed under a song (or hidden):
    (long enough for Shazam, too short)."""
    clips = [m for m in show["extras"] if m.get("auto") and m.get("file") and Path(m["file"]).suffix.lower() in LISTEN_EXT]
    short = [m["file"] for m in clips if m.get("seconds") is not None and m["seconds"] < MIN_SECONDS]
    return [m["file"] for m in clips if m["file"] not in short], short


def listen(paths, deadline):
    """Run cb-shazam over the files, yielding (path, result) as each one finishes."""
    for i in range(0, len(paths), BATCH):
        if deadline and time.time() > deadline:
            return
        batch = paths[i:i + BATCH]
        proc = subprocess.Popen([str(BIN), *map(str, batch)], stdout=subprocess.PIPE, text=True)
        for line in proc.stdout:
            line = line.strip()
            if line.startswith("{"):
                out = json.loads(line)
                yield Path(out["file"]), out
        if proc.wait() not in (0, None):
            raise SystemExit(f"cb-shazam stopped with an error (exit {proc.returncode}); see above.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--show", metavar="SHOW_ID", help="only this show")
    ap.add_argument("--apply", action="store_true", help="tag the clips whose song is on the setlist")
    ap.add_argument("--retry", action="store_true", help="listen again to clips Shazam didn't recognise last time")
    ap.add_argument("--time-limit", type=float, metavar="SECONDS", help="stop listening after this long (re-run to continue)")
    args = ap.parse_args()

    cfg, genres = read_config(), read_genres()
    rows = [r for r in read_concerts() if not args.show or r["id"] == args.show]
    if args.show and not rows:
        raise SystemExit(f"No show {args.show} in concerts.csv")
    cache = read_cache()

    # 1. Which clips still need a song, and which of those Shazam hasn't heard yet
    shows, todo, too_short = {}, [], 0
    for row in rows:
        show, _ = build.build_show(row, cfg, genres, [])
        names, short = untagged(show)
        too_short += len(short)
        names = [n for n in names if (MEDIA_DIR / row["id"] / n).is_file()]
        if not names:
            continue
        shows[row["id"]] = (row, show, names)
        for n in names:
            prev = heard_for(cache, row["id"], n)
            if prev is None or (args.retry and not prev.get("heard")):
                todo.append(MEDIA_DIR / row["id"] / n)

    total = sum(len(v[2]) for v in shows.values())
    print(f"{total} untagged clip(s) in {len(shows)} show(s); {len(todo)} for Shazam to listen to."
          + (f" ({too_short} more are under {MIN_SECONDS} s, too short for Shazam: tag those yourself.)" if too_short else ""))

    # 2. Listen
    if todo:
        if not BIN.exists():
            raise SystemExit(f"\nThe Shazam helper isn't built yet ({BIN.relative_to(ROOT)}).\n"
                             "On your Mac: tools/shazam/build.sh com.yourname.concertbuddy.shazam  (docs/shazam.md)")
        deadline = time.time() + args.time_limit if args.time_limit else None
        done = 0
        for n, (path, out) in enumerate(listen(todo, deadline), 1):
            done = n
            sid = path.parent.name
            heard = summarize(out.get("windows", []))
            errors = [w["error"] for w in out.get("windows", []) if w.get("error")]
            cache.setdefault(sid, {})[path.name] = {
                "heard": heard, "windows": len(out.get("windows", [])), "seconds": round(out.get("seconds") or 0, 1),
                **({"error": out.get("error") or errors[0]} if (out.get("error") or (errors and not heard)) else {}),
            }
            write_cache(cache)
            top = heard[0] if heard else None
            print(f"  [{n}/{len(todo)}] {sid}/{path.name}: " + (f"{top['title']} — {top['artist']}" if top else out.get("error") or "no match"))
        if done < len(todo):
            print(f"Stopped with {len(todo) - done} still to listen to; run again to continue.")

    # 3. Match what was heard to each show's setlist. Only songs on the setlist are tagged;
    #    songs by an act on the bill that aren't on its setlist are listed (the setlist may be
    #    missing them); anything by somebody not on the bill is set aside as a wrong guess.
    applied = on_list = off_list = wrong = nothing = 0
    offlist, unrelated = [], []
    for sid, (row, show, names) in shows.items():
        assign, lines = {}, []
        for name in names:
            res = heard_for(cache, sid, name)
            if res is None:
                continue
            top = (res.get("heard") or [None])[0]
            if not top:
                nothing += 1
                continue
            verdict, act, song = judge_heard(top["title"], top["artist"], show["acts"])
            votes = f"{top['votes']}/{res.get('windows', 1)}"
            heard = f"\"{top['title']}\" — {top['artist']} ({votes})"
            if verdict == "match":
                on_list += 1
                assign[name] = f"{act['n']}-{song['n']}"
                who = f"{act['artist']} · " if len(show["acts"]) > 1 else ""
                lines.append(f"  {name:<28} → {who}{song['n']:>2}. {song['title']}   (Shazam: {heard})")
            elif verdict == "offlist":
                off_list += 1
                offlist.append(f"  {sid}  {name}: {heard}, by {act['artist']}"
                               + ("" if any(st["songs"] for st in act["sets"]) else ", who has no setlist yet"))
            else:
                wrong += 1
                unrelated.append(f"  {sid}  {name}: {heard}")
        if lines:
            print(f"\n{sid}")
            print("\n".join(lines))
        if args.apply and assign:
            build.save_tags(sid, assign)
            applied += len(assign)

    if offlist:
        print("\nBy someone on the bill, but not on their setlist (left untagged; the setlist may be missing it):")
        print("\n".join(offlist))
    if unrelated:
        print("\nNot anyone on the bill, so probably a wrong guess (crowd noise, walk-on music). Left for you to tag:")
        print("\n".join(unrelated))
    print(f"\n{on_list} clip(s) matched a song on the setlist, {off_list} heard an off-setlist song by an act on the bill, "
          f"{wrong} heard someone not on the bill, {nothing} Shazam didn't recognise.")
    if args.apply:
        print(f"Tagged {applied} clip(s) in shows/*.json. Check them at http://localhost:8000/tag.html (build.py --serve).")
    elif on_list:
        print("Dry run: run again with --apply to tag them. (Or open the tagging screen: Shazam's picks show up there as suggestions.)")


if __name__ == "__main__":
    main()
