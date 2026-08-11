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


class RatingBucket(BaseModel):
    rating: float
    count: int


class BookDetailResponse(BaseModel):
    hardcover_id: str
    title: str
    subtitle: str | None
    description: str | None
    page_count: int | None
    rating: float | None
    ratings_count: int
    # Low to high. Shape matters: a 4.2 from a bimodal split is a different book
    # from a 4.2 everyone mildly liked.
    ratings_distribution: list[RatingBucket]
    release_date: str | None
    users_read_count: int
    cover_url: str | None
    authors: list[str]
    genres: list[str]
    moods: list[str]
    isbns: list[str]
