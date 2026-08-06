"""SQLAlchemy models.

Every model module must be imported here or Alembic autogenerate will not see
the table and will emit a spurious drop.

Planned (Phase 2):
    user, refresh_token, book, author, book_author,
    book_rating, shelf, shelf_item, user_book
"""

from app.db.base import Base

__all__ = ["Base"]
