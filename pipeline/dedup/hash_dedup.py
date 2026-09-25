"""
hash_dedup.py
=============

WHAT THIS FILE DOES:
Turns one article's content into a single short "fingerprint" string
(a hash). Two articles with the exact same title+body will ALWAYS
produce the exact same fingerprint — that's the whole trick dedup_engine.py
relies on: instead of comparing full article text against every other
article one by one (slow, and awkward to store), we just compare these
short fingerprints, which is instant.

This file only computes the fingerprint. It doesn't decide what to DO
with duplicates (skip them, log them, etc.) — that decision-making logic
lives in dedup_engine.py, kept separate on purpose: "how do I fingerprint
one article" and "what do I do with a batch of fingerprints" are two
different jobs.
"""

# hashlib is Python's built-in library for hashing — turning any amount
# of text into a fixed-length string of letters/numbers that uniquely
# represents it. The same input text ALWAYS produces the same hash, and
# even a tiny change (one different letter) produces a completely
# different hash.
import hashlib

from parse.pib_parser import RawArticle


def _normalize_for_hashing(text: str | None) -> str:
    """
    Before hashing, we squash away differences that don't represent a
    REAL difference in content — like whether a word is capitalized, or
    how many spaces sit between two words. Without this step, "Cabinet
    Approves Scheme" and "cabinet   approves scheme" would hash
    differently and wrongly look like two unrelated articles, even
    though they're clearly the same content.

    .lower()          -> makes everything lowercase
    .split()          -> splits the text into a list of words, and
                          conveniently also throws away ALL whitespace
                          differences (single spaces, tabs, newlines,
                          multiple spaces) in the process
    " ".join(...)     -> puts the words back together with exactly one
                          space between each, so the final result has
                          perfectly consistent spacing no matter how
                          the original text was formatted
    """
    if text is None:
        return ""
    return " ".join(text.lower().split())


def compute_content_hash(article: RawArticle) -> str:
    """
    Builds one fingerprint string for an article, based on its title
    and body text combined (ministry/date are deliberately left out —
    two ministries jointly announcing the same thing might each list
    themselves as "the" ministry, so including that field could make
    genuine duplicates look different).

    hashlib.sha256(...)   -> creates a SHA-256 hash object. SHA-256 is a
                              standard, reliable hashing algorithm — the
                              same one used all over the place (Git commit
                              hashes, password storage, file integrity
                              checks). We don't need anything fancier
                              than this for our purposes.
    .encode("utf-8")      -> hashlib works on BYTES, not on Python text
                              (str) directly, so we convert the string
                              into its UTF-8 byte representation first.
    .hexdigest()          -> converts the hash's internal binary result
                              into a readable string of hex characters
                              (like "a3f5c9..."), which is what actually
                              gets stored and compared.
    """
    normalized_title = _normalize_for_hashing(article.title)
    normalized_body = _normalize_for_hashing(article.body_text)

    # Combining title+body with a separator between them, so that
    # (for example) title="AB" + body="CD" doesn't accidentally hash the
    # same as title="A" + body="BCD" — the separator keeps the two
    # fields distinct even after being joined into one string.
    combined = f"{normalized_title}||{normalized_body}"

    return hashlib.sha256(combined.encode("utf-8")).hexdigest()