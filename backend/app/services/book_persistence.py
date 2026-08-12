"""Turning a provider payload into domain rows.

This is the only write path into `books`, and it runs on cache-on-save: a book
is persisted when a user shelves it or records a reading status, never when it
merely appears in search results. That is what keeps `books` a table of books
people care about rather than a log of everything anyone typed.

Everything here is idempotent. Shelving the same book onto a second shelf must
not create a second book row, duplicate its authors, or stack up ratings.
"""

from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Author, Book, BookAuthor, BookRating, RatingSource
from app.providers.hardcover import AuthorRef, BookDetail, HardcoverClient
from app.services.book_detail import get_book_detail


def _parse_release_date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        # Providers sometimes give a year alone. A missing date is survivable;
        # refusing to save the book over it is not.
        return None


def _ensure_authors(db: Session, refs: list[AuthorRef]) -> list[Author]:
    """Get-or-create by provider id, preserving the order given."""
    if not refs:
        return []

    ids = [ref.hardcover_id for ref in refs]
    existing = {
        author.hardcover_id: author
        for author in db.scalars(select(Author).where(Author.hardcover_id.in_(ids)))
    }

    authors: list[Author] = []
    for ref in refs:
        author = existing.get(ref.hardcover_id)
        if author is None:
            author = Author(hardcover_id=ref.hardcover_id, name=ref.name)
            db.add(author)
            existing[ref.hardcover_id] = author
        elif author.name != ref.name:
            # The provider is the source of truth for how a name is spelled.
            author.name = ref.name
        authors.append(author)

    db.flush()
    return authors


def _sync_authors(db: Session, book: Book, refs: list[AuthorRef]) -> None:
    authors = _ensure_authors(db, refs)
    wanted = {author.id: position for position, author in enumerate(authors)}

    existing = {link.author_id: link for link in book.authors}
    for author_id, link in existing.items():
        if author_id not in wanted:
            db.delete(link)
        elif link.position != wanted[author_id]:
            link.position = wanted[author_id]

    for author_id, position in wanted.items():
        if author_id not in existing:
            db.add(BookAuthor(book_id=book.id, author_id=author_id, position=position))

    db.flush()
    # book.authors was loaded (empty) above, so the identity map still holds that
    # empty collection. Without expiring it the caller sees a book with no
    # authors until the session is closed.
    db.expire(book, ["authors"])


def _sync_rating(db: Session, book: Book, detail: BookDetail) -> None:
    """One row per (book, source). Hardcover is the only source so far; the key
    is what lets others coexist later rather than overwrite.
    """
    if detail.rating is None and detail.ratings_count == 0:
        return

    existing = db.scalar(
        select(BookRating).where(
            BookRating.book_id == book.id,
            BookRating.source == RatingSource.HARDCOVER,
        )
    )
    now = datetime.now(UTC)

    if existing is None:
        db.add(
            BookRating(
                book_id=book.id,
                source=RatingSource.HARDCOVER,
                rating=detail.rating,
                ratings_count=detail.ratings_count,
                fetched_at=now,
            )
        )
    else:
        existing.rating = detail.rating
        existing.ratings_count = detail.ratings_count
        existing.fetched_at = now

    db.flush()


def _apply_detail(db: Session, book: Book, detail: BookDetail) -> Book:
    book.title = detail.title
    book.subtitle = detail.subtitle
    book.description = detail.description
    book.page_count = detail.page_count
    book.cover_url = detail.cover_url
    book.published_date = _parse_release_date(detail.release_date)
    book.isbn13 = next((i for i in detail.isbns if len(i) == 13), None)
    book.isbn10 = next((i for i in detail.isbns if len(i) == 10), None)
    book.metadata_refreshed_at = datetime.now(UTC)

    db.flush()
    _sync_authors(db, book, detail.authors)
    _sync_rating(db, book, detail)
    return book


def ensure_book(
    db: Session,
    hardcover_id: str,
    *,
    client: HardcoverClient | None = None,
) -> Book | None:
    """The persisted book for a provider id, creating it if absent.

    None when the provider does not know the id -- the caller turns that into a
    404 rather than persisting a shell row.
    """
    book = db.scalar(select(Book).where(Book.hardcover_id == hardcover_id))
    if book is not None:
        return book

    detail = get_book_detail(db, hardcover_id, client=client)
    if detail is None:
        return None

    book = Book(hardcover_id=hardcover_id, title=detail.title)
    db.add(book)
    db.flush()
    return _apply_detail(db, book, detail)
