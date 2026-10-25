"""
fix_ministries.py
==================

ONE-TIME cleanup of the `ministry` column in the Supabase `articles` table.

THE PROBLEM
    Some rows have a headline or a paragraph saved as their "ministry"
    (for example "Central Secretariat Group-C Employees Thank Dr. ..."),
    so those long texts showed up in the Ministry dropdown.

WHAT THIS SCRIPT DOES
    1. Reads every distinct ministry value currently in the table.
    2. Checks each one against the canonical ministry list your pipeline
       already uses (pipeline/clean/text_cleaner.py).
         - already a canonical name   -> left alone
         - a different spelling of one -> renamed to the canonical spelling
         - not a ministry at all       -> set to NULL (empty)
    3. By default it only PRINTS what it would change (a "dry run").
       Add --apply to really update the database.

HOW TO RUN (from the project root, with your virtual environment on)
    python scripts/fix_ministries.py            # dry run: look first
    python scripts/fix_ministries.py --apply    # do it

It needs SUPABASE_URL and SUPABASE_KEY (the service key) in your .env,
the same as scripts/supabase_insert.py.
"""

import argparse
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass

from supabase import create_client

# The canonical list lives in the pipeline folder, so add that folder to
# Python's search path before importing from it.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
from clean.text_cleaner import CANONICAL_MINISTRIES, _match_ministry  # noqa: E402

PAGE_SIZE = 1000  # Supabase returns at most this many rows per request


def classify(values: list[str]) -> dict[str, str | None]:
    """For each ministry value that needs fixing, decide its replacement.

    Returns {old_value: new_value}. new_value is None when the old value is
    not a ministry at all. Values that are already correct are not included.
    """
    canonical = set(CANONICAL_MINISTRIES)
    changes: dict[str, str | None] = {}
    for value in values:
        if value in canonical:
            continue  # already correct
        # allow_contained=False: a headline that only MENTIONS a ministry is
        # junk, not that ministry, so it must not be renamed to it.
        changes[value] = _match_ministry(value, allow_contained=False)
    return changes


def fetch_distinct_ministries(client) -> dict[str, int]:
    """Returns {ministry_value: number_of_articles} for every non-empty value.

    Supabase limits each request to ~1000 rows, so we read the table in
    pages until a page comes back short.
    """
    counts: dict[str, int] = {}
    start = 0
    while True:
        result = (
            client.table("articles")
            .select("ministry")
            .not_.is_("ministry", "null")
            .order("id")  # stable order so pages do not overlap
            .range(start, start + PAGE_SIZE - 1)
            .execute()
        )
        rows = result.data or []
        for row in rows:
            counts[row["ministry"]] = counts.get(row["ministry"], 0) + 1
        if len(rows) < PAGE_SIZE:
            break
        start += PAGE_SIZE
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean the articles.ministry column")
    parser.add_argument("--apply", action="store_true", help="really update the database")
    args = parser.parse_args()

    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY")
    if not url or not key:
        sys.exit("Missing SUPABASE_URL or SUPABASE_KEY in your environment / .env")
    client = create_client(url, key)

    counts = fetch_distinct_ministries(client)
    changes = classify(list(counts))

    print(f"Distinct ministry values found : {len(counts)}")
    print(f"Values that need fixing        : {len(changes)}\n")

    renamed = {old: new for old, new in changes.items() if new}
    cleared = [old for old, new in changes.items() if not new]
    for old, new in renamed.items():
        print(f"RENAME ({counts[old]:>4} rows)  {old[:70]!r}  ->  {new!r}")
    for old in cleared:
        print(f"CLEAR  ({counts[old]:>4} rows)  {old[:70]!r}  ->  NULL")

    if not changes:
        print("Nothing to fix.")
        return
    if not args.apply:
        print("\nDRY RUN: nothing changed. Run again with --apply to update the database.")
        return

    # Update every row that has the old value in one request per value.
    for old, new in changes.items():
        client.table("articles").update({"ministry": new}).eq("ministry", old).execute()
    print(f"\nDone. Updated {len(changes)} distinct value(s).")


if __name__ == "__main__":
    main()
