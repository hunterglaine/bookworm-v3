from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Integer, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.author import Author
    from app.models.book import Book


class BookAuthor(Base):
    """Association between a book and its authors.

    Carries `position` because author order is meaningful -- it is the order
    printed on the cover, and "et al." depends on knowing who came first.
    """

    __tablename__ = "book_authors"

    book_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("books.id", ondelete="CASCADE"), primary_key=True
    )
    author_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("authors.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    book: Mapped[Book] = relationship(back_populates="authors")
    author: Mapped[Author] = relationship(back_populates="books")
