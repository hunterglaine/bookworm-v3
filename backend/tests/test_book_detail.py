"""Book detail: parsing, caching, and the endpoint."""

import json
from pathlib import Path
from typing import Any

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CachedProviderResponse
from app.providers.hardcover import HardcoverClient, parse_book_response
from app.services.book_detail import get_book_detail

FIXTURES = Path(__file__).parent / "fixtures"
PIRANESI_ID = "175280"
CREDENTIALS = {"email": "detail@example.com", "password": "correct-horse-battery"}


def load(name: str) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads((FIXTURES / f"hardcover_book_{name}.json").read_text())
    return payload


class CountingClient(HardcoverClient):
    def __init__(self, payload: dict[str, Any]) -> None:
        self.calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            self.calls += 1
            return httpx.Response(200, json=payload)

        super().__init__(transport=httpx.MockTransport(handler))


def test_detail_carries_what_search_could_not() -> None:
    """description and ratings_distribution are the reason this query exists."""
    book = parse_book_response(load("piranesi"))

    assert book is not None
    assert book.description and len(book.description) > 100
    assert len(book.ratings_distribution) > 1


def test_distribution_is_sorted_low_to_high() -> None:
    book = parse_book_response(load("piranesi"))
    assert book is not None

    ratings = [bucket.rating for bucket in book.ratings_distribution]
    assert ratings == sorted(ratings)


def test_distribution_totals_roughly_the_ratings_count() -> None:
    book = parse_book_response(load("piranesi"))
    assert book is not None

    assert sum(bucket.count for bucket in book.ratings_distribution) == book.ratings_count


def test_authors_carry_provider_identity() -> None:
    """Names alone would merge distinct people who share one -- the id is what
    keeps them apart when the author is persisted.
    """
    book = parse_book_response(load("piranesi"))
    assert book is not None

    assert "Susanna Clarke" in book.author_names
    clarke = next(a for a in book.authors if a.name == "Susanna Clarke")
    assert clarke.hardcover_id == "86621"


def test_unknown_id_is_not_an_error() -> None:
    """An empty result means 404, not a provider failure."""
    assert parse_book_response({"data": {"books": []}}) is None


def test_second_fetch_is_served_from_cache(db: Session) -> None:
    provider = CountingClient(load("piranesi"))

    first = get_book_detail(db, PIRANESI_ID, client=provider)
    second = get_book_detail(db, PIRANESI_ID, client=provider)

    assert provider.calls == 1
    assert first is not None and second is not None
    assert first.description == second.description
    assert first.ratings_distribution == second.ratings_distribution


def test_cached_under_the_book_kind(db: Session) -> None:
    """Search and detail share a table, so the kind keeps them apart."""
    get_book_detail(db, PIRANESI_ID, client=CountingClient(load("piranesi")))

    entry = db.scalar(select(CachedProviderResponse))
    assert entry is not None
    assert entry.kind == "book"
    assert entry.cache_key == PIRANESI_ID


def test_missing_book_is_not_cached(db: Session) -> None:
    """Caching a 404 would hide the book for a full TTL if it later appears."""
    provider = CountingClient({"data": {"books": []}})

    assert get_book_detail(db, "999999999", client=provider) is None
    assert db.scalar(select(CachedProviderResponse)) is None


def test_non_numeric_id_never_reaches_the_provider(db: Session) -> None:
    provider = CountingClient(load("piranesi"))
    assert get_book_detail(db, "not-an-id", client=provider) is None
    assert provider.calls == 0


def test_detail_requires_authentication(client: TestClient) -> None:
    assert client.get(f"/api/v1/books/{PIRANESI_ID}").status_code == 401


def test_unknown_book_returns_404(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json=CREDENTIALS)
    assert client.get("/api/v1/books/not-an-id").status_code == 404
