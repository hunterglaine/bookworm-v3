"""Hardcover book search.

Hardcover's `search` field is a Typesense passthrough: the GraphQL response
carries a single `results` blob rather than a typed selection set, so the shape
below is discovered from real responses rather than from the schema. Fixtures in
tests/fixtures pin it.

Note that search documents carry no description -- that needs a separate lookup
against the books table, which is Phase 5's problem.
"""

from dataclasses import dataclass
from typing import Any, Self

import httpx

from app.config import get_settings

SEARCH_QUERY = """query Search($query: String!, $perPage: Int!) {
  search(query: $query, query_type: "Book", per_page: $perPage, page: 1) {
    results
  }
}"""

# How many candidates to ask for. This is a fetch depth, not a page size: the
# ranker needs room to work. Hardcover returned "Sapiens: A Brief History of
# Humankind" at position 9 behind eight near-empty stubs, so anything under ~10
# cannot recover it no matter how good the scoring is.
DEFAULT_PER_PAGE = 25


class HardcoverError(RuntimeError):
    """The provider could not answer. Distinguishes a bad upstream from a bug."""


@dataclass(frozen=True, slots=True)
class BookSearchHit:
    """One search result, normalized out of the Typesense document."""

    hardcover_id: str
    title: str
    authors: list[str]
    cover_url: str | None
    page_count: int | None
    rating: float | None
    ratings_count: int
    release_year: int | None
    isbns: list[str]
    genres: list[str]
    slug: str | None


def _parse_hit(document: dict[str, Any]) -> BookSearchHit | None:
    """None for documents too incomplete to show -- a result with no title is
    not something a user can click on.
    """
    title = document.get("title")
    book_id = document.get("id")
    if not title or not book_id:
        return None

    # A rating of 0.0 with no ratings behind it is absence, not a score of zero.
    ratings_count = int(document.get("ratings_count") or 0)
    raw_rating = document.get("rating")
    rating = float(raw_rating) if raw_rating and ratings_count > 0 else None

    image = document.get("image")
    cover_url = image.get("url") if isinstance(image, dict) else None

    return BookSearchHit(
        hardcover_id=str(book_id),
        title=str(title),
        authors=[str(a) for a in document.get("author_names") or []],
        cover_url=str(cover_url) if cover_url else None,
        page_count=int(document["pages"]) if document.get("pages") else None,
        rating=rating,
        ratings_count=ratings_count,
        release_year=int(document["release_year"]) if document.get("release_year") else None,
        isbns=[str(i) for i in document.get("isbns") or []],
        genres=[str(g) for g in document.get("genres") or []],
        slug=str(document["slug"]) if document.get("slug") else None,
    )


def parse_search_response(payload: dict[str, Any]) -> list[BookSearchHit]:
    """Normalize a raw GraphQL response into hits, in the order returned."""
    if payload.get("errors"):
        messages = "; ".join(str(e.get("message", e)) for e in payload["errors"])
        raise HardcoverError(f"Hardcover returned errors: {messages}")

    search = (payload.get("data") or {}).get("search") or {}
    results = search.get("results") or {}
    hits = results.get("hits") or []

    parsed = (_parse_hit(hit.get("document") or {}) for hit in hits)
    return [hit for hit in parsed if hit is not None]


class HardcoverClient:
    """Blocking client. `transport` exists so tests can serve recorded fixtures.

    Sync rather than async deliberately: the app uses a synchronous Session and
    plain `def` endpoints, which FastAPI runs in a threadpool. An async client
    would force async endpoints, and those would block the event loop on every
    database call instead.
    """

    def __init__(
        self,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 15.0,
    ) -> None:
        settings = get_settings()
        if not settings.hardcover_token:
            raise HardcoverError("HARDCOVER_TOKEN is not set")

        self._client = httpx.Client(
            # The stored token is the bare JWT, so the scheme is added here.
            headers={"Authorization": f"Bearer {settings.hardcover_token}"},
            timeout=timeout,
            transport=transport,
        )
        self._url = settings.hardcover_api_url

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def search(self, query: str, *, limit: int = DEFAULT_PER_PAGE) -> list[BookSearchHit]:
        try:
            response = self._client.post(
                self._url,
                json={"query": SEARCH_QUERY, "variables": {"query": query, "perPage": limit}},
            )
        except httpx.HTTPError as exc:
            raise HardcoverError(f"Hardcover request failed: {exc}") from exc

        if response.status_code == httpx.codes.TOO_MANY_REQUESTS:
            raise HardcoverError("Hardcover rate limit exceeded (60 req/min)")
        if response.is_error:
            raise HardcoverError(f"Hardcover returned HTTP {response.status_code}")

        return parse_search_response(response.json())
