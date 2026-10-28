"""
relevance_classifier.py
=======================

WHAT THIS FILE DOES
-------------------
Reads the summarized PIB releases (the files in data/exports/YYYY/MM/DD.json
that sarvam_summarizer.py creates) and gives each release a UPSC relevance
score from 0 to 10. It saves the score back into the SAME file, next to the
summary, so every later step (Supabase, the app, the Telegram channel) can
simply say "show me only the important ones".

Fields added to every article record:

    relevance_score    0-10 number from the model
    relevance_label    "important" / "maybe" / "skip"  (worked out HERE in
                       code from the score, not by the model, so the
                       thresholds are always consistent)
    papers             which GS papers it belongs to, e.g. ["GS2", "GS3"]
    topic              one topic from a fixed list (so filters stay tidy)
    relevance_reason   one short sentence: WHY this score (great for debugging)
    classifier_version the rubric version that produced the score

WHY WE CLASSIFY THE SUMMARY AND NOT THE FULL ARTICLE
-----------------------------------------------------
The summary + key facts + keywords already contain the important content.
Sending ~100 words instead of ~1500 makes each call much cheaper and faster.

WHY AN LLM AND NOT A TRAINED MODEL
----------------------------------
"Is this important for UPSC?" is a judgement call. A clear written rubric
(see _build_system_prompt) works well, and you can improve it just by
editing text. Use evaluate_classifier.py to measure how often the model
agrees with YOUR own judgement, then tweak the rubric until it does.

HOW TO RUN (from the repo root)
-------------------------------
    python pipeline/classify/relevance_classifier.py --limit 5     # small test
    python pipeline/classify/relevance_classifier.py               # everything new
    python pipeline/classify/relevance_classifier.py --date 2026-10-02
    python pipeline/classify/relevance_classifier.py --force       # re-score all

Needs SARVAM_API_KEY in your environment or in a .env file (same as the
summarizer).
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # reads SARVAM_API_KEY from a .env file if there is one


# ============================================================
# CONFIGURATION  (the things you will most likely want to tweak)
# ============================================================

MODEL = "sarvam-105b"        # same model the summarizer uses
TEMPERATURE = 0.0            # 0 = most consistent answers (we want a judge, not a poet)
MAX_TOKENS = 300             # the answer is tiny JSON, so this is plenty
MAX_RETRIES = 3              # how many times to retry a failed call
REQUEST_DELAY_SECONDS = 0.5  # small pause between calls (be gentle with the API)

# Bump this whenever you change the rubric. Records scored with an OLD
# version get re-scored automatically on the next run, so you can improve
# the rubric and refresh old scores without using --force.
CLASSIFIER_VERSION = "v1"

# Score -> label. Change these two numbers to make the filter stricter/looser.
IMPORTANT_MIN = 7   # score 7-10  -> "important"
MAYBE_MIN = 4       # score 4-6   -> "maybe"   (0-3 -> "skip")

# The model must pick a topic from this list. A fixed list keeps your
# filters clean ("Economy" never turns into "Economic Policy" or "economy").
TOPICS = [
    "Polity & Governance",
    "International Relations",
    "Economy",
    "Agriculture",
    "Environment & Ecology",
    "Science & Technology",
    "Internal Security & Defence",
    "Social Justice & Welfare",
    "Health",
    "Education",
    "History, Art & Culture",
    "Geography & Disasters",
    "Ethics & Administration",
    "Infrastructure & Energy",
    "Other",
]

VALID_PAPERS = ("GS1", "GS2", "GS3", "GS4")

# Where the files live. This file is at <repo>/pipeline/classify/, so
# parents[2] is the repo root.
BASE_DIR = Path(__file__).resolve().parents[2]
EXPORTS_DIR = BASE_DIR / "data" / "exports"


# ============================================================
# THE RUBRIC  (this is the "brain" -- edit it to change behaviour)
# ============================================================

def _build_system_prompt() -> str:
    """
    The instructions sent to the model with every article.

    You are the expert here, not me: read the score bands below and change
    anything that does not match how YOU think about UPSC importance. After
    editing, bump CLASSIFIER_VERSION and re-run.
    """
    topics = ", ".join(f'"{t}"' for t in TOPICS)
    return (
        "You are an experienced UPSC Civil Services mentor. You are shown a "
        "summary of ONE Press Information Bureau (PIB) press release. Decide "
        "how important it is for a UPSC aspirant's current-affairs "
        "preparation (Prelims and Mains).\n\n"
        "SCORE BANDS\n"
        "9-10 MUST KNOW: a major new policy, scheme or mission launched or "
        "approved (for example a Cabinet decision); a new Act, Bill or "
        "constitutional/legal change; a significant international agreement "
        "or summit outcome; a major national report or index with rankings; "
        "a big economic decision.\n"
        "7-8 IMPORTANT: a substantive initiative with clear details; key "
        "data or report releases; important MoUs or agreements; strategically "
        "significant defence exercises or acquisitions; science and "
        "technology missions and milestones; environment and ecology items "
        "(species, protected areas, treaties, climate commitments).\n"
        "4-6 MAYBE: progress updates on existing schemes with figures; "
        "routine MoUs; minor schemes; regular statistics; awards. Useful "
        "background but not a priority.\n"
        "0-3 SKIP: ceremonial or greeting content, condolences, tributes, "
        "anniversaries; minister visits or speeches with no policy "
        "announcement; inauguration of local projects; awareness events; "
        "routine meetings; state-specific local news; photo-ops.\n\n"
        "RULES\n"
        "- Think about what an exam could ask: names, numbers, places and "
        "dates for Prelims; issues, impact and pros/cons for Mains.\n"
        "- Use ONLY the text given. If it is too thin to judge, score 3 or less.\n"
        "- Do not reward length. A short release about a new law can be a 9.\n"
        "- papers: up to 2 of GS1 (history, culture, society, geography), "
        "GS2 (polity, governance, social justice, international relations), "
        "GS3 (economy, agriculture, environment, science and technology, "
        "security, disaster management), GS4 (ethics and integrity). Use an "
        "empty list if the score is 3 or less.\n"
        f"- topic: exactly one of: {topics}.\n"
        "- reason: ONE sentence, maximum 20 words, saying why you gave this score.\n\n"
        "Return ONLY valid JSON, no Markdown, in exactly this shape:\n"
        '{"score": 0, "papers": [], "topic": "", "reason": ""}'
    )


def _build_user_prompt(record: dict) -> str:
    """
    Turns one article record into the text the model reads.
    We send only the useful short fields, never the full article body.
    """
    facts = record.get("important_facts") or []
    keywords = record.get("keywords") or []
    parts = [
        f"Title: {record.get('title') or ''}",
        f"Ministry: {record.get('ministry') or 'unknown'}",
        f"Summary: {record.get('summary') or ''}",
    ]
    if facts:
        parts.append("Key facts: " + " | ".join(facts))
    if keywords:
        parts.append("Keywords: " + ", ".join(keywords))
    return "\n".join(parts)


# ============================================================
# TURNING THE MODEL'S REPLY INTO SAFE, CLEAN DATA
# ============================================================
# Never trust an LLM's output blindly. It can add Markdown fences, return
# 8.5 instead of 8, invent a topic, or forget a field. These helpers force
# every reply into the exact shape the rest of the pipeline expects.

def label_for(score: int) -> str:
    """Score -> 'important' / 'maybe' / 'skip' using the thresholds above."""
    if score >= IMPORTANT_MIN:
        return "important"
    if score >= MAYBE_MIN:
        return "maybe"
    return "skip"


def parse_reply(text: str) -> dict:
    """
    Pulls the JSON out of the model's reply and validates it.
    Raises ValueError if the reply is unusable (the caller will retry).
    """
    # Remove ```json ... ``` fences if the model added them.
    text = re.sub(r"^```(?:json)?|```$", "", (text or "").strip(), flags=re.MULTILINE).strip()

    # Take everything from the first "{" to the last "}".
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in reply")
    data = json.loads(text[start : end + 1])

    # --- score: must be a number; round it, then keep it within 0..10 ---
    raw_score = data.get("score")
    if isinstance(raw_score, bool) or not isinstance(raw_score, (int, float)):
        raise ValueError(f"'score' is not a number: {raw_score!r}")
    score = max(0, min(10, round(raw_score)))

    # --- papers: keep only valid GS papers, no repeats, max 2 ---
    papers = []
    for p in data.get("papers") or []:
        p = str(p).strip().upper()
        if p in VALID_PAPERS and p not in papers:
            papers.append(p)
    papers = papers[:2]

    # --- topic: must be on our list, otherwise "Other" ---
    topic = str(data.get("topic") or "").strip()
    if topic not in TOPICS:
        topic = "Other"

    # --- reason: short text, trimmed so a rambling model cannot bloat the file ---
    reason = re.sub(r"\s+", " ", str(data.get("reason") or "")).strip()[:200]

    return {
        "relevance_score": score,
        "relevance_label": label_for(score),
        "papers": papers,
        "topic": topic,
        "relevance_reason": reason,
        "classifier_version": CLASSIFIER_VERSION,
    }


# ============================================================
# CALLING SARVAM
# ============================================================

def build_client():
    """Creates the Sarvam client. Imported here so other files can import
    this module (e.g. for label_for) without needing the SDK installed."""
    from sarvamai import SarvamAI

    api_key = os.getenv("SARVAM_API_KEY")
    if not api_key:
        print("SARVAM_API_KEY not found. Check your .env file.")
        sys.exit(1)
    return SarvamAI(api_subscription_key=api_key)


def classify_record(client, record: dict) -> dict:
    """
    Classifies ONE article record. Returns the new fields to merge in.
    Retries on temporary errors and bad replies. Raises if it still fails.
    """
    system_prompt = _build_system_prompt()
    user_prompt = _build_user_prompt(record)
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.chat.completions(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
                reasoning_effort=None,  # reasoning off, same as the summarizer
            )
            content = response.choices[0].message.content
            if not content:
                raise ValueError("model returned empty content")
            return parse_reply(content)

        except Exception as e:
            # A wrong API key will never start working, so stop immediately.
            if getattr(e, "status_code", None) in (401, 403):
                raise RuntimeError(f"Sarvam rejected the API key: {e}")

            last_error = e
            wait = 2 ** attempt  # wait 2s, 4s, 8s ... between tries
            print(f"   attempt {attempt}/{MAX_RETRIES} failed ({e}); retrying in {wait}s")
            time.sleep(wait)

    raise RuntimeError(f"failed after {MAX_RETRIES} attempts: {last_error}")


# ============================================================
# PROCESSING THE FILES
# ============================================================

def needs_scoring(record: dict, force: bool) -> bool:
    """A record needs scoring if it has no score yet, was scored by an older
    rubric version, or the user passed --force."""
    if force:
        return True
    return record.get("classifier_version") != CLASSIFIER_VERSION


def process_file(client, path: Path, force: bool, limit: int | None) -> int:
    """
    Scores every record in ONE day file. Returns how many were scored.
    `limit` is the maximum number of records to score in this file (None = no limit).
    """
    records = json.loads(path.read_text(encoding="utf-8"))
    scored = 0

    try:
        for i, record in enumerate(records, start=1):
            if limit is not None and scored >= limit:
                break
            if not needs_scoring(record, force):
                continue

            print(f"[{i}/{len(records)}] {record.get('title')}")
            try:
                record.update(classify_record(client, record))  # add the new fields
                scored += 1
                print(f"   -> {record['relevance_score']}/10 {record['relevance_label']} "
                      f"{record['papers']} | {record['relevance_reason']}")
            except RuntimeError as e:
                if "API key" in str(e):
                    raise  # fatal: stop everything
                # One bad article must not stop the others. Leave it without
                # a score; the next run will simply try it again.
                print(f"   ERROR: {e}")

            time.sleep(REQUEST_DELAY_SECONDS)
    finally:
        # `finally` runs even if you press Ctrl+C halfway, so the scores
        # already earned are saved and you do not pay for them twice.
        if scored:
            path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Saved {scored} score(s) -> {path}")

    return scored


def find_files(date_text: str | None) -> list[Path]:
    """All day files in data/exports/, or just one day if --date was given."""
    if date_text:
        day = datetime.strptime(date_text, "%Y-%m-%d")
        path = EXPORTS_DIR / f"{day:%Y}" / f"{day:%m}" / f"{day:%d}.json"
        return [path] if path.exists() else []
    return sorted(EXPORTS_DIR.rglob("*.json"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Score PIB releases for UPSC relevance")
    parser.add_argument("--limit", type=int, default=None,
                        help="maximum number of articles to score (good for a first test)")
    parser.add_argument("--date", type=str, default=None,
                        help="only this day, format YYYY-MM-DD")
    parser.add_argument("--force", action="store_true",
                        help="re-score articles even if they already have a score")
    args = parser.parse_args()

    files = find_files(args.date)
    if not files:
        print(f"No summary files found in {EXPORTS_DIR}. Run the summarizer first.")
        sys.exit(1)

    client = build_client()
    print(f"Model: {MODEL} | rubric {CLASSIFIER_VERSION} | {len(files)} file(s)")

    remaining = args.limit
    total = 0
    for path in files:
        if remaining is not None and remaining <= 0:
            break
        done = process_file(client, path, args.force, remaining)
        total += done
        if remaining is not None:
            remaining -= done

    print(f"\nDone. Scored {total} article(s).")


if __name__ == "__main__":
    main()
