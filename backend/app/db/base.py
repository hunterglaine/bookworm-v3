from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base. Alembic autogenerate reads metadata from here.

    Every model module must be imported in app/models/__init__.py, otherwise
    autogenerate will not see the table and will emit a drop.
    """


class TimestampMixin:
    """created_at/updated_at maintained by the database, not the application.

    server_default and onupdate mean a row written by a migration or by psql
    gets correct timestamps too, which application-side defaults would miss.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
