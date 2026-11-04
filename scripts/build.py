#!/usr/bin/env python3
"""Build the static site into _site/.

    python3 scripts/build.py            # build
    python3 scripts/build.py --serve    # build, then preview at http://localhost:8000

Reads concerts.csv, config.json, shows/<id>.json and media/<id>/, and writes
_site/ (the folder GitHub Pages serves). Never edits your source files.
"""
import argparse
import html
import http.server
import json
import os
import re
import shutil
import socketserver
import sys
from functools import partial
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    MEDIA_DIR, ROOT, bill, clean_set_name, load_show, read_concerts, read_config, read_genres, show_acts, slugify,
)

OUT = ROOT / "_site"
SITE_SRC = ROOT / "site"

VIDEO_EXT = {".mp4", ".m4v", ".mov", ".webm"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".heic"}
AUDIO_EXT = {".mp3", ".m4a", ".aac", ".wav", ".ogg"}
MEDIA_EXT = VIDEO_EXT | IMAGE_EXT | AUDIO_EXT


# ---------- time + media helpers ----------

def to_seconds(t):
    """'1:02:15' / '62:15' / '75' / '1h2m15s' / 75 -> seconds (int) or None."""
    if t in (None, ""):
        return None
    if isinstance(t, (int, float)):
        return int(t)
    t = str(t).strip()
    m = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s?)?", t)
    if m and any(m.groups()) and not t.isdigit():
        h, mi, s = (int(x or 0) for x in m.groups())
        return h * 3600 + mi * 60 + s
    parts = t.split(":")
    if all(p.isdigit() for p in parts):
        total = 0
        for p in parts:
            total = total * 60 + int(p)
        return total
    return None


def youtube_id(u):
    p = urlparse(u)
    host = p.netloc.lower().removeprefix("www.").removeprefix("m.")
    if host == "youtu.be":
        return p.path.strip("/").split("/")[0], parse_qs(p.query)
    if host.endswith("youtube.com") or host == "youtube-nocookie.com":
        q = parse_qs(p.query)
        if "v" in q:
            return q["v"][0], q
        m = re.match(r"/(?:shorts|live|embed)/([\w-]+)", p.path)
        if m:
            return m.group(1), q
    return None, {}


def resolve_media(item, sid, cfg, default_by):
    """Turn a hand-written media entry (or a scanned file) into what the page needs."""
    if isinstance(item, str):
        item = {"src": item}
    src = (item.get("src") or item.get("url") or item.get("file") or "").strip()
    out = {
        "by": item.get("by") or default_by,
        "credit": item.get("credit", ""),
        "caption": item.get("caption", ""),
    }
    start, end = to_seconds(item.get("start")), to_seconds(item.get("end"))
    is_url = bool(re.match(r"https?://", src))

    if is_url:
        out["by"] = item.get("by") or "fan"
        yt, q = youtube_id(src)
        if yt:
            if start is None and "t" in q:
                start = to_seconds(q["t"][0])
            out.update(kind="youtube", id=yt, url=src)
        elif m := re.search(r"instagram\.com/(?:[\w.]+/)?(?:p|reel|reels|tv)/([\w-]+)", src):
            out.update(kind="instagram", url=src, embed=f"https://www.instagram.com/p/{m.group(1)}/embed")
        elif m := re.search(r"tiktok\.com/.*/video/(\d+)", src):
            out.update(kind="tiktok", url=src, embed=f"https://www.tiktok.com/embed/v2/{m.group(1)}")
        else:
            ext = Path(urlparse(src).path).suffix.lower()
            kind = "video" if ext in VIDEO_EXT else "image" if ext in IMAGE_EXT else "audio" if ext in AUDIO_EXT else "link"
            out.update(kind=kind, url=src)
    else:
        ext = Path(src).suffix.lower()
        kind = "video" if ext in VIDEO_EXT else "image" if ext in IMAGE_EXT else "audio" if ext in AUDIO_EXT else "link"
        base = cfg["media_base_url"].rstrip("/")
        rel = f"{quote(sid)}/{quote(src)}"
        out.update(kind=kind, file=src, url=f"{base}/{rel}" if base else f"media/{rel}")

    if start is not None:
        out["start"] = start
    if end is not None:
        out["end"] = end
    return out


def song_from_filename(name, acts):
    """`IMG_0412--Them-Changes.mov` -> the song "Them Changes".

    Only the part after the first `--` is matched; a trailing -2 / -b counter is
    ignored. To point at a specific act (e.g. an opener who played a song with the
    same title), put the act first: `IMG_0412--Channel-Tres--Topless.mp4`.
    Without an act, the headliner wins, then co-headliners, then openers."""
    parts = Path(name).stem.split("--")
    if len(parts) < 2:
        return None
    by_act = {slugify(a["artist"]): a for a in acts}
    pool = acts
    if len(parts) >= 3 and slugify(parts[1]) in by_act:
        pool, parts = [by_act[slugify(parts[1])]], parts[1:]
    tag = slugify("-".join(parts[1:]))
    rank = {"headliner": 0, "co-headliner": 1, "opener": 2}
    for act in sorted(pool, key=lambda a: rank.get(a["role"], 3)):
        songs = {}
        for st in act["sets"]:
            for so in st["songs"]:
                songs.setdefault(slugify(so["title"]), so)
        for c in (tag, re.sub(r"-(\d+|[a-z])$", "", tag)):
            if c in songs:
                return songs[c]
        # Longest song slug that the tag starts with ("them-changes-encore" -> "them-changes")
        hits = [k for k in songs if tag.startswith(k + "-")]
        if hits:
            return songs[max(hits, key=len)]
    return None


def tidy_note(note):
    """setlist.fm marks a segue with a bare '>' (or '> ' in front of other text)."""
    note = (note or "").strip()
    if note == ">":
        return "segues into the next song"
    if note.startswith("> "):
        return "segues into the next song; " + note[2:]
    return note


# ---------- per-show build ----------

def build_show(row, cfg, genres, warnings):
    sid = row["id"]
    src = load_show(sid) or {}
    src_acts = {slugify(a.get("artist", "")): a for a in show_acts(src, row)}

    acts = []
    on_bill = bill(row, src.get("order"))
    for a in on_bill:
        acts.append({**a, "_src": src_acts.pop(slugify(a["artist"]), {})})
    for a in src_acts.values():  # setlists in the show file for acts not in the CSV
        warnings.append(f"{sid}: shows/{sid}.json has a setlist for '{a.get('artist')}', who isn't in this show's artist or opener column")
        acts.append({"artist": a.get("artist", "?"), "role": "opener", "_src": a})

    for i, act in enumerate(acts):
        a_src = act.pop("_src")
        act["n"] = i + 1
        act["genres"] = genres.get(slugify(act["artist"]), [])
        act["source"] = a_src.get("source", "")
        act["provisional"] = a_src.get("provisional", "")
        act["sets"] = []
        n = 0
        for si, st in enumerate(a_src.get("sets", [])):
            songs = []
            for song in st.get("songs", []):
                n += 1
                songs.append({
                    "n": n,
                    "title": song.get("title", "").strip(),
                    "note": tidy_note(song.get("note", "")),
                    "media": [resolve_media(m, sid, cfg, "me") for m in song.get("media", [])],
                })
            act["sets"].append({"name": clean_set_name(st.get("name", ""), si), "songs": songs})
    headliner = next(a for a in acts if a["role"] == "headliner")
    if row.get("setlist_url") and not headliner["source"]:
        headliner["source"] = row["setlist_url"]

    extras = [resolve_media(m, sid, cfg, "me") for m in src.get("extras", [])]
    for link in re.split(r"[\s|]+", row.get("media_links", "")):
        if link:
            extras.append(resolve_media(link, sid, cfg, "me"))

    def all_songs():
        return [so for a in acts for st in a["sets"] for so in st["songs"]]

    def all_media():
        return [*extras, *(m for so in all_songs() for m in so["media"])]

    # Files dropped into media/<id>/ that aren't already referenced by name.
    referenced = {m["file"] for m in all_media() if m.get("file")}
    folder = MEDIA_DIR / sid
    if folder.is_dir():
        for f in sorted(folder.iterdir()):
            if f.name.startswith(".") or f.suffix.lower() not in MEDIA_EXT or f.name in referenced:
                continue
            item = resolve_media({"src": f.name}, sid, cfg, "me")
            song = song_from_filename(f.name, acts)
            if song:
                song["media"].append(item)
            else:
                if "--" in f.stem and all_songs():
                    warnings.append(f"{sid}: '{f.name}' didn't match a song on the setlist, so it went under Other moments")
                extras.append(item)
            if f.suffix.lower() == ".heic":
                warnings.append(f"{sid}: '{f.name}' is HEIC, which only Safari shows. Export it as JPEG.")
            if f.stat().st_size > 95 * 1024 * 1024 and not cfg["media_base_url"]:
                warnings.append(f"{sid}: '{f.name}' is over 95 MB; GitHub rejects files over 100 MB. See README › Big videos.")
    for m in all_media():
        if m.get("file") and not (folder / m["file"]).exists() and not cfg["media_base_url"]:
            warnings.append(f"{sid}: shows/{sid}.json mentions '{m['file']}' but it isn't in media/{sid}/")

    for so in all_songs():
        so["media"].sort(key=lambda m: m["by"] != "me")  # your own footage first

    # The show's genres are its headlining acts' genres, main genre first.
    show_genres = []
    for a in sorted(acts, key=lambda a: a["role"] != "headliner"):
        if a["role"] != "opener":
            show_genres += [g for g in a["genres"] if g not in show_genres]

    songs = all_songs()
    show = {
        "id": sid,
        "artist": row["artist"],
        "date": row["date"],
        "venue": row.get("venue", ""),
        "location": row.get("location", ""),
        "opener": row.get("opener", ""),
        "with": row.get("companions", ""),
        "notes": row.get("notes", ""),
        "genres": show_genres,
        "acts": acts,
        "extras": extras,
    }
    summary = {k: show[k] for k in ("id", "artist", "date", "venue", "location", "opener", "with", "notes", "genres")}
    summary.update(
        acts=[{"artist": a["artist"], "role": a["role"], "songs": sum(len(st["songs"]) for st in a["sets"])} for a in acts],
        songs=len(songs),
        filmed=sum(1 for so in songs if so["media"]),
        mine=sum(1 for so in songs if any(m["by"] == "me" for m in so["media"])),
        clips=sum(len(so["media"]) for so in songs) + len(extras),
        provisional=any(a["provisional"] for a in acts),
    )
    return show, summary


def site_url(cfg):
    """Public address of the site, for link previews. config.json wins; on GitHub Actions
    it's worked out from the repo name, so forks get correct previews with no setup."""
    url = (cfg.get("site_url") or "").strip()
    if not url and os.environ.get("GITHUB_REPOSITORY"):
        owner, repo = os.environ["GITHUB_REPOSITORY"].split("/", 1)
        url = f"https://{owner}.github.io/" if repo.lower() == f"{owner.lower()}.github.io" else f"https://{owner}.github.io/{repo}/"
    return url if not url or url.endswith("/") else url + "/"


def fill_page_meta(cfg, summaries):
    """Fill the {{placeholders}} in the page <head>s (title, description, preview image)."""
    years = sorted(s["date"][:4] for s in summaries)
    who = f"{cfg['owner']}'s" if cfg.get("owner") else "My"
    desc = f"{len(summaries)} shows since {years[0]}. {who} concert log: setlists, photos and clips from every show, song by song." if years else cfg["tagline"]
    values = {"site_title": cfg["site_title"], "description": desc, "site_url": site_url(cfg)}
    for page in OUT.glob("*.html"):
        text = page.read_text(encoding="utf-8")
        for k, v in values.items():
            text = text.replace("{{" + k + "}}", html.escape(v, quote=True))
        page.write_text(text, encoding="utf-8")


def build():
    cfg = read_config()
    rows = read_concerts()
    genres = read_genres()
    warnings = []

    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(SITE_SRC, OUT)
    (OUT / "data" / "shows").mkdir(parents=True)

    summaries = []
    for row in rows:
        show, summary = build_show(row, cfg, genres, warnings)
        summaries.append(summary)
        (OUT / "data" / "shows" / f"{row['id']}.json").write_text(json.dumps(show, ensure_ascii=False), encoding="utf-8")

    site_cfg = {k: cfg[k] for k in ("site_title", "owner", "tagline", "highlight_companion", "repo_url")}
    (OUT / "data" / "concerts.json").write_text(
        json.dumps({"config": site_cfg, "shows": summaries}, ensure_ascii=False), encoding="utf-8"
    )

    fill_page_meta(cfg, summaries)

    if MEDIA_DIR.is_dir() and not cfg["media_base_url"]:
        shutil.copytree(MEDIA_DIR, OUT / "media", ignore=shutil.ignore_patterns(".*", "README*"))
    (OUT / ".nojekyll").write_text("")

    with_setlist = [s for s in summaries if s["songs"]]
    acts = [a for s in summaries for a in s["acts"]]
    print(f"Built {len(summaries)} shows, {len(acts)} acts → {OUT.relative_to(ROOT)}/")
    print(f"  {sum(1 for a in acts if a['songs'])} acts with a setlist, {sum(s['clips'] for s in summaries)} media items")
    for s in summaries:
        if s["clips"] or s["provisional"]:
            flag = "  (provisional setlist)" if s["provisional"] else ""
            print(f"  {s['id']}: {s['filmed']}/{s['songs']} songs have footage{flag}")
    missing = sorted({a["artist"] for a in acts} - {a for a in acts_with_genres(summaries)})
    if genres and missing:
        print(f"  ! No genre in artists.csv for: {', '.join(missing)}")
    for w in warnings:
        print(f"  ! {w}")


def acts_with_genres(summaries):
    genres = read_genres()
    return [a["artist"] for s in summaries for a in s["acts"] if genres.get(slugify(a["artist"]))]


def serve(port):
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(OUT))
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"Previewing at http://localhost:{port}  (Ctrl+C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--serve", action="store_true", help="preview the built site locally")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    build()
    if args.serve:
        serve(args.port)
