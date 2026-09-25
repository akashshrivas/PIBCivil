"""
seen_tracker.py — remembers which PRIDs have already been fetched, across
runs, so a polling loop only does work on genuinely new releases.

Backed by a single flat text file (one PRID per line) rather than a
database, since this project doesn't have one wired up yet. Loaded into
memory as a set for O(1) lookups; written back to disk after each batch.
"""

from pathlib import Path

DATA_ROOT = Path(__file__).resolve().parent.parent.parent / "data"  # PIBCivil/data
SEEN_FILE = DATA_ROOT / ".state" / "seen_prids.txt"


def load_seen() -> set[str]:
    if not SEEN_FILE.exists():
        return set()
    return set(SEEN_FILE.read_text(encoding="utf-8").splitlines())


def mark_seen(prids: list[str]) -> None:
    SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    existing = load_seen()
    existing.update(prids)
    SEEN_FILE.write_text("\n".join(sorted(existing)), encoding="utf-8")