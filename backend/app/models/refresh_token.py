from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class RefreshToken(TimestampMixin, Base):
    """A revocable session.

    Stores the SHA-256 digest, never the token itself, so a database leak
    cannot be replayed as a live session. Rows are kept after revocation rather
    than deleted -- rotation needs to tell "already used" apart from "never
    existed", and only the former indicates a stolen token.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="refresh_tokens")

    @property
    def is_usable(self) -> bool:
        return self.revoked_at is None and self.expires_at > datetime.now(UTC)
