"""
backfill_range.py
==================

WHAT THIS FILE DOES:
Runs pipeline.py's run_backfill() once for EVERY day in a date range,
so you can test the whole pipeline against a full month of real
historical data with one command, instead of typing
`python pipeline.py --backfill <date>` thirty separate times by hand.

WHY A SEPARATE SCRIPT, NOT JUST A LOOP IN pipeline.py ITSELF:
pipeline.py's job is running ONE pipeline action (once, in a loop, or
for one backfill date) -- that's deliberately its whole scope. "Run
many backfills in sequence" is a different concern (it needs its own
summary reporting, its own pacing/delay logic, its own per-day failure
handling) layered ON TOP of what pipeline.py already does, not folded
into it. Keeping it separate means pipeline.py stays simple, and this
file can import and reuse run_backfill() exactly as-is.

WHY A DELAY BETWEEN DAYS:
Running 30 backfills back-to-back with no pause means 30 rounds of
Playwright launching a browser and hitting PIB's server in quick
succession. A small pause between each day is just being a considerate
client of someone else's government server, not a strict technical
requirement.

WHY ONE DAY'S FAILURE DOESN'T STOP THE WHOLE MONTH:
Same "fail as data, not as crashes" principle used throughout this
project (see pipeline.py's fetch_articles() for the per-article version
of this same idea). A browser hiccup on, say, April 15th shouldn't
throw away the 29 other days of real data this run could otherwise
collect -- it gets logged and the script moves on, with a final summary
telling you exactly which day(s) to retry individually afterward.
"""

import argparse
import time
from datetime import date, datetime, timedelta

from loguru import logger

from pipeline import run_backfill


def _daterange(start: date, end: date):
    """Yields every date from start to end, inclusive of both ends."""
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def backfill_range(
    start: date,
    end: date,
    headless: bool = False,
    force: bool = False,
    delay_seconds: float = 4.0,
) -> dict[date, tuple[str, int]]:
    """
    Runs run_backfill() for every day from start to end.

    Returns a dict of {date: (status, article_count)}, where status is
    "ok" or "failed" -- used to print the end-of-run summary, and handed
    back to the caller in case a test/script wants to inspect results
    programmatically rather than just reading the printed log.
    """
    results: dict[date, tuple[str, int]] = {}
    total_days = (end - start).days + 1

    for i, day in enumerate(_daterange(start, end), start=1):
        logger.info(f"=== [{i}/{total_days}] Backfilling {day} ===")
        try:
            count = run_backfill(day, headless=headless, force=force)
            results[day] = ("ok", count)
        except Exception:
            # Broad except is intentional HERE (same reasoning as
            # pipeline.py's run_loop()): this is the outermost safety
            # net for a long, unattended multi-day batch. One bad day,
            # whatever the cause, gets logged and the run continues.
            logger.exception(f"Backfill FAILED for {day} -- continuing to next day")
            results[day] = ("failed", 0)

        # Skip the delay after the very last day -- no point pausing
        # when there's nothing left to be polite about.
        if i < total_days:
            time.sleep(delay_seconds)

    _print_summary(start, end, results)
    return results


def _print_summary(start: date, end: date, results: dict[date, tuple[str, int]]) -> None:
    ok_days = [d for d, (status, _) in results.items() if status == "ok"]
    failed_days = [d for d, (status, _) in results.items() if status == "failed"]
    total_articles = sum(count for _, count in results.values())

    logger.info("=" * 60)
    logger.info(f"BACKFILL RANGE COMPLETE: {start} to {end}")
    logger.info(f"Days succeeded : {len(ok_days)} / {len(results)}")
    logger.info(f"Total NEW articles saved across the range: {total_articles}")
    if failed_days:
        failed_str = ", ".join(str(d) for d in failed_days)
        logger.warning(f"Failed day(s) -- retry individually: {failed_str}")
        for d in failed_days:
            logger.warning(f"  python pipeline.py --backfill {d}")
    logger.info("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill every day in a date range.")
    parser.add_argument("--start", required=True, metavar="YYYY-MM-DD")
    parser.add_argument("--end", required=True, metavar="YYYY-MM-DD")
    parser.add_argument("--headless", action="store_true", help="run without a visible browser")
    parser.add_argument("--force", action="store_true", help="re-fetch days even if already saved")
    parser.add_argument("--delay", type=float, default=4.0, help="seconds to pause between days")
    args = parser.parse_args()

    start_date = datetime.strptime(args.start, "%Y-%m-%d").date()
    end_date = datetime.strptime(args.end, "%Y-%m-%d").date()

    if end_date < start_date:
        raise SystemExit("--end must not be before --start")

    backfill_range(start_date, end_date, headless=args.headless, force=args.force, delay_seconds=args.delay)