from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Date, DateTime, Identity, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.book_author import BookAuthor
    from app.models.book_rating import BookRating


class Book(TimestampMixin, Base):
    """A book, written only when a user shelves one.

    Search results are not persisted -- they come from the provider live, so
    this table stays meaningful instead of filling with search debris.
    """

    __tablename__ = "books"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)

    # Identity keys, all optional: a book is whatever the provider that supplied
    # it could tell us, and providers disagree about which ids exist.
    hardcover_id: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    isbn13: Mapped[str | None] = mapped_column(String(13), index=True)
    isbn10: Mapped[str | None] = mapped_column(String(10), index=True)
    google_books_id: Mapped[str | None] = mapped_column(String(64), index=True)
    open_library_id: Mapped[str | None] = mapped_column(String(64), index=True)
    goodreads_id: Mapped[str | None] = mapped_column(String(64), index=True)

    title: Mapped[str] = mapped_column(String(500), index=True)
    subtitle: Mapped[str | None] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text)
    page_count: Mapped[int | None] = mapped_column(Integer)
    cover_url: Mapped[str | None] = mapped_column(Text)
    # Dominant colour of the cover, as "#rrggbb". Generated spines take their
    # colour from it -- without it a shelf is thirty identical grey rectangles.
    cover_color: Mapped[str | None] = mapped_column(String(9))
    published_date: Mapped[date | None] = mapped_column(Date)

    # Drives cache invalidation -- provider metadata goes stale, and the 60
    # req/min budget means we refresh deliberately rather than on every view.
    metadata_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    authors: Mapped[list[BookAuthor]] = relationship(
        back_populates="book",
        cascade="all, delete-orphan",
        order_by="BookAuthor.position",
    )
    ratings: Mapped[list[BookRating]] = relationship(
        back_populates="book", cascade="all, delete-orphan"
    )
