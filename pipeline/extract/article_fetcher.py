"""
article_fetcher.py — fetches ONE PIB press release page's raw HTML.

This file no longer parses anything. It only knows how to build the URL
for a PRID and get the raw HTML text back. Turning that HTML into
structured fields (title, ministry, date, body) is parse/pib_parser.py's
job now — see that file for why the split matters.
"""

from dataclasses import dataclass

import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

BASE_URL = "https://www.pib.gov.in"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


@dataclass
class FetchedPage:
    """Raw fetch result — html is None if the fetch itself failed."""

    prid: str
    url: str
    html: str | None = None
    fetched_ok: bool = True


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=15))
def _fetch_html(client: httpx.Client, url: str) -> str:
    response = client.get(url, headers=HEADERS, timeout=20.0)
    response.raise_for_status()
    return response.text


def fetch_article_html(client: httpx.Client, prid: str) -> FetchedPage:
    """Get the raw HTML for one PRID. Never raises — a failed fetch comes
    back as fetched_ok=False so callers can decide how to handle it."""
    url = f"{BASE_URL}/PressReleasePage.aspx?PRID={prid}"
    try:
        html = _fetch_html(client, url)
    except httpx.HTTPError as exc:
        logger.warning(f"Failed to fetch PRID {prid}: {exc}")
        return FetchedPage(prid=prid, url=url, html=None, fetched_ok=False)

    logger.info(f"Fetched PRID {prid} ({len(html)} chars)")
    return FetchedPage(prid=prid, url=url, html=html, fetched_ok=True)


def run(prids: list[str]) -> list[FetchedPage]:
    """Entry point used by pipeline.py — fetch raw HTML for a batch of PRIDs."""
    with httpx.Client(follow_redirects=True) as client:
        return [fetch_article_html(client, prid) for prid in prids]


if __name__ == "__main__":
    # Quick manual test — just proves fetching works, no parsing involved.
    for page in run(["1895315"]):
        print(page.prid, page.fetched_ok, len(page.html or ""))