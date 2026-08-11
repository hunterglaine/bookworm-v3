"""Search orchestration: caching, ranking, and the endpoint."""

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CachedProviderResponse
from app.providers.hardcover import HardcoverClient, parse_search_response
from app.services.book_search import cache_key, normalize_query, rank, search_books

FIXTURES = Path(__file__).parent / "fixtures"
CREDENTIALS = {"email": "searcher@example.com", "password": "correct-horse-battery"}


def load(name: str) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads((FIXTURES / f"hardcover_search_{name}.json").read_text())
    return payload


class CountingClient(HardcoverClient):
    """Serves a fixture and records how many times it was asked."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            self.calls += 1
            return httpx.Response(200, json=payload)

        super().__init__(transport=httpx.MockTransport(handler))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Piranesi ", "piranesi"),
        ("PIRANESI", "piranesi"),
        ("Tomorrow  and\tTomorrow", "tomorrow and tomorrow"),
    ],
)
def test_queries_normalize_to_one_cache_entry(raw: str, expected: str) -> None:
    assert normalize_query(raw) == expected


def test_ranking_promotes_the_right_piranesi() -> None:
    """Hardcover returns the art-history Piranesi at #0 with zero ratings."""
    hits = parse_search_response(load("piranesi"))
    assert hits[0].authors[0] == "Giovanni Battista Piranesi"

    ranked = rank("piranesi", hits)
    assert "Susanna Clarke" in ranked[0].authors


def test_ranking_demotes_superman_for_tomorrow() -> None:
    hits = parse_search_response(load("tomorrow"))
    assert hits[0].title == "Superman for Tomorrow"

    ranked = rank("tomorrow and tomorrow and tomorrow", hits)
    assert ranked[0].title != "Superman for Tomorrow"


def test_ranking_finds_the_real_sapiens() -> None:
    hits = parse_search_response(load("sapiens"))
    ranked = rank("sapiens", hits)
    assert "Yuval Noah Harari" in ranked[0].authors


def test_second_search_is_served_from_cache(db: Session) -> None:
    """The whole point of the table: one upstream call per query per TTL."""
    provider = CountingClient(load("piranesi"))

    first = search_books(db, "Piranesi", client=provider)
    second = search_books(db, "  piranesi  ", client=provider)

    assert provider.calls == 1
    assert [hit.hardcover_id for hit in first] == [hit.hardcover_id for hit in second]


def test_cache_row_is_written_under_the_normalized_key(db: Session) -> None:
    search_books(db, "  PIRANESI ", client=CountingClient(load("piranesi")))

    entry = db.scalar(select(CachedProviderResponse))
    assert entry is not None
    assert entry.kind == "search"
    assert entry.cache_key == cache_key("piranesi")


def test_cache_stores_unranked_results(db: Session) -> None:
    """Ranking happens on read, so a heuristic change applies to cached entries
    immediately rather than waiting out the TTL.
    """
    search_books(db, "Piranesi", client=CountingClient(load("piranesi")))

    entry = db.scalar(select(CachedProviderResponse))
    assert entry is not None
    assert entry.payload[0]["authors"][0] == "Giovanni Battista Piranesi"


def test_cache_write_is_committed(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """get_db closes the session without committing, so an uncommitted cache
    write is silently discarded and every request stays a cache miss.

    Reading back through the same session cannot catch that -- it sees
    uncommitted data -- so this asserts the commit directly.
    """
    commits = 0
    original = Session.commit

    def counting_commit(self: Session) -> None:
        nonlocal commits
        commits += 1
        original(self)

    monkeypatch.setattr(Session, "commit", counting_commit)
    search_books(db, "Piranesi", client=CountingClient(load("piranesi")))

    assert commits == 1


def test_blank_query_never_reaches_the_provider(db: Session) -> None:
    provider = CountingClient(load("piranesi"))
    assert search_books(db, "   ", client=provider) == []
    assert provider.calls == 0


def test_search_requires_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/books/search", params={"q": "piranesi"}).status_code == 401


def test_search_rejects_an_empty_query(client: TestClient) -> None:
    client.post("/api/v1/auth/register", json=CREDENTIALS)
    assert client.get("/api/v1/books/search", params={"q": ""}).status_code == 422
