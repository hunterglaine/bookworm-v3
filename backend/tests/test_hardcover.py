"""Provider tests against recorded responses.

Fixtures are real Hardcover payloads captured once by hand. Nothing here touches
the network, so the suite is deterministic and costs none of the 60 req/min
budget.
"""

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.providers.hardcover import (
    HardcoverClient,
    HardcoverError,
    parse_search_response,
)

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads((FIXTURES / f"hardcover_search_{name}.json").read_text())
    return payload


def client_serving(payload: dict[str, Any], status: int = 200) -> HardcoverClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=payload)

    return HardcoverClient(transport=httpx.MockTransport(handler))


def test_parses_a_real_response() -> None:
    hits = parse_search_response(load("piranesi"))

    assert len(hits) == 25
    assert all(hit.title for hit in hits)
    assert all(hit.hardcover_id for hit in hits)


def test_absent_rating_is_none_not_zero() -> None:
    """Hardcover reports rating 0.0 for unrated books. Zero is a valid score,
    so storing it as one would drag every average down.
    """
    hits = parse_search_response(load("piranesi"))
    unrated = [hit for hit in hits if hit.ratings_count == 0]

    assert unrated, "fixture should contain at least one unrated edition"
    assert all(hit.rating is None for hit in unrated)


def test_rated_books_keep_their_score() -> None:
    hits = parse_search_response(load("piranesi"))
    rated = [hit for hit in hits if hit.ratings_count > 0]

    assert rated
    assert all(hit.rating is not None and 0 < hit.rating <= 5 for hit in rated)


def test_documents_without_a_title_are_dropped() -> None:
    payload = {"data": {"search": {"results": {"hits": [{"document": {"id": "1"}}]}}}}
    assert parse_search_response(payload) == []


def test_graphql_errors_raise() -> None:
    payload = {"errors": [{"message": "field 'nope' not found"}]}
    with pytest.raises(HardcoverError, match="not found"):
        parse_search_response(payload)


def test_empty_results_are_not_an_error() -> None:
    payload: dict[str, Any] = {"data": {"search": {"results": {"hits": []}}}}
    assert parse_search_response(payload) == []


def test_search_returns_hits_in_provider_order() -> None:
    with client_serving(load("tomorrow")) as provider:
        hits = provider.search("Tomorrow and Tomorrow and Tomorrow")

    # Ranking is a separate concern -- the provider preserves what it was given.
    assert hits[0].title == "Superman for Tomorrow"


def test_rate_limit_is_reported_distinctly() -> None:
    with (
        client_serving({}, status=429) as provider,
        pytest.raises(HardcoverError, match="rate limit"),
    ):
        provider.search("anything")


def test_server_error_raises() -> None:
    with (
        client_serving({}, status=500) as provider,
        pytest.raises(HardcoverError, match="HTTP 500"),
    ):
        provider.search("anything")


def test_sends_bearer_scheme_with_the_bare_token() -> None:
    """The stored token has no "Bearer " prefix, so the client adds it. Getting
    this wrong surfaces as a 401 that looks like an expired token.
    """
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=load("sapiens"))

    with HardcoverClient(transport=httpx.MockTransport(handler)) as provider:
        provider.search("Sapiens")

    authorization = seen[0].headers["authorization"]
    assert authorization.startswith("Bearer ")
    assert not authorization.startswith("Bearer Bearer")
