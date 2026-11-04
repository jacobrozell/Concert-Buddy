#!/usr/bin/env python3
"""Upload your photos and videos to a Cloudflare R2 bucket, so they don't have
to live in the Git repo (GitHub allows 100 MB per file and ~1 GB per site).

One-time setup: see README › "Hosting media on Cloudflare R2". Your keys go in a
file called .env next to concerts.csv (it's git-ignored, never committed):

    R2_ACCOUNT_ID=…            # Cloudflare dashboard › R2 › Account details
    R2_ACCESS_KEY_ID=…         # R2 › Manage API tokens › Create (Object Read & Write)
    R2_SECRET_ACCESS_KEY=…
    R2_BUCKET=concert-media
    R2_PUBLIC_URL=https://pub-….r2.dev   # bucket › Settings › Public access

Then:
    python3 scripts/upload_media.py --dry-run    # what would be uploaded
    python3 scripts/upload_media.py              # upload new and changed files
    python3 scripts/upload_media.py --show 2026-11-03-thundercat

Files go to <bucket>/<show-id>/<file name>, the same layout as media/. Anything
already in the bucket with the same size is skipped, so re-running is cheap.
originals/, inbox/, hidden files and media.json are never uploaded.
Standard library only.
"""
import argparse
import datetime as dt
import hashlib
import hmac
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CONFIG_PATH, MEDIA_DIR, ROOT, read_concerts  # noqa: E402

MEDIA_EXT = {".mp4", ".m4v", ".mov", ".webm", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".heic",
             ".mp3", ".m4a", ".aac", ".wav", ".ogg"}
TYPES = {".mov": "video/quicktime", ".m4v": "video/x-m4v", ".heic": "image/heic", ".m4a": "audio/mp4"}


# ---------- AWS Signature Version 4 (what R2's S3-compatible API expects) ----------

def _hmac(key, msg):
    return hmac.new(key, msg.encode(), hashlib.sha256).digest()


def sign(method, host, path, query, headers, payload_hash, key_id, secret, region="auto", service="s3", now=None):
    """Return the request headers with an AWS SigV4 Authorization header added."""
    now = now or dt.datetime.now(dt.timezone.utc)
    amz_date, day = now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")
    h = {k.lower(): " ".join(str(v).split()) for k, v in headers.items()}
    h.update({"host": host, "x-amz-date": amz_date, "x-amz-content-sha256": payload_hash})
    names = sorted(h)
    canonical = "\n".join([
        method,
        quote(path, safe="/-_.~"),
        "&".join(f"{quote(k, safe='-_.~')}={quote(str(v), safe='-_.~')}" for k, v in sorted(query.items())),
        "".join(f"{k}:{h[k]}\n" for k in names),
        ";".join(names),
        payload_hash,
    ])
    scope = f"{day}/{region}/{service}/aws4_request"
    to_sign = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canonical.encode()).hexdigest()])
    k = _hmac(_hmac(_hmac(_hmac(("AWS4" + secret).encode(), day), region), service), "aws4_request")
    signature = hmac.new(k, to_sign.encode(), hashlib.sha256).hexdigest()
    h["authorization"] = f"AWS4-HMAC-SHA256 Credential={key_id}/{scope}, SignedHeaders={';'.join(names)}, Signature={signature}"
    return h


class R2:
    def __init__(self, account, key_id, secret, bucket):
        self.host = f"{account}.r2.cloudflarestorage.com"
        self.key_id, self.secret, self.bucket = key_id, secret, bucket

    def _request(self, method, key="", query=None, headers=None, body=None, payload_hash=None):
        path = f"/{self.bucket}" + (f"/{key}" if key else "")
        query = query or {}
        payload_hash = payload_hash or hashlib.sha256(b"").hexdigest()
        h = sign(method, self.host, path, query, headers or {}, payload_hash, self.key_id, self.secret)
        qs = "&".join(f"{quote(k, safe='-_.~')}={quote(str(v), safe='-_.~')}" for k, v in sorted(query.items()))
        url = f"https://{self.host}{quote(path, safe='/-_.~')}" + (f"?{qs}" if qs else "")
        req = urllib.request.Request(url, data=body, method=method, headers={k: v for k, v in h.items() if k != "host"})
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="ignore")
            code = ET.fromstring(detail).findtext("Code") if detail.startswith("<") else detail[:200]
            hint = {"InvalidAccessKeyId": "check R2_ACCESS_KEY_ID", "SignatureDoesNotMatch": "check R2_SECRET_ACCESS_KEY",
                    "NoSuchBucket": "check R2_BUCKET", "AccessDenied": "the API token needs Object Read & Write on this bucket"}.get(code, "")
            raise SystemExit(f"R2 said {e.code} {code}{f' ({hint})' if hint else ''}")

    def list(self):
        """{key: size} for everything in the bucket."""
        out, token = {}, None
        while True:
            q = {"list-type": "2", **({"continuation-token": token} if token else {})}
            root = ET.fromstring(self._request("GET", query=q))
            ns = {"s3": root.tag.split("}")[0].strip("{")} if root.tag.startswith("{") else {}
            find = (lambda el, tag: el.findall(f"s3:{tag}", ns)) if ns else (lambda el, tag: el.findall(tag))
            for c in find(root, "Contents"):
                key = c.find("s3:Key", ns) if ns else c.find("Key")
                size = c.find("s3:Size", ns) if ns else c.find("Size")
                out[key.text] = int(size.text)
            trunc = root.find("s3:IsTruncated", ns) if ns else root.find("IsTruncated")
            nxt = root.find("s3:NextContinuationToken", ns) if ns else root.find("NextContinuationToken")
            if trunc is None or trunc.text != "true" or nxt is None:
                return out
            token = nxt.text

    def put(self, key, path):
        ctype = TYPES.get(path.suffix.lower()) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        size = path.stat().st_size
        with open(path, "rb") as f:
            self._request("PUT", key, headers={"content-type": ctype, "content-length": str(size),
                                                "cache-control": "public, max-age=604800"},
                          body=f, payload_hash="UNSIGNED-PAYLOAD")


# ---------- syncing ----------

def load_env():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    need = ["R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"]
    missing = [k for k in need if not os.environ.get(k)]
    if missing:
        raise SystemExit(f"Missing {', '.join(missing)}. Put them in a .env file next to concerts.csv (see the top of this script).")


def local_files(only=None):
    shows = {r["id"] for r in read_concerts()}
    for folder in sorted(p for p in MEDIA_DIR.iterdir() if p.is_dir() and p.name in shows):
        if only and folder.name != only:
            continue
        for f in sorted(folder.iterdir()):
            if f.is_file() and not f.name.startswith(".") and f.suffix.lower() in MEDIA_EXT:
                yield f"{folder.name}/{f.name}", f


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="list what would be uploaded, upload nothing")
    ap.add_argument("--show", metavar="SHOW_ID", help="only this show's folder")
    args = ap.parse_args()
    load_env()
    r2 = R2(os.environ["R2_ACCOUNT_ID"], os.environ["R2_ACCESS_KEY_ID"], os.environ["R2_SECRET_ACCESS_KEY"], os.environ["R2_BUCKET"])

    remote = r2.list()
    todo = [(k, f) for k, f in local_files(args.show) if remote.get(k) != f.stat().st_size]
    total = sum(f.stat().st_size for _, f in todo)
    print(f"{len(remote)} files already in {os.environ['R2_BUCKET']}; {len(todo)} to upload ({total / 1048576:.0f} MB)")
    for i, (key, f) in enumerate(todo, 1):
        print(f"  [{i}/{len(todo)}] {key}  {f.stat().st_size / 1048576:.0f} MB", end="" if not args.dry_run else "\n", flush=True)
        if args.dry_run:
            continue
        r2.put(key, f)
        print("  ✓")

    public = os.environ.get("R2_PUBLIC_URL", "").rstrip("/")
    cfg = json.loads(CONFIG_PATH.read_text()) if CONFIG_PATH.exists() else {}
    if public and not args.dry_run and cfg.get("media_base_url", "").rstrip("/") != public:
        cfg["media_base_url"] = public
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
        print(f"\nSet media_base_url in config.json to {public}: the site now plays media from R2.")
    elif not public and not cfg.get("media_base_url"):
        print("\nNext: turn on public access for the bucket and put its address in .env as R2_PUBLIC_URL "
              "(or in config.json as media_base_url), then run this again.")
    if todo and not args.dry_run:
        print("Commit the media.json files and config.json (not the media itself), then push.")


if __name__ == "__main__":
    main()
