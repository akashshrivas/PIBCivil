"""
dedup_engine.py
===============

WHAT THIS FILE DOES:
Takes a batch of cleaned articles and returns a SMALLER list with any
duplicates removed — where "duplicate" means "an article whose content
fingerprint (from hash_dedup.py) we've already seen before, either in
an earlier pipeline run or elsewhere in this same batch."

WHY THIS IS SEPARATE FROM seen_tracker.py:
seen_tracker.py already stops us from re-fetching the SAME PRID twice.
This file catches a different case: PIB sometimes publishes the exact
same announcement under TWO DIFFERENT PRIDs (for example, a joint
scheme announced by two ministries, each posting their own copy). Those
have different PRIDs — seen_tracker.py has no way to know they're
duplicates — but hash_dedup.py's fingerprint would be identical for both,
which is exactly what this file checks for.

HOW DUPLICATES ARE REMEMBERED ACROSS RUNS:
Just like seen_tracker.py's seen_prids.txt, we keep a small file on disk
(content_hashes.json) mapping each fingerprint we've ever seen to the
PRID of the FIRST article that had it. This lets us recognize a
duplicate even if it shows up in a completely separate pipeline run,
days later.
"""

import json
from pathlib import Path

from loguru import logger

from parse.pib_parser import RawArticle
from dedup.hash_dedup import compute_content_hash

# Same __file__-relative trick used in storage_manager.py and
# seen_tracker.py, so this always finds the right file regardless of
# which directory you happened to run the script from.
DATA_ROOT = Path(__file__).resolve().parent.parent.parent / "data"
HASH_FILE = DATA_ROOT / ".state" / "content_hashes.json"


def _load_known_hashes() -> dict[str, str]:
    """
    Loads the {fingerprint: prid} mapping from disk. Returns an empty
    dict if the file doesn't exist yet (i.e. this is the very first
    time dedup has ever run).
    """
    if not HASH_FILE.exists():
        return {}
    return json.loads(HASH_FILE.read_text(encoding="utf-8"))


def _save_known_hashes(hashes: dict[str, str]) -> None:
    """Writes the updated {fingerprint: prid} mapping back to disk."""
    HASH_FILE.parent.mkdir(parents=True, exist_ok=True)
    HASH_FILE.write_text(json.dumps(hashes, indent=2), encoding="utf-8")


def filter_duplicates(articles: list[RawArticle]) -> list[RawArticle]:
    """
    The main function this file exists to provide. Takes a list of
    cleaned articles, returns a new list with duplicates removed.

    Two different kinds of duplicates are checked for:
      1. "I've seen this exact content before, in an EARLIER pipeline
          run" -> checked against `known_hashes`, loaded from disk.
      2. "Two articles in THIS SAME BATCH have identical content" ->
          this can genuinely happen if, say, both a national release
          and a regional bureau's copy of it show up in the same
          backfill day. Checked by watching for repeats as we loop.

    Both cases are handled by the same simple rule: the first time we
    see a fingerprint (whether from disk or from earlier in this loop),
    we keep that article and remember its fingerprint. Every time AFTER
    that with the same fingerprint, we skip it and log which PRID it
    was a duplicate of.
    """
    known_hashes = _load_known_hashes()
    unique_articles: list[RawArticle] = []

    for article in articles:
        # A failed fetch has no real content to fingerprint — nothing
        # useful to compare, so it's never treated as a duplicate.
        # We keep it as-is and let it pass through unchanged.
        if not article.fetched_ok:
            unique_articles.append(article)
            continue

        content_hash = compute_content_hash(article)

        if content_hash in known_hashes:
            original_prid = known_hashes[content_hash]
            logger.info(
                f"Skipping PRID {article.prid} — duplicate content of PRID {original_prid}"
            )
            continue  # skip this article entirely — it does NOT go into unique_articles

        # First time seeing this fingerprint: keep the article, and
        # remember the fingerprint so any FUTURE duplicate (in this
        # batch or a later run) gets caught too.
        known_hashes[content_hash] = article.prid
        unique_articles.append(article)

    _save_known_hashes(known_hashes)

    skipped_count = len(articles) - len(unique_articles)
    if skipped_count:
        logger.info(f"Dedup: skipped {skipped_count} duplicate(s) out of {len(articles)} article(s)")

    return unique_articles