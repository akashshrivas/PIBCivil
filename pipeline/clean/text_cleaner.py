"""
text_cleaner.py
================

WHAT THIS FILE DOES (in one sentence):
Takes the messy title/ministry/body_text fields inside a RawArticle
(straight out of parsing) and returns a NEW RawArticle where those same
fields are tidied up — no leftover encoding glitches, no leftover
"read this in other languages" footer text, no weird extra blank lines.

WHY THIS EXISTS (the actual problem it solves):
When you open a saved data/raw/*.json file and read the body_text field,
you'll notice two annoying things:
  1. Occasional garbled characters, like â€™ appearing instead of a
     normal apostrophe ’. This happens because PIB's old servers
     sometimes serve text in one encoding while claiming a different
     one — when that mismatch happens, quote marks and dashes get
     mangled into these strange character sequences.
  2. A leftover sentence like "Read this release in: Hindi , Urdu ,
     Punjabi" sitting at the end of the body text. pib_parser.py
     already pulls the actual translation LINKS out into their own
     field (article.translations) — but the sentence announcing them
     is still sitting inside the body text itself, because it's just
     plain visible text on the page, not a link.

This file fixes both problems. Nothing here touches the network and
nothing here changes what pib_parser.py already extracted correctly —
this stage only cleans up the text that stage already got right in
substance, but not yet in presentation.
"""

# --- IMPORTS -----------------------------------------------------------
# Standard library import: 're' is Python's built-in regular expression
# module. We use it below to find and remove specific unwanted patterns
# of text (like the "Read this release in:" sentence).
import re

# Third-party import: 'ftfy' is a small library whose entire job is
# fixing exactly the kind of garbled-encoding text problem described
# above. Its main function is literally called fix_text().
# (If this import fails, run: pip install ftfy)
import ftfy

# This is a "sibling folder" import, same rule as everywhere else in
# this project: parse/ and clean/ are both direct children of pipeline/,
# so we reach across with a plain absolute import, never a relative
# '..' one.
from parse.pib_parser import RawArticle


# --- CONSTANTS -----------------------------------------------------------
# This one matches the "(Release ID: 2312498)" footer line that shows up
# INSIDE body_text — even though pib_parser.py already extracts this same
# number into its own `prid` field, the sentence announcing it is still
# sitting in the plain visible text of the page, so it ends up duplicated
# inside body_text too.
#   \(              -> matches a literal opening parenthesis (escaped with
#                       \ because ( normally means "start of a capture
#                       group" in regex — \( means "an actual ( character")
#   Release ID:\s*\d+  -> the words "Release ID:", then the number
#   \)               -> a literal closing parenthesis
RELEASE_ID_LINE_RE = re.compile(r"\(Release ID:\s*\d+\)", re.IGNORECASE)

# This one matches the "Posted On: 19 SEP 2026 6:40PM by PIB Delhi" line —
# same duplication problem as above: pib_parser.py already pulls the date
# out into posted_on_raw, but this whole sentence is still sitting in the
# plain page text.
#   Posted On:.*?by PIB\s*\w*   -> "Posted On:", then (non-greedy) any
#                                   characters, then "by PIB" and
#                                   optionally one more word (the city
#                                   name, e.g. "Delhi")
POSTED_ON_LINE_RE = re.compile(r"Posted On:.*?by PIB\s*\w*", re.IGNORECASE)

# This matches "Read this release in:" and everything up to the end of
# that line/paragraph — see _remove_translation_footer() below for the
# full breakdown of how this pattern works.
TRANSLATION_FOOTER_RE = re.compile(
    r"Read this release in.*?(?=\n|$)",
    re.IGNORECASE,
)


# --- HELPER FUNCTIONS ----------------------------------------------------

def _fix_encoding(text: str) -> str:
    """
    Fixes garbled characters like â€™ back into their correct form (’).

    ftfy.fix_text() is smart about this: it detects the specific kind of
    encoding mismatch that happened and reverses it. We don't need to
    know or handle the details ourselves — that's the whole point of
    using this library instead of writing our own fix-up rules.
    """
    return ftfy.fix_text(text)


def _remove_metadata_lines(text: str) -> str:
    """
    Removes the "Posted On: ... by PIB Delhi" and "(Release ID: 12345)"
    lines from body_text — since that same information already lives in
    article.posted_on_raw and article.prid, leaving it in the body text
    too is just noise for anything (like the future classify/ stage)
    that reads body_text to understand what the article is actually about.
    """
    text = POSTED_ON_LINE_RE.sub("", text)
    text = RELEASE_ID_LINE_RE.sub("", text)
    return text


def _remove_translation_footer(text: str) -> str:
    """
    Deletes the "Read this release in: Hindi, Urdu..." sentence, if present.

    re.sub(pattern, replacement, text) means: "find every place in
    `text` that matches `pattern`, and replace it with `replacement`."
    Here, replacement is an empty string "" — so every match just gets
    deleted, leaving nothing behind in its place.
    """
    return TRANSLATION_FOOTER_RE.sub("", text)


def _collapse_whitespace(text: str) -> str:
    """
    Turns messy spacing into clean, consistent spacing.

    After deleting the translation footer above, you can be left with
    extra blank lines where that sentence used to be (like pulling a
    book off a shelf and leaving an empty gap). This function tidies
    that up:
      - re.sub(r"[ \t]+", " ", text)
            Replaces any run of spaces/tabs with a single space.
            (r"[ \t]+" means "one or more spaces or tab characters")
      - re.sub(r"\n{3,}", "\n\n", text)
            Replaces 3-or-more newlines in a row with just 2 (so
            paragraphs stay separated, but you don't get 5 blank lines
            stacked on top of each other).
      - .strip()
            Removes any leading/trailing whitespace from the very
            start and end of the whole text.
    """
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_text(text: str | None) -> str | None:
    """
    The main "clean one piece of text" function. Runs all three fixes
    above, in order, on a single string.

    Why check `if text is None` first: title/ministry/body_text can all
    genuinely be None (for example, if parsing couldn't find a title on
    a particular page). Trying to run string operations like .strip() on
    None would crash with an error, so we short-circuit and just return
    None right back out — "there's nothing to clean, so don't try."
    """
    if text is None:
        return None

    text = _fix_encoding(text)
    text = _remove_metadata_lines(text)
    text = _remove_translation_footer(text)
    text = _collapse_whitespace(text)
    return text


# --- MAIN ENTRY POINT ----------------------------------------------------

def clean_article(article: RawArticle) -> RawArticle:
    """
    Takes one RawArticle (straight from parsing) and returns a NEW
    RawArticle with title/ministry/body_text all cleaned.

    Important design choice: this does NOT modify `article` in place —
    it builds and returns a brand new object instead. This matters
    because of a principle we've used everywhere else in this project:
    a function that doesn't change its input and always gives the same
    output for the same input (a "pure function") is much easier to
    test and reason about, since you never have to worry about "wait,
    did something already change this object earlier?"

    `article.model_copy(update={...})` is a pydantic method: it makes a
    full copy of `article`, then overwrites just the fields you list in
    `update`, leaving everything else (prid, url, translations, etc.)
    exactly as it was.
    """
    return article.model_copy(
        update={
            "title": clean_text(article.title),
            "ministry": clean_text(article.ministry),
            "body_text": clean_text(article.body_text),
        }
    )


def clean_articles(articles: list[RawArticle]) -> list[RawArticle]:
    """
    Convenience function for cleaning a whole batch at once — used by
    pipeline.py once this stage is wired in. This is just a list
    comprehension (explained in code-walkthrough.md) applying
    clean_article() to every item.
    """
    return [clean_article(article) for article in articles]


# --- QUICK MANUAL TEST ----------------------------------------------------
# This block only runs if you execute this file directly
# (python pipeline/clean/text_cleaner.py) — it does NOT run when this
# file is imported by pipeline.py. It's here so you can sanity-check
# the cleaning logic instantly, without needing any real scraped data.
if __name__ == "__main__":
    from parse.pib_parser import RawArticle  # re-imported here just for this standalone test

    messy_article = RawArticle(
        prid="9999999",
        url="https://example.com",
        title="Cabinet approves new scheme",
        body_text=(
            "The Cabinet today approved a new scheme for farmers.\n\n\n\n"
            "It   will    benefit millions.\n"
            "Read this release in: Hindi , Urdu , Punjabi"
        ),
    )

    cleaned = clean_article(messy_article)
    print("BEFORE:")
    print(repr(messy_article.body_text))
    print("\nAFTER:")
    print(repr(cleaned.body_text))