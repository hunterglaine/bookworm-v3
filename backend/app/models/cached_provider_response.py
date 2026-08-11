from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CachedProviderResponse(Base):
    """Provider responses held to stay inside 60 requests/minute.

    One table rather than one per response shape: this models a storage
    mechanism, not a domain entity. Both a search and a book detail are "a
    provider response we did not want to pay for twice", so they share a single
    eviction query and a single TTL setting. Per-shape tables would duplicate
    that logic once more with every cached call added.

    `kind` makes the two uses visible in the schema instead of hiding them in a
    key prefix, which keeps the table readable in psql and leaves room for
    per-kind expiry without a migration.

    Stored in Postgres rather than process memory so the budget is shared across
    workers and survives a restart.
    """

    __tablename__ = "cached_provider_responses"

    # "search" | "book". Not an enum: adding a cached call should not require a
    # migration, and a wrong value here fails loudly at the call site anyway.
    kind: Mapped[str] = mapped_column(String(32), primary_key=True)
    cache_key: Mapped[str] = mapped_column(String(512), primary_key=True)
    # A list for searches, an object for details -- whatever the provider gave.
    payload: Mapped[Any] = mapped_column(JSONB)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
