"""
pipeline.py
===========

WHAT THIS FILE DOES:
This is the "conductor" of the extract-through-Silver stage of the
pipeline. It doesn't know anything PIB-specific itself — it just calls
the other files in the right order:

    discover PRIDs -> fetch raw HTML -> parse into structured fields
        -> [BRONZE: data/raw/] -> clean the text -> drop duplicates
        -> [SILVER: data/processed/]

Summarization is DELIBERATELY NOT called from here. Per the agreed
architecture, summarize/summarizer.py runs as its own separate,
decoupled pass — it reads Silver (from R2 once that's wired up, from
data/processed/ locally for now) and writes finished summaries on its
own schedule. Keeping this file's job limited to extract-through-Silver
means there's exactly ONE place that produces Silver data, and exactly
ONE place that consumes it to produce summaries — no risk of two
different code paths racing to write the same output differently.

classify/ is also deliberately NOT part of this chain right now — it's
built and tested on its own, but parked until this core flow is solid.

Four ways to run it from the command line:
  python pipeline.py                       -> runs once (RSS-based) and exits
  python pipeline.py --loop                -> polls RSS every POLL_INTERVAL_SECONDS forever
  python pipeline.py --backfill 2026-09-15 -> catch-up fetch for one past date via
                                               the date-search page (Playwright)
  python pipeline.py --yesterday           -> same as --backfill, but the date is
                                               "yesterday by INDIAN time (IST)"
  add --headless to --backfill/--yesterday to run without a visible browser

WHY --yesterday EXISTS (timezones):
PIB dates every release in Indian time. A job that starts at 00:01 IST on
5 October is still running on 4 October in UTC (the clock of a GitHub
Actions runner or any cloud server), so "today minus one day" by the
machine's own clock would fetch 3 October — the wrong day. --yesterday
always computes the date in IST, so it gives 4 October no matter which
timezone the machine is set to.
"""

import argparse
import time
from datetime import date, datetime, timedelta, timezone

from loguru import logger

# Each import below comes from a different pipeline stage. Notice the
# pattern: every stage exposes ONE simple function that this file calls —
# pipeline.py never reaches inside another stage's internal helpers.
from extract.rss_fetcher import run as discover_releases
from extract.article_fetcher import run as fetch_raw_pages
from extract.backfill_fetcher import backfill_day
from parse.pib_parser import parse_fetched_page, RawArticle
from clean.text_cleaner import clean_article
from dedup.dedup_engine import filter_duplicates
from storage.storage_manager import save_bronze_articles, save_silver_articles, get_saved_prids_for_day
from storage.seen_tracker import load_seen, mark_seen

POLL_INTERVAL_SECONDS = 300  # 5 minutes

# India Standard Time is UTC+05:30 all year and has NO daylight saving, so a
# fixed offset is exactly right (and needs no timezone database, which
# Windows Python does not ship with).
IST = timezone(timedelta(hours=5, minutes=30))


def yesterday_ist(now: datetime | None = None) -> date:
    """
    Yesterday's calendar date in Indian time, whatever timezone this machine
    uses. `now` is only a parameter so the logic can be tested with a fake
    clock; normally leave it out.

    Example: at 18:31 UTC on 5 Oct it is 00:01 IST on 6 Oct,
    so this returns 5 Oct (while "UTC today minus one" would wrongly say 4 Oct).
    """
    now = now or datetime.now(timezone.utc)
    return (now.astimezone(IST) - timedelta(days=1)).date()


def fetch_articles(prids: list[str]):
    """
    Runs a batch of PRIDs through fetch -> parse -> [BRONZE SAVE] ->
    clean -> dedup, and returns the cleaned+deduped list for the caller
    to Silver-save.

    ROBUSTNESS NOTE: parsing and cleaning are wrapped in per-article
    try/except below. Without this, one malformed article raising an
    exception inside a plain list comprehension would crash the ENTIRE
    batch — losing the Bronze save for every other article that parsed
    fine, and (in --loop mode) never calling mark_seen(), which would
    cause the exact same crash to repeat forever on every future poll
    until the bad PRID eventually ages out of the RSS feed. Isolating
    failures per-article means one bad article is logged and skipped
    (as fetched_ok=False, same pattern article_fetcher.py already uses
    for network failures) while everything else proceeds normally.
    """
    pages = fetch_raw_pages(prids)

    parsed_articles = []
    for page in pages:
        try:
            parsed_articles.append(parse_fetched_page(page))
        except Exception:
            logger.exception(f"PRID {page.prid}: failed to parse — marking as failed, continuing batch")
            parsed_articles.append(RawArticle(prid=page.prid, url=page.url, fetched_ok=False))

    # BRONZE: save exactly what parsing produced, before any cleaning
    # or dedup — duplicates, messy text, and failed-parse stubs included,
    # on purpose (Bronze is the untouched historical record).
    save_bronze_articles(parsed_articles)

    cleaned_articles = []
    for article in parsed_articles:
        try:
            cleaned_articles.append(clean_article(article))
        except Exception:
            logger.exception(f"PRID {article.prid}: failed to clean — keeping uncleaned version, continuing batch")
            cleaned_articles.append(article)

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
    save_silver_articles(articles)        # cleaned + deduped — summarization runs separately, later

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
    save_silver_articles(articles)        # cleaned + deduped — summarization runs separately, later

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
        "--yesterday",
        action="store_true",
        help="catch-up fetch for yesterday, where 'yesterday' is by Indian time (IST), "
             "whatever timezone this machine uses",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="run --backfill without a visible browser (not recommended on Windows — see backfill_fetcher.py notes)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="with --backfill, re-fetch everything for that date even if already saved for that day",
    )
    args = parser.parse_args()

    if args.backfill and args.yesterday:
        parser.error("use either --backfill DATE or --yesterday, not both")

    if args.backfill or args.yesterday:
        if args.yesterday:
            target = yesterday_ist()
        else:
            target = datetime.strptime(args.backfill, "%Y-%m-%d").date()

        logger.info(f"Target day: {target} (Indian date)")

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