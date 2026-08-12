from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ReadingStatus


class ShelfCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class ShelfUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class ShelfResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    book_count: int
    # Only meaningful when the request asked about a specific book; False
    # otherwise. Lives here rather than on the book detail response because
    # that one is served from a cache shared by every user.
    contains_book: bool = False


class ShelfBookAdd(BaseModel):
    hardcover_id: str = Field(min_length=1, max_length=64)


class BookSummary(BaseModel):
    """A persisted book, as it appears on a shelf or in a reading list."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    hardcover_id: str | None
    title: str
    subtitle: str | None
    authors: list[str]
    cover_url: str | None
    # Drives the generated spine. Without it every spine is the same grey.
    cover_color: str | None
    page_count: int | None


class ShelfDetailResponse(BaseModel):
    id: int
    name: str
    slug: str
    books: list[BookSummary]


class ShelfContents(BaseModel):
    """The books a shelf should hold, in order.

    Sets membership as well as order, so a drag between shelves is two of these
    -- the source without the book, the target with it -- rather than a delete,
    an add, and a reorder that can half-fail.
    """

    book_ids: list[int]


class BookshelfShelf(BaseModel):
    id: int
    name: str
    slug: str
    books: list[BookSummary]


class ReadingStatusUpdate(BaseModel):
    status: ReadingStatus | None = None
    rating: float | None = Field(default=None, ge=0, le=5)
    review: str | None = None
    started_at: date | None = None
    finished_at: date | None = None


class ReadingEntryResponse(BaseModel):
    status: ReadingStatus
    rating: float | None
    review: str | None
    started_at: date | None
    finished_at: date | None
    updated_at: datetime
    book: BookSummary
