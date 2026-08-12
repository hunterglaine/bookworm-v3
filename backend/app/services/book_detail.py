"""Book detail: cache lookup, then a provider call.

Unlike search there is no ranking step -- an id resolves to one book or to
nothing. The `books` table is not consulted: rows only exist there once a user
shelves a book, so detail is provider-backed for every book until Phase 6.
"""

from dataclasses import asdict, fields
from typing import Any

from sqlalchemy.orm import Session

from app.providers.hardcover import AuthorRef, BookDetail, HardcoverClient, RatingBucket
from app.services import provider_cache


def _decode(payload: Any) -> BookDetail | None:
    """Rebuild a detail from a cached payload, or None if it is unusable.

    Tolerates a payload written by an older shape of BookDetail -- a deploy
    should degrade to a cache miss, not a 500.
    """
    if not isinstance(payload, dict):
        return None

    known = {f.name for f in fields(BookDetail)}
    try:
        values = {k: v for k, v in payload.items() if k in known}
        values["ratings_distribution"] = [
            RatingBucket(**bucket) for bucket in values.get("ratings_distribution") or []
        ]
        values["authors"] = [AuthorRef(**author) for author in values.get("authors") or []]
        return BookDetail(**values)
    except TypeError:
        return None


def get_book_detail(
    db: Session,
    hardcover_id: str,
    *,
    client: HardcoverClient | None = None,
) -> BookDetail | None:
    detail = _decode(provider_cache.read(db, provider_cache.BOOK, hardcover_id))
    if detail is not None:
        return detail

    provider = client or HardcoverClient()
    try:
        detail = provider.get_book(hardcover_id)
    finally:
        if client is None:
            provider.close()

    if detail is None:
        # Not cached: a miss is cheap, and caching it would keep a book
        # invisible for the whole TTL if the catalogue later gains it.
        return None

    provider_cache.write(db, provider_cache.BOOK, hardcover_id, asdict(detail))
    db.commit()
    return detail
