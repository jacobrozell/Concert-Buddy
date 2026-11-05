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
from urllib.parse import parse_qs, quote, unquote, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    MEDIA_DIR, ROOT, bill, clean_set_name, judge_heard, save_show, load_show, read_concerts, read_config, read_genres, read_manifest,
    companions_of, is_solo, set_show_field, show_acts, slugify, song_key, split_artists,
)

OUT = ROOT / "_site"
SERVING = False  # set by --serve: media is served straight from media/ instead of being copied
WAITING = {}     # show id -> clips listed in media.json that can't be served yet (not here, no media_base_url)
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
        # In the local preview, play files from your own disk even when they also live in the cloud.
        local = not base or (SERVING and (MEDIA_DIR / sid / src).exists())
        out.update(kind=kind, file=src, url=f"media/{rel}" if local else f"{base}/{rel}")

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

    # Your own files: whatever is in media/<id>/ plus anything listed in media/<id>/media.json
    # (files that now live only in cloud storage are still listed there).
    folder = MEDIA_DIR / sid
    manifest = read_manifest(sid)
    hidden = set(src.get("hidden", []))
    local_files = {f.name: f for f in folder.iterdir()} if folder.is_dir() else {}
    names = sorted({n for n, f in local_files.items() if f.is_file() and not n.startswith(".") and f.suffix.lower() in MEDIA_EXT} | set(manifest))

    # A file can only go on the site if it can be served: it's here to be published with the
    # site, or it's in cloud storage (media_base_url). Listed-but-absent files wait for an upload.
    def servable(name):
        return name in local_files or bool(cfg["media_base_url"])

    waiting = [n for n in names if not servable(n)]
    if waiting:
        WAITING[sid] = len(waiting)
    for st_songs in (so for a in acts for st in a["sets"] for so in st["songs"]):
        st_songs["media"] = [m for m in st_songs["media"] if not m.get("file") or servable(m["file"])]
    extras = [m for m in extras if not m.get("file") or servable(m["file"])]
    referenced = {m["file"] for m in all_media() if m.get("file")}
    for name in names:
        if name in referenced or name in hidden or not servable(name):
            continue
        item = resolve_media({"src": name}, sid, cfg, "me")
        item["auto"] = True  # found in the folder, not placed by hand
        song = song_from_filename(name, acts)
        if song:
            item["by_name"] = True
            song["media"].append(item)
        else:
            if "--" in Path(name).stem and all_songs():
                warnings.append(f"{sid}: '{name}' didn't match a song on the setlist, so it went under Other moments")
            extras.append(item)
        f = local_files.get(name)
        if f and f.suffix.lower() == ".heic":
            warnings.append(f"{sid}: '{name}' is HEIC, which only Safari shows. Export it as JPEG.")
        if f and f.stat().st_size > 95 * 1024 * 1024 and not cfg["media_base_url"]:
            warnings.append(f"{sid}: '{name}' is over 95 MB; GitHub rejects files over 100 MB. See docs/hosting-media.md.")
    for m in all_media():
        if m.get("file") and m["file"] not in local_files and m["file"] not in manifest and not cfg["media_base_url"]:
            warnings.append(f"{sid}: shows/{sid}.json mentions '{m['file']}' but it isn't in media/{sid}/")
    all_media_now = all_media()
    for m in all_media_now:  # when it was filmed, for ordering and display
        info = manifest.get(m.get("file"), {})
        if info.get("taken"):
            m["taken"] = info["taken"]
        if info.get("seconds"):
            m["seconds"] = info["seconds"]
        if info.get("estimated"):
            m["estimated"] = True
    extras = [m for m in extras if m.get("file") not in hidden]
    if SERVING:  # what Shazam heard in each clip (scripts/shazam_tag.py), for the tagging screen
        heard = shazam_heard().get(sid, {})
        for m in all_media_now:
            res = heard.get(m.get("file"))
            if res is None:
                continue
            top = (res.get("heard") or [None])[0]
            if not top:
                m["shazam"] = {"title": ""}
                continue
            verdict, act, song = judge_heard(top["title"], top.get("artist", ""), acts)
            m["shazam"] = {"title": top["title"], "artist": top.get("artist", ""), "votes": top.get("votes", 1),
                           "windows": res.get("windows", 1), "verdict": verdict, "act": act["artist"] if act else "",
                           "key": f"{act['n']}-{song['n']}" if song else ""}
    hidden_items = []
    if SERVING:  # the tagging screen needs to see hidden files too
        for name in sorted(hidden):
            h = resolve_media({"src": name}, sid, cfg, "me")
            h.update({k: v for k, v in manifest.get(name, {}).items() if k in ("taken", "seconds")})
            hidden_items.append(h)
    extras.sort(key=lambda m: m.get("taken") or "~")

    for so in all_songs():
        so["media"].sort(key=lambda m: (m["by"] != "me", m.get("taken") or "~"))  # your own footage first, then filming order

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
    if SERVING:
        show["hidden"] = hidden_items
    summary = {k: show[k] for k in ("id", "artist", "date", "venue", "location", "opener", "with", "notes", "genres")}
    summary.update(
        acts=[{"artist": a["artist"], "role": a["role"], "songs": sum(len(st["songs"]) for st in a["sets"])} for a in acts],
        songs=len(songs),
        filmed=sum(1 for so in songs if so["media"]),
        mine=sum(1 for so in songs if any(m["by"] == "me" for m in so["media"])),
        clips=sum(len(so["media"]) for so in songs) + len(extras),
        untagged=sum(1 for m in extras if m.get("auto")),
        provisional=any(a["provisional"] for a in acts),
    )
    return show, summary


def shazam_heard():
    """media/.shazam.json, written by scripts/shazam_tag.py: {show id: {file: {"heard": [...]}}}."""
    p = MEDIA_DIR / ".shazam.json"
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except ValueError:
        return {}


# ---------- stats + memories ----------

def compute_stats(built):
    """Everything the stats and artist pages show, worked out from all the built shows.
    Also marks each act with how many times you've seen that artist, and each song with
    how many times you've heard it live (and which time this was), for the show page."""
    built = sorted(built, key=lambda b: b[0]["date"])
    artists, venues, cities, people = {}, {}, {}, {}
    solo, unlogged = [], []
    song_refs = []
    weekdays, months = [0] * 7, [0] * 12
    footage = clips = 0
    import datetime as dt

    for show, summary in built:
        d = dt.date.fromisoformat(show["date"])
        weekdays[(d.weekday() + 1) % 7] += 1  # Sunday first, like the JS Date
        months[d.month - 1] += 1
        v = venues.setdefault((show["venue"], show["location"]), {"venue": show["venue"], "location": show["location"], "shows": []})
        v["shows"].append(show["id"])
        cities.setdefault(show["location"], []).append(show["id"])
        for p in companions_of(show["with"]):
            people.setdefault(p, []).append(show["id"])
        if is_solo(show["with"]):
            solo.append(show["id"])
        elif not show["with"].strip():
            unlogged.append(show["id"])
        media = [*show["extras"], *(m for a in show["acts"] for st in a["sets"] for so in st["songs"] for m in so["media"])]
        clips += len(media)
        footage += sum(m.get("seconds") or 0 for m in media if m.get("kind") == "video")
        for a in show["acts"]:
            slug = slugify(a["artist"])
            ar = artists.setdefault(slug, {"slug": slug, "name": a["artist"], "genres": a["genres"], "shows": [], "songs": {}})
            songs = [so for st in a["sets"] for so in st["songs"]]
            ar["shows"].append({"id": show["id"], "date": show["date"], "venue": show["venue"], "location": show["location"],
                                "role": a["role"], "act": a["n"], "headliner": show["artist"], "songs": len(songs),
                                "filmed": sum(1 for so in songs if so["media"]), "provisional": bool(a["provisional"])})
            a["slug"], a["seen"], a["seen_nth"] = slug, None, len(ar["shows"])
            for so in songs:
                k = song_key(so["title"]) or so["title"].lower()
                e = ar["songs"].setdefault(k, {"title": so["title"], "times": []})
                e["times"].append({"id": show["id"], "date": show["date"], "act": a["n"], "song": so["n"],
                                   "filmed": bool(so["media"]), "provisional": bool(a["provisional"])})
                song_refs.append((so, e, len(e["times"])))
    for show, _ in built:
        for a in show["acts"]:
            a["seen"] = len(artists[a["slug"]]["shows"])
    for so, e, nth in song_refs:
        so["live"] = {"count": len(e["times"]), "nth": nth}

    def span(ids, by_id):
        dates = [by_id[i]["date"] for i in ids]
        return {"count": len(ids), "first": min(dates), "last": max(dates), "ids": ids}

    by_id = {s["id"]: s for s, _ in built}
    artist_list = []
    for ar in artists.values():
        songs = sorted(({"title": e["title"], "count": len(e["times"]), "confirmed": sum(not t["provisional"] for t in e["times"]),
                         "times": e["times"]} for e in ar["songs"].values()),
                       key=lambda x: (-x["count"], x["title"].lower()))
        artist_list.append({"slug": ar["slug"], "name": ar["name"], "genres": ar["genres"], "count": len(ar["shows"]),
                            "first": ar["shows"][0]["date"], "last": ar["shows"][-1]["date"],
                            "headlined": sum(1 for s in ar["shows"] if s["role"] != "opener"), "shows": ar["shows"], "songs": songs})
    artist_list.sort(key=lambda a: (-a["count"], -sum(s["songs"] for s in a["shows"]), a["name"].lower()))

    top_songs = sorted(({"artist": a["name"], "slug": a["slug"], **s} for a in artist_list for s in a["songs"] if s["count"] > 1),
                       key=lambda s: s["times"][-1]["date"], reverse=True)       # most recently heard first...
    top_songs.sort(key=lambda s: (-s["count"], -s["confirmed"]))                  # ...within the same count

    # a few facts worth a sentence
    facts = []
    if built:
        first, last = built[0][0], built[-1][0]
        facts.append({"label": "First show", "value": first["artist"], "detail": first["date"], "id": first["id"]})
        years = {}
        for s, _ in built:
            years.setdefault(s["date"][:4], []).append(s["id"])
        y, ids = max(years.items(), key=lambda kv: (len(kv[1]), kv[0]))
        facts.append({"label": "Busiest year", "value": f"{y}", "detail": f"{len(ids)} shows"})
        gaps = [((dt.date.fromisoformat(b[0]["date"]) - dt.date.fromisoformat(a[0]["date"])).days, a[0], b[0]) for a, b in zip(built, built[1:])]
        if gaps:
            g, a, b = max(gaps, key=lambda x: x[0])
            mon = lambda s: dt.date.fromisoformat(s["date"]).strftime("%b %Y")
            facts.append({"label": "Longest wait between shows", "value": f"{g // 365} yr {g % 365 // 30} mo" if g >= 365 else f"{g} days",
                          "detail": f"{a['artist']}, {mon(a)} → {b['artist']}, {mon(b)}", "id": b["id"]})
        def total_songs(s):
            return sum(len(st["songs"]) for a in s["acts"] for st in a["sets"])
        big = max(built, key=lambda b: (total_songs(b[0]), b[0]["date"]))[0]
        if total_songs(big):
            facts.append({"label": "Most songs in one night", "value": str(total_songs(big)), "detail": f"{big['artist']}, {big['date']}", "id": big["id"]})
        bills = max(built, key=lambda b: (len(b[0]["acts"]), b[0]["date"]))[0]
        if len(bills["acts"]) > 2:
            facts.append({"label": "Biggest bill", "value": f"{len(bills['acts'])} acts", "detail": f"{bills['artist']}, {bills['date']}", "id": bills["id"]})
        filmed = max(built, key=lambda b: (b[1]["clips"], b[0]["date"]))
        if filmed[1]["clips"]:
            facts.append({"label": "Most filmed night", "value": f"{filmed[1]['clips']} clips", "detail": f"{filmed[0]['artist']}, {filmed[0]['date']}", "id": filmed[0]["id"]})

    states = {(loc.split(",")[-1].strip()) for loc in cities if loc}
    return {
        "totals": {
            "shows": len(built), "artists": len(artists), "venues": len(venues), "cities": len(cities), "states": len(states),
            "songs": sum(len(e["times"]) for ar in artists.values() for e in ar["songs"].values()),
            "distinct_songs": sum(len(ar["songs"]) for ar in artists.values()),
            "clips": clips, "footage_seconds": round(footage), "filmed_shows": sum(1 for _, s in built if s["clips"]),
            "provisional_shows": sum(1 for _, s in built if s["provisional"]),
            "solo": len(solo), "with_unlogged": len(unlogged),
        },
        "top_songs": top_songs[:40],
        "artists": artist_list,
        "venues": sorted(({"venue": v["venue"], "location": v["location"], **span(v["shows"], by_id)} for v in venues.values()),
                         key=lambda v: (-v["count"], v["first"])),
        "cities": sorted(({"location": c, **span(ids, by_id)} for c, ids in cities.items()), key=lambda c: (-c["count"], c["first"])),
        "companions": sorted(({"name": p, **span(ids, by_id)} for p, ids in people.items()), key=lambda c: (-c["count"], c["first"])),
        "weekdays": weekdays,
        "months": months,
        "facts": facts,
    }


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


def build(quiet=False):
    cfg = read_config()
    rows = read_concerts()
    genres = read_genres()
    warnings = []
    WAITING.clear()

    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(SITE_SRC, OUT)
    (OUT / "data" / "shows").mkdir(parents=True)

    built = [build_show(row, cfg, genres, warnings) for row in rows]
    summaries = [summary for _, summary in built]
    stats = compute_stats(built)  # also adds times-seen / times-heard to each show's acts and songs
    for show, _ in built:
        (OUT / "data" / "shows" / f"{show['id']}.json").write_text(json.dumps(show, ensure_ascii=False), encoding="utf-8")
    (OUT / "data" / "stats.json").write_text(json.dumps(stats, ensure_ascii=False), encoding="utf-8")

    site_cfg = {k: cfg[k] for k in ("site_title", "owner", "tagline", "highlight_companion", "repo_url")}
    (OUT / "data" / "concerts.json").write_text(
        json.dumps({"config": site_cfg, "shows": summaries}, ensure_ascii=False), encoding="utf-8"
    )

    fill_page_meta(cfg, summaries)

    if MEDIA_DIR.is_dir() and not cfg["media_base_url"] and not SERVING:
        shutil.copytree(MEDIA_DIR, OUT / "media", ignore=shutil.ignore_patterns(".*", "README*", "*.json", "originals", "inbox"))
    (OUT / ".nojekyll").write_text("")
    # Downloadable copies: this log, and a blank template to start your own
    shutil.copy(ROOT / "concerts.csv", OUT / "concerts.csv")
    tpl = ROOT / "templates" / "concerts_template.csv"
    if tpl.exists():
        shutil.copy(tpl, OUT / "concerts_template.csv")

    if quiet:
        return
    if WAITING:
        print(f"  {sum(WAITING.values())} clips in media.json files aren't on this machine and there's no media_base_url yet,")
        print("    so they're left off the site until you upload them (python3 scripts/upload_media.py).")
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


class PreviewHandler(http.server.SimpleHTTPRequestHandler):
    """Serves _site/, plus media/ straight from your disk (with the byte-range
    support Safari needs to play video), plus the tagging screen's save endpoint."""

    def translate_path(self, path):
        p = unquote(urlparse(path).path)
        if p.startswith("/media/"):
            target = (MEDIA_DIR / p[len("/media/"):]).resolve()
            if MEDIA_DIR.resolve() in target.parents:
                return str(target)
        return super().translate_path(path)

    def send_head(self):
        rng = self.headers.get("Range")
        path = self.translate_path(self.path)
        if not rng or not os.path.isfile(path):
            return super().send_head()
        size = os.path.getsize(path)
        m = re.match(r"bytes=(\d*)-(\d*)", rng)
        start, end = (int(m.group(1)) if m.group(1) else None, int(m.group(2)) if m.group(2) else None) if m else (None, None)
        if start is None:  # suffix range: last N bytes
            start, end = max(0, size - (end or 0)), size - 1
        end = min(end if end is not None else size - 1, size - 1)
        if start > end:
            self.send_error(416)
            return None
        f = open(path, "rb")
        f.seek(start)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        self._remaining = end - start + 1
        return f

    def copyfile(self, source, outputfile):
        remaining = getattr(self, "_remaining", None)
        if remaining is None:
            return super().copyfile(source, outputfile)
        try:
            while remaining > 0:
                chunk = source.read(min(1 << 20, remaining))
                if not chunk:
                    break
                outputfile.write(chunk)
                remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass  # the browser stopped reading (normal while scrubbing video)
        finally:
            self._remaining = None

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_POST(self):
        path = urlparse(self.path).path
        m = re.fullmatch(r"/api/shows/([\w.-]+)/tags", path)
        if not m and path != "/api/companions":
            return self.send_error(404)
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            if m:
                save_tags(m.group(1), body.get("assign", {}))
            else:  # who you went with: {"with": {show id: "Alex / Sam" | "Solo" | ""}} -> concerts.csv
                updates = body.get("with") or {}
                if not isinstance(updates, dict) or not all(isinstance(v, str) for v in updates.values()):
                    raise ValueError("expected {\"with\": {show id: text}}")
                set_show_field(updates, "companions")
            build(quiet=True)
            payload, code = {"ok": True}, 200
        except (ValueError, KeyError) as e:
            payload, code = {"ok": False, "error": str(e)}, 400
        data = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        if args and str(args[1])[:1] in "45":
            super().log_message(fmt, *args)


def save_tags(sid, assign):
    """Apply the tagging screen's choices to shows/<id>.json.
    assign: {file name: "<act n>-<song n>" | "extra" | "hidden" | ""}  ("" = untag)."""
    rows = {r["id"]: r for r in read_concerts()}
    if sid not in rows:
        raise ValueError(f"no show {sid}")
    row, src = rows[sid], load_show(sid) or {}
    acts_src = {slugify(a.get("artist", "")): a for a in show_acts(src, row)}
    stage = bill(row, src.get("order"))
    names = set(assign)

    def is_one_of(m):
        name = m if isinstance(m, str) else (m.get("src") or m.get("file") or m.get("url") or "")
        return name in names

    for a in acts_src.values():
        for st in a.get("sets", []):
            for so in st.get("songs", []):
                if so.get("media"):
                    so["media"] = [m for m in so["media"] if not is_one_of(m)]
                    if not so["media"]:
                        del so["media"]
    extras = [m for m in src.get("extras", []) if not is_one_of(m)]
    hidden = [h for h in src.get("hidden", []) if h not in names]

    for name, target in assign.items():
        if target == "extra":
            extras.append({"src": name})
        elif target == "hidden":
            hidden.append(name)
        elif target:
            act_n, song_n = (int(x) for x in target.split("-"))
            act = acts_src.get(slugify(stage[act_n - 1]["artist"]))
            songs = [so for st in (act or {}).get("sets", []) for so in st.get("songs", [])]
            if not act or not 1 <= song_n <= len(songs):
                raise ValueError(f"no song {target} in {sid}")
            songs[song_n - 1].setdefault("media", []).append({"src": name})

    out = {k: v for k, v in src.items() if k not in ("sets", "source", "provisional", "acts", "extras", "hidden")}
    out["acts"] = [acts_src[slugify(a["artist"])] for a in stage if slugify(a["artist"]) in acts_src]
    out["acts"] += [a for k, a in acts_src.items() if k not in {slugify(x["artist"]) for x in stage}]
    if extras:
        out["extras"] = extras
    if hidden:
        out["hidden"] = sorted(set(hidden))
    save_show(sid, out)


def serve(port):
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    socketserver.ThreadingTCPServer.daemon_threads = True
    with socketserver.ThreadingTCPServer(("", port), partial(PreviewHandler, directory=str(OUT))) as httpd:
        print(f"Previewing at http://localhost:{port}  (Ctrl+C to stop)")
        print(f"Tag your clips with songs at http://localhost:{port}/tag.html")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--serve", action="store_true", help="preview the built site locally")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    if args.serve:
        SERVING = True
    build()
    if args.serve:
        serve(args.port)
