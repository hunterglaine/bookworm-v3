from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Identity, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.book_author import BookAuthor


class Author(TimestampMixin, Base):
    """Normalized rather than a JSON blob on books, so "everything on my
    shelves by Le Guin" is a join instead of a scan.
    """

    __tablename__ = "authors"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)

    books: Mapped[list[BookAuthor]] = relationship(
        back_populates="author", cascade="all, delete-orphan"
    )
