"""Database fixtures.

Tests run against a real Postgres (`bookworm_test`, created on demand) rather
than SQLite, because the schema leans on Postgres specifics -- IDENTITY columns,
CHECK constraints, timezone-aware timestamps -- that SQLite would silently
accept differently.

Schema here comes from Base.metadata, not from Alembic. Migrations are verified
separately in CI by running `alembic upgrade head` against a clean database, so
a broken migration still gets caught without paying for it in every test run.
"""

from collections.abc import Generator

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, make_url, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core import security
from app.db.base import Base
from app.db.session import get_db
from app.main import app

# Registers every model on Base.metadata. Bound to a private alias rather than
# written as `import app.models`, which would rebind `app` to the package and
# shadow the FastAPI instance imported above.
from app import models as _models  # noqa: F401  isort:skip


@pytest.fixture(scope="session")
def engine() -> Generator[Engine]:
    url = make_url(get_settings().database_url)
    test_url = url.set(database=f"{url.database}_test")

    # "postgres" is the maintenance database -- CREATE DATABASE cannot run from
    # inside the database being created, and cannot run in a transaction.
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.execute(
            text("select 1 from pg_database where datname = :name"),
            {"name": test_url.database},
        ).scalar()
        if not exists:
            conn.execute(text(f'create database "{test_url.database}"'))
    admin.dispose()

    test_engine = create_engine(test_url)
    Base.metadata.create_all(test_engine)
    yield test_engine
    Base.metadata.drop_all(test_engine)
    test_engine.dispose()


@pytest.fixture
def db(engine: Engine) -> Generator[Session]:
    """A session whose work is rolled back when the test ends.

    join_transaction_mode="create_savepoint" lets a test call session.commit()
    -- which some behaviour genuinely needs, e.g. checking a server_default --
    without ending the outer transaction that provides the isolation.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture(scope="session", autouse=True)
def _cheap_password_hashing() -> Generator[None]:
    """Argon2 at OWASP strength costs ~50ms a call, which a suite that logs in
    repeatedly pays over and over.

    Weakened here rather than in app.core.security, so the production defaults
    stay strong and no weak setting can ship by accident.
    """
    original = security._hasher
    security._hasher = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)
    yield
    security._hasher = original


@pytest.fixture
def client(db: Session) -> Generator[TestClient]:
    """A client sharing the test's transaction, so requests roll back too."""

    def _override_get_db() -> Generator[Session]:
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
