"""Shelf helpers: slugs and book summaries."""

import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Book, Shelf

_NON_SLUG = re.compile(r"[^a-z0-9]+")
MAX_SLUG_LENGTH = 100


def slugify(name: str) -> str:
    return _NON_SLUG.sub("-", name.lower()).strip("-")[:MAX_SLUG_LENGTH] or "shelf"


def unique_slug(db: Session, user_id: int, name: str, *, exclude_id: int | None = None) -> str:
    """A slug free within this user's shelves.

    Uniqueness is per user, so two people can both have "favourites"; only a
    collision with the same owner needs a suffix.
    """
    base = slugify(name)

    query = select(Shelf.slug).where(Shelf.user_id == user_id)
    if exclude_id is not None:
        # Renaming a shelf to its own current name must not collide with itself.
        query = query.where(Shelf.id != exclude_id)

    taken = set(db.scalars(query))

    if base not in taken:
        return base

    suffix = 2
    while f"{base}-{suffix}"[:MAX_SLUG_LENGTH] in taken:
        suffix += 1
    return f"{base}-{suffix}"[:MAX_SLUG_LENGTH]


def author_names(book: Book) -> list[str]:
    """Cover order, which is what book.authors is already sorted by."""
    return [link.author.name for link in book.authors]


def next_position(db: Session, shelf_id: int) -> int:
    """Append to the end. Manual reordering lands with the bookshelf UI."""
    from app.models import ShelfItem

    highest = db.scalar(select(func.max(ShelfItem.position)).where(ShelfItem.shelf_id == shelf_id))
    return 0 if highest is None else highest + 1
