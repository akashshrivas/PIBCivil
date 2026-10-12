"""
inspect_gold_record.py
=======================
Diagnostic only -- prints ONE real record from your most recent gold
file in R2, so we can see the exact field names your Sarvam summarizer
actually writes (e.g. "summary_points" vs "key_points" vs "facts").

Run from the project root:
    python -m scripts.inspect_gold_record
"""

import json
import sys
from pathlib import Path

import boto3

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass

import os

GOLD_PREFIX = "gold/"


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"Missing environment variable: {name}")
    return value


def main() -> None:
    account_id = _require_env("R2_ACCOUNT_ID")
    s3 = boto3.client(
        service_name="s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=_require_env("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=_require_env("R2_SECRET_ACCESS_KEY"),
        region_name="auto",
    )
    bucket = _require_env("R2_BUCKET")

    paginator = s3.get_paginator("list_objects_v2")
    keys = []
    for page in paginator.paginate(Bucket=bucket, Prefix=GOLD_PREFIX):
        for obj in page.get("Contents", []):
            if not obj["Key"].endswith("/"):
                keys.append(obj["Key"])

    if not keys:
        sys.exit("No gold files found under 'gold/' -- nothing to inspect.")

    latest_key = sorted(keys)[-1]
    print(f"Reading: {latest_key}\n")

    response = s3.get_object(Bucket=bucket, Key=latest_key)
    records = json.loads(response["Body"].read())

    if not records:
        sys.exit(f"{latest_key} has zero records.")

    print("Keys in one record:", list(records[0].keys()))
    print()
    print("Full record (pretty-printed):")
    print(json.dumps(records[0], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()