#!/usr/bin/env python3
"""Sort a pile of photos and videos into the right show folders, using the
capture time (and location) your phone saved inside each file.

    1. Drop files into media/inbox/ (or straight into media/)
    2. python3 scripts/import_media.py            # dry run: shows where everything would go
    3. python3 scripts/import_media.py --apply    # moves them into media/<show-id>/

Optional, after sorting:
    python3 scripts/import_media.py --convert 1080   # shrink videos to H.264 MP4 (plays everywhere,
                                                     # ~5-10x smaller); originals kept in originals/

How a file is matched to a show:
  - The capture time is read from the file (videos: ffprobe; JPEG photos: EXIF).
    Files without one fall back to a date in the file name, then to their
    camera-roll neighbours (IMG_5343 sits between two clips from the same show).
  - Anything filmed before 5 AM counts toward the previous night's show.
  - A time saved without a timezone is tried against every timezone; it's only
    matched if exactly one show date fits.
  - When several clips from a show have GPS, any clip far from the rest is
    flagged so you can check it.
Nothing is deleted. Files that match no show stay where they are and are listed.
Needs ffmpeg/ffprobe for videos (brew install ffmpeg).
"""
import argparse
import datetime as dt
import json
import math
import re
import shutil
import statistics
import struct
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import MEDIA_DIR, read_concerts  # noqa: E402

INBOX = MEDIA_DIR / "inbox"
VIDEO_EXT = {".mp4", ".m4v", ".mov", ".webm"}
PHOTO_EXT = {".jpg", ".jpeg", ".png", ".heic", ".webp"}
NIGHT_ROLLOVER_HOURS = 5
CAPTURE_LOG = ".captured.json"  # per show folder: file -> capture time, for ordering clips


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
                             capture_output=True, text=True, timeout=60).stdout
    except FileNotFoundError:
        raise SystemExit("ffprobe not found. Install ffmpeg first (brew install ffmpeg).")
    fmt = json.loads(out or "{}").get("format", {})
    tags = {k.lower(): v for k, v in (fmt.get("tags") or {}).items()}
    # Apple's own tag keeps the local timezone; creation_time is usually UTC.
    t, has_tz = parse_time(tags.get("com.apple.quicktime.creationdate"))
    if not t:
        t, has_tz = parse_time(tags.get("creation_time"))
        if t and t.utcoffset() == dt.timedelta(0):
            has_tz = False  # UTC tells us the moment, not the local date; treat as unknown zone
    gps = parse_iso6709(tags.get("com.apple.quicktime.location.iso6709") or tags.get("location"))
    return t, has_tz, gps, float(fmt.get("duration") or 0)


def read_exif(path):
    """Minimal EXIF reader for JPEG: DateTimeOriginal (+ OffsetTimeOriginal) and GPS."""
    data = path.read_bytes()[:256 * 1024]
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

    root = ifd(u32(4))
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
    m = re.search(r"(20\d{2})[-_]?([01]\d)[-_]?([0-3]\d)", name)
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


def candidates():
    files = []
    if INBOX.is_dir():
        files += [p for p in INBOX.rglob("*") if p.is_file()]
    files += [p for p in MEDIA_DIR.iterdir() if p.is_file()]
    return sorted(p for p in files if p.suffix.lower() in VIDEO_EXT | PHOTO_EXT and not p.name.startswith("."))


def plan():
    shows_by_date = {}
    for r in read_concerts():
        shows_by_date.setdefault(dt.date.fromisoformat(r["date"]), []).append(r)
    items = []
    for p in candidates():
        ext = p.suffix.lower()
        t, has_tz, gps, dur = None, False, None, 0.0
        if ext in VIDEO_EXT:
            t, has_tz, gps, dur = probe_video(p)
        elif ext in (".jpg", ".jpeg"):
            t, has_tz, gps = read_exif(p)
        item = {"path": p, "time": t, "gps": gps, "duration": dur, "show": None, "how": "", "warn": ""}
        if t and has_tz:
            d = night_of(t)
            if d in shows_by_date:
                item["show"], item["how"] = shows_by_date[d][0], "capture time"
            else:
                item["warn"] = f"no show in your log on {d:%a %b %-d, %Y}"
        elif t:  # no timezone: try them all
            base = t.replace(tzinfo=None)
            dates = {night_of(base + dt.timedelta(hours=h)) for h in range(-12, 15)}
            hits = sorted({d for d in dates if d in shows_by_date})
            if len(hits) == 1:
                item["show"], item["how"] = shows_by_date[hits[0]][0], "capture time (timezone guessed)"
            else:
                item["warn"] = "capture time has no timezone and fits " + ("no show" if not hits else f"{len(hits)} shows")
        elif date_from_name(p.name) in shows_by_date:
            item["show"], item["how"] = shows_by_date[date_from_name(p.name)][0], "date in file name"
        items.append(item)

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
            it["warn"] = ""
        elif not it["warn"]:
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
                    it["warn"] = f"{km(it['gps'], centre):.0f} km from the show's other clips; check it"
    return items


def describe(items):
    by_show, unmatched = {}, []
    for it in items:
        (by_show.setdefault(it["show"]["id"], []) if it["show"] else unmatched).append(it)
    for sid in sorted(by_show):
        group = sorted(by_show[sid], key=lambda it: (it["time"] is None, it["time"].replace(tzinfo=None) if it["time"] else 0))
        print(f"\n{sid}  ({len(group)} files)")
        for it in group:
            when = it["time"].strftime("%-I:%M %p") if it["time"] else "  ?   "
            extra = f"{it['duration']:.0f}s" if it["duration"] else ""
            note = f"  [{it['how']}]" if it["how"] != "capture time" else ""
            warn = f"  ! {it['warn']}" if it["warn"] else ""
            print(f"  {when:>8}  {it['path'].name:44} {extra:>5}{note}{warn}")
    if unmatched:
        print(f"\nNot matched ({len(unmatched)}): left where they are")
        for it in unmatched:
            when = it["time"].strftime("%Y-%m-%d %-I:%M %p") if it["time"] else "no capture time"
            where = f" at {it['gps'][0]:.3f},{it['gps'][1]:.3f}" if it["gps"] else ""
            print(f"  {it['path'].name:44} {when}{where}  ({it['warn']})")


def apply(items):
    moved = 0
    for it in items:
        if not it["show"]:
            continue
        dest_dir = MEDIA_DIR / it["show"]["id"]
        dest_dir.mkdir(exist_ok=True)
        dest = dest_dir / it["path"].name
        n = 2
        while dest.exists():
            dest = dest_dir / f"{it['path'].stem}-{n}{it['path'].suffix}"
            n += 1
        shutil.move(str(it["path"]), dest)
        log_path = dest_dir / CAPTURE_LOG
        log = json.loads(log_path.read_text()) if log_path.exists() else {}
        if it["time"]:
            log[dest.name] = it["time"].isoformat()
        log_path.write_text(json.dumps(dict(sorted(log.items(), key=lambda kv: kv[1])), indent=1) + "\n")
        moved += 1
    print(f"\nMoved {moved} file(s) into their show folders.")


def convert(height):
    """Re-encode videos in show folders to H.264 MP4; originals go to originals/ (git-ignored)."""
    todo = [p for p in MEDIA_DIR.glob("*/*") if p.suffix.lower() in VIDEO_EXT and p.parent.name != "inbox"
            and not (p.suffix.lower() == ".mp4" and p.stat().st_size < 30 * 1024 * 1024)]
    if not todo:
        print("Nothing to convert.")
        return
    before = after = 0
    for p in sorted(todo):
        out = p.with_suffix(".mp4") if p.suffix.lower() != ".mp4" else p.with_name(p.stem + "-small.mp4")
        cmd = ["ffmpeg", "-loglevel", "error", "-y", "-i", str(p),
               "-vf", f"scale='if(gt(iw,ih),-2,{height})':'if(gt(iw,ih),{height},-2)'",
               "-c:v", "libx264", "-crf", "26", "-preset", "veryfast", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", "-map_metadata", "-1", str(out)]
        print(f"  {p.parent.name}/{p.name} …", end="", flush=True)
        if subprocess.run(cmd).returncode != 0:
            print(" failed, left as is")
            continue
        (p.parent / "originals").mkdir(exist_ok=True)
        before += p.stat().st_size
        shutil.move(str(p), p.parent / "originals" / p.name)
        if out.name.endswith("-small.mp4"):
            out = out.rename(p)
        after += out.stat().st_size
        log_path = p.parent / CAPTURE_LOG
        if log_path.exists():
            log = json.loads(log_path.read_text())
            if p.name in log and out.name != p.name:
                log[out.name] = log.pop(p.name)
                log_path.write_text(json.dumps(log, indent=1) + "\n")
        print(f" {out.stat().st_size // 1048576} MB")
    print(f"\n{before / 1048576:.0f} MB → {after / 1048576:.0f} MB. Originals are in each show's originals/ folder (not committed).")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="move the files (default is a dry run)")
    ap.add_argument("--convert", type=int, metavar="HEIGHT", nargs="?", const=1080,
                    help="shrink videos already in show folders to H.264 MP4 (default 1080)")
    args = ap.parse_args()
    if args.convert:
        convert(args.convert)
    else:
        items = plan()
        if not items:
            print("Nothing to sort. Put photos and videos in media/inbox/ (or media/) first.")
        else:
            describe(items)
            if args.apply:
                apply(items)
            elif any(it["show"] for it in items):
                print("\nDry run. Run again with --apply to move them.")
