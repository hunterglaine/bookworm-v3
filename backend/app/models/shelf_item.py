from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.book import Book
    from app.models.shelf import Shelf


class ShelfItem(Base):
    """A book's placement on one shelf.

    `position` exists because the whole point of the UI is a shelf you arrange,
    so the order has to be the user's, not the database's.
    """

    __tablename__ = "shelf_items"

    shelf_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("shelves.id", ondelete="CASCADE"), primary_key=True
    )
    book_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("books.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    shelf: Mapped[Shelf] = relationship(back_populates="items")
    book: Mapped[Book] = relationship()
