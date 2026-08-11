# Search re-ranking

Why `app/services/ranking.py` exists and how its constants were chosen. The
implementation lives in the code; this file holds the measurements behind it.

## The problem

Hardcover's search is Typesense-backed and ranks on text relevance alone, which
surfaces the wrong edition often enough to matter. Taking hit `#0` gave the
correct book **13/20** on a 20-book sample.

Two failure modes, both measured:

1. **Parasitic editions** — "Workbook for X", "Summary and Discussions of X" —
   outrank the book itself.
2. **The canonical edition sits several positions down**, behind sparse
   duplicates that match the title just as literally.

The right book was almost always present, just not first:

| Query | Correct book at | Ratings |
|---|---|---|
| Tomorrow, and Tomorrow, and Tomorrow | #5 — Gabrielle Zevin | 2,631 |
| The Body Keeps the Score | #2 — van der Kolk | 443 |
| Stoner | #3 — John Williams | 823 |
| Piranesi | #1 — Susanna Clarke | 2,946 |
| James | #2 — Percival Everett | 616 |
| Sapiens | below the top 8 | — |

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

## Fetch depth is not page size

`FETCH_DEPTH = 25` in `app/services/book_search.py` is load-bearing, and the
reason is worth recording because the obvious value is wrong.

Searching "Sapiens" returns **228 matches**, and the first eight are all
near-identical stubs:

```
 0       0 ratings  Sapiens        ['Silvana Condemi']
 1       1 ratings  Sapiens        []
 2       1 ratings  Sapiens        ['Cátia Cernov']
 3–7     0 ratings  Sapiens        [] …
 9    2145 ratings  Sapiens: A Brief History of Humankind  ['Yuval Noah Harari']
```

Harari sits at **position 9**. No scoring function, however good, can recover a
result that was never fetched — so the provider is asked for 25 candidates and
only the best 8 are returned. Fetching shallow and ranking well is not a
substitute for fetching deep enough.

## Why the tokenizer looks too permissive

Set-based tokenization collapses "Tomorrow and Tomorrow and Tomorrow" to
`{tomorrow, and}`, so a single shared token clears the 50% overlap threshold.
The filter therefore does *not* reject "Superman for Tomorrow" — the popularity
term demotes it instead.

That division of labour is intentional: the filter drops junk, the score orders
what remains. An early test asserted rejection and was wrong about the design
rather than about the code.

## Refreshing the fixtures

`tests/fixtures/hardcover_search_*.json` are real responses captured by hand.
They pin the Typesense document shape, which is not described by the GraphQL
schema — `search` returns a single opaque `results` blob. Re-record them if the
provider's response shape changes.
