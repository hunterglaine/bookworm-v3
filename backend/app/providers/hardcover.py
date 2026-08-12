"""Hardcover book search and detail.

Two different query styles, because Hardcover exposes two different things:

- `search` is a Typesense passthrough. The response carries one opaque `results`
  blob rather than a typed selection set, so its shape is discovered from real
  responses rather than from the schema. Fixtures in tests/fixtures pin it.
- `books` is an ordinary Hasura table query with a real selection set, and it is
  the only place `description` and `ratings_distribution` are available --
  search documents carry neither.
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

BOOK_QUERY = """query Book($id: Int!) {
  books(where: {id: {_eq: $id}}, limit: 1) {
    id
    title
    subtitle
    description
    pages
    rating
    ratings_count
    ratings_distribution
    release_date
    users_read_count
    cached_tags
    image { url }
    contributions { author { id name } }
    editions(limit: 20) { isbn_10 isbn_13 }
  }
}"""


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


@dataclass(frozen=True, slots=True)
class RatingBucket:
    """One bar of the ratings histogram."""

    rating: float
    count: int


@dataclass(frozen=True, slots=True)
class AuthorRef:
    """An author with provider identity, so persistence can match on the id
    rather than the name.
    """

    hardcover_id: str
    name: str


@dataclass(frozen=True, slots=True)
class BookDetail:
    """Everything the detail view needs, from the books table rather than search."""

    hardcover_id: str
    title: str
    subtitle: str | None
    description: str | None
    page_count: int | None
    rating: float | None
    ratings_count: int
    ratings_distribution: list[RatingBucket]
    release_date: str | None
    users_read_count: int
    cover_url: str | None
    authors: list[AuthorRef]
    genres: list[str]
    moods: list[str]
    isbns: list[str]

    @property
    def author_names(self) -> list[str]:
        return [author.name for author in self.authors]


def _tag_names(cached_tags: Any, category: str) -> list[str]:
    """Pull one category out of `cached_tags`.

    The field is a dict keyed by category ("Genre", "Mood", "Tag"), each holding
    entries already ordered by how many users applied them.
    """
    if not isinstance(cached_tags, dict):
        return []
    entries = cached_tags.get(category) or []
    if not isinstance(entries, list):
        return []
    return [str(e["tag"]) for e in entries if isinstance(e, dict) and e.get("tag")]


def _parse_distribution(raw: Any) -> list[RatingBucket]:
    """Sorted low to high, so the histogram renders in a predictable order."""
    if not isinstance(raw, list):
        return []

    buckets = [
        RatingBucket(rating=float(e["rating"]), count=int(e.get("count") or 0))
        for e in raw
        if isinstance(e, dict) and e.get("rating") is not None
    ]
    return sorted(buckets, key=lambda b: b.rating)


def parse_book_response(payload: dict[str, Any]) -> BookDetail | None:
    """None when the id matches nothing -- an unknown book is a 404, not an error."""
    if payload.get("errors"):
        messages = "; ".join(str(e.get("message", e)) for e in payload["errors"])
        raise HardcoverError(f"Hardcover returned errors: {messages}")

    rows = (payload.get("data") or {}).get("books") or []
    if not rows:
        return None

    row = rows[0]
    if not row.get("id") or not row.get("title"):
        return None

    ratings_count = int(row.get("ratings_count") or 0)
    raw_rating = row.get("rating")
    rating = float(raw_rating) if raw_rating and ratings_count > 0 else None

    image = row.get("image")
    cover_url = image.get("url") if isinstance(image, dict) else None

    authors: list[AuthorRef] = []
    seen_authors: set[str] = set()
    for contribution in row.get("contributions") or []:
        if not isinstance(contribution, dict):
            continue
        author = contribution.get("author")
        if not isinstance(author, dict) or not author.get("id") or not author.get("name"):
            continue
        author_id = str(author["id"])
        # One person can contribute twice (author and illustrator, say); the
        # book should still list them once.
        if author_id in seen_authors:
            continue
        seen_authors.add(author_id)
        authors.append(AuthorRef(hardcover_id=author_id, name=str(author["name"])))

    isbns: list[str] = []
    for edition in row.get("editions") or []:
        if not isinstance(edition, dict):
            continue
        isbns.extend(str(edition[k]) for k in ("isbn_13", "isbn_10") if edition.get(k))

    return BookDetail(
        hardcover_id=str(row["id"]),
        title=str(row["title"]),
        subtitle=str(row["subtitle"]) if row.get("subtitle") else None,
        description=str(row["description"]) if row.get("description") else None,
        page_count=int(row["pages"]) if row.get("pages") else None,
        rating=rating,
        ratings_count=ratings_count,
        ratings_distribution=_parse_distribution(row.get("ratings_distribution")),
        release_date=str(row["release_date"]) if row.get("release_date") else None,
        users_read_count=int(row.get("users_read_count") or 0),
        cover_url=str(cover_url) if cover_url else None,
        authors=authors,
        genres=_tag_names(row.get("cached_tags"), "Genre"),
        moods=_tag_names(row.get("cached_tags"), "Mood"),
        isbns=list(dict.fromkeys(isbns)),
    )


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

    def _post(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._client.post(self._url, json={"query": query, "variables": variables})
        except httpx.HTTPError as exc:
            raise HardcoverError(f"Hardcover request failed: {exc}") from exc

        if response.status_code == httpx.codes.TOO_MANY_REQUESTS:
            raise HardcoverError("Hardcover rate limit exceeded (60 req/min)")
        if response.is_error:
            raise HardcoverError(f"Hardcover returned HTTP {response.status_code}")

        body: dict[str, Any] = response.json()
        return body

    def search(self, query: str, *, limit: int = DEFAULT_PER_PAGE) -> list[BookSearchHit]:
        return parse_search_response(self._post(SEARCH_QUERY, {"query": query, "perPage": limit}))

    def get_book(self, hardcover_id: str) -> BookDetail | None:
        """None when no book has that id."""
        try:
            book_id = int(hardcover_id)
        except ValueError:
            return None

        return parse_book_response(self._post(BOOK_QUERY, {"id": book_id}))
