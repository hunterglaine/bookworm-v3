from pydantic import BaseModel


class BookSearchResult(BaseModel):
    hardcover_id: str
    title: str
    authors: list[str]
    cover_url: str | None
    page_count: int | None
    # None means unrated, not zero -- see the provider's parsing note.
    rating: float | None
    ratings_count: int
    release_year: int | None
    genres: list[str]


class BookSearchResponse(BaseModel):
    query: str
    results: list[BookSearchResult]
