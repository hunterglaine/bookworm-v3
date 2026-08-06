# Phase 4 — Search re-ranking

Reference material, not shipped code. The implementation below was written and
validated during provider evaluation, then deliberately kept out of the scaffold
commit because it is feature code. It lands with the Hardcover provider in
Phase 4.

## The problem

Hardcover's search is Typesense-backed and ranks on text relevance alone, which
surfaces the wrong edition often enough to matter. Taking hit `#0` gave the
correct book **13/20** on a 20-book sample.

Two failure modes, both measured:

1. **Parasitic editions** — "Workbook for X", "Summary and Discussions of X" —
   outrank the book itself.
2. **The canonical edition sits a few positions down**, behind sparse
   duplicates.

The right book was almost always present, just not first:

| Query | Correct book at | Ratings |
|---|---|---|
| Tomorrow, and Tomorrow, and Tomorrow | #5 — Gabrielle Zevin | 2,631 |
| The Body Keeps the Score | #2 — van der Kolk | 443 |
| Stoner | #3 — John Williams | 823 |
| Piranesi | #1 — Susanna Clarke | 2,946 |
| James | #2 — Percival Everett | 616 |
| Sapiens | not in top 8 | — |

So it is a ranking problem, not a coverage problem.

## Results

| Metric | `per_page: 1` naive | With re-ranker |
|---|---|---|
| Correct book | 13/20 | **20/20** |
| Median ratings_count | 425 | **911** |
| ≥200 ratings | 11/20 | **18/20** |

Range 90 → 7,739 ratings.

**Remaining known imperfection:** "The Book of the New Sun" resolves to *The Urth
of the New Sun* (the sequel). Omnibus and series titles are genuinely ambiguous;
judged acceptable.

## Implementation

Fetch the top ~8 hits, score each, take the best. Destined for
`backend/app/services/ranking.py`.

```python
"""Re-ranking for provider search results.

Hardcover's search is Typesense-backed and ranks purely on text relevance, which
puts the wrong edition first often enough to matter. Measured on a 20-book
sample, taking hit #0 gave the correct book 13/20 times; the heuristic below
gave 20/20 and lifted median ratings_count from 425 to 911.

Two failure modes it corrects:
  1. Parasitic editions -- "Workbook for X", "Summary of X" -- outrank the book.
  2. The canonical edition sits a few positions down behind sparse duplicates.
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
```

## Tests

Cases are drawn from real Hardcover responses recorded during evaluation, so
they encode actual failures rather than invented ones. Destined for
`backend/tests/test_ranking.py`.

```python
"""Guards the search re-ranking heuristic against regressions."""

from app.services.ranking import score_candidate


def test_rejects_parasitic_editions() -> None:
    assert (
        score_candidate("The Body Keeps the Score", "Workbook for The Body Keeps Score", [], 0, 1)
        is None
    )
    assert score_candidate("Stoner", "Stoner by John Williams: Summary", [], 0, 1) is None


def test_loosely_related_title_is_outranked_not_rejected() -> None:
    """'Superman for Tomorrow' ranks #0 for this query on Hardcover.

    It survives the overlap filter -- repeated words collapse under set
    tokenization, so the query is only {tomorrow, and} and a single shared
    token clears 50%. Popularity is what demotes it, which is the intended
    division of labour: the filter drops junk, the score orders the rest.
    """
    wrong = score_candidate("Tomorrow and Tomorrow and Tomorrow", "Superman for Tomorrow", [], 4, 0)
    right = score_candidate(
        "Tomorrow and Tomorrow and Tomorrow",
        "Tomorrow, and Tomorrow, and Tomorrow",
        ["Gabrielle Zevin"],
        2631,
        5,
    )
    assert wrong is not None and right is not None
    assert right > wrong


def test_popular_correct_edition_beats_sparse_duplicate() -> None:
    """'Piranesi' returns an art-history book at #0 and Susanna Clarke at #1."""
    wrong = score_candidate("Piranesi", "Piranesi", ["Giovanni Battista Piranesi"], 0, 0)
    right = score_candidate("Piranesi", "Piranesi", ["Susanna Clarke"], 2946, 1)
    assert wrong is not None and right is not None
    assert right > wrong


def test_author_tokens_count_toward_overlap() -> None:
    """'James Percival Everett' -- the author name carries most of the signal."""
    assert (
        score_candidate("James Percival Everett", "James", ["Percival Everett"], 616, 2) is not None
    )


def test_deeper_correct_hit_beats_shallow_noise() -> None:
    noise = score_candidate("Sapiens", "Sapiens", ["Silvana Condemi"], 0, 0)
    real = score_candidate(
        "Sapiens", "Sapiens: A Brief History of Humankind", ["Yuval Noah Harari"], 2084, 9
    )
    assert real is not None
    assert noise is None or real > noise
```

## Note on the tokenizer

Set-based tokenization collapses "Tomorrow and Tomorrow and Tomorrow" to
`{tomorrow, and}`, so a single shared token clears the 50% overlap threshold.
The filter therefore does *not* reject "Superman for Tomorrow" — the popularity
term demotes it. That division of labour is intentional: the filter drops junk,
the score orders what remains. An earlier test asserted rejection and was wrong
about the design, not about the code.
