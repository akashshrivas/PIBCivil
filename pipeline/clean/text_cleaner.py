"""
text_cleaner.py
===============

Silver-layer cleaner. Takes a RawArticle straight out of parsing and returns
a NEW RawArticle whose body_text contains ONLY the real press-release
paragraphs.

What it removes from body_text
  - the ministry line(s), the repeated title and the sub-headline lines
    (the ministry is moved into the `ministry` field instead)
  - the "Posted On: <date> by PIB <city>" block, even when it is split
    over two lines (the date fills `posted_on_raw` when that is empty)
  - the footer: "***", staff initials (SS/DK), "(Release ID: ...)",
    "Visitor Counter : ...", and "Read this release in:" together with
    the list of language names under it
  - the embedded social-media block ("... posted on X;" and the tweet
    text that repeats the article)
  - stray separator lines, repeated lines, invisible characters

What it fixes
  - garbled encoding (via ftfy), \\r\\n line endings, non-breaking spaces
  - messy spacing; paragraphs come out separated by one blank line

Why the old version left junk behind
  - "Posted On:" and the date sit on different lines in raw PIB text, but
    the old regex could not cross a line break, so it never matched.
  - It removed only the "Read this release in:" line, so the language
    names on the following lines stayed in body_text.
  - "***", initials and "Visitor Counter" were never handled.

Nothing here touches the network. Needs: pip install ftfy
"""

import difflib
import re

import ftfy

from parse.pib_parser import RawArticle


# ============================================================
# SETTINGS
# ============================================================

# Cut the embedded tweet block ("The Prime Minister's Office posted on X;"
# followed by the tweet text, which just repeats the article).
STRIP_SOCIAL_EMBEDS = True

# The sub-headlines under the title usually repeat the first paragraph.
# Set True to keep them (they are put at the start of body_text).
KEEP_SUBHEADINGS = False


# ============================================================
# PATTERNS
# ============================================================

# "Posted On:\n   27 SEP 2026 10:19AM by PIB Delhi" -- \s matches line
# breaks, so this works whether it is one line or two. The city is a single
# word so it can never swallow the first word of the article.
_POSTED_ON_RE = re.compile(
    r"Posted\s+On\s*:?\s*"
    r"(?P<date>\d{1,2}\s+[A-Za-z]{3}\s+\d{4})\s+"
    r"(?P<time>\d{1,2}:\d{2}\s*[AP]M)"
    r"(?:\s+by\s+PIB\s+[A-Za-z]+)?",
    re.IGNORECASE,
)

# First line of the footer: everything from here to the end is dropped.
_FOOTER_START_RE = re.compile(
    r"^(?:\(?\s*Release ID\b.*|Visitor Counter\b.*|Read this release in\b.*)$",
    re.IGNORECASE,
)

# "***", "* * *"
_STAR_LINE_RE = re.compile(r"^[\*\s]{3,}$")

# Staff initials at the end: "SS/DK", "MJPS/SS/ST"
_INITIALS_RE = re.compile(r"^(?:[A-Za-z]{1,10}\s*/\s*)+[A-Za-z]{1,10}\.?$")

# Lines holding only punctuation, e.g. the "," between language names
_PUNCT_ONLY_RE = re.compile(r"^[\s,|;:\-\u2013\u2014]*$")

# A line that only introduces a social post, e.g.
#   "The Prime Minister's Office posted on X;"
# Lines like "In a post on X, he said ..." carry real content and are kept.
_SOCIAL_LEAD_RE = re.compile(
    r"\b(?:posted|post|tweeted|wrote)\b[^.!?]{0,40}\b(?:on|in)\s+(?:X|Twitter)\b"
    r"\s*[:;,\-\u2013\u2014]?\s*$",
    re.IGNORECASE,
)

_INVISIBLE_RE = re.compile("[\u200b\u200c\u200d\u2060\ufeff\u00ad]")


# ============================================================
# MINISTRIES (canonical names)
# ============================================================
# The ministry stored in silver files is always one of these, so the same
# ministry is always spelled the same way. Add new names as you meet them.

CANONICAL_MINISTRIES = [
    "Prime Minister's Office",
    "President's Secretariat",
    "Vice President's Secretariat",
    "Cabinet Secretariat",
    "Cabinet",
    "NITI Aayog",
    "Election Commission of India",
    "Department of Atomic Energy",
    "Department of Space",
    "Ministry of Agriculture and Farmers Welfare",
    "Ministry of AYUSH",
    "Ministry of Chemicals and Fertilizers",
    "Ministry of Civil Aviation",
    "Ministry of Coal",
    "Ministry of Commerce and Industry",
    "Ministry of Communications",
    "Ministry of Consumer Affairs, Food and Public Distribution",
    "Ministry of Cooperation",
    "Ministry of Corporate Affairs",
    "Ministry of Culture",
    "Ministry of Defence",
    "Ministry of Development of North Eastern Region",
    "Ministry of Earth Sciences",
    "Ministry of Education",
    "Ministry of Electronics and Information Technology",
    "Ministry of Environment, Forest and Climate Change",
    "Ministry of External Affairs",
    "Ministry of Finance",
    "Ministry of Fisheries, Animal Husbandry and Dairying",
    "Ministry of Food Processing Industries",
    "Ministry of Health and Family Welfare",
    "Ministry of Heavy Industries",
    "Ministry of Home Affairs",
    "Ministry of Housing and Urban Affairs",
    "Ministry of Information and Broadcasting",
    "Ministry of Jal Shakti",
    "Ministry of Labour and Employment",
    "Ministry of Law and Justice",
    "Ministry of Micro, Small and Medium Enterprises",
    "Ministry of Mines",
    "Ministry of Minority Affairs",
    "Ministry of New and Renewable Energy",
    "Ministry of Panchayati Raj",
    "Ministry of Parliamentary Affairs",
    "Ministry of Personnel, Public Grievances and Pensions",
    "Ministry of Petroleum and Natural Gas",
    "Ministry of Ports, Shipping and Waterways",
    "Ministry of Power",
    "Ministry of Railways",
    "Ministry of Road Transport and Highways",
    "Ministry of Rural Development",
    "Ministry of Science and Technology",
    "Ministry of Skill Development and Entrepreneurship",
    "Ministry of Social Justice and Empowerment",
    "Ministry of Statistics and Programme Implementation",
    "Ministry of Steel",
    "Ministry of Textiles",
    "Ministry of Tourism",
    "Ministry of Tribal Affairs",
    "Ministry of Women and Child Development",
    "Ministry of Youth Affairs and Sports",
]


def _norm_key(text: str) -> str:
    """Lowercase, '&' -> 'and', punctuation removed, spaces collapsed."""
    text = text.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


_MINISTRY_BY_KEY = {_norm_key(name): name for name in CANONICAL_MINISTRIES}


def _match_ministry(text):
    """
    Canonical ministry name found in `text`, or None.
    1) a canonical name appearing anywhere in the text (longest wins)
    2) otherwise a close fuzzy match for short texts (typos, small variants)
    """
    if not text or not str(text).strip():
        return None

    key = _norm_key(str(text))
    padded = f" {key} "

    hits = [k for k in _MINISTRY_BY_KEY if f" {k} " in padded]
    if hits:
        return _MINISTRY_BY_KEY[max(hits, key=len)]

    if len(key) <= 120:
        close = difflib.get_close_matches(key, list(_MINISTRY_BY_KEY), n=1, cutoff=0.85)
        if close:
            return _MINISTRY_BY_KEY[close[0]]

    return None


# ============================================================
# BASIC TEXT FIXES
# ============================================================

def _normalize_text(text: str) -> str:
    """Encoding fix, line endings, invisible characters, spacing inside lines."""
    text = ftfy.fix_text(text)  # also turns \r\n into \n
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _INVISIBLE_RE.sub("", text)
    text = text.replace("\xa0", " ")
    return re.sub(r"[ \t]+", " ", text)


def clean_text(text: str | None) -> str | None:
    """Clean a single-line field (title, ministry): encoding + one-line spacing."""
    if text is None:
        return None
    text = re.sub(r"\s+", " ", _normalize_text(text)).strip()
    return text or None


# ============================================================
# BODY CLEANING
# ============================================================

def _ministry_prefix_len(lines: list[str]) -> int:
    """How many leading lines (1 or 2) form exactly one canonical ministry name."""
    for n in (1, 2):
        if len(lines) >= n and _norm_key(" ".join(lines[:n])) in _MINISTRY_BY_KEY:
            return n
    return 0


def _process_body(raw_body: str, title: str | None):
    """
    Returns (ministry_from_header, posted_on_text, clean_body).
    clean_body holds only the real paragraphs, separated by one blank line.
    """
    text = _normalize_text(raw_body)
    title_key = _norm_key(title) if title else ""

    ministry = None
    posted_on = None
    subheadings: list[str] = []

    marker = _POSTED_ON_RE.search(text)

    if marker:
        # Everything BEFORE "Posted On" is header (ministry, title, sub-headlines);
        # everything AFTER it is the article.
        date = re.sub(r"\s+", " ", marker.group("date")).upper()
        time = re.sub(r"\s+", "", marker.group("time")).upper()
        posted_on = f"{date} {time}"

        header = [ln.strip() for ln in text[: marker.start()].split("\n") if ln.strip()]
        body_lines = text[marker.end():].split("\n")

        title_idx = next(
            (i for i, ln in enumerate(header) if title_key and _norm_key(ln) == title_key),
            None,
        )
        if title_idx is not None:
            ministry = _match_ministry(" ".join(header[:title_idx]))
            subheadings = header[title_idx + 1:]
        else:
            ministry = _match_ministry(" ".join(header))
    else:
        # No "Posted On" marker: strip a leading ministry / title if present.
        lines = [ln.strip() for ln in text.split("\n")]
        while lines and not lines[0]:
            lines.pop(0)

        n = _ministry_prefix_len(lines)
        if n:
            ministry = _MINISTRY_BY_KEY[_norm_key(" ".join(lines[:n]))]
            lines = lines[n:]
            while lines and not lines[0]:
                lines.pop(0)

        if lines and title_key and _norm_key(lines[0]) == title_key:
            lines = lines[1:]

        body_lines = lines

    body_lines = [ln.strip() for ln in body_lines]
    body_lines = [ln for ln in body_lines if ln]

    # 1. Footer: cut from the first footer line to the end.
    for i, line in enumerate(body_lines):
        if _FOOTER_START_RE.match(line):
            body_lines = body_lines[:i]
            break

    # 2. Embedded social post: cut from the lead-in line to the end.
    if STRIP_SOCIAL_EMBEDS:
        for i, line in enumerate(body_lines):
            if i > 0 and _SOCIAL_LEAD_RE.search(line):
                body_lines = body_lines[:i]
                break

    # 3. Drop separator lines, repeated lines and a repeated title.
    cleaned: list[str] = []
    for line in body_lines:
        if _STAR_LINE_RE.match(line) or _PUNCT_ONLY_RE.match(line):
            continue
        if cleaned and line == cleaned[-1]:
            continue
        if title_key and _norm_key(line) == title_key:
            continue
        cleaned.append(line)

    # 4. Staff initials left at the very end ("SS/DK").
    while cleaned and _INITIALS_RE.match(cleaned[-1]):
        cleaned.pop()

    if KEEP_SUBHEADINGS:
        cleaned = subheadings + cleaned

    return ministry, posted_on, "\n\n".join(cleaned)


# ============================================================
# MAIN ENTRY POINTS
# ============================================================

def clean_article(article: RawArticle) -> RawArticle:
    """
    Returns a NEW RawArticle with clean title / ministry / body_text.
    Also fills `ministry` and `posted_on_raw` from the header when they are
    empty. The input article is never modified.
    """
    title = clean_text(article.title)

    ministry = clean_text(article.ministry)
    if ministry:
        ministry = _match_ministry(ministry) or ministry

    updates = {"title": title}

    if article.body_text:
        header_ministry, posted_on, body = _process_body(article.body_text, title)

        ministry = ministry or header_ministry
        updates["body_text"] = body

        if posted_on and not getattr(article, "posted_on_raw", None):
            updates["posted_on_raw"] = posted_on

    updates["ministry"] = ministry

    return article.model_copy(update=updates)


def clean_articles(articles: list[RawArticle]) -> list[RawArticle]:
    """Clean a whole batch (used by pipeline.py)."""
    return [clean_article(article) for article in articles]


# ============================================================
# QUICK MANUAL TEST
# ============================================================

if __name__ == "__main__":
    sample = RawArticle(
        prid="2315470",
        url="https://example.com",
        title="Two-Day National Conference on Rabi Campaign 2026 to Begin Tomorrow in New Delhi",
        posted_on_raw="27 SEP 2026 10:19AM",
        body_text=(
            "Ministry of Agriculture &\r\nFarmers Welfare\n"
            "Two-Day National Conference on Rabi Campaign 2026 to Begin Tomorrow in New Delhi\n"
            "Conference to Focus on Strengthening Centre\u2013State Coordination\n"
            "Posted On:\r\n                27 SEP 2026 10:19AM by PIB Delhi\n"
            "The Department of Agriculture will organise the National Conference on 28\u201329 September 2026.\n"
            "The two-day Conference will focus on strengthening Centre\u2013State coordination.\n"
            "***\nSS/DK\n(Release ID: 2315470)\nVisitor Counter : 1448\n"
            "Read this release in:\nTelugu\n,\nUrdu\n,\nMarathi\n,\n\u0939\u093f\u0928\u094d\u0926\u0940"
        ),
    )

    cleaned = clean_article(sample)
    print("MINISTRY:", cleaned.ministry)
    print("POSTED  :", cleaned.posted_on_raw)
    print("BODY    :\n" + cleaned.body_text)