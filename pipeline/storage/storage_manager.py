"""
storage_manager.py
===================

WHAT THIS FILE DOES:
Saves articles to disk, one JSON file per day (an array of that day's
articles), nested by year/month — but now into ONE OF TWO possible
folders depending on which "layer" of the medallion architecture the
data represents:

    data/raw/<YYYY>/<MM>/<DD>.json         <- BRONZE: exactly what came
                                                out of parsing, untouched
                                                by clean/dedup
    data/processed/<YYYY>/<MM>/<DD>.json   <- SILVER: the cleaned AND
                                                deduplicated version

WHY THIS SPLIT MATTERS (the mistake this fixes):
Earlier, only ONE save happened — after clean+dedup had already run —
so data/raw/ was secretly holding already-cleaned data, not a true
untouched snapshot. That breaks the whole point of a Bronze layer: if
you ever find a bug in text_cleaner.py, you need the ORIGINAL messy
text still sitting somewhere so you can re-clean it correctly. Now,
pipeline.py calls save_bronze_articles() right after parsing (before
clean/dedup ever touch the data), and save_silver_articles() separately
afterward, once clean+dedup have actually run.

Bronze also deliberately keeps duplicates that dedup/ would otherwise
remove — that's correct medallion practice: Bronze is the permanent,
complete historical record of everything that was ever fetched; Silver
is the "the useful, deduplicated version" built FROM Bronze.

Both layers reuse the exact same day-file merge logic (load what's
there, merge new articles in by PRID, write back) — only the target
folder name differs, so the shared logic is written ONCE
(_save_articles_to_layer) and both public functions just call it with
a different `layer` argument.

If an article's date can't be parsed (date_cleaner returns None), it
goes into unknown_date.json (inside whichever layer folder) instead of
being silently dropped or guessed into today's file — guessing would
quietly misfile a real release under the wrong day.
"""

import json
from datetime import datetime
from pathlib import Path

from loguru import logger

from clean.date_cleaner import parse_posted_on
from parse.pib_parser import RawArticle

DATA_ROOT = Path(__file__).resolve().parent.parent.parent / "data"  # PIBCivil/data


def _day_file_for(dt: datetime | None, layer: str) -> Path:
    """
    Builds the path to one day's JSON file inside a given layer folder.

    `layer` is just a folder name — "raw" or "processed" — passed in by
    whichever public function called this. This is the ONE place that
    decides the actual file path, so both Bronze and Silver saving go
    through identical path-building logic and can never accidentally
    drift out of sync with each other.
    """
    if dt is None:
        return DATA_ROOT / layer / "unknown_date.json"
    return DATA_ROOT / layer / f"{dt.year:04d}" / f"{dt.month:02d}" / f"{dt.day:02d}.json"


def _load_day_file(path: Path) -> dict[str, dict]:
    """Load an existing day file as {prid: article_dict}, or empty if it doesn't exist yet."""
    if not path.exists():
        return {}
    try:
        records = json.loads(path.read_text(encoding="utf-8"))
        return {record["prid"]: record for record in records}
    except (json.JSONDecodeError, KeyError):
        logger.warning(f"{path} was unreadable/corrupt — starting fresh for this day")
        return {}


def _write_day_file(path: Path, records_by_prid: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Sort by prid for a stable, diffable file rather than insertion order.
    ordered = [records_by_prid[prid] for prid in sorted(records_by_prid)]
    path.write_text(json.dumps(ordered, indent=2, ensure_ascii=False), encoding="utf-8")


def _save_articles_to_layer(articles: list[RawArticle], layer: str) -> list[Path]:
    """
    The shared "group by day, merge, write" logic used by BOTH Bronze
    and Silver saves. Neither save_bronze_articles() nor
    save_silver_articles() below duplicate this logic themselves — they
    just call this function with a different `layer` name.
    """
    articles_by_day_file: dict[Path, list[RawArticle]] = {}
    for article in articles:
        posted_dt = parse_posted_on(article.posted_on_raw)
        day_file = _day_file_for(posted_dt, layer)
        articles_by_day_file.setdefault(day_file, []).append(article)
        if posted_dt is None:
            logger.warning(f"PRID {article.prid}: couldn't parse date, filed under {layer}/unknown_date.json")

    written_paths = []
    for day_file, day_articles in articles_by_day_file.items():
        existing = _load_day_file(day_file)
        for article in day_articles:
            existing[article.prid] = json.loads(article.model_dump_json())  # merge/replace by prid
        _write_day_file(day_file, existing)
        logger.info(f"{day_file.relative_to(DATA_ROOT)}: {len(existing)} article(s) total")
        written_paths.append(day_file)

    return written_paths


def save_bronze_articles(articles: list[RawArticle]) -> list[Path]:
    """
    BRONZE save — call this with articles straight from parsing, BEFORE
    clean/dedup have touched them. This is meant to be a permanent,
    untouched historical record: every article ever fetched, exactly as
    parsed, duplicates included.
    """
    return _save_articles_to_layer(articles, layer="raw")


def save_silver_articles(articles: list[RawArticle]) -> list[Path]:
    """
    SILVER save — call this with articles AFTER clean/dedup have both
    run. This is the "useful" version: tidied text, no cross-PRID
    duplicates.
    """
    return _save_articles_to_layer(articles, layer="processed")


def get_saved_prids_for_day(year: int, month: int, day: int, layer: str = "processed") -> set[str]:
    """
    Returns the set of PRIDs already saved for one specific day, read
    directly from that day's actual JSON file — not from a separate
    tracking log. This is what makes backfill's "is this already done?"
    check self-correcting: if you delete data/processed/2026/09/13.json,
    this naturally returns an empty set for that day, and backfill will
    correctly treat everything as new again. There's nothing extra to
    remember to clean up in sync with the data file, because this reads
    the data file itself.
    """
    articles = list_by_day(year, month, day, layer=layer)
    return {article["prid"] for article in articles}


def list_by_day(year: int, month: int, day: int, layer: str = "raw") -> list[dict]:
    """All articles saved for one specific day, from a given layer
    (defaults to "raw" for backward compatibility — pass layer="processed"
    to read Silver instead)."""
    day_file = DATA_ROOT / layer / f"{year:04d}" / f"{month:02d}" / f"{day:02d}.json"
    if not day_file.exists():
        return []
    return json.loads(day_file.read_text(encoding="utf-8"))


def list_by_month(year: int, month: int, layer: str = "raw") -> list[dict]:
    """All articles saved across every day in one month, from a given layer."""
    month_dir = DATA_ROOT / layer / f"{year:04d}" / f"{month:02d}"
    if not month_dir.exists():
        return []
    articles = []
    for day_file in sorted(month_dir.glob("*.json")):
        articles.extend(json.loads(day_file.read_text(encoding="utf-8")))
    return articles