"""Reading status, ratings, and reviews -- the user's own relationship to a book.

Deliberately separate from shelves. Shelving is filing; this is reading. A book
can sit on three shelves and still have exactly one status, or none at all.
"""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.models import Book, UserBook
from app.providers.hardcover import HardcoverError
from app.schemas.shelf import BookSummary, ReadingEntryResponse, ReadingStatusUpdate
from app.services.book_persistence import ensure_book
from app.services.shelves import author_names

router = APIRouter(prefix="/me")


def _entry(entry: UserBook, book: Book) -> ReadingEntryResponse:
    return ReadingEntryResponse(
        status=entry.status,
        rating=entry.rating,
        review=entry.review,
        started_at=entry.started_at,
        finished_at=entry.finished_at,
        updated_at=entry.updated_at,
        book=BookSummary(
            id=book.id,
            hardcover_id=book.hardcover_id,
            title=book.title,
            subtitle=book.subtitle,
            authors=author_names(book),
            cover_url=book.cover_url,
            page_count=book.page_count,
        ),
    )


@router.get("/books", response_model=list[ReadingEntryResponse])
def list_reading(current_user: CurrentUser, db: DbSession) -> list[ReadingEntryResponse]:
    rows = db.execute(
        select(UserBook, Book)
        .join(Book, Book.id == UserBook.book_id)
        .where(UserBook.user_id == current_user.id)
        .order_by(UserBook.updated_at.desc())
        .options(selectinload(Book.authors))
    ).all()

    return [_entry(entry, book) for entry, book in rows]


@router.put("/books/{hardcover_id}", response_model=ReadingEntryResponse)
def set_reading_status(
    hardcover_id: str,
    payload: ReadingStatusUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> ReadingEntryResponse:
    """Create or update this user's entry for a book.

    Recording a status persists the book, same as shelving does -- both are a
    user saying the book matters to them.
    """
    try:
        book = ensure_book(db, hardcover_id)
    except HardcoverError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    if book is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

    entry = db.scalar(
        select(UserBook).where(UserBook.user_id == current_user.id, UserBook.book_id == book.id)
    )
    if entry is None:
        entry = UserBook(user_id=current_user.id, book_id=book.id)
        db.add(entry)

    # Only fields actually sent are touched, so setting a rating does not wipe
    # a review, and clearing one is still possible by sending it as null.
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(entry, field, value)

    db.commit()
    db.refresh(entry)
    return _entry(entry, book)


@router.delete("/books/{hardcover_id}", status_code=status.HTTP_204_NO_CONTENT)
def clear_reading_status(hardcover_id: str, current_user: CurrentUser, db: DbSession) -> None:
    """Forget the reading entry. The book stays, and stays on its shelves."""
    entry = db.scalar(
        select(UserBook)
        .join(Book, Book.id == UserBook.book_id)
        .where(UserBook.user_id == current_user.id, Book.hardcover_id == hardcover_id)
    )
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No reading entry")

    db.delete(entry)
    db.commit()
