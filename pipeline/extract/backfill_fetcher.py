"""
backfill_fetcher.py — gets ALL PRIDs for a specific past date, by driving
PIB's date filter dropdowns on allRel.aspx with a real (headless) browser.

CONFIRMED (via browser Inspect, 20 Sep 2026):
  - URL:  https://pib.gov.in/allRel.aspx?reg=48&lang=1
  - The date filter is THREE separate <select> dropdowns (Day/Month/Year),
    not a text field + search button. Each one's onchange fires
    __doPostBack directly -> selecting a value reloads the page with that
    filter applied. There is no separate "Search" button to click.
  - Day dropdown id:   ContentPlaceHolder1_ddlday
  - Month dropdown id: ContentPlaceHolder1_ddlMonth  (capital M)
  - Year dropdown id:  ContentPlaceHolder1_ddlYear   (capital Y)
  - All three use plain numeric values (day: 1-31 not zero-padded,
    month: 1-12, year: e.g. 2026) — matches str(target_date.day/month/year)
    as already used below, no further changes needed there.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime

from bs4 import BeautifulSoup
from loguru import logger
from playwright.sync_api import sync_playwright
from tenacity import retry, stop_after_attempt, wait_exponential

ALL_RELEASES_URL = "https://pib.gov.in/allRel.aspx?reg=48&lang=1"

DAY_SELECT = "#ContentPlaceHolder1_ddlday"      # confirmed
MONTH_SELECT = "#ContentPlaceHolder1_ddlMonth"  # confirmed (capital M)
YEAR_SELECT = "#ContentPlaceHolder1_ddlYear"    # confirmed (capital Y)

PRID_RE = re.compile(r"PRID=(\d+)", re.IGNORECASE)


@dataclass
class DiscoveredRelease:
    prid: str
    title: str | None
    url: str


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=3, max=20))
def backfill_day(target_date: date, headless: bool = True) -> list[DiscoveredRelease]:
    """Drive allRel.aspx's day/month/year dropdowns for one date and return every PRID found."""
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()
        page.goto(ALL_RELEASES_URL, wait_until="networkidle")
        page.screenshot(path="debug_allrel.png", full_page=True)
        page.wait_for_selector(DAY_SELECT, state="visible", timeout=15000)

        # Each select triggers its own postback (full page reload), so wait
        # for the page to settle after EACH one before touching the next —
        # otherwise the next select's element may have already been replaced
        # by the postback and Playwright will fail to find it.
        page.select_option(DAY_SELECT, value=str(target_date.day))
        page.wait_for_load_state("networkidle")

        page.select_option(MONTH_SELECT, value=str(target_date.month))
        page.wait_for_load_state("networkidle")

        page.select_option(YEAR_SELECT, value=str(target_date.year))
        page.wait_for_load_state("networkidle")

        # One more short pause here on purpose: networkidle can report
        # "settled" a moment before a trailing background request actually
        # finishes, and page.content() fails outright if called while the
        # page is still mid-navigation. A brief fixed wait is simpler and
        # more reliable here than trying to detect that exact moment.
        page.wait_for_timeout(1000)

        html = page.content()
        browser.close()

    soup = BeautifulSoup(html, "lxml")
    found: dict[str, DiscoveredRelease] = {}
    for anchor in soup.find_all("a", href=True):
        match = PRID_RE.search(anchor["href"])
        if not match:
            continue
        prid = match.group(1)
        if prid in found:
            continue
        found[prid] = DiscoveredRelease(
            prid=prid,
            title=anchor.get_text(strip=True) or None,
            url=f"https://www.pib.gov.in/PressReleasePage.aspx?PRID={prid}",
        )

    logger.info(f"Backfill for {target_date}: found {len(found)} release(s)")
    return list(found.values())


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test the backfill dropdown-driving logic for one date.")
    parser.add_argument("target_date", metavar="YYYY-MM-DD", help="date to backfill, e.g. 2026-09-17")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="run without a visible browser (default: visible, for debugging)",
    )
    args = parser.parse_args()

    target = datetime.strptime(args.target_date, "%Y-%m-%d").date()

    # headless=False by default here (opposite of pipeline.py's default) since
    # this script's whole purpose is watching the browser while you debug —
    # pass --headless once you trust it and just want a quick check.
    results = backfill_day(target, headless=args.headless)
    for r in results:
        print(r.prid, r.title)