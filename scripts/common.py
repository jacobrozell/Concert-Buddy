"""Shared helpers for ConcertBuddy scripts. Standard library only."""
import csv
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "concerts.csv"
CONFIG_PATH = ROOT / "config.json"
SHOWS_DIR = ROOT / "shows"
MEDIA_DIR = ROOT / "media"


def slugify(text):
    """'Them Changes!' -> 'them-changes'. Accents are folded, '&' becomes 'and'."""
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    text = text.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def show_id(row):
    """Stable id for a show: an explicit `id` column wins, else <date>-<first-artist-slug>."""
    if (row.get("id") or "").strip():
        return row["id"].strip()
    first_artist = re.split(r"\s+/\s+", row.get("artist", ""))[0]
    return f"{row['date'].strip()}-{slugify(first_artist)}"


def read_concerts():
    with open(CSV_PATH, newline="", encoding="utf-8-sig") as f:
        rows = [
            {k.strip(): (v or "").strip() for k, v in r.items() if k}
            for r in csv.DictReader(f)
        ]
    rows = [r for r in rows if r.get("artist") and r.get("date")]
    for r in rows:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["date"]):
            raise SystemExit(f"concerts.csv: date must be YYYY-MM-DD, got {r['date']!r} for {r['artist']}")
        r["id"] = show_id(r)
    seen = set()
    for r in rows:
        if r["id"] in seen:
            raise SystemExit(f"concerts.csv: two shows share the id {r['id']!r}. Add an `id` column to tell them apart.")
        seen.add(r["id"])
    return rows


def read_config():
    defaults = {
        "site_title": "Concert Log",
        "owner": "",
        "tagline": "Every concert I've been to, one ticket stub at a time.",
        "highlight_companion": "",
        "media_base_url": "",
        "repo_url": "",
    }
    if CONFIG_PATH.exists():
        defaults.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
    return defaults


def show_path(sid):
    return SHOWS_DIR / f"{sid}.json"


def load_show(sid):
    p = show_path(sid)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def save_show(sid, data):
    SHOWS_DIR.mkdir(exist_ok=True)
    show_path(sid).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def iter_songs(show):
    for s in (show or {}).get("sets", []):
        for song in s.get("songs", []):
            yield song
