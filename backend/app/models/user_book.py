from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    Enum,
    Float,
    ForeignKey,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import ReadingStatus

if TYPE_CHECKING:
    from app.models.book import Book
    from app.models.user import User


class UserBook(TimestampMixin, Base):
    """A user's own relationship to a book: status, rating, review, dates.

    Separate from shelves on purpose. Shelving is filing; this is reading.
    """

    __tablename__ = "user_books"
    __table_args__ = (
        CheckConstraint("rating >= 0 AND rating <= 5", name="ck_user_books_rating_range"),
        CheckConstraint(
            "finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at",
            name="ck_user_books_finished_after_started",
        ),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    book_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("books.id", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[ReadingStatus] = mapped_column(
        # values_callable makes the CHECK match the StrEnum's values rather than
        # its member names -- without it, server_default below would violate the
        # very constraint on its own column. See book_rating.py.
        Enum(
            ReadingStatus,
            native_enum=False,
            length=20,
            create_constraint=True,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
        server_default=text(f"'{ReadingStatus.WANT_TO_READ.value}'"),
    )
    rating: Mapped[float | None] = mapped_column(Float)
    review: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[date | None] = mapped_column(Date)
    finished_at: Mapped[date | None] = mapped_column(Date)

    user: Mapped[User] = relationship(back_populates="books")
    book: Mapped[Book] = relationship()
