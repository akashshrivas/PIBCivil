"""
pib_parser.py — turns one FetchedPage's raw HTML into a structured RawArticle.

This is exactly the parsing logic that used to live inside
article_fetcher.py — moved here unchanged, so extract/ only fetches and
parse/ only structures. Confirmed by inspecting a live page
(PressReleasePage.aspx?PRID=1895315): the page is plain server-rendered
HTML with a reasonably consistent shape:
  - a heading with the ministry name
  - an <h2>-ish title
  - a "Posted On: <date> <time> by PIB <city>" line
  - the body text
  - a "(Release ID: <prid>)" footer line
  - links to translations in other languages

CSS selectors below are written defensively (multiple fallbacks) because
PIB's markup is old and inconsistent across years of releases — verify
against a handful of real pages and adjust if a field comes back empty.
"""

import re
from dataclasses import field

from bs4 import BeautifulSoup
from pydantic import BaseModel

from extract.article_fetcher import FetchedPage  # extract/ is a sibling of parse/, not nested inside it

BASE_URL = "https://www.pib.gov.in"

RELEASE_ID_RE = re.compile(r"Release ID:\s*(\d+)", re.IGNORECASE)
POSTED_ON_RE = re.compile(r"Posted On:\s*([^\n]+?)\s+by PIB", re.IGNORECASE)


class RawArticle(BaseModel):
    """Structured record produced by parsing — this is what gets saved to data/raw/."""

    prid: str
    url: str
    ministry: str | None = None
    title: str | None = None
    posted_on_raw: str | None = None
    body_text: str | None = None
    translations: dict[str, str] = field(default_factory=dict)
    fetched_ok: bool = True


def _extract_ministry(soup: BeautifulSoup) -> str | None:
    # Ministry name typically appears as a heading right above the title.
    for tag in soup.find_all(["h3", "h4", "strong"]):
        text = tag.get_text(strip=True)
        if text.lower().startswith("ministry of") or "secretariat" in text.lower():
            return text
    return None


def _extract_title(soup: BeautifulSoup) -> str | None:
    for tag in soup.find_all(["h1", "h2"]):
        text = tag.get_text(strip=True)
        if text:
            return text
    return None


def _extract_translations(soup: BeautifulSoup) -> dict[str, str]:
    translations = {}
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        text = anchor.get_text(strip=True)
        if "PressReleasePage.aspx?PRID=" in href and text and text.isalpha():
            translations[text] = href if href.startswith("http") else f"{BASE_URL}/{href.lstrip('/')}"
    return translations


def parse_article(prid: str, url: str, html: str) -> RawArticle:
    """Pure function: HTML text in, structured RawArticle out. No network,
    no I/O — this is exactly what makes it fast to test against saved
    HTML samples without hitting PIB at all."""
    soup = BeautifulSoup(html, "lxml")
    full_text = soup.get_text("\n", strip=True)

    posted_on_match = POSTED_ON_RE.search(full_text)
    release_id_match = RELEASE_ID_RE.search(full_text)

    # Prefer the main content container if present; fall back to whole page text.
    content_div = soup.find("div", attrs={"class": re.compile("content|innerContent", re.I)})
    body_text = content_div.get_text("\n", strip=True) if content_div else full_text

    return RawArticle(
        prid=release_id_match.group(1) if release_id_match else prid,
        url=url,
        ministry=_extract_ministry(soup),
        title=_extract_title(soup),
        posted_on_raw=posted_on_match.group(1).strip() if posted_on_match else None,
        body_text=body_text,
        translations=_extract_translations(soup),
    )


def parse_fetched_page(page: FetchedPage) -> RawArticle:
    """Bridges extract's output to parse's job. If the fetch itself failed,
    there's no HTML to parse — pass the failure straight through instead
    of calling parse_article() on nothing."""
    if not page.fetched_ok or page.html is None:
        return RawArticle(prid=page.prid, url=page.url, fetched_ok=False)
    return parse_article(page.prid, page.url, page.html)


if __name__ == "__main__":
    # Quick manual test using a saved HTML sample — no network needed.
    # Replace this with a real saved .html file once you have one handy.
    sample_html = "<html><body><h1>Test Title</h1><p>Posted On: 01 FEB 2023 1:35PM by PIB Delhi</p></body></html>"
    result = parse_article("1234567", "https://example.com", sample_html)
    print(result.model_dump_json(indent=2))