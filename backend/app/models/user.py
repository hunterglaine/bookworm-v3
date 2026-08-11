from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, Identity, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.refresh_token import RefreshToken
    from app.models.shelf import Shelf
    from app.models.user_book import UserBook


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    # 320 is the RFC 5321 maximum: 64-char local part + @ + 255-char domain.
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    shelves: Mapped[list[Shelf]] = relationship(back_populates="user", cascade="all, delete-orphan")
    books: Mapped[list[UserBook]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
