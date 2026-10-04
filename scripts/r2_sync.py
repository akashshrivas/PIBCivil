"""
r2_sync.py
==========

Syncs the local data/ folders with a Cloudflare R2 bucket, one prefix per layer:

    data/raw             <->  bronze/    raw articles exactly as fetched
    data/processed       <->  silver/    cleaned articles
    data/exports          <->  gold/      summaries (summary, facts, keywords)
    data/.state           <->  _state/    pipeline bookkeeping (dedup / seen IDs)

Why this exists: a GitHub Actions runner starts empty and is thrown away when
the run ends. So every run must
    1. DOWNLOAD what is already in R2 (so dedup state and existing summaries
       are known and Sarvam is not called again for finished articles), and
    2. UPLOAD what the run produced.

Usage (from the repo root):
    python scripts/r2_sync.py download --since-days 7
    python scripts/r2_sync.py upload

Environment variables (GitHub secrets in the workflow):
    R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET

Needs: pip install boto3

FIX HISTORY -- read this if a layer ever silently stops uploading again:
    Gold summaries stopped uploading entirely, with NO error message.
    Root cause: LAYERS listed the local folder as "exports_sarvam", but
    every summarizer script in this project (summarizer.py,
    extractive_summarizer.py, storage_manager.py's save_gold_articles())
    writes to "data/exports" instead -- so `data/exports_sarvam` simply
    didn't exist on disk. upload()'s `if not local_dir.exists(): continue`
    check skipped the whole layer silently, with no print statement
    explaining why. Fixed two ways: (1) the folder name below now matches
    what the summarizers actually write to, and (2) a missing folder now
    prints a clear warning instead of failing silently, so this exact
    class of bug can never hide again.
"""

import argparse
import hashlib
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import boto3
from botocore.config import Config

# Optional, for running on your own machine: read R2_* values from the same
# .env file the summarizer uses. Real environment variables (GitHub secrets)
# always win, so this does nothing in GitHub Actions.
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"

# (local folder under data/, prefix in the bucket)
#
# IMPORTANT: "exports" here MUST match whatever folder name your actual
# summarizer script writes to. If you deliberately keep Sarvam's output
# in a separately-named folder (e.g. "exports_sarvam"), change this
# tuple's first value to match -- just make sure the two are never out
# of sync, since that mismatch is exactly what caused Gold to silently
# stop uploading before.
LAYERS = [
    ("raw", "bronze/"),
    ("processed", "silver/"),
    ("exports", "gold/"),
    (".state", "_state/"),
]

# Keys like  bronze/2026/09/27.json  or  silver/2026/09/27_silver.json
_DATE_IN_KEY = re.compile(r"(\d{4})/(\d{1,2})/(\d{1,2})")


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"Missing environment variable: {name}")
    return value


def _client():
    account_id = _require_env("R2_ACCOUNT_ID")
    return boto3.client(
        service_name="s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=_require_env("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=_require_env("R2_SECRET_ACCESS_KEY"),
        region_name="auto",  # required by boto3, not used by R2
        config=Config(retries={"max_attempts": 5, "mode": "standard"}),
    )


def _md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _list_remote(s3, bucket: str, prefix: str) -> dict[str, str]:
    """{key: etag} for everything under a prefix. For small single-part
    uploads the ETag is the file's MD5, which lets us skip unchanged files."""
    remote = {}
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            if not obj["Key"].endswith("/"):
                remote[obj["Key"]] = obj["ETag"].strip('"')
    return remote


def _key_date(key: str):
    match = _DATE_IN_KEY.search(key)
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def upload(s3, bucket: str) -> None:
    uploaded = skipped = 0

    for local_name, prefix in LAYERS:
        local_dir = DATA_DIR / local_name

        # FIX: a missing folder used to just `continue` here with zero
        # output, which is exactly how the Gold layer went missing
        # without anyone noticing. Now it says so explicitly, every
        # time, so a naming mismatch like this can't hide again.
        if not local_dir.exists():
            print(f"SKIPPING layer '{local_name}' -> {prefix}: {local_dir} does not exist locally")
            continue

        remote = _list_remote(s3, bucket, prefix)
        layer_uploaded = 0

        for path in sorted(p for p in local_dir.rglob("*") if p.is_file()):
            key = prefix + path.relative_to(local_dir).as_posix()

            if remote.get(key) == _md5(path):
                skipped += 1
                continue

            extra = {"ContentType": "application/json"} if path.suffix == ".json" else {}
            s3.upload_file(str(path), bucket, key, ExtraArgs=extra)
            print(f"uploaded  {key}")
            uploaded += 1
            layer_uploaded += 1

        # A SECOND, narrower safety net: the folder exists, but if it's
        # EMPTY (zero files found), say so too -- that's just as
        # suspicious as a missing folder (e.g. the summarizer ran but
        # wrote nowhere), and silently moving on would hide that just
        # as easily as the original bug did.
        if layer_uploaded == 0 and not any(local_dir.rglob("*")):
            print(f"NOTE: layer '{local_name}' folder exists but contains no files")

    print(f"\nUpload done: {uploaded} uploaded, {skipped} unchanged")


def download(s3, bucket: str, since_days) -> None:
    cutoff = date.today() - timedelta(days=since_days) if since_days else None
    downloaded = skipped = 0

    for local_name, prefix in LAYERS:
        local_dir = DATA_DIR / local_name

        for key, etag in _list_remote(s3, bucket, prefix).items():
            # Old days are not needed to run today; _state/ has no date and is always fetched.
            key_date = _key_date(key)
            if cutoff and key_date and key_date < cutoff:
                continue

            path = local_dir / key[len(prefix):]

            if path.exists() and _md5(path) == etag:
                skipped += 1
                continue

            path.parent.mkdir(parents=True, exist_ok=True)
            s3.download_file(bucket, key, str(path))
            print(f"downloaded {key}")
            downloaded += 1

    print(f"\nDownload done: {downloaded} downloaded, {skipped} already up to date")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync data/ with Cloudflare R2")
    sub = parser.add_subparsers(dest="command", required=True)

    down = sub.add_parser("download", help="R2 -> local")
    down.add_argument("--since-days", type=int, default=None,
                      help="only fetch dated files from the last N days (state is always fetched)")

    sub.add_parser("upload", help="local -> R2")

    args = parser.parse_args()
    bucket = _require_env("R2_BUCKET")
    client = _client()

    if args.command == "download":
        download(client, bucket, args.since_days)
    else:
        upload(client, bucket)