"""Password hashing and token handling.

Two different kinds of token, deliberately:

- The **access token** is a signed JWT. Nothing needs to touch the database to
  verify it, which is the point -- but equally, nothing can revoke it, which is
  why it is short-lived.
- The **refresh token** is opaque random bytes, stored as a SHA-256 digest. It
  is checked against the database on every use, so revocation is real. SHA-256
  rather than Argon2 is correct here: the input is 256 bits of entropy from the
  system CSPRNG, so there is no guessable password to slow an attacker down on.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.config import get_settings

# argon2-cffi's defaults track OWASP guidance. Tests override the parameters via
# a fixture rather than weakening them here, so the weak settings can never
# reach production by accident.
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        _hasher.verify(password_hash, password)
    except VerifyMismatchError, VerificationError, InvalidHashError:
        return False
    return True


def needs_rehash(password_hash: str) -> bool:
    """True when a hash predates the current Argon2 parameters."""
    return _hasher.check_needs_rehash(password_hash)


def create_access_token(user_id: int) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_ttl_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decoded payload, or None if the token is invalid, expired, or forged."""
    settings = get_settings()
    try:
        decoded: dict[str, Any] = jwt.decode(
            token, settings.secret_key, algorithms=[settings.jwt_algorithm]
        )
    except jwt.PyJWTError:
        return None
    return decoded


def generate_refresh_token() -> tuple[str, str]:
    """Return (raw token for the cookie, digest to store).

    The raw value never touches the database, so a database leak alone cannot
    be replayed as a session.
    """
    raw = secrets.token_urlsafe(32)
    return raw, hash_refresh_token(raw)


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
