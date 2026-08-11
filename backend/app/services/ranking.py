"""Re-ranking for provider search results.

Hardcover's search is Typesense-backed and ranks purely on text relevance, which
puts the wrong edition first often enough to matter. Measured on a 20-book
sample, taking hit #0 gave the correct book 13/20 times; the heuristic below
gave 20/20 and lifted median ratings_count from 425 to 911.

Two failure modes it corrects:
  1. Parasitic editions -- "Workbook for X", "Summary of X" -- outrank the book.
  2. The canonical edition sits a few positions down behind sparse duplicates.

See docs/phase-4-search-ranking.md for the measurements.
"""

import math
import re

JUNK_TITLE = re.compile(
    r"\b(workbook|summary|summaries|study guide|analysis of|key takeaways|"
    r"conversation starters|book club|quicklet|sparknotes|cliffs?notes)\b",
    re.IGNORECASE,
)

MIN_QUERY_OVERLAP = 0.5


def _tokens(text: str | None) -> set[str]:
    return set(re.findall(r"[a-z0-9']+", (text or "").lower()))


def score_candidate(
    query: str, title: str, authors: list[str], ratings_count: int, position: int
) -> float | None:
    """Score one candidate, or None if it should be rejected outright."""
    if JUNK_TITLE.search(title):
        return None

    query_tokens = _tokens(query)
    if not query_tokens:
        return None

    matched = query_tokens & (_tokens(title) | _tokens(" ".join(authors)))
    overlap = len(matched) / len(query_tokens)
    if overlap < MIN_QUERY_OVERLAP:
        return None

    # Relevance dominates; popularity breaks ties; original rank is a faint prior.
    return overlap * 3 + math.log10(ratings_count + 1) - position * 0.02
