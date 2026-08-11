from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import ACCESS_COOKIE, REFRESH_COOKIE, CurrentUser, DbSession
from app.config import get_settings
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models import RefreshToken, User
from app.schemas.auth import LoginRequest, RegisterRequest, UserResponse

router = APIRouter(prefix="/auth")

# Verified against when no user matches, so a request for an unknown address
# costs the same as one for a known address. Without this, response timing
# tells an attacker which emails are registered.
_DUMMY_HASH = hash_password("timing-attack-placeholder")

# The refresh cookie is scoped to this prefix, so it is not attached to every
# request the way the access cookie is. Fewer places to leak from.
_REFRESH_COOKIE_PATH = "/api/v1/auth"


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        max_age=settings.access_token_ttl_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=settings.refresh_token_ttl_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path=_REFRESH_COOKIE_PATH,
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path=_REFRESH_COOKIE_PATH)


def _issue_session(db: Session, user: User, response: Response) -> None:
    settings = get_settings()
    raw_token, token_digest = generate_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_digest,
            expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_ttl_days),
        )
    )
    db.flush()
    _set_auth_cookies(response, create_access_token(user.id), raw_token)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, response: Response, db: DbSession) -> User:
    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
    )
    db.add(user)
    db.flush()

    _issue_session(db, user, response)
    db.commit()
    return user


@router.post("/login", response_model=UserResponse)
def login(payload: LoginRequest, response: Response, db: DbSession) -> User:
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password"
    )

    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None:
        verify_password(_DUMMY_HASH, payload.password)
        raise invalid
    if not verify_password(user.password_hash, payload.password) or not user.is_active:
        raise invalid

    _issue_session(db, user, response)
    db.commit()
    return user


@router.post("/refresh", response_model=UserResponse)
def refresh(request: Request, response: Response, db: DbSession) -> User:
    """Exchange a refresh token for a new pair, rotating the old one out."""
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
    )

    raw_token = request.cookies.get(REFRESH_COOKIE)
    if not raw_token:
        raise invalid

    stored = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_token))
    )
    if stored is None:
        raise invalid

    if not stored.is_usable:
        # A revoked token being presented again means the raw value leaked --
        # the legitimate client would have rotated to the replacement. Drop
        # every session for that user rather than just refusing this one.
        if stored.revoked_at is not None:
            for token in db.scalars(
                select(RefreshToken).where(
                    RefreshToken.user_id == stored.user_id,
                    RefreshToken.revoked_at.is_(None),
                )
            ):
                token.revoked_at = datetime.now(UTC)
            db.commit()
        _clear_auth_cookies(response)
        raise invalid

    user = db.get(User, stored.user_id)
    if user is None or not user.is_active:
        raise invalid

    stored.revoked_at = datetime.now(UTC)
    _issue_session(db, user, response)
    db.commit()
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: DbSession) -> None:
    raw_token = request.cookies.get(REFRESH_COOKIE)
    if raw_token:
        stored = db.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_token))
        )
        if stored is not None and stored.revoked_at is None:
            stored.revoked_at = datetime.now(UTC)
            db.commit()

    _clear_auth_cookies(response)


@router.get("/me", response_model=UserResponse)
def me(current_user: CurrentUser) -> User:
    return current_user
