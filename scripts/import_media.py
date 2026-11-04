#!/usr/bin/env python3
"""Sort photos and videos into the right show folders, using the capture time
(and location) your phone or camera saved inside each file.

New files you've copied in (they're MOVED into place):
    1. Drop them into media/inbox/ (or straight into media/)
    2. python3 scripts/import_media.py                  # dry run: where everything would go
    3. python3 scripts/import_media.py --apply          # move them
       python3 scripts/import_media.py --apply --convert   # …and shrink videos to 1080p MP4 on the way

A folder or external drive (files are READ IN PLACE and COPIED; the originals stay put):
    python3 scripts/import_media.py --from /Volumes/MyDrive/Videos               # report only
    python3 scripts/import_media.py --from /Volumes/MyDrive/Videos --apply --convert
    The report also lists every night with clips but no show in your log: those are
    probably shows to add to concerts.csv.

Clips that are short (under 10 seconds) or whose show is a guess go to
media/_review/<show-id>/ instead of the show folder, so you can look at them:
    python3 scripts/import_media.py --restore IMG_1234.MOV   # keep one: back into its show
    python3 scripts/import_media.py --review                 # send short/unsure clips already in
                                                             # show folders to review

Other jobs:
    python3 scripts/import_media.py --convert           # shrink videos already in show folders
                                                        # (originals kept in originals/, never committed)
    python3 scripts/import_media.py --index             # refresh media.json for files you put
                                                        # straight into show folders

How a file is matched to a show:
  - The capture time inside the file decides (videos: ffprobe; JPEG photos: EXIF).
    Anything filmed before 5 AM counts toward the previous night.
  - A time saved without a timezone is tried against every timezone; it's matched
    only if exactly one show date fits.
  - No capture time: a date in the file name, then camera-roll neighbours
    (IMG_5343 between two clips of the same show), then the file's own date.
    These are guesses, so those clips go to review.
  - A clip whose GPS is far from that show's other clips goes to review.
  - A clip you already have (same show, same capture time, same length) is skipped.
Nothing is ever deleted. Needs ffmpeg (brew install ffmpeg). On a Mac, conversion
uses Apple's hardware video encoder automatically, which is several times faster.
"""
import argparse
import concurrent.futures as cf
import datetime as dt
import json
import math
import os
import re
import shutil
import statistics
import struct
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import MANIFEST, MEDIA_DIR, load_show, read_concerts, read_manifest, save_show, write_manifest  # noqa: E402

INBOX = MEDIA_DIR / "inbox"
REVIEW = MEDIA_DIR / "_review"
VIDEO_EXT = {".mp4", ".m4v", ".mov", ".webm", ".avi", ".mts", ".m2ts", ".3gp", ".mpg", ".mpeg", ".mkv", ".wmv"}
PHOTO_EXT = {".jpg", ".jpeg", ".png", ".heic", ".webp"}
NIGHT_ROLLOVER_HOURS = 5
GUESSES = {"date in file name", "between neighbouring files from that show", "file date"}


# ---------- reading capture info ----------

def parse_time(text):
    """ISO-ish timestamp -> (datetime, has_timezone)."""
    text = (text or "").strip().replace("Z", "+00:00")
    text = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", text)  # -0600 -> -06:00
    text = re.sub(r"\.\d+", "", text)
    try:
        t = dt.datetime.fromisoformat(text)
    except ValueError:
        return None, False
    return t, t.tzinfo is not None


def parse_iso6709(text):
    m = re.match(r"([+-]\d+(?:\.\d+)?)([+-]\d+(?:\.\d+)?)", text or "")
    return (float(m.group(1)), float(m.group(2))) if m else None


def probe_video(path):
    try:
        out = subprocess.run(["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(path)],
                             capture_output=True, text=True, timeout=120).stdout
    except FileNotFoundError:
        raise SystemExit("ffprobe not found. Install ffmpeg first (brew install ffmpeg).")
    except subprocess.TimeoutExpired:
        return None, False, None, 0.0
    fmt = json.loads(out or "{}").get("format", {})
    tags = {k.lower(): v for k, v in (fmt.get("tags") or {}).items()}
    # Apple's own tag keeps the local timezone; creation_time is usually UTC.
    t, has_tz = parse_time(tags.get("com.apple.quicktime.creationdate"))
    if not t:
        t, has_tz = parse_time(tags.get("creation_time") or tags.get("date"))
        if t and t.utcoffset() == dt.timedelta(0):
            has_tz = False  # UTC tells us the moment, not the local date; treat as unknown zone
    gps = parse_iso6709(tags.get("com.apple.quicktime.location.iso6709") or tags.get("location"))
    return t, has_tz, gps, float(fmt.get("duration") or 0)


def read_exif(path):
    """Minimal EXIF reader for JPEG: DateTimeOriginal (+ OffsetTimeOriginal) and GPS."""
    with open(path, "rb") as f:
        data = f.read(256 * 1024)
    i = data.find(b"Exif\x00\x00")
    if data[:2] != b"\xff\xd8" or i < 0:
        return None, False, None
    tiff = data[i + 6:]
    end = "<" if tiff[:2] == b"II" else ">"

    def u16(o): return struct.unpack(end + "H", tiff[o:o + 2])[0]
    def u32(o): return struct.unpack(end + "I", tiff[o:o + 4])[0]

    def ifd(off):
        out = {}
        try:
            for k in range(u16(off)):
                e = off + 2 + 12 * k
                tag, typ, cnt = u16(e), u16(e + 2), u32(e + 4)
                size = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1, 9: 4, 10: 8}.get(typ, 1) * cnt
                val_off = e + 8 if size <= 4 else u32(e + 8)
                raw = tiff[val_off:val_off + size]
                if typ == 2:
                    out[tag] = raw.rstrip(b"\x00").decode(errors="ignore")
                elif typ == 3:
                    out[tag] = u16(val_off)
                elif typ == 4:
                    out[tag] = u32(val_off)
                elif typ == 5:
                    out[tag] = [u32(val_off + 8 * j) / max(1, u32(val_off + 8 * j + 4)) for j in range(cnt)]
        except (struct.error, IndexError):
            pass
        return out

    try:
        root = ifd(u32(4))
    except struct.error:
        return None, False, None
    exif = ifd(root[0x8769]) if 0x8769 in root else {}
    gpsd = ifd(root[0x8825]) if 0x8825 in root else {}
    stamp = exif.get(0x9003) or root.get(0x0132)  # DateTimeOriginal, else DateTime
    t, has_tz = None, False
    if stamp:
        iso = stamp.replace(":", "-", 2).replace(" ", "T") + (exif.get(0x9011) or "")
        t, has_tz = parse_time(iso)
    gps = None
    if 2 in gpsd and 4 in gpsd:
        lat = sum(v / 60 ** k for k, v in enumerate(gpsd[2])) * (-1 if gpsd.get(1) == "S" else 1)
        lon = sum(v / 60 ** k for k, v in enumerate(gpsd[4])) * (-1 if gpsd.get(3) == "W" else 1)
        gps = (lat, lon)
    return t, has_tz, gps


def date_from_name(name):
    m = re.search(r"((?:19|20)\d{2})[-_]?([01]\d)[-_]?([0-3]\d)", name)
    if m:
        try:
            return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


# ---------- matching ----------

def night_of(local_time):
    return (local_time - dt.timedelta(hours=NIGHT_ROLLOVER_HOURS)).date()


def km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def candidates(sources):
    """(path, mode) for every photo/video: 'move' for the inbox, 'copy' for --from folders."""
    found = []
    if sources:
        for src in sources:
            root = Path(src).expanduser()
            if not root.exists():
                raise SystemExit(f"{root} doesn't exist (is the drive plugged in?)")
            for dirpath, dirnames, filenames in os.walk(root):
                # skip hidden folders, Photos/Lightroom libraries, and system folders
                dirnames[:] = [d for d in dirnames if not d.startswith(".") and not d.endswith((".photoslibrary", ".lrlibrary", ".fcpbundle"))
                               and d not in ("$RECYCLE.BIN", "System Volume Information")]
                for name in filenames:
                    p = Path(dirpath) / name
                    if not name.startswith((".", "._")) and p.suffix.lower() in VIDEO_EXT | PHOTO_EXT:
                        found.append((p, "copy"))
    else:
        files = [p for p in INBOX.rglob("*") if p.is_file()] if INBOX.is_dir() else []
        files += [p for p in MEDIA_DIR.iterdir() if p.is_file()]
        found = [(p, "move") for p in files if p.suffix.lower() in VIDEO_EXT | PHOTO_EXT and not p.name.startswith(".")]
    return sorted(found)


def read_meta(path):
    ext = path.suffix.lower()
    if ext in VIDEO_EXT:
        return probe_video(path)
    if ext in (".jpg", ".jpeg"):
        return (*read_exif(path), 0.0)
    return None, False, None, 0.0


def existing_keys():
    """(show id, capture time to the minute, length to the second) for every clip you already have,
    including ones in review: used to skip duplicates."""
    keys = set()
    folders = [p for p in MEDIA_DIR.iterdir() if p.is_dir() and not p.name.startswith((".", "_")) and p.name != "inbox"]
    folders += [p for p in REVIEW.iterdir() if p.is_dir()] if REVIEW.is_dir() else []
    for folder in folders:
        manifest = folder / MANIFEST
        if manifest.exists():
            for e in json.loads(manifest.read_text(encoding="utf-8")).values():
                if e.get("taken") and not e.get("estimated"):
                    keys.add(dup_key(folder.name, e["taken"], e.get("seconds")))
    return keys


def dup_key(sid, taken, seconds):
    t, _ = parse_time(taken) if isinstance(taken, str) else (taken, True)
    stamp = t.strftime("%Y-%m-%dT%H:%M") if t else str(taken)[:16]
    return (sid, stamp, round(seconds or 0))


def plan(sources, min_seconds, progress=True):
    shows_by_date = {}
    for r in read_concerts():
        shows_by_date.setdefault(dt.date.fromisoformat(r["date"]), []).append(r)
    files = candidates(sources)
    items = []
    for k, (p, mode) in enumerate(files, 1):
        if progress and len(files) > 40 and k % 25 == 0:
            print(f"  reading {k}/{len(files)}…", file=sys.stderr, flush=True)
        t, has_tz, gps, dur = read_meta(p)
        is_video = p.suffix.lower() in VIDEO_EXT
        item = {"path": p, "mode": mode, "video": is_video, "time": t, "gps": gps, "duration": dur,
                "show": None, "how": "", "warn": "", "dest": None}
        if t and has_tz:
            d = night_of(t)
            if d in shows_by_date:
                item["show"], item["how"] = shows_by_date[d][0], "capture time"
            else:
                item["night"] = d
                item["warn"] = f"no show in your log on {d:%a %b %-d, %Y}"
        elif t:  # no timezone: try them all
            base = t.replace(tzinfo=None)
            dates = {night_of(base + dt.timedelta(hours=h)) for h in range(-12, 15)}
            hits = sorted({d for d in dates if d in shows_by_date})
            if len(hits) == 1:
                item["show"], item["how"] = shows_by_date[hits[0]][0], "capture time (timezone guessed)"
                item["utc"] = base  # the stored time is UTC; the local zone is settled below
            else:
                item["night"] = night_of(base - dt.timedelta(hours=6))
                item["warn"] = "capture time has no timezone and fits " + ("no show" if not hits else f"{len(hits)} shows")
        elif date_from_name(p.name) in shows_by_date:
            item["show"], item["how"] = shows_by_date[date_from_name(p.name)][0], "date in file name"
        items.append(item)

    # Times saved in UTC: borrow the zone from the same show's other clips, else assume
    # the zone that puts the clip closest to 9 PM local.
    for it in items:
        if "utc" not in it:
            continue
        zones = [x["time"].utcoffset() for x in items if x["show"] and x["show"]["id"] == it["show"]["id"] and "utc" not in x and x["time"] and x["time"].utcoffset() is not None]
        zones += [t.utcoffset() for t, has_tz in (parse_time(e.get("taken")) for e in read_manifest(it["show"]["id"]).values()) if has_tz]
        if zones:
            off = statistics.mode(zones)
        else:
            want = dt.date.fromisoformat(it["show"]["date"])
            fits = [dt.timedelta(hours=h) for h in range(-12, 15) if night_of(it["utc"] + dt.timedelta(hours=h)) == want]
            off = min(fits, key=lambda o: abs(((it["utc"] + o).hour - 21) % 24))
        it["time"] = (it["utc"] + off).replace(tzinfo=dt.timezone(off))

    # Camera-roll neighbours: IMG_5343 between IMG_5342 and IMG_5344 of the same show.
    numbered = {}
    for it in items:
        m = re.fullmatch(r"(IMG|DSC|PXL|MVI)_?(\d{3,})", it["path"].stem, re.I)
        if m:
            numbered[(m.group(1).upper(), int(m.group(2)))] = it
    for (prefix, n), it in numbered.items():
        if it["show"] or it["time"]:
            continue
        before = next((numbered[(prefix, k)] for k in range(n - 1, n - 6, -1) if (prefix, k) in numbered and numbered[(prefix, k)]["show"]), None)
        after = next((numbered[(prefix, k)] for k in range(n + 1, n + 6) if (prefix, k) in numbered and numbered[(prefix, k)]["show"]), None)
        if before and after and before["show"]["id"] == after["show"]["id"]:
            it["show"], it["how"] = before["show"], "between neighbouring files from that show"
            it["time"], it["estimated"] = before["time"], True

    # Last resort: the file's own date (often the day it was copied, so only ever a guess).
    for it in items:
        if it["show"] or it["time"]:
            continue
        local = dt.datetime.fromtimestamp(it["path"].stat().st_mtime)
        d = night_of(local)
        if d in shows_by_date:
            it["show"], it["how"] = shows_by_date[d][0], "file date"
        else:
            it["warn"] = "no capture time in the file"

    # GPS sanity check per show.
    by_show = {}
    for it in items:
        if it["show"]:
            by_show.setdefault(it["show"]["id"], []).append(it)
    for group in by_show.values():
        pts = [it["gps"] for it in group if it["gps"]]
        if len(pts) >= 3:
            centre = (statistics.median(p[0] for p in pts), statistics.median(p[1] for p in pts))
            for it in group:
                if it["gps"] and km(it["gps"], centre) > 5:
                    it["warn"] = f"{km(it['gps'], centre):.0f} km from the show's other clips"

    # Duplicates of clips you already have (or of each other in this batch).
    have = existing_keys()
    for it in items:
        if not it["show"]:
            continue
        if not it["time"] or it.get("estimated"):
            # no capture time to compare: same name and size already in its show or review folder
            sid, size = it["show"]["id"], it["path"].stat().st_size
            if any((f / sid / it["path"].name).is_file() and (f / sid / it["path"].name).stat().st_size == size for f in (MEDIA_DIR, REVIEW)):
                it["dest"] = "duplicate"
            continue
        key = dup_key(it["show"]["id"], it["time"], it["duration"])
        if key in have:
            it["dest"] = "duplicate"
        have.add(key)

    # Where each one goes.
    for it in items:
        if not it["show"] or it["dest"] == "duplicate":
            continue
        if it["how"] in GUESSES or it["warn"]:
            it["dest"], it["why"] = "review", it["warn"] or f"show guessed from {it['how']}"
        elif it["video"] and it["duration"] < min_seconds:
            it["dest"], it["why"] = "review", f"only {it['duration']:.1f}s long"
        else:
            it["dest"] = "show"
    return items


def describe(items, sources):
    by_show, unmatched = {}, []
    for it in items:
        (by_show.setdefault(it["show"]["id"], []) if it["show"] else unmatched).append(it)
    for sid in sorted(by_show):
        group = sorted(by_show[sid], key=lambda it: (it["time"] is None, it["time"].replace(tzinfo=None) if it["time"] else 0))
        n_show = sum(it["dest"] == "show" for it in group)
        n_rev = sum(it["dest"] == "review" for it in group)
        n_dup = sum(it["dest"] == "duplicate" for it in group)
        print(f"\n{sid}  ({n_show} to the show" + (f", {n_rev} to review" if n_rev else "") + (f", {n_dup} already there" if n_dup else "") + ")")
        for it in group:
            if it["dest"] == "duplicate" and len(group) > 12:
                continue
            when = ("≈" if it.get("estimated") else "") + (it["time"].strftime("%-I:%M %p") if it["time"] else "?")
            extra = f"{it['duration']:.0f}s" if it["duration"] else ""
            tag = {"review": f"→ review: {it.get('why', '')}", "duplicate": "(already have it)"}.get(it["dest"], "")
            note = f"  [{it['how']}]" if it["how"] not in ("capture time", "") and it["dest"] != "review" else ""
            print(f"  {when:>9}  {it['path'].name[:44]:44} {extra:>5}  {tag}{note}")

    nights = {}
    for it in unmatched:
        if it.get("night"):
            nights.setdefault(it["night"], []).append(it)
    if nights:
        print(f"\nNights with clips but no show in your log ({len(nights)}). Probably shows to add to concerts.csv:")
        for d in sorted(nights):
            group = nights[d]
            times = sorted(it["time"] for it in group if it["time"])
            pts = [it["gps"] for it in group if it["gps"]]
            where = ""
            if pts:
                lat, lon = statistics.median(p[0] for p in pts), statistics.median(p[1] for p in pts)
                where = f"  near {lat:.4f},{lon:.4f}  https://maps.google.com/?q={lat:.5f},{lon:.5f}"
            span = f"{times[0]:%-I:%M %p}–{times[-1]:%-I:%M %p}" if times else ""
            print(f"  {d:%a %b %-d, %Y}  {len(group):3} clip{'s' if len(group) > 1 else ' '}  {span:19}{where}")
    no_time = [it for it in unmatched if not it.get("night")]
    if no_time:
        print(f"\nNo usable date ({len(no_time)}): left alone")
        for it in no_time[:15]:
            print(f"  {it['path'].name}  ({it['warn'] or 'no capture time'})")
        if len(no_time) > 15:
            print(f"  … and {len(no_time) - 15} more")


# ---------- converting ----------

def encoder_choice(pref="auto"):
    """'apple' (hardware, macOS) when available, else 'x264'."""
    if pref in ("apple", "x264"):
        return pref
    try:
        encoders = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    except FileNotFoundError:
        raise SystemExit("ffmpeg not found. Install it first (brew install ffmpeg).")
    return "apple" if "h264_videotoolbox" in encoders else "x264"


def encode(src, out, height, encoder):
    # Short side becomes `height` (never upscaled); sizes kept even, which H.264 needs.
    scale = f"scale='if(gt(iw,ih),-2,trunc(min({height},iw)/2)*2)':'if(gt(iw,ih),trunc(min({height},ih)/2)*2,-2)'"
    video = (["-c:v", "h264_videotoolbox", "-b:v", "3500k" if height >= 1080 else "1800k", "-maxrate", "6M", "-bufsize", "8M"]
             if encoder == "apple" else ["-c:v", "libx264", "-crf", "26", "-preset", "veryfast"])
    cmd = ["ffmpeg", "-loglevel", "error", "-y", "-i", str(src), "-vf", scale, *video, "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", "-map_metadata", "-1", str(out)]
    ok = subprocess.run(cmd).returncode == 0 and out.exists() and out.stat().st_size > 0
    if not ok and out.exists():
        out.unlink()
    return ok


def unique(path):
    n, p = 2, path
    while p.exists():
        p = path.with_name(f"{path.stem}-{n}{path.suffix}")
        n += 1
    return p


# ---------- doing it ----------

def entry(path, it=None):
    e = {}
    if it and it.get("time"):
        e["taken"] = it["time"].isoformat()
    if it and it.get("estimated"):
        e["estimated"] = True
    if it and it.get("duration"):
        e["seconds"] = round(it["duration"], 1)
    e["bytes"] = path.stat().st_size
    if it and it.get("why"):
        e["review"] = it["why"]
    return e


def apply(items, convert_height, encoder, jobs):
    todo = [it for it in items if it["dest"] in ("show", "review")]
    if not todo:
        print("\nNothing to move.")
        return

    def run(it):
        sid = it["show"]["id"]
        folder = (MEDIA_DIR / sid) if it["dest"] == "show" else (REVIEW / sid)
        folder.mkdir(parents=True, exist_ok=True)
        src = it["path"]
        if convert_height and it["video"] and it["dest"] == "show":
            out = unique(folder / (src.stem + ".mp4"))
            if encode(src, out, convert_height, encoder):
                if it["mode"] == "move":  # keep the original out of the way (never committed)
                    (folder / "originals").mkdir(exist_ok=True)
                    shutil.move(str(src), unique(folder / "originals" / src.name))
                return sid, folder, out, it, "converted"
            # conversion failed: fall through and bring the original in as-is
        dest = unique(folder / src.name)
        (shutil.move if it["mode"] == "move" else shutil.copy2)(str(src), dest)
        return sid, folder, dest, it, "moved" if it["mode"] == "move" else "copied"

    done = []
    with cf.ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        futures = [pool.submit(run, it) for it in todo]
        for k, fut in enumerate(cf.as_completed(futures), 1):
            sid, folder, dest, it, how = fut.result()
            done.append((folder, dest, it))
            print(f"  [{k}/{len(todo)}] {how} → {folder.relative_to(MEDIA_DIR)}/{dest.name}  {dest.stat().st_size / 1048576:.0f} MB", flush=True)

    by_folder = {}
    for folder, dest, it in done:
        by_folder.setdefault(folder, []).append((dest, it))
    for folder, files in by_folder.items():
        manifest = folder / MANIFEST
        entries = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {}
        for dest, it in files:
            entries[dest.name] = entry(dest, it)
        if folder.parent == MEDIA_DIR:
            write_manifest(folder.name, entries)
        else:
            manifest.write_text(json.dumps(dict(sorted(entries.items(), key=lambda kv: (kv[1].get("taken") or "~", kv[0]))), indent=1) + "\n", encoding="utf-8")
    if any(it["dest"] == "review" for _, _, it in done):
        write_review_readme()
    n_show = sum(it["dest"] == "show" for _, _, it in done)
    n_rev = len(done) - n_show
    print(f"\nDone: {n_show} into show folders, {n_rev} into media/_review/." + (" Originals left where they were." if any(it["mode"] == "copy" for _, _, it in done) else ""))


def write_review_readme():
    REVIEW.mkdir(exist_ok=True)
    lines = ["Clips set aside for you to look at: under 10 seconds, or the show they belong to is a guess.",
             "Each folder is named after the show it would go to; media.json in it says why.", "",
             "Keep one:  python3 scripts/import_media.py --restore IMG_1234.MOV   (moves it into its show)",
             "Keep all of a show's:  python3 scripts/import_media.py --restore 2026-11-03-thundercat",
             "Don't want it: delete it. Nothing in this folder is put on the site or committed.", ""]
    for folder in sorted(p for p in REVIEW.iterdir() if p.is_dir()):
        m = folder / MANIFEST
        entries = json.loads(m.read_text(encoding="utf-8")) if m.exists() else {}
        for name in sorted(p.name for p in folder.iterdir() if p.is_file() and p.name != MANIFEST):
            lines.append(f"{folder.name}/{name}  ({entries.get(name, {}).get('review', '')})")
    (REVIEW / "README.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def review_existing(min_seconds, apply_changes):
    """Move short or guessed clips that are already in show folders into media/_review/."""
    shows = {r["id"] for r in read_concerts()}
    moves = []
    for folder in sorted(p for p in MEDIA_DIR.iterdir() if p.is_dir() and p.name in shows):
        entries = read_manifest(folder.name)
        tagged = json.dumps(load_show(folder.name) or {})
        for name, e in entries.items():
            f = folder / name
            if not f.is_file() or f.suffix.lower() not in VIDEO_EXT:
                continue
            why = (f"only {e['seconds']:.1f}s long" if e.get("seconds") is not None and e["seconds"] < min_seconds
                   else "no capture time, so the show is a guess" if not e.get("taken") or e.get("estimated") else "")
            if why and json.dumps(name) not in tagged:  # leave clips you've already tagged alone
                moves.append((folder.name, name, why))
    for sid, name, why in moves:
        print(f"  {sid}/{name}  ({why})")
    print(f"\n{len(moves)} clip(s) {'moved' if apply_changes else 'would move'} to media/_review/.")
    if not apply_changes:
        if moves:
            print("Dry run. Run again with --apply to move them.")
        return
    for sid, name, why in moves:
        (REVIEW / sid).mkdir(parents=True, exist_ok=True)
        shutil.move(str(MEDIA_DIR / sid / name), REVIEW / sid / name)
        entries = read_manifest(sid)
        e = entries.pop(name, {})
        write_manifest(sid, entries)
        rm = REVIEW / sid / MANIFEST
        rev = json.loads(rm.read_text(encoding="utf-8")) if rm.exists() else {}
        rev[name] = {**e, "review": why}
        rm.write_text(json.dumps(rev, indent=1) + "\n", encoding="utf-8")
    write_review_readme()


def restore(names):
    """Move clips (or a whole show's worth) from media/_review/ back into their show folders."""
    if not REVIEW.is_dir():
        raise SystemExit("Nothing in media/_review/.")
    moved = 0
    for target in names:
        folders = [REVIEW / target] if (REVIEW / target).is_dir() else [p for p in REVIEW.iterdir() if p.is_dir()]
        for folder in folders:
            rm = folder / MANIFEST
            rev = json.loads(rm.read_text(encoding="utf-8")) if rm.exists() else {}
            for f in sorted(folder.iterdir()):
                if f.name == MANIFEST or not f.is_file() or (folder.name != target and f.name != target):
                    continue
                dest = unique(MEDIA_DIR / folder.name / f.name)
                dest.parent.mkdir(exist_ok=True)
                shutil.move(str(f), dest)
                e = {k: v for k, v in rev.pop(f.name, {}).items() if k != "review"}
                entries = read_manifest(folder.name)
                entries[dest.name] = e or {"bytes": dest.stat().st_size}
                write_manifest(folder.name, entries)
                print(f"  {folder.name}/{dest.name}")
                moved += 1
            if rev:
                rm.write_text(json.dumps(rev, indent=1) + "\n", encoding="utf-8")
            elif rm.exists():
                rm.unlink()
    write_review_readme()
    print(f"Restored {moved} clip(s)." if moved else f"Didn't find {', '.join(names)} in media/_review/.")


def rename_references(sid, old, new):
    """Point shows/<id>.json at the converted file's new name."""
    show = load_show(sid)
    if not show or old == new:
        return
    text = json.dumps(show)
    if json.dumps(old) in text:
        save_show(sid, json.loads(text.replace(json.dumps(old), json.dumps(new))))


def convert_existing(height, encoder, jobs):
    """Re-encode videos already in show folders; originals go to originals/ (git-ignored)."""
    shows = {r["id"] for r in read_concerts()}
    todo = sorted(p for p in MEDIA_DIR.glob("*/*") if p.parent.name in shows and p.suffix.lower() in VIDEO_EXT
                  and not (p.suffix.lower() == ".mp4" and p.stat().st_size < 30 * 1024 * 1024))
    if not todo:
        print("Nothing to convert.")
        return
    print(f"Converting {len(todo)} video(s) to {height}p with the {'Apple hardware' if encoder == 'apple' else 'x264'} encoder…")

    def run(p):
        out = p.with_suffix(".mp4") if p.suffix.lower() != ".mp4" else p.with_name(p.stem + "-small.mp4")
        if not encode(p, out, height, encoder):
            return p, None, 0
        size = p.stat().st_size
        (p.parent / "originals").mkdir(exist_ok=True)
        shutil.move(str(p), unique(p.parent / "originals" / p.name))
        if out.name.endswith("-small.mp4"):
            out = out.rename(p)
        return p, out, size

    before = after = 0
    with cf.ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
        for k, (p, out, size) in enumerate(pool.map(run, todo), 1):
            if not out:
                print(f"  [{k}/{len(todo)}] {p.parent.name}/{p.name}: failed, left as is")
                continue
            before += size
            after += out.stat().st_size
            entries = read_manifest(p.parent.name)
            old = entries.pop(p.name, {})
            entries[out.name] = {**old, "bytes": out.stat().st_size}
            write_manifest(p.parent.name, entries)
            rename_references(p.parent.name, p.name, out.name)
            print(f"  [{k}/{len(todo)}] {p.parent.name}/{out.name}  {size / 1048576:.0f} → {out.stat().st_size / 1048576:.0f} MB", flush=True)
    print(f"\n{before / 1048576:.0f} MB → {after / 1048576:.0f} MB. Originals are in each show's originals/ folder (not committed).")


def index():
    """Rebuild media.json for every show folder from the files that are there.
    Entries for files that are gone (e.g. moved to cloud storage) are kept."""
    shows = {r["id"] for r in read_concerts()}
    for folder in sorted(p for p in MEDIA_DIR.iterdir() if p.is_dir() and p.name in shows):
        entries = read_manifest(folder.name)
        added = 0
        for f in sorted(folder.iterdir()):
            ext = f.suffix.lower()
            if not f.is_file() or f.name.startswith(".") or ext not in VIDEO_EXT | PHOTO_EXT:
                continue
            old = entries.get(f.name, {})
            if old.get("bytes") == f.stat().st_size and (old.get("taken") or ext not in VIDEO_EXT | {".jpg", ".jpeg"}):
                continue
            t, has_tz, gps, dur = read_meta(f)
            it = {"time": t if (t is None or has_tz) else t.replace(tzinfo=None), "duration": dur}  # UTC-only times stay zone-less until fixed below
            entries[f.name] = {**old, **entry(f, it)}
            added += 1
        # Times without a zone are UTC (see probe_video): use the zone of this show's other files.
        zones = [parse_time(e["taken"])[0].utcoffset() for e in entries.values() if parse_time(e.get("taken"))[1]]
        if zones:
            off = statistics.mode(zones)
            for e in entries.values():
                t, has_tz = parse_time(e.get("taken"))
                if t and not has_tz:
                    e["taken"] = (t + off).replace(tzinfo=dt.timezone(off)).isoformat()
        # No capture time at all (some photos): borrow the time of the camera-roll file just before it.
        numbered = {}
        for name, e in entries.items():
            m = re.fullmatch(r"(IMG|DSC|PXL|MVI)_?(\d{3,})", Path(name).stem, re.I)
            if m:
                numbered[(m.group(1).upper(), int(m.group(2)))] = e
        for (prefix, n), e in numbered.items():
            if not e.get("taken") or e.get("estimated"):
                prev = next((numbered[(prefix, k)] for k in range(n - 1, n - 20, -1) if numbered.get((prefix, k), {}).get("taken") and not numbered[(prefix, k)].get("estimated")), None)
                if prev:
                    e["taken"], e["estimated"] = prev["taken"], True
        write_manifest(folder.name, entries)
        print(f"  {folder.name}: {len(entries)} files ({added} updated)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="sources", nargs="+", metavar="FOLDER", help="read a folder or drive in place and copy what matches")
    ap.add_argument("--apply", action="store_true", help="actually move/copy files (default is a dry run)")
    ap.add_argument("--convert", type=int, metavar="HEIGHT", nargs="?", const=1080,
                    help="shrink videos to H.264 MP4 (default 1080): while importing, or on their own for show folders")
    ap.add_argument("--encoder", choices=["auto", "apple", "x264"], default="auto",
                    help="auto (default) uses Apple's hardware encoder when ffmpeg has it")
    ap.add_argument("--jobs", type=int, help="videos to convert at once (default: 3 with the Apple encoder, 1 otherwise)")
    ap.add_argument("--min-seconds", type=float, default=10, help="videos shorter than this go to review (default 10)")
    ap.add_argument("--review", action="store_true", help="send short/unsure clips already in show folders to review")
    ap.add_argument("--restore", nargs="+", metavar="NAME", help="move clips (file names or a show id) from review back into their show")
    ap.add_argument("--index", action="store_true", help="refresh media.json in every show folder")
    args = ap.parse_args()

    if args.restore:
        restore(args.restore)
    elif args.review:
        review_existing(args.min_seconds, args.apply)
    elif args.index:
        index()
    elif args.convert and not (args.apply or args.sources):
        enc = encoder_choice(args.encoder)
        convert_existing(args.convert, enc, args.jobs or (3 if enc == "apple" else 1))
    else:
        items = plan(args.sources, args.min_seconds)
        if not items:
            print("Nothing to sort. Put photos and videos in media/inbox/ (or media/), or use --from FOLDER.")
        else:
            describe(items, args.sources)
            if args.apply:
                enc = encoder_choice(args.encoder) if args.convert else None
                apply(items, args.convert, enc, args.jobs or (3 if enc == "apple" else 1))
            elif any(it["dest"] in ("show", "review") for it in items):
                verb = "copy" if args.sources else "move"
                print(f"\nDry run. Run again with --apply to {verb} them" + (" (add --convert to shrink videos on the way)." if not args.convert else "."))
