"""SQLAlchemy models.

Every model module must be imported here or Alembic autogenerate will not see
the table and will emit a spurious drop.
"""

from app.db.base import Base
from app.models.author import Author
from app.models.book import Book
from app.models.book_author import BookAuthor
from app.models.book_rating import BookRating
from app.models.cached_provider_response import CachedProviderResponse
from app.models.enums import RatingSource, ReadingStatus
from app.models.refresh_token import RefreshToken
from app.models.shelf import Shelf
from app.models.shelf_item import ShelfItem
from app.models.user import User
from app.models.user_book import UserBook

__all__ = [
    "Author",
    "Base",
    "Book",
    "BookAuthor",
    "BookRating",
    "CachedProviderResponse",
    "RatingSource",
    "ReadingStatus",
    "RefreshToken",
    "Shelf",
    "ShelfItem",
    "User",
    "UserBook",
]
