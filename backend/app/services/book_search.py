"""Book search: cache lookup, provider call, then ranking.

Ranking happens on read rather than being baked into the cache, so a change to
the heuristic takes effect immediately instead of waiting out the TTL on every
stored entry. It is a pure function over at most a handful of rows, so the cost
is nil.
"""

import re
from dataclasses import asdict, fields
from typing import Any

from sqlalchemy.orm import Session

from app.providers.hardcover import DEFAULT_PER_PAGE, BookSearchHit, HardcoverClient
from app.services import provider_cache
from app.services.ranking import score_candidate

MAX_QUERY_LENGTH = 200

# Fetch deep, show shallow. The provider is asked for FETCH_DEPTH candidates so
# the ranker has room to recover a good result buried behind near-empty stubs;
# only the best DEFAULT_RESULT_LIMIT are returned.
FETCH_DEPTH = DEFAULT_PER_PAGE
DEFAULT_RESULT_LIMIT = 8

_WHITESPACE = re.compile(r"\s+")


def normalize_query(query: str) -> str:
    """Collapse a query to its cacheable form.

    "  Piranesi " and "piranesi" are the same search, and treating them as two
    is two API calls out of a budget of sixty.
    """
    return _WHITESPACE.sub(" ", query).strip().lower()[:MAX_QUERY_LENGTH]


def cache_key(normalized_query: str, depth: int = FETCH_DEPTH) -> str:
    """Keyed by fetch depth, not by display limit.

    One cached fetch serves every page size, since narrowing happens after
    ranking. Including the display limit would multiply entries for no benefit.
    """
    return f"{depth}:{normalized_query}"


def _decode(payload: Any) -> list[BookSearchHit] | None:
    """Rebuild hits from a cached payload, or None if it is unusable.

    Tolerates a payload written by an older shape of BookSearchHit -- a deploy
    should degrade to a cache miss, not a 500.
    """
    if not isinstance(payload, list):
        return None

    known = {f.name for f in fields(BookSearchHit)}
    try:
        return [BookSearchHit(**{k: v for k, v in row.items() if k in known}) for row in payload]
    except TypeError:
        return None


def rank(query: str, hits: list[BookSearchHit]) -> list[BookSearchHit]:
    """Best first, with junk editions dropped entirely."""
    scored: list[tuple[float, BookSearchHit]] = []
    for position, hit in enumerate(hits):
        score = score_candidate(query, hit.title, hit.authors, hit.ratings_count, position)
        if score is not None:
            scored.append((score, hit))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [hit for _, hit in scored]


def search_books(
    db: Session,
    query: str,
    *,
    limit: int = DEFAULT_RESULT_LIMIT,
    client: HardcoverClient | None = None,
) -> list[BookSearchHit]:
    normalized = normalize_query(query)
    if not normalized:
        return []

    key = cache_key(normalized)
    hits = _decode(provider_cache.read(db, provider_cache.SEARCH, key))

    if hits is None:
        provider = client or HardcoverClient()
        try:
            hits = provider.search(normalized, limit=FETCH_DEPTH)
        finally:
            if client is None:
                provider.close()
        provider_cache.write(db, provider_cache.SEARCH, key, [asdict(hit) for hit in hits])
        db.commit()

    return rank(normalized, hits)[:limit]
