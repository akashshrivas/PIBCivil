"""
evaluate_classifier.py
======================

WHAT THIS FILE DOES
-------------------
Helps you answer the most important question about the classifier:
"Does it agree with ME?"  It has two modes.

1) label     You read PIB summaries one by one and press a single key:
                 i = important   m = maybe   s = skip   u = undo   q = quit
             Your answers are saved to data/labels/labels.json after EVERY
             key press, so you can quit any time and continue later.
             The model's score is deliberately hidden while you label, so it
             cannot influence your judgement.

2) evaluate  Compares your labels with the classifier's labels and prints:
               - overall agreement %
               - a table of your label vs the model's label
               - the worst mistakes: things YOU marked important that the
                 model skipped (missed news), and things you marked skip that
                 the model called important (noise)
             Use the mistakes to improve the rubric in relevance_classifier.py
             (then bump CLASSIFIER_VERSION and re-run it).

HOW TO USE (from the repo root)
-------------------------------
    python pipeline/classify/evaluate_classifier.py label --count 60
    python pipeline/classify/relevance_classifier.py            # score them
    python pipeline/classify/evaluate_classifier.py evaluate

Aim for 50-100 labels. With fewer than ~30 the numbers are too shaky to trust.
"""

import argparse
import json
import random
import sys
from pathlib import Path

# This works because Python puts this file's own folder on sys.path when you
# run it as a script, so we can import the sibling file by its plain name.
from relevance_classifier import BASE_DIR, EXPORTS_DIR

LABELS_PATH = BASE_DIR / "data" / "labels" / "labels.json"

# The three labels, in order from most to least important. The order is used
# to print the comparison table.
LABELS = ["important", "maybe", "skip"]
KEY_TO_LABEL = {"i": "important", "m": "maybe", "s": "skip"}


# ============================================================
# LOADING AND SAVING
# ============================================================

def load_all_records() -> list[dict]:
    """Every article record from every file in data/exports/."""
    records = []
    for path in sorted(EXPORTS_DIR.rglob("*.json")):
        try:
            records.extend(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError) as e:
            print(f"Skipping unreadable file {path}: {e}")
    return records


def load_labels() -> dict:
    """Your saved labels as {prid: {"label": ..., "title": ...}}."""
    if LABELS_PATH.exists():
        return json.loads(LABELS_PATH.read_text(encoding="utf-8"))
    return {}


def save_labels(labels: dict) -> None:
    LABELS_PATH.parent.mkdir(parents=True, exist_ok=True)
    LABELS_PATH.write_text(json.dumps(labels, ensure_ascii=False, indent=2), encoding="utf-8")


# ============================================================
# MODE 1: LABEL
# ============================================================

def run_label(count: int, seed: int) -> None:
    records = load_all_records()
    if not records:
        print(f"No summaries found in {EXPORTS_DIR}. Run the summarizer first.")
        sys.exit(1)

    labels = load_labels()
    todo = [r for r in records if r.get("prid") and r["prid"] not in labels]

    # Shuffle with a fixed seed so you get a MIX of days and ministries,
    # not 60 releases from the same morning. Same seed = same order, so
    # quitting and coming back continues where you stopped.
    random.Random(seed).shuffle(todo)

    print(f"{len(labels)} already labelled, {len(todo)} left. Labelling up to {count} now.")
    print("Keys: [i]mportant  [m]aybe  [s]kip  [u]ndo last  [q]uit\n")
    print("Think like an examiner: would this be worth a student's time?\n")

    done_now = []  # prids labelled in this session (used by undo)
    index = 0
    while index < len(todo) and len(done_now) < count:
        record = todo[index]
        print("-" * 70)
        print(f"({len(labels) + 1} labelled so far)  {record.get('posted_on')}  |  {record.get('ministry')}")
        print(f"TITLE  : {record.get('title')}")
        print(f"SUMMARY: {record.get('summary')}")
        for fact in (record.get("important_facts") or [])[:3]:
            print(f"  - {fact}")

        answer = input("\n[i/m/s/u/q] > ").strip().lower()

        if answer == "q":
            break
        if answer == "u":
            if done_now:
                last = done_now.pop()
                labels.pop(last, None)
                save_labels(labels)
                index -= 1  # show that article again
                print("Undone.")
            else:
                print("Nothing to undo.")
            continue
        if answer in KEY_TO_LABEL:
            labels[record["prid"]] = {"label": KEY_TO_LABEL[answer], "title": record.get("title")}
            save_labels(labels)  # saved immediately, nothing is lost if you quit
            done_now.append(record["prid"])
            index += 1
        else:
            print("Please press i, m, s, u or q.")

    counts = {name: sum(1 for v in labels.values() if v["label"] == name) for name in LABELS}
    print(f"\nSaved to {LABELS_PATH}")
    print(f"Total labels: {len(labels)}  ->  {counts}")


# ============================================================
# MODE 2: EVALUATE
# ============================================================

def run_evaluate() -> None:
    labels = load_labels()
    if not labels:
        print("No labels yet. Run:  python pipeline/classify/evaluate_classifier.py label")
        sys.exit(1)

    # Match your labels to the articles that already have a model score.
    by_prid = {r["prid"]: r for r in load_all_records() if r.get("prid")}
    pairs = []  # (your label, model label, record)
    unscored = 0
    for prid, mine in labels.items():
        record = by_prid.get(prid)
        if record is None:
            continue  # the article file is no longer on disk
        if "relevance_label" not in record:
            unscored += 1
            continue
        pairs.append((mine["label"], record["relevance_label"], record))

    if unscored:
        print(f"Note: {unscored} labelled article(s) have no model score yet. "
              f"Run relevance_classifier.py first.\n")
    if not pairs:
        print("Nothing to compare yet.")
        sys.exit(1)

    total = len(pairs)
    agree = sum(1 for mine, model, _ in pairs if mine == model)
    print(f"Compared {total} article(s).")
    print(f"Exact agreement: {agree}/{total} = {agree / total:.0%}")
    if total < 30:
        print("(Fewer than 30 labels: treat these numbers as a rough guide only.)")

    # --- the comparison table: rows = what YOU said, columns = what the model said ---
    print("\nRows = your label, columns = model label")
    print(f"{'':>12}" + "".join(f"{name:>12}" for name in LABELS))
    for mine_name in LABELS:
        row = [sum(1 for m, mo, _ in pairs if m == mine_name and mo == model_name)
               for model_name in LABELS]
        print(f"{mine_name:>12}" + "".join(f"{n:>12}" for n in row))

    # --- the two mistakes that matter most ---
    missed = [(r, mo) for m, mo, r in pairs if m == "important" and mo == "skip"]
    noise = [(r, mo) for m, mo, r in pairs if m == "skip" and mo == "important"]

    def show(title: str, items: list) -> None:
        print(f"\n{title}: {len(items)}")
        for record, _ in items[:10]:
            print(f"  [{record.get('relevance_score')}/10] {record.get('title')}")
            print(f"        model said: {record.get('relevance_reason')}")

    show("MISSED NEWS (you said important, model said skip) -- the worst kind", missed)
    show("NOISE (you said skip, model said important)", noise)

    print("\nWhat to do next: read the reasons above, edit the rubric in "
          "relevance_classifier.py, change CLASSIFIER_VERSION to 'v2', re-run "
          "it, then run this evaluation again.")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Label PIB releases and evaluate the classifier")
    sub = parser.add_subparsers(dest="mode", required=True)

    p_label = sub.add_parser("label", help="label releases by pressing keys")
    p_label.add_argument("--count", type=int, default=60, help="how many to label this session")
    p_label.add_argument("--seed", type=int, default=42, help="shuffle seed (keep the same to continue)")

    sub.add_parser("evaluate", help="compare your labels with the model")

    args = parser.parse_args()
    if args.mode == "label":
        run_label(args.count, args.seed)
    else:
        run_evaluate()
