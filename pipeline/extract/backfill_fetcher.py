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

FIX (5 Oct 2026) — "Unable to retrieve content because the page is
navigating":
  The old code called page.wait_for_load_state("networkidle") right after
  each select_option(). But the postback navigation starts a moment AFTER
  the selection, so on a slow connection (GitHub's servers are far from
  PIB) "networkidle" reported "idle" about the OLD page straight away, the
  code raced ahead, and page.content() ran in the middle of the real
  reload. A fixed 1-second pause only hid this on fast connections.
  Now each selection stamps the current page with a marker and waits for
  the marker to disappear, which can only happen once the NEW page has
  loaded — however long that takes. The final values are also checked, and
  a screenshot is saved if anything still goes wrong.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime

from bs4 import BeautifulSoup
from loguru import logger
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright
from tenacity import retry, stop_after_attempt, wait_exponential

ALL_RELEASES_URL = "https://pib.gov.in/allRel.aspx?reg=48&lang=1"

DAY_SELECT = "#ContentPlaceHolder1_ddlday"      # confirmed
MONTH_SELECT = "#ContentPlaceHolder1_ddlMonth"  # confirmed (capital M)
YEAR_SELECT = "#ContentPlaceHolder1_ddlYear"    # confirmed (capital Y)

# How long to wait for ONE dropdown's page reload (slow links can take a while).
POSTBACK_TIMEOUT_MS = 60_000

PRID_RE = re.compile(r"PRID=(\d+)", re.IGNORECASE)


@dataclass
class DiscoveredRelease:
    prid: str
    title: str | None
    url: str


def _select_and_wait_for_reload(page, selector: str, value: str) -> None:
    """
    Choose a dropdown value, then wait until the page has REALLY reloaded.

    How it works: set a flag on the current page's `window`, make the
    selection, and wait for the flag to be gone. A reload throws the old
    page away, so the flag only disappears once the new page exists.
    """
    page.evaluate("() => { window.__awaiting_postback = true; }")
    page.select_option(selector, value=value)

    try:
        page.wait_for_function(
            "() => !window.__awaiting_postback", timeout=POSTBACK_TIMEOUT_MS
        )
    except PlaywrightTimeoutError:
        # No reload happened (e.g. the value was already selected). Carry on;
        # the final check below still verifies the filter really was applied.
        logger.warning(f"{selector}: no page reload after selecting {value!r} — continuing")

    page.wait_for_load_state("networkidle")
    page.wait_for_selector(selector, state="visible", timeout=15000)


def _content_when_stable(page, attempts: int = 10) -> str:
    """page.content(), retried if the page is still mid-navigation."""
    last_error = None
    for _ in range(attempts):
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
            return page.content()
        except PlaywrightError as e:  # includes timeouts
            last_error = e
            page.wait_for_timeout(1000)
    raise last_error


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=3, max=20))
def backfill_day(target_date: date, headless: bool = True) -> list[DiscoveredRelease]:
    """Drive allRel.aspx's day/month/year dropdowns for one date and return every PRID found."""
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = None
        try:
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
            # for the page to REALLY reload after EACH one before touching the
            # next — otherwise the next select's element may have been replaced
            # by the postback and Playwright will fail to find it.
            _select_and_wait_for_reload(page, DAY_SELECT, str(target_date.day))
            _select_and_wait_for_reload(page, MONTH_SELECT, str(target_date.month))
            _select_and_wait_for_reload(page, YEAR_SELECT, str(target_date.year))

            # Make sure the page really shows the date we asked for.
            expected = (str(target_date.day), str(target_date.month), str(target_date.year))
            actual = (
                page.input_value(DAY_SELECT),
                page.input_value(MONTH_SELECT),
                page.input_value(YEAR_SELECT),
            )
            if actual != expected:
                raise RuntimeError(
                    f"dropdowns show day/month/year {actual}, expected {expected} — filter not applied"
                )

            html = _content_when_stable(page)

        except Exception as e:
            logger.warning(f"Backfill attempt for {target_date} failed: {e}")
            if page is not None:
                try:
                    page.screenshot(path="debug_allrel_failed.png", full_page=True)
                except Exception:
                    pass
            raise
        finally:
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