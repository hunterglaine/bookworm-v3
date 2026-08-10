from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import RatingSource

if TYPE_CHECKING:
    from app.models.book import Book


class BookRating(TimestampMixin, Base):
    """One row per (book, source).

    Keyed this way so several providers can coexist on the same book and the UI
    decides which to show. This is what keeps the ratings-source decision
    reversible.
    """

    __tablename__ = "book_ratings"
    __table_args__ = (
        CheckConstraint("rating >= 0 AND rating <= 5", name="ck_book_ratings_rating_range"),
        CheckConstraint("ratings_count >= 0", name="ck_book_ratings_count_non_negative"),
    )

    book_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("books.id", ondelete="CASCADE"), primary_key=True
    )
    source: Mapped[RatingSource] = mapped_column(
        # create_constraint=True is required: SQLAlchemy omits the CHECK by
        # default for non-native enums, which would leave the column a bare
        # VARCHAR accepting anything.
        #
        # values_callable is required too, and less obvious: by default
        # SQLAlchemy persists the enum *member name* ("HARDCOVER"), not its
        # value ("hardcover"). Without this the CHECK would accept only
        # SHOUTING_CASE and every lowercase literal in the codebase would fail.
        Enum(
            RatingSource,
            native_enum=False,
            length=20,
            create_constraint=True,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        primary_key=True,
    )

    rating: Mapped[float | None] = mapped_column(Float)
    ratings_count: Mapped[int | None] = mapped_column(Integer)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    book: Mapped[Book] = relationship(back_populates="ratings")
