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
        "site_url": "",
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


def clean_set_name(name, index=0):
    """'Set 1:' -> 'Set 1', 'Main Set' / 'MAIN SET' -> 'Main set', '' -> 'Main set' or 'Set N'."""
    name = re.sub(r"\s+", " ", (name or "")).strip().rstrip(":").strip()
    if not name:
        return "Main set" if index == 0 else f"Set {index + 1}"
    if name.lower() == "main set":
        return "Main set"
    return name


MANIFEST = "media.json"  # per show folder: every media file with its capture time, length and size


def read_manifest(sid):
    """media/<id>/media.json -> {file name: {"taken": iso, "seconds": float, "bytes": int}}.
    It lists files even after they've been moved to cloud storage, so the build
    (and GitHub Actions, which never sees the files) still knows they exist."""
    p = MEDIA_DIR / sid / MANIFEST
    if not p.exists():
        legacy = MEDIA_DIR / sid / ".captured.json"  # older format: {file: iso time}
        if legacy.exists():
            return {k: {"taken": v} for k, v in json.loads(legacy.read_text(encoding="utf-8")).items()}
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def write_manifest(sid, entries):
    folder = MEDIA_DIR / sid
    folder.mkdir(parents=True, exist_ok=True)
    ordered = dict(sorted(entries.items(), key=lambda kv: (kv[1].get("taken") or "~", kv[0])))
    (folder / MANIFEST).write_text(json.dumps(ordered, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    legacy = folder / ".captured.json"
    if legacy.exists():
        legacy.unlink()


def split_artists(text):
    """'The Shins / Silversun Pickups' -> ['The Shins', 'Silversun Pickups']."""
    return [a.strip() for a in re.split(r"\s+/\s+", text or "") if a.strip()]


def bill(row, order=None):
    """Every act on a show's bill, in the order they played (first on stage first).

    The CSV lists artists the way a poster bills them, biggest name first, in both
    the `artist` and `opener` columns, so the stage order is: openers reversed, then
    the artist column reversed (the first-listed artist headlines and plays last).
    A show file can override this with "order": ["First act", "Second act", ...].
    """
    heads = split_artists(row.get("artist", ""))
    openers = split_artists(row.get("opener", ""))
    opener_slugs = {slugify(o) for o in openers}
    heads = [h for h in heads if slugify(h) not in opener_slugs] or heads[:1]
    acts = [{"artist": a, "role": "opener"} for a in reversed(openers)]
    acts += [{"artist": a, "role": "headliner" if i == 0 else "co-headliner"} for i, a in reversed(list(enumerate(heads)))]
    if order:
        rank = {slugify(a): i for i, a in enumerate(order)}
        acts.sort(key=lambda a: rank.get(slugify(a["artist"]), len(rank)))
    return acts


def show_acts(show, row):
    """A show file's acts as a list of {"artist", "sets", ...}, reading the older
    single-setlist format ({"sets": [...]}) as the headliner's setlist."""
    show = show or {}
    if "acts" in show:
        return show["acts"]
    if show.get("sets"):
        legacy = {k: v for k, v in show.items() if k in ("sets", "source", "provisional")}
        return [{"artist": split_artists(row.get("artist", ""))[0], **legacy}]
    return []


def read_genres():
    """artists.csv -> {artist slug: [genre, ...]} (first genre is the main one)."""
    path = ROOT / "artists.csv"
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        return {
            slugify(r["artist"]): [g.strip() for g in (r.get("genres") or "").split(";") if g.strip()]
            for r in csv.DictReader(f) if (r.get("artist") or "").strip()
        }
