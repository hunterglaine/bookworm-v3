from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, literal, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.models import Book, Shelf, ShelfItem
from app.providers.hardcover import HardcoverError
from app.schemas.shelf import (
    BookshelfShelf,
    BookSummary,
    ShelfBookAdd,
    ShelfContents,
    ShelfCreate,
    ShelfDetailResponse,
    ShelfResponse,
    ShelfUpdate,
)
from app.services.book_persistence import ensure_book
from app.services.shelves import author_names, next_position, unique_slug

router = APIRouter(prefix="/shelves")


def _summary(book: Book) -> BookSummary:
    return BookSummary(
        id=book.id,
        hardcover_id=book.hardcover_id,
        title=book.title,
        subtitle=book.subtitle,
        authors=author_names(book),
        cover_url=book.cover_url,
        cover_color=book.cover_color,
        page_count=book.page_count,
    )


def _owned_shelf(db: DbSession, user_id: int, shelf_id: int) -> Shelf:
    """404 rather than 403 for someone else's shelf -- whether it exists is not
    information a stranger is entitled to.
    """
    shelf = db.scalar(select(Shelf).where(Shelf.id == shelf_id, Shelf.user_id == user_id))
    if shelf is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shelf not found")
    return shelf


@router.get("", response_model=list[ShelfResponse])
def list_shelves(
    current_user: CurrentUser,
    db: DbSession,
    contains: Annotated[str | None, Query(max_length=64)] = None,
) -> list[ShelfResponse]:
    """The user's shelves, optionally flagging which hold a given book.

    `contains` takes a Hardcover id and answers "is it already on this shelf?"
    per row. It rides on this endpoint rather than on book detail because the
    answer is per user, and the book detail response is cached across all users.
    """
    holds_book = (
        select(ShelfItem.shelf_id)
        .join(Book, Book.id == ShelfItem.book_id)
        .where(ShelfItem.shelf_id == Shelf.id, Book.hardcover_id == contains)
        .exists()
    )

    rows = db.execute(
        select(
            Shelf,
            func.count(ShelfItem.book_id),
            holds_book if contains else literal(False),
        )
        .outerjoin(ShelfItem, ShelfItem.shelf_id == Shelf.id)
        .where(Shelf.user_id == current_user.id)
        .group_by(Shelf.id)
        .order_by(Shelf.name)
    ).all()

    return [
        ShelfResponse(
            id=shelf.id,
            name=shelf.name,
            slug=shelf.slug,
            book_count=count,
            contains_book=bool(has_book),
        )
        for shelf, count, has_book in rows
    ]


@router.get("/bookshelf", response_model=list[BookshelfShelf])
def bookshelf(current_user: CurrentUser, db: DbSession) -> list[BookshelfShelf]:
    """Every shelf with its books, in shelf order.

    One request rather than one per shelf: the visual bookshelf renders all of
    them at once, so N+1 round trips would be the whole page load.
    """
    shelves = db.scalars(
        select(Shelf).where(Shelf.user_id == current_user.id).order_by(Shelf.name)
    ).all()
    if not shelves:
        return []

    rows = db.execute(
        select(ShelfItem.shelf_id, Book)
        .join(Book, Book.id == ShelfItem.book_id)
        .where(ShelfItem.shelf_id.in_([shelf.id for shelf in shelves]))
        .order_by(ShelfItem.shelf_id, ShelfItem.position, ShelfItem.added_at)
        .options(selectinload(Book.authors))
    ).all()

    by_shelf: dict[int, list[BookSummary]] = {shelf.id: [] for shelf in shelves}
    for shelf_id, book in rows:
        by_shelf[shelf_id].append(_summary(book))

    return [
        BookshelfShelf(id=s.id, name=s.name, slug=s.slug, books=by_shelf[s.id]) for s in shelves
    ]


@router.post("", response_model=ShelfResponse, status_code=status.HTTP_201_CREATED)
def create_shelf(payload: ShelfCreate, current_user: CurrentUser, db: DbSession) -> ShelfResponse:
    shelf = Shelf(
        user_id=current_user.id,
        name=payload.name,
        slug=unique_slug(db, current_user.id, payload.name),
    )
    db.add(shelf)
    db.commit()

    return ShelfResponse(id=shelf.id, name=shelf.name, slug=shelf.slug, book_count=0)


@router.get("/{shelf_id}", response_model=ShelfDetailResponse)
def get_shelf(shelf_id: int, current_user: CurrentUser, db: DbSession) -> ShelfDetailResponse:
    shelf = _owned_shelf(db, current_user.id, shelf_id)

    books = db.scalars(
        select(Book)
        .join(ShelfItem, ShelfItem.book_id == Book.id)
        .where(ShelfItem.shelf_id == shelf.id)
        .order_by(ShelfItem.position, ShelfItem.added_at)
        .options(selectinload(Book.authors))
    ).all()

    return ShelfDetailResponse(
        id=shelf.id,
        name=shelf.name,
        slug=shelf.slug,
        books=[_summary(book) for book in books],
    )


@router.patch("/{shelf_id}", response_model=ShelfResponse)
def rename_shelf(
    shelf_id: int, payload: ShelfUpdate, current_user: CurrentUser, db: DbSession
) -> ShelfResponse:
    shelf = _owned_shelf(db, current_user.id, shelf_id)
    shelf.name = payload.name
    shelf.slug = unique_slug(db, current_user.id, payload.name, exclude_id=shelf.id)

    count = db.scalar(select(func.count(ShelfItem.book_id)).where(ShelfItem.shelf_id == shelf.id))
    db.commit()

    return ShelfResponse(id=shelf.id, name=shelf.name, slug=shelf.slug, book_count=count or 0)


@router.delete("/{shelf_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_shelf(shelf_id: int, current_user: CurrentUser, db: DbSession) -> None:
    shelf = _owned_shelf(db, current_user.id, shelf_id)
    # Only the shelf and its placements go; the books themselves may sit on
    # other shelves, and deleting them here would be a surprise.
    db.delete(shelf)
    db.commit()


@router.post("/{shelf_id}/books", response_model=BookSummary, status_code=status.HTTP_201_CREATED)
def add_book(
    shelf_id: int, payload: ShelfBookAdd, current_user: CurrentUser, db: DbSession
) -> BookSummary:
    """Shelving is the write path: this is where a book first becomes a row."""
    shelf = _owned_shelf(db, current_user.id, shelf_id)

    try:
        book = ensure_book(db, payload.hardcover_id)
    except HardcoverError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    if book is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

    already = db.scalar(
        select(ShelfItem).where(ShelfItem.shelf_id == shelf.id, ShelfItem.book_id == book.id)
    )
    if already is None:
        db.add(ShelfItem(shelf_id=shelf.id, book_id=book.id, position=next_position(db, shelf.id)))

    db.commit()
    return _summary(book)


@router.put("/{shelf_id}/books", response_model=ShelfDetailResponse)
def set_shelf_contents(
    shelf_id: int, payload: ShelfContents, current_user: CurrentUser, db: DbSession
) -> ShelfDetailResponse:
    """Replace what a shelf holds, and the order it holds it in.

    Sets membership as well as order so that a drag between shelves is two
    calls that each fully describe one shelf, rather than a remove and an add
    that can leave the book on both shelves or neither if one fails.

    Only books already persisted can be referenced -- this reorders what the
    user has, it is not a way to create books.
    """
    shelf = _owned_shelf(db, current_user.id, shelf_id)

    wanted = list(dict.fromkeys(payload.book_ids))
    known = set(db.scalars(select(Book.id).where(Book.id.in_(wanted))).all()) if wanted else set()
    missing = [book_id for book_id in wanted if book_id not in known]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown book ids: {missing}"
        )

    existing = {
        item.book_id: item
        for item in db.scalars(select(ShelfItem).where(ShelfItem.shelf_id == shelf.id))
    }

    for book_id, stale in existing.items():
        if book_id not in known:
            db.delete(stale)

    for position, book_id in enumerate(wanted):
        current = existing.get(book_id)
        if current is None:
            db.add(ShelfItem(shelf_id=shelf.id, book_id=book_id, position=position))
        else:
            current.position = position

    db.commit()

    books = db.scalars(
        select(Book)
        .join(ShelfItem, ShelfItem.book_id == Book.id)
        .where(ShelfItem.shelf_id == shelf.id)
        .order_by(ShelfItem.position, ShelfItem.added_at)
        .options(selectinload(Book.authors))
    ).all()

    return ShelfDetailResponse(
        id=shelf.id, name=shelf.name, slug=shelf.slug, books=[_summary(b) for b in books]
    )


@router.delete("/{shelf_id}/books/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_book(shelf_id: int, book_id: int, current_user: CurrentUser, db: DbSession) -> None:
    shelf = _owned_shelf(db, current_user.id, shelf_id)

    item = db.scalar(
        select(ShelfItem).where(ShelfItem.shelf_id == shelf.id, ShelfItem.book_id == book_id)
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not on this shelf")

    db.delete(item)
    db.commit()
