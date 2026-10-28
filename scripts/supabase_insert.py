"""
supabase_insert.py
===================

Reads Gold-layer JSON files from R2 (the "gold/" prefix) and UPSERTS
the data into Supabase, matching the normalized schema:

    sources            -> looked up once ('pib')
    articles           -> one row per article, unique (source_id, release_id)
    article_summaries  -> one row per article/language/model/prompt_version

Re-running is always safe: both tables are upserted on their unique keys.

HOW TO RUN
    python scripts/supabase_insert.py                    # ALL gold files (full re-sync)
    python scripts/supabase_insert.py --date 2026-10-13  # only the gold file for that day

The nightly GitHub workflow uses --date, so each run only touches the one day
it just fetched. Without --date it re-inserts every day in R2 (slow, but handy
for a full re-sync).

NOTE ON MISSING FIELDS:
Gold records contain prid/title/ministry/posted_on/summary/important_facts/keywords.
- `ministry` stays NULL unless the gold record has it.
- `published_on` (NOT NULL in the schema) falls back to the date in the
  R2 key, e.g. "gold/2026/04/15.json" -> 2026-04-15.
"""

import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

import boto3

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass

from supabase import create_client

GOLD_PREFIX = "gold/"
_DATE_IN_KEY = re.compile(r"(\d{4})/(\d{1,2})/(\d{1,2})")

# Values for the article_summaries table
SOURCE_SLUG = "pib"
SUMMARY_LANGUAGE = "en"
SUMMARY_MODEL = "sarvam-m"  # change if you use a different model
PROMPT_VERSION = "v1"  # bump this when you change the summarizer prompt


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"Missing environment variable: {name}")
    return value


def _r2_client():
    account_id = _require_env("R2_ACCOUNT_ID")
    return boto3.client(
        service_name="s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=_require_env("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=_require_env("R2_SECRET_ACCESS_KEY"),
        region_name="auto",
    )


def _supabase_client():
    return create_client(_require_env("SUPABASE_URL"), _require_env("SUPABASE_KEY"))


def _get_source_id(supabase) -> int:
    """Looks up the numeric id of the 'pib' row in the sources table."""
    result = (
        supabase.table("sources").select("id").eq("slug", SOURCE_SLUG).execute()
    )
    if not result.data:
        sys.exit(
            f"No row with slug '{SOURCE_SLUG}' in the sources table. "
            "Did you run the schema SQL?"
        )
    return result.data[0]["id"]


def _date_from_key(key: str) -> date | None:
    match = _DATE_IN_KEY.search(key)
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError:
        return None


def _list_gold_keys(s3, bucket: str) -> list[str]:
    keys = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=GOLD_PREFIX):
        for obj in page.get("Contents", []):
            if not obj["Key"].endswith("/"):
                keys.append(obj["Key"])
    return keys


def _published_on(record: dict, fallback_date: date | None) -> str | None:
    """The articles.published_on column is a DATE, so keep only YYYY-MM-DD."""
    raw = record.get("posted_on") or record.get("published_on")
    if raw:
        return str(raw)[:10]
    return fallback_date.isoformat() if fallback_date else None


def _clean_ministry(value: str | None) -> str | None:
    """Only a known ministry name may be saved in the articles table.

    Old gold files in R2 can still hold a headline or paragraph in the
    `ministry` field. This is the last safety net before the database:
    the value is matched against the same canonical list the pipeline uses.
    If it is not a known ministry we save NULL instead of the junk text.
    """
    if not value:
        return None
    try:
        # The canonical list lives in the pipeline folder, so add it to
        # Python's search path before importing.
        pipeline_dir = str(Path(__file__).resolve().parents[1] / "pipeline")
        if pipeline_dir not in sys.path:
            sys.path.insert(0, pipeline_dir)
        from clean.text_cleaner import _match_ministry

        return _match_ministry(value, allow_contained=False)
    except ImportError:
        # Pipeline dependencies are missing here. Fall back to a simple
        # length check so a long headline can never get through.
        return value if len(value) <= 100 else None


def _build_article_row(
    record: dict, fallback_date: date | None, source_id: int
) -> dict:
    """Maps one gold record onto the articles table. Raises ValueError if a
    NOT NULL column (release_id, title, published_on) can't be filled."""
    prid = record.get("prid")
    title = record.get("title")
    published_on = _published_on(record, fallback_date)

    if not prid:
        raise ValueError("missing prid")
    if not title:
        raise ValueError("missing title")
    if not published_on:
        raise ValueError("no published date and none in the file path")

    return {
        "source_id": source_id,
        "release_id": str(prid),
        "url": record.get("url"),
        "title": title,
        "ministry": _clean_ministry(record.get("ministry")),
        "published_on": published_on,
        "language": SUMMARY_LANGUAGE,
    }


def _build_summary_row(record: dict, article_id: str) -> dict | None:
    """Maps one gold record onto article_summaries. Returns None if the
    record has no summary text (the summary column is NOT NULL)."""
    points = record.get("important_facts") or []
    summary = record.get("summary") or "\n".join(f"- {p}" for p in points)
    if not summary:
        return None

    return {
        "article_id": article_id,
        "language": SUMMARY_LANGUAGE,
        "summary": summary,
        "important_facts": points,
        "keywords": record.get("keywords") or [],
        "model": SUMMARY_MODEL,
        "prompt_version": PROMPT_VERSION,
    }


def insert_gold_data(only_date: date | None = None) -> None:
    """Upserts gold data into Supabase.

    only_date=None   -> process every gold file in R2.
    only_date=<date> -> process only the gold file(s) whose key date matches
                        (e.g. gold/2026/10/13.json for 2026-10-13).
    """
    s3 = _r2_client()
    supabase = _supabase_client()
    bucket = _require_env("R2_BUCKET")
    source_id = _get_source_id(supabase)

    keys = _list_gold_keys(s3, bucket)
    print(f"Found {len(keys)} gold file(s) in R2 under '{GOLD_PREFIX}'")

    # NEW: keep only the file(s) for the requested day.
    if only_date is not None:
        keys = [k for k in keys if _date_from_key(k) == only_date]
        print(f"Keeping {len(keys)} file(s) for {only_date.isoformat()}")
        if not keys:
            # Nothing to insert for this day (for example, no releases that day).
            # Print a warning and finish normally so the pipeline does NOT fail.
            print(
                f"WARNING: no gold file found in R2 for {only_date.isoformat()} "
                f"(looked for a key like {GOLD_PREFIX}{only_date:%Y/%m/%d}.json). "
                "Nothing inserted."
            )
            return

    total_articles = 0
    total_summaries = 0

    for key in sorted(keys):
        fallback_date = _date_from_key(key)

        response = s3.get_object(Bucket=bucket, Key=key)
        raw_bytes = response["Body"].read()

        try:
            records = json.loads(raw_bytes)
        except json.JSONDecodeError as e:
            print(f"SKIPPING {key}: not valid JSON ({e})")
            continue

        if not isinstance(records, list):
            print(f"SKIPPING {key}: expected a JSON array, got {type(records).__name__}")
            continue

        # Keyed by release_id so duplicates inside one file collapse to one
        # row (Postgres rejects an upsert that hits the same row twice).
        article_rows: dict[str, dict] = {}
        records_by_release: dict[str, dict] = {}
        for record in records:
            try:
                row = _build_article_row(record, fallback_date, source_id)
            except ValueError as e:
                print(f"  Skipping one record in {key}: {e}")
                continue
            article_rows[row["release_id"]] = row
            records_by_release[row["release_id"]] = record

        if not article_rows:
            print(f"{key}: 0 valid rows, skipping")
            continue

        # Step 1: upsert articles. The response contains the generated
        # uuid `id` for each row, which article_summaries needs.
        result = (
            supabase.table("articles")
            .upsert(list(article_rows.values()), on_conflict="source_id,release_id")
            .execute()
        )
        id_by_release = {row["release_id"]: row["id"] for row in result.data}

        # Step 2: upsert summaries, linked by article_id.
        summary_rows = []
        for release_id, record in records_by_release.items():
            article_id = id_by_release.get(release_id)
            if not article_id:
                continue
            summary_row = _build_summary_row(record, article_id)
            if summary_row:
                summary_rows.append(summary_row)

        if summary_rows:
            (
                supabase.table("article_summaries")
                .upsert(
                    summary_rows,
                    on_conflict="article_id,language,model,prompt_version",
                )
                .execute()
            )

        print(
            f"{key}: upserted {len(article_rows)} article(s), "
            f"{len(summary_rows)} summary row(s)"
        )
        total_articles += len(article_rows)
        total_summaries += len(summary_rows)

    print()
    print(
        f"DONE: {total_articles} article(s) and {total_summaries} summary row(s) "
        f"upserted across {len(keys)} file(s)"
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upsert gold data from R2 into Supabase.")
    parser.add_argument(
        "--date",
        help="Only insert this day, as YYYY-MM-DD. Leave out to insert every day in R2.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    day = None
    if args.date:
        try:
            day = date.fromisoformat(args.date)
        except ValueError:
            sys.exit(f"--date must look like 2026-10-13, got: {args.date}")
    insert_gold_data(only_date=day)
