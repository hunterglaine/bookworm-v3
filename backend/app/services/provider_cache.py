"""Read/write helpers for cached provider responses.

Kept in one place so TTL and expiry are defined once. Every cached provider call
goes through here rather than reimplementing the freshness check.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import CachedProviderResponse

SEARCH = "search"
BOOK = "book"


def read(db: Session, kind: str, cache_key: str) -> Any | None:
    """The cached payload, or None when absent or past its TTL."""
    settings = get_settings()
    cutoff = datetime.now(UTC) - timedelta(hours=settings.search_cache_ttl_hours)

    return db.scalar(
        select(CachedProviderResponse.payload).where(
            CachedProviderResponse.kind == kind,
            CachedProviderResponse.cache_key == cache_key,
            CachedProviderResponse.fetched_at >= cutoff,
        )
    )


def write(db: Session, kind: str, cache_key: str, payload: Any) -> None:
    """Store a response, replacing any previous one for the same key.

    The caller commits. get_db only closes the session, so an uncommitted write
    is rolled back and every request stays a cache miss.
    """
    statement = pg_insert(CachedProviderResponse).values(
        kind=kind, cache_key=cache_key, payload=payload, fetched_at=datetime.now(UTC)
    )
    db.execute(
        statement.on_conflict_do_update(
            index_elements=[CachedProviderResponse.kind, CachedProviderResponse.cache_key],
            set_={
                "payload": statement.excluded.payload,
                "fetched_at": statement.excluded.fetched_at,
            },
        )
    )
