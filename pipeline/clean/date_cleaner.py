"""
date_cleaner.py — turns article_fetcher's raw "Posted On" string into a
real datetime, so storage_manager.py knows which year/month/day folder
to file a release under.

PIB's format looks like: "01 FEB 2023 1:35PM" (day, 3-letter month in any
case, year, then time with no space before AM/PM). Built defensively with
a regex rather than a single strptime format string, because PIB's exact
spacing/punctuation is not 100% consistent across old and new releases —
if you find a real PRID that fails to parse, check what's different about
its raw string and extend DATE_RE rather than special-casing it downstream.
"""

import re
from datetime import datetime

DATE_RE = re.compile(
    r"(\d{1,2})\s+([A-Za-z]{3,})\s+(\d{4})\s+(\d{1,2}):(\d{2})\s*([AP]M)",
    re.IGNORECASE,
)


def parse_posted_on(raw: str | None) -> datetime | None:
    """Return a datetime for a raw 'Posted On' string, or None if it can't be parsed."""
    if not raw:
        return None

    match = DATE_RE.search(raw)
    if not match:
        return None

    day, month_name, year, hour, minute, ampm = match.groups()
    try:
        normalized = f"{day} {month_name[:3].title()} {year} {hour}:{minute} {ampm.upper()}"
        return datetime.strptime(normalized, "%d %b %Y %I:%M %p")
    except ValueError:
        return None


if __name__ == "__main__":
    # Quick manual sanity checks.
    for sample in ["01 FEB 2023 1:35PM", "19 SEP 2026 6:40PM", "not a date"]:
        print(sample, "->", parse_posted_on(sample))