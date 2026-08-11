"""Auth flow: registration, login, session rotation, and revocation."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import ACCESS_COOKIE, REFRESH_COOKIE
from app.models import RefreshToken, User

CREDENTIALS = {"email": "reader@example.com", "password": "correct-horse-battery"}


def register(client: TestClient, **overrides: object) -> Response:
    return client.post("/api/v1/auth/register", json={**CREDENTIALS, **overrides})


def test_register_creates_user_and_starts_a_session(client: TestClient) -> None:
    response = register(client, display_name="Reader")

    assert response.status_code == 201
    assert response.json()["email"] == CREDENTIALS["email"]
    assert "password" not in response.text and "hash" not in response.text
    assert ACCESS_COOKIE in client.cookies
    assert REFRESH_COOKIE in client.cookies


def test_password_is_never_stored_in_the_clear(client: TestClient, db: Session) -> None:
    register(client)

    user = db.scalar(select(User).where(User.email == CREDENTIALS["email"]))
    assert user is not None
    assert user.password_hash != CREDENTIALS["password"]
    assert user.password_hash.startswith("$argon2")


def test_duplicate_email_is_rejected(client: TestClient) -> None:
    register(client)
    assert register(client).status_code == 409


def test_short_password_is_rejected(client: TestClient) -> None:
    assert register(client, password="short").status_code == 422


def test_login_with_correct_credentials_starts_a_session(client: TestClient) -> None:
    register(client)
    client.cookies.clear()

    response = client.post("/api/v1/auth/login", json=CREDENTIALS)

    assert response.status_code == 200
    assert ACCESS_COOKIE in client.cookies


def test_login_with_wrong_password_is_rejected(client: TestClient) -> None:
    register(client)
    client.cookies.clear()

    response = client.post(
        "/api/v1/auth/login", json={**CREDENTIALS, "password": "wrong-horse-battery"}
    )
    assert response.status_code == 401
    assert ACCESS_COOKIE not in client.cookies


def test_login_with_unknown_email_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever-long-one"}
    )
    assert response.status_code == 401


def test_me_requires_a_session(client: TestClient) -> None:
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_returns_the_signed_in_user(client: TestClient) -> None:
    register(client)

    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == CREDENTIALS["email"]


def test_deactivated_user_loses_access_immediately(client: TestClient, db: Session) -> None:
    """Checked per request rather than at login, so disabling an account takes
    effect within the access token's lifetime instead of at next sign-in.
    """
    register(client)
    user = db.scalar(select(User).where(User.email == CREDENTIALS["email"]))
    assert user is not None
    user.is_active = False
    db.flush()

    assert client.get("/api/v1/auth/me").status_code == 401


def test_refresh_rotates_the_token(client: TestClient) -> None:
    register(client)
    original = client.cookies[REFRESH_COOKIE]

    response = client.post("/api/v1/auth/refresh")

    assert response.status_code == 200
    assert client.cookies[REFRESH_COOKIE] != original


def test_a_rotated_token_cannot_be_used_again(client: TestClient) -> None:
    register(client)
    stale = client.cookies[REFRESH_COOKIE]
    client.post("/api/v1/auth/refresh")

    client.cookies.set(REFRESH_COOKIE, stale, path="/api/v1/auth")
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_replaying_a_revoked_token_kills_every_session(client: TestClient, db: Session) -> None:
    """Replay means the raw value leaked -- the real client would have rotated
    on. Refusing just that one request would leave the thief's other tokens
    working, so every live session for the user is dropped.
    """
    register(client)
    stale = client.cookies[REFRESH_COOKIE]
    client.post("/api/v1/auth/refresh")  # rotates; `stale` is now revoked

    client.cookies.set(REFRESH_COOKIE, stale, path="/api/v1/auth")
    client.post("/api/v1/auth/refresh")

    live = db.scalars(select(RefreshToken).where(RefreshToken.revoked_at.is_(None))).all()
    assert live == []


def test_logout_revokes_the_session_and_clears_cookies(client: TestClient, db: Session) -> None:
    register(client)

    response = client.post("/api/v1/auth/logout")

    assert response.status_code == 204
    assert ACCESS_COOKIE not in client.cookies
    live = db.scalars(select(RefreshToken).where(RefreshToken.revoked_at.is_(None))).all()
    assert live == []


def test_expired_refresh_token_is_rejected(client: TestClient, db: Session) -> None:
    register(client)
    stored = db.scalars(select(RefreshToken)).one()
    stored.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.flush()

    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_access_cookie_is_httponly_and_samesite_lax(client: TestClient) -> None:
    """The cookie the browser attaches automatically is the one JavaScript must
    not be able to read, and the one that needs CSRF protection.
    """
    response = register(client)

    access = next(h for h in response.headers.get_list("set-cookie") if h.startswith(ACCESS_COOKIE))
    assert "HttpOnly" in access
    assert "SameSite=lax" in access.replace("samesite", "SameSite")
