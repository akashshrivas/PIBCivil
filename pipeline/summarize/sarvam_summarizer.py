# sarvam_summarizer.py
# ====================
#
# LLM summarizer for PIB articles using Sarvam (sarvamai SDK).
#
# Output per article:
#   {
#     "prid", "title", "ministry", "posted_on",
#     "summary":         short factual summary of the main development,
#     "important_facts": extra important details NOT already in the summary,
#     "keywords":        institutions, schemes, persons, initiatives, ... (full names)
#   }
#
# - The article is cleaned first (ministry line, repeated title, "Posted On",
#   tweet block, footer removed), so the LLM only sees the real text.
# - title / ministry / posted_on come from the article data, not the model.
#   The model is asked for the ministry ONLY when the article data has none
#   (saves output tokens).
# - Facts that just repeat the summary are dropped in code as well.
#
# Setup:
#   pip install sarvamai python-dotenv
#   SARVAM_API_KEY in your environment or in a .env file
#
# Run from the repo root (either way works):
#   python -m pipeline.summarize.sarvam_summarizer --limit 3
#   python pipeline/summarize/sarvam_summarizer.py --limit 3
#   python -m pipeline.summarize.sarvam_summarizer

import argparse
import difflib
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from sarvamai import SarvamAI

# pib_parser.py imports its siblings as top-level packages (extract.*, parse.*),
# so the pipeline/ folder itself must be on sys.path BEFORE importing it.
PIPELINE_DIR = Path(__file__).resolve().parents[1]
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

from parse.pib_parser import RawArticle  # noqa: E402

load_dotenv()


# ============================================================
# CONFIGURATION
# ============================================================

MODEL = "sarvam-105b"          # 128K context, so no chunking is needed
TEMPERATURE = 0.1              # low = more faithful, less creative
MAX_TOKENS = 1000
REASONING_EFFORT = None        # reasoning off (reasoning tokens eat MAX_TOKENS)
MAX_RETRIES = 3
REQUEST_DELAY_SECONDS = 0.5    # small pause between articles
MIN_BODY_WORDS = 15            # skip articles with almost no text

MAX_FACTS = 6
MAX_KEYWORDS = 8
FACT_REPEAT_THRESHOLD = 0.8    # fact is dropped if 80%+ of its words are in the summary

# Separate folder so it does not mix with earlier exports.
OUTPUT_FOLDER_NAME = "exports"

API_KEY = os.getenv("SARVAM_API_KEY")


# ============================================================
# CLEANING
# ============================================================

# "Posted On: 02 OCT 2026 6:55PM by PIB Delhi" -- on its own line OR glued
# to the next sentence.
_POSTED_ON = re.compile(
    r"Posted\s+On\s*:?\s*"
    r"\d{1,2}\s+[A-Za-z]{3}\s+\d{4}\s+"
    r"\d{1,2}:\d{2}\s*[AP]M"
    r"(?:\s+by\s+PIB\s+\S+)?",
    re.IGNORECASE,
)

_FOOTER = re.compile(r"\*{3,}|Visitor\s+Counter", re.IGNORECASE)

_SOCIAL_POST = re.compile(
    r"\b(?:posted|post|tweeted|wrote)\s+(?:this\s+)?(?:on|in)\s+(?:X|Twitter)\b",
    re.IGNORECASE,
)

_DATE_ONLY = re.compile(r"\d{1,2}\s+[A-Za-z]{3}\s+\d{4}")


def _normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _to_iso_date(text):
    """'02 OCT 2026 6:55PM' -> '2026-10-02'. Falls back to the raw text."""
    if not text:
        return None
    match = _DATE_ONLY.search(text)
    if match:
        try:
            return datetime.strptime(match.group(0), "%d %b %Y").date().isoformat()
        except ValueError:
            pass
    return text


# ------------------------------------------------------------
# Canonical ministry names. Anything we store as "ministry" must match one
# of these, so the same ministry is always spelled the same way and random
# header text (e.g. a "PIB Backgrounder ..." headline) can never end up there.
# Add to this list whenever you meet a new one.
# ------------------------------------------------------------
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


def _norm_ministry(text: str) -> str:
    """Lowercase, '&' -> 'and', punctuation removed, spaces collapsed."""
    text = text.lower().replace("&", " and ")
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


_MINISTRY_BY_NORM = {_norm_ministry(name): name for name in CANONICAL_MINISTRIES}


def _match_ministry(text):
    """
    Return the canonical ministry name found in `text`, or None.
    1) a canonical name appearing anywhere in the text (longest wins), so
       "Ministry of Petroleum & Natural Gas  PIB Backgrounder ..." still matches
    2) otherwise a close fuzzy match for short texts (typos, small variants)
    """
    if not text or not str(text).strip():
        return None

    norm = _norm_ministry(str(text))
    padded = f" {norm} "

    hits = [n for n in _MINISTRY_BY_NORM if f" {n} " in padded]
    if hits:
        return _MINISTRY_BY_NORM[max(hits, key=len)]

    if len(norm) <= 120:
        close = difflib.get_close_matches(norm, list(_MINISTRY_BY_NORM), n=1, cutoff=0.85)
        if close:
            return _MINISTRY_BY_NORM[close[0]]

    return None


def _resolve_ministry(article: RawArticle, parts):
    """Ministry from article data (standardized if possible), else from the header."""
    if article.ministry:
        return _match_ministry(article.ministry) or article.ministry
    return parts[0]


def _extract_parts(article: RawArticle):
    """Split body_text into (ministry, posted_text, clean_body)."""
    raw = article.body_text or ""

    footer = _FOOTER.search(raw)
    if footer:
        raw = raw[: footer.start()]

    social = _SOCIAL_POST.search(raw)
    if social:
        raw = raw[: social.start()]
        last_end = max(raw.rfind(ch) for ch in ".!?")
        if last_end != -1:
            raw = raw[: last_end + 1]

    ministry = None
    posted_text = None
    title_norm = _normalize_spaces(article.title or "")

    posted = _POSTED_ON.search(raw)
    if posted:
        posted_text = posted.group(0)
        header = _normalize_spaces(raw[: posted.start()])
        if title_norm:
            header = header.replace(title_norm, "").strip(" :-")
        ministry = _match_ministry(header)
        body = raw[posted.end():]
    else:
        lines = raw.split("\n")
        first = lines[0].strip() if lines else ""
        # Exact match only: a paragraph that merely MENTIONS a ministry must
        # never be mistaken for the header line (silver files have no header).
        first_match = _MINISTRY_BY_NORM.get(_norm_ministry(first))
        if len(lines) > 1 and first_match:
            ministry = first_match
            body = "\n".join(lines[1:])
        else:
            body = raw

    body = _normalize_spaces(body)
    if title_norm:
        body = body.replace(title_norm, " ")

    return ministry, posted_text, _normalize_spaces(body)


def _get_posted_date(article: RawArticle, parts):
    raw = getattr(article, "posted_on_raw", None)
    return _to_iso_date(raw if raw else parts[1])


# ============================================================
# PROMPT
# ============================================================

def _build_system_prompt(need_ministry: bool) -> str:
    """
    Short prompt (sent with every article, so every token counts).
    The ministry field is only requested when we do not already know it.
    """
    if need_ministry:
        schema = '{"ministry": "", "summary": "", "important_facts": [], "keywords": []}'
        ministry_rule = (
            "- ministry: the ministry or department issuing the release, "
            "only if the article names it; otherwise null.\n"
        )
    else:
        schema = '{"summary": "", "important_facts": [], "keywords": []}'
        ministry_rule = ""

    return (
        "You summarize Indian government (PIB) press releases for a "
        "current-affairs digest.\n"
        "Use ONLY facts stated in the article. No outside knowledge, opinion, "
        "analysis or exam commentary. Drop ceremonial language, praise, "
        "greetings and repetition. Keep names, numbers, dates, places, schemes "
        "and decisions exactly as written.\n"
        "Return ONLY valid JSON, no Markdown, in this exact shape:\n"
        f"{schema}\n"
        f"{ministry_rule}"
        "- summary: 1-3 sentences, max 60 words, the main development only.\n"
        "- important_facts: 0-6 items, one sentence each under 25 words. Include "
        "ONLY important details that are NOT already stated in the summary "
        "(figures, decisions, dates, places, outcomes). Never restate the "
        "summary. If the summary already covers everything important, return [].\n"
        "- keywords: 5-8 important items from the article: institutions, "
        "schemes, persons, initiatives, programmes, events or places. Write full "
        "official names, not abbreviations or short forms (e.g. 'Indian Space "
        "Research Organisation', not 'ISRO'); names only known by their acronym, "
        "such as BRICS, may stay as they are. No generic words like 'growth' "
        "or 'passengers'."
    )


def _build_user_prompt(title: str, body: str) -> str:
    return f"Title: {title}\n\nArticle:\n{body}"


# ============================================================
# SARVAM CALL + PARSING
# ============================================================

def _call_sarvam(client, system_prompt: str, user_prompt: str):
    """One API call. Returns (content, usage_dict)."""
    response = client.chat.completions(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
        reasoning_effort=REASONING_EFFORT,
    )

    choice = response.choices[0]
    content = choice.message.content
    finish_reason = getattr(choice, "finish_reason", None)

    if not content:
        if finish_reason == "length":
            # Retrying with the same settings cannot help, so fail fast.
            raise RuntimeError(
                "model ran out of tokens before writing the answer "
                "(finish_reason=length). Raise MAX_TOKENS."
            )
        raise ValueError(f"model returned empty content (finish_reason={finish_reason})")

    usage = {"input": 0, "output": 0, "total": 0}
    if getattr(response, "usage", None):
        usage = {
            "input": response.usage.prompt_tokens or 0,
            "output": response.usage.completion_tokens or 0,
            "total": response.usage.total_tokens or 0,
        }

    return content, usage


def _string_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(v).strip() for v in value if str(v).strip()]


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9.]+", text.lower()))


def _clean_facts(facts: list[str], summary: str) -> list[str]:
    """Drop duplicates and facts that mostly repeat the summary; cap the count."""
    summary_words = _words(summary)
    seen = set()
    kept = []

    for fact in facts:
        key = fact.lower().strip(" .")
        if key in seen:
            continue
        seen.add(key)

        fact_words = _words(fact)
        if fact_words and len(fact_words & summary_words) / len(fact_words) >= FACT_REPEAT_THRESHOLD:
            continue

        kept.append(fact)

    return kept[:MAX_FACTS]


def _clean_keywords(keywords: list[str]) -> list[str]:
    """Strip stray punctuation, dedupe case-insensitively, cap the count."""
    seen = set()
    kept = []

    for keyword in keywords:
        keyword = keyword.strip(" .,;:")
        key = keyword.lower()
        if not keyword or key in seen:
            continue
        seen.add(key)
        kept.append(keyword)

    return kept[:MAX_KEYWORDS]


def _parse_output(text: str) -> dict:
    """Pull the JSON object out of the reply and validate its shape."""
    text = re.sub(r"^```(?:json)?|```$", "", (text or "").strip(), flags=re.MULTILINE).strip()

    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in reply")

    data = json.loads(text[start : end + 1])

    summary = data.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("'summary' missing or empty")
    summary = summary.strip()

    ministry = data.get("ministry")
    if not isinstance(ministry, str) or not ministry.strip():
        ministry = None

    return {
        "ministry": ministry,
        "summary": summary,
        "important_facts": _clean_facts(_string_list(data.get("important_facts")), summary),
        "keywords": _clean_keywords(_string_list(data.get("keywords"))),
    }


def summarize_with_sarvam(client, title: str, ministry_known: bool, body: str):
    """Returns (parsed_dict, usage_dict). Retries on API errors / bad JSON."""
    system_prompt = _build_system_prompt(need_ministry=not ministry_known)
    user_prompt = _build_user_prompt(title, body)
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            content, usage = _call_sarvam(client, system_prompt, user_prompt)
            return _parse_output(content), usage

        except RuntimeError:
            raise  # fail-fast cases (out of tokens)

        except Exception as e:
            # Bad key: retrying will not help.
            if getattr(e, "status_code", None) in (401, 403):
                raise RuntimeError(f"Sarvam rejected the API key: {e}")

            last_error = e
            wait = 2 ** attempt
            print(f"   attempt {attempt}/{MAX_RETRIES} failed ({e}); retrying in {wait}s")
            time.sleep(wait)

    raise RuntimeError(f"failed after {MAX_RETRIES} attempts: {last_error}")


# ============================================================
# PROCESS ONE JSON FILE
# ============================================================

def process_json_file(client, input_path: Path, output_path: Path, totals: dict, limit=None) -> int:
    """
    Summarize every new article in one processed file and merge the results
    into output_path by PRID. Returns the number of articles summarized.
    """
    print(f"\nProcessing: {input_path}")

    with input_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        print(f"Skipping {input_path}: expected a list")
        return 0

    print(f"Found {len(data)} articles")

    existing_by_prid: dict = {}
    if output_path.exists():
        try:
            existing_data = json.loads(output_path.read_text(encoding="utf-8"))
            existing_by_prid = {item["prid"]: item for item in existing_data}
        except (json.JSONDecodeError, KeyError, TypeError):
            print(f"{output_path} was unreadable/corrupt -- starting fresh")

    articles = []
    for item in data:
        try:
            articles.append(RawArticle.model_validate(item))
        except Exception as e:
            print(f"Could not parse article {item.get('prid', 'unknown')}: {e}")

    new_count = 0
    for i, article in enumerate(articles, start=1):
        if limit is not None and new_count >= limit:
            break

        if article.prid in existing_by_prid:
            continue

        if not article.fetched_ok or not article.body_text:
            print(f"[{i}/{len(articles)}] Skipping (no body text): {article.prid}")
            continue

        parts = _extract_parts(article)
        clean_body = parts[2]
        word_count = len(clean_body.split())

        if word_count < MIN_BODY_WORDS:
            print(f"[{i}/{len(articles)}] Skipping (too little text): {article.prid}")
            continue

        ministry_known = _resolve_ministry(article, parts)
        print(f"[{i}/{len(articles)}] Summarizing ({word_count} words): {article.title}")

        try:
            parsed, usage = summarize_with_sarvam(
                client, article.title, bool(ministry_known), clean_body
            )

            # Trusted values win; the model's ministry is only a fallback.
            existing_by_prid[article.prid] = {
                "prid": article.prid,
                "title": article.title,
                "ministry": ministry_known or _match_ministry(parsed["ministry"]),
                "posted_on": _get_posted_date(article, parts),
                "summary": parsed["summary"],
                "important_facts": parsed["important_facts"],
                "keywords": parsed["keywords"],
            }

            for key in ("input", "output", "total"):
                totals[key] += usage[key]
            new_count += 1

        except Exception as e:
            print(f"ERROR summarizing {article.prid}: {e}")

        time.sleep(REQUEST_DELAY_SECONDS)

    if new_count == 0:
        print(f"Nothing new to summarize for {input_path.name}")
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_data = list(existing_by_prid.values())

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"Saved {new_count} new summary(ies) -> {output_path} ({len(output_data)} total)")
    return new_count


# ============================================================
# MAIN: PROCESS EVERYTHING IN data/processed/
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Summarize PIB articles with Sarvam")
    parser.add_argument("--limit", type=int, default=None,
                        help="max number of NEW articles to summarize (good for a first test)")
    args = parser.parse_args()

    if not API_KEY:
        print("SARVAM_API_KEY not found. Check your .env file.")
        sys.exit(1)

    client = SarvamAI(api_subscription_key=API_KEY)

    base_dir = Path(__file__).resolve().parents[2]
    processed_dir = base_dir / "data" / "processed"
    exports_dir = base_dir / "data" / OUTPUT_FOLDER_NAME

    print("=" * 60)
    print("PIB ARTICLE SUMMARIZER -- SARVAM LLM")
    print("=" * 60)
    print(f"Model           : {MODEL}")
    print(f"Input directory : {processed_dir}")
    print(f"Output directory: {exports_dir}")

    json_files = sorted(processed_dir.rglob("*.json"))
    if not json_files:
        print("\nNo JSON files found.")
        sys.exit()

    print(f"\nFound {len(json_files)} JSON files.")

    totals = {"input": 0, "output": 0, "total": 0}
    remaining = args.limit

    for input_path in json_files:
        if remaining is not None and remaining <= 0:
            break

        relative_path = input_path.relative_to(processed_dir)
        output_path = exports_dir / relative_path

        print("\n" + "-" * 60)
        print(f"Input : {input_path}")
        print(f"Output: {output_path}")

        try:
            done = process_json_file(client, input_path, output_path, totals, limit=remaining)
            if remaining is not None:
                remaining -= done
        except Exception as e:
            print(f"ERROR processing {input_path}: {e}")

    print("\n" + "=" * 60)
    print("ALL FILES PROCESSED")
    print("=" * 60)
    print(f"Input tokens : {totals['input']}")
    print(f"Output tokens: {totals['output']}")
    print(f"Total tokens : {totals['total']}")