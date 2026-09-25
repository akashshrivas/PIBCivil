"""
pipeline.py
===========

WHAT THIS FILE DOES:
This is the "conductor" of the whole pipeline. It doesn't know anything
PIB-specific itself — it just calls the other files in the right order:

    discover PRIDs -> fetch raw HTML -> parse into structured fields
        -> clean the text -> save, grouped by day

Three ways to run it from the command line:
  python pipeline.py                       -> runs once (RSS-based) and exits
  python pipeline.py --loop                -> polls RSS every POLL_INTERVAL_SECONDS forever
  python pipeline.py --backfill 2026-09-15 -> catch-up fetch for one past date via
                                               the date-search page (Playwright)
  add --visible to --backfill to watch the browser instead of running headless
"""

import argparse
import time
from datetime import date, datetime

from loguru import logger

# Each import below comes from a different pipeline stage. Notice the
# pattern: every stage exposes ONE simple function that this file calls —
# pipeline.py never reaches inside another stage's internal helpers.
from extract.rss_fetcher import run as discover_releases
from extract.article_fetcher import run as fetch_raw_pages
from extract.backfill_fetcher import backfill_day
from parse.pib_parser import parse_fetched_page
from clean.text_cleaner import clean_articles
from dedup.dedup_engine import filter_duplicates
from storage.storage_manager import save_bronze_articles, save_silver_articles, get_saved_prids_for_day
from storage.seen_tracker import load_seen, mark_seen

POLL_INTERVAL_SECONDS = 300  # 5 minutes


def fetch_articles(prids: list[str]):
    """
    Runs a batch of PRIDs through fetch -> parse -> [BRONZE SAVE] ->
    clean -> dedup, and returns the cleaned+deduped list for the caller
    to Silver-save.

    The Bronze save happens RIGHT HERE, immediately after parsing and
    before clean_articles()/filter_duplicates() ever touch the data —
    that's what makes data/raw/ a true untouched snapshot instead of
    secretly holding already-cleaned data. Silver saving happens
    separately, in run_once()/run_backfill() below, using whatever this
    function returns.
    """
    pages = fetch_raw_pages(prids)
    parsed_articles = [parse_fetched_page(page) for page in pages]

    # BRONZE: save exactly what parsing produced, before any cleaning
    # or dedup — duplicates and messy text included, on purpose.
    save_bronze_articles(parsed_articles)

    cleaned_articles = clean_articles(parsed_articles)
    unique_articles = filter_duplicates(cleaned_articles)
    return unique_articles


def run_once() -> int:
    """One discover -> fetch-new-only -> save pass. Returns count of new articles saved."""
    seen = load_seen()
    releases = discover_releases()

    new_prids = [r.prid for r in releases if r.prid not in seen]
    if not new_prids:
        logger.info("No new releases since last check.")
        return 0

    logger.info(f"Found {len(new_prids)} new release(s): {new_prids}")
    articles = fetch_articles(new_prids)  # Bronze already saved inside fetch_articles()
    save_silver_articles(articles)        # this is the cleaned + deduped result
    mark_seen(new_prids)
    return len(new_prids)


def run_loop() -> None:
    logger.info(f"Polling every {POLL_INTERVAL_SECONDS}s. Press Ctrl+C to stop.")
    while True:
        try:
            run_once()
        except Exception:
            # Catching every exception here is intentional and different
            # from the specific httpx.HTTPError catches elsewhere: this is
            # the OUTERMOST safety net for a process meant to run forever
            # unattended. One bad cycle (any cause) gets logged, and the
            # loop keeps going instead of the whole background job dying.
            logger.exception("Error during this poll cycle — will retry next interval.")
        time.sleep(POLL_INTERVAL_SECONDS)


def run_backfill(target_date: date, headless: bool = True, force: bool = False) -> int:
    """
    Catch-up pass for one past date: find every PRID PIB lists for that
    day, skip anything already SAVED FOR THIS SPECIFIC DAY, fetch+clean+
    save the rest.

    Unlike run_once() (which checks the global seen_prids.txt, since RSS
    doesn't know an article's date until after fetching it), backfill
    already knows the target date up front — so instead of a separate
    tracking file that could drift out of sync with reality, it checks
    what's ACTUALLY sitting in that day's saved file. This is what makes
    backfill self-correcting: delete data/processed/<date>.json, and this
    naturally treats everything as new again on the next run, no --force
    or manual seen_prids.txt editing required.

    force=True still exists as an explicit override for the rare case
    you want to re-fetch even PRIDs that ARE still saved (e.g. you
    suspect the saved content is stale/wrong and want a fresh copy).
    """
    releases = backfill_day(target_date, headless=headless)

    if force:
        new_prids = [r.prid for r in releases]
        logger.info(f"Backfill {target_date}: --force used, re-fetching all {len(new_prids)} release(s)")
    else:
        already_saved = get_saved_prids_for_day(target_date.year, target_date.month, target_date.day)
        new_prids = [r.prid for r in releases if r.prid not in already_saved]
        if not new_prids:
            logger.info(f"Backfill {target_date}: nothing new — already had all {len(releases)} release(s).")
            return 0
        logger.info(f"Backfill {target_date}: found {len(new_prids)} release(s) that were missed: {new_prids}")

    articles = fetch_articles(new_prids)  # Bronze already saved inside fetch_articles()
    save_silver_articles(articles)        # this is the cleaned + deduped result
    mark_seen(new_prids)                  # still update the global log too, so RSS polling won't redo this work
    return len(new_prids)


if __name__ == "__main__":
    # argparse builds a proper --flag command-line interface for us,
    # including automatic --help text, instead of us hand-parsing
    # sys.argv ourselves.
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true", help="poll continuously instead of running once")
    parser.add_argument("--backfill", metavar="YYYY-MM-DD", help="catch-up fetch for one past date")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="run --backfill without a visible browser (not recommended on Windows — see backfill_fetcher.py notes)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="with --backfill, re-fetch everything for that date even if seen_prids.txt says it's already done",
    )
    args = parser.parse_args()

    if args.backfill:
        target = datetime.strptime(args.backfill, "%Y-%m-%d").date()
        # Defaults to VISIBLE now, not headless — headless Chromium gets
        # blocked on allRel.aspx inconsistently even with anti-detection
        # tweaks applied (realistic User-Agent, disabled automation flag,
        # normal viewport). The real fix (Xvfb) only works on Linux, so on
        # Windows, visible is just the practical everyday choice.
        run_backfill(target, headless=args.headless, force=args.force)
    elif args.loop:
        run_loop()
    else:
        run_once()