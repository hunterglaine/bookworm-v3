"""Shared FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import User

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(request: Request, db: DbSession) -> User:
    """The signed-in user, or 401.

    Deactivated accounts are rejected here rather than at login, so disabling an
    account takes effect within the access token's lifetime instead of lasting
    until the user happens to sign out.
    """
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
    )

    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise unauthorized

    payload = decode_access_token(token)
    if payload is None:
        raise unauthorized

    try:
        user_id = int(payload["sub"])
    except KeyError, TypeError, ValueError:
        raise unauthorized from None

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
