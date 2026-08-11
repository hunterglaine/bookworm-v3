"""Book search: cache lookup, provider call, then ranking.

Ranking happens on read rather than being baked into the cache, so a change to
the heuristic takes effect immediately instead of waiting out the TTL on every
stored entry. It is a pure function over at most a handful of rows, so the cost
is nil.
"""

import re
from dataclasses import asdict, fields
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import CachedSearch
from app.providers.hardcover import DEFAULT_PER_PAGE, BookSearchHit, HardcoverClient
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


def _read_cache(db: Session, key: str) -> list[BookSearchHit] | None:
    settings = get_settings()
    cutoff = datetime.now(UTC) - timedelta(hours=settings.search_cache_ttl_hours)

    entry = db.scalar(
        select(CachedSearch).where(
            CachedSearch.query_key == key,
            CachedSearch.fetched_at >= cutoff,
        )
    )
    if entry is None:
        return None

    # Tolerate a stored payload written by an older shape of BookSearchHit --
    # a deploy should degrade to a cache miss, not a 500.
    known = {f.name for f in fields(BookSearchHit)}
    try:
        return [
            BookSearchHit(**{k: v for k, v in row.items() if k in known}) for row in entry.payload
        ]
    except TypeError:
        return None


def _write_cache(db: Session, key: str, hits: list[BookSearchHit]) -> None:
    payload: list[dict[str, Any]] = [asdict(hit) for hit in hits]
    statement = pg_insert(CachedSearch).values(
        query_key=key, payload=payload, fetched_at=datetime.now(UTC)
    )
    db.execute(
        statement.on_conflict_do_update(
            index_elements=[CachedSearch.query_key],
            set_={
                "payload": statement.excluded.payload,
                "fetched_at": statement.excluded.fetched_at,
            },
        )
    )


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
    hits = _read_cache(db, key)

    if hits is None:
        provider = client or HardcoverClient()
        try:
            hits = provider.search(normalized, limit=FETCH_DEPTH)
        finally:
            if client is None:
                provider.close()
        _write_cache(db, key, hits)
        # Must commit: get_db only closes the session, so an uncommitted write
        # is rolled back and every request becomes a cache miss -- which is
        # invisible in a test that reads back through the same session.
        db.commit()

    return rank(normalized, hits)[:limit]
