"""
rss_fetcher.py — reads PIB's RSS feed to discover press release IDs, with an
optional pass to attach real publish dates.

PIB's feed:  https://pib.gov.in/RssMain.aspx?ModId=6&reg=3&lang=1
  - ModId=6  -> press releases (ModId=8 is photos, ModId=10 is media advisories)
  - reg/lang -> region/language. IMPORTANT: I could not independently confirm
                these actually switch the feed to English — my own test fetches
                of this exact endpoint returned identical Hindi content for every
                combination of reg/lang/Regid/Lang I tried, which looks like a
                caching layer on my end rather than the live server's real
                behaviour. The lowercase `reg=3&lang=1` pattern IS confirmed
                correct for the article pages (PressReleasePage.aspx), found in
                links inside PIB's own published PDFs — but verify against this
                RSS endpoint yourself with a fresh, non-cached request before
                trusting it.

KNOWN GAP: the feed itself has no <pubDate>/<guid> — only <title> and <link>.
There is no way to get a real publish date without also fetching the article
page. `discover_from_rss()` gives you PRIDs fast with no date. `run(with_dates=True)`
fetches each article too (reusing article_fetcher's date parsing) so you get a
real "Posted On" value, at the cost of one extra HTTP request per item.
"""

import re
from dataclasses import dataclass

import feedparser
import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

try:
    from .article_fetcher import fetch_article_html  # when imported as extract.rss_fetcher
except ImportError:
    from article_fetcher import fetch_article_html  # when run directly: python rss_fetcher.py

from parse.pib_parser import parse_fetched_page  # parse/ is a sibling of extract/, not nested inside it

RSS_URL = "https://pib.gov.in/RssMain.aspx?ModId=6&reg=3&lang=1"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

PRID_RE = re.compile(r"PRID=(\d+)", re.IGNORECASE)


@dataclass
class DiscoveredRelease:
    prid: str
    title: str
    feed_link: str
    posted_on_raw: str | None = None  # only populated when with_dates=True


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=15))
def _fetch_feed_text(client: httpx.Client, url: str) -> str:
    response = client.get(url, headers=HEADERS, timeout=20.0)
    response.raise_for_status()
    return response.text


def discover_from_rss(client: httpx.Client, url: str = RSS_URL) -> list[DiscoveredRelease]:
    """Fetch and parse PIB's RSS feed into a list of discovered releases (no dates)."""
    raw_xml = _fetch_feed_text(client, url)
    parsed = feedparser.parse(raw_xml)

    if parsed.bozo:
        logger.warning(f"RSS feed parsed with warnings: {parsed.bozo_exception}")

    releases: list[DiscoveredRelease] = []
    for entry in parsed.entries:
        link = entry.get("link", "")
        match = PRID_RE.search(link)
        if not match:
            continue
        releases.append(
            DiscoveredRelease(prid=match.group(1), title=entry.get("title", ""), feed_link=link)
        )

    logger.info(f"Discovered {len(releases)} release(s) from RSS feed")
    return releases


def run(with_dates: bool = False) -> list[DiscoveredRelease]:
    """Entry point used by pipeline.py.

    with_dates=False (default): fast, just PRIDs + titles from the feed.
    with_dates=True: also fetches each article page to fill in posted_on_raw —
    slower (N extra requests), but gives you a real publish date.
    """
    with httpx.Client(follow_redirects=True) as client:
        releases = discover_from_rss(client)

        if with_dates:
            for release in releases:
                page = fetch_article_html(client, release.prid)
                article = parse_fetched_page(page)
                release.posted_on_raw = article.posted_on_raw

        return releases


if __name__ == "__main__":
    for release in run(with_dates=True):
        print(release.prid, release.posted_on_raw, release.title)