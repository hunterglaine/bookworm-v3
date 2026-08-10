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
from sqlalchemy import Engine, create_engine, make_url, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.base import Base

# Importing the package registers every model on Base.metadata.
import app.models  # noqa: F401  isort:skip


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
