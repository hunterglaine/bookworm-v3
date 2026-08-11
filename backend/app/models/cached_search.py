from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CachedSearch(Base):
    """Provider search results, held to stay inside 60 requests/minute.

    Stored in Postgres rather than in process memory so the budget is shared
    across workers and survives a restart -- N workers with local caches would
    make N times the upstream calls for the same query.

    The payload is *pre-ranking* on purpose: ranking is a cheap pure function,
    so ranking on read means a change to the heuristic takes effect immediately
    instead of waiting out the TTL on every cached entry.
    """

    __tablename__ = "cached_searches"

    # "{limit}:{normalized query}" -- readable in psql, which is half the reason
    # this lives in the database at all.
    query_key: Mapped[str] = mapped_column(String(512), primary_key=True)
    payload: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
