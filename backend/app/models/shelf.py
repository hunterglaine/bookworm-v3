from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Identity, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.shelf_item import ShelfItem
    from app.models.user import User


class Shelf(TimestampMixin, Base):
    """A user-created shelf. Orthogonal to reading status.

    A book can sit on three shelves while having exactly one status -- that
    separation is why shelves and user_books are different tables.
    """

    __tablename__ = "shelves"
    __table_args__ = (UniqueConstraint("user_id", "slug", name="uq_shelves_user_slug"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    slug: Mapped[str] = mapped_column(String(100))

    user: Mapped[User] = relationship(back_populates="shelves")
    items: Mapped[list[ShelfItem]] = relationship(
        back_populates="shelf", cascade="all, delete-orphan", order_by="ShelfItem.position"
    )
