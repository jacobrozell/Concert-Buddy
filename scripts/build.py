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
from common import MEDIA_DIR, ROOT, clean_set_name, load_show, read_concerts, read_config, slugify  # noqa: E402

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


def song_from_filename(name, songs_by_slug):
    """`IMG_0412--Them-Changes.mov` -> the song whose slug is 'them-changes'.
    Only the part after the first `--` is matched; a trailing -2 / -b counter is ignored."""
    stem = Path(name).stem
    if "--" not in stem:
        return None
    tag = slugify(stem.split("--", 1)[1])
    candidates = [tag, re.sub(r"-(\d+|[a-z])$", "", tag)]
    for c in candidates:
        if c in songs_by_slug:
            return songs_by_slug[c]
    # Longest song slug that the tag starts with ("them-changes-encore" -> "them-changes")
    hits = [s for s in songs_by_slug if tag.startswith(s + "-") or tag == s]
    return songs_by_slug[max(hits, key=len)] if hits else None


def tidy_note(note):
    """setlist.fm marks a segue with a bare '>' (or '> ' in front of other text)."""
    note = (note or "").strip()
    if note == ">":
        return "segues into the next song"
    if note.startswith("> "):
        return "segues into the next song; " + note[2:]
    return note


# ---------- per-show build ----------

def build_show(row, cfg, warnings):
    sid = row["id"]
    src = load_show(sid) or {}
    sets_out, songs_by_slug, n = [], {}, 0

    for si, s in enumerate(src.get("sets", [])):
        songs = []
        for song in s.get("songs", []):
            n += 1
            entry = {
                "n": n,
                "title": song.get("title", "").strip(),
                "note": tidy_note(song.get("note", "")),
                "media": [resolve_media(m, sid, cfg, "me") for m in song.get("media", [])],
            }
            songs.append(entry)
            songs_by_slug.setdefault(slugify(entry["title"]), entry)
        sets_out.append({"name": clean_set_name(s.get("name", ""), si), "songs": songs})

    extras = [resolve_media(m, sid, cfg, "me") for m in src.get("extras", [])]
    for link in re.split(r"[\s|]+", row.get("media_links", "")):
        if link:
            extras.append(resolve_media(link, sid, cfg, "me"))

    # Files dropped into media/<id>/ that aren't already referenced by name.
    def all_media():
        return [*extras, *(m for st in sets_out for so in st["songs"] for m in so["media"])]

    referenced = {m["file"] for m in all_media() if m.get("file")}
    folder = MEDIA_DIR / sid
    if folder.is_dir():
        for f in sorted(folder.iterdir()):
            if f.name.startswith(".") or f.suffix.lower() not in MEDIA_EXT or f.name in referenced:
                continue
            item = resolve_media({"src": f.name}, sid, cfg, "me")
            song = song_from_filename(f.name, songs_by_slug)
            if song:
                song["media"].append(item)
            else:
                if "--" in f.stem and songs_by_slug:
                    warnings.append(f"{sid}: '{f.name}' didn't match a song on the setlist, so it went under Other moments")
                extras.append(item)
            if f.suffix.lower() == ".heic":
                warnings.append(f"{sid}: '{f.name}' is HEIC, which only Safari shows. Export it as JPEG.")
            if f.stat().st_size > 95 * 1024 * 1024 and not cfg["media_base_url"]:
                warnings.append(f"{sid}: '{f.name}' is over 95 MB; GitHub rejects files over 100 MB. See README › Big videos.")
    for m in all_media():
        if m.get("file") and not (folder / m["file"]).exists() and not cfg["media_base_url"]:
            warnings.append(f"{sid}: shows/{sid}.json mentions '{m['file']}' but it isn't in media/{sid}/")

    for st in sets_out:
        for so in st["songs"]:
            so["media"].sort(key=lambda m: m["by"] != "me")  # your own footage first

    all_songs = [so for st in sets_out for so in st["songs"]]
    show = {
        "id": sid,
        "artist": row["artist"],
        "date": row["date"],
        "venue": row.get("venue", ""),
        "location": row.get("location", ""),
        "opener": row.get("opener", ""),
        "with": row.get("companions", ""),
        "notes": row.get("notes", ""),
        "setlist_url": row.get("setlist_url", "") or src.get("source", ""),
        "provisional": src.get("provisional", ""),
        "sets": sets_out,
        "extras": extras,
    }
    summary = {
        k: show[k] for k in ("id", "artist", "date", "venue", "location", "opener", "with", "notes", "setlist_url")
    }
    summary.update(
        songs=len(all_songs),
        filmed=sum(1 for s in all_songs if s["media"]),
        mine=sum(1 for s in all_songs if any(m["by"] == "me" for m in s["media"])),
        clips=sum(len(s["media"]) for s in all_songs) + len(extras),
        provisional=bool(show["provisional"]),
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
    warnings = []

    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(SITE_SRC, OUT)
    (OUT / "data" / "shows").mkdir(parents=True)

    summaries = []
    for row in rows:
        show, summary = build_show(row, cfg, warnings)
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
    print(f"Built {len(summaries)} shows → {OUT.relative_to(ROOT)}/")
    print(f"  {len(with_setlist)} with a setlist, {sum(s['clips'] for s in summaries)} media items")
    for s in with_setlist:
        flag = "  (provisional setlist)" if s["provisional"] else ""
        print(f"  {s['id']}: {s['filmed']}/{s['songs']} songs have footage{flag}")
    for w in warnings:
        print(f"  ! {w}")


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
