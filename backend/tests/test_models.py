"""Schema-level guarantees.

These assert things the database enforces, not things the application does --
if a constraint is missing from a migration, the corresponding test fails.
"""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Author,
    Book,
    BookAuthor,
    BookRating,
    RatingSource,
    ReadingStatus,
    Shelf,
    ShelfItem,
    User,
    UserBook,
)


def make_user(db: Session, email: str = "reader@example.com") -> User:
    user = User(email=email, password_hash="not-a-real-hash")
    db.add(user)
    db.flush()
    return user


def make_book(db: Session, title: str = "Piranesi") -> Book:
    book = Book(title=title)
    db.add(book)
    db.flush()
    return book


def test_email_is_unique(db: Session) -> None:
    make_user(db, "dup@example.com")
    db.add(User(email="dup@example.com", password_hash="x"))
    with pytest.raises(IntegrityError):
        db.flush()


def test_reading_status_defaults_to_want_to_read(db: Session) -> None:
    """The server_default has to agree with the enum CHECK on the same column.

    An earlier version stored enum *names* in the constraint while defaulting to
    a lowercase *value*, so any insert relying on the default was rejected.
    """
    user, book = make_user(db), make_book(db)
    db.add(UserBook(user_id=user.id, book_id=book.id))
    db.flush()
    db.commit()

    stored = db.query(UserBook).one()
    assert stored.status is ReadingStatus.WANT_TO_READ


def test_rating_outside_zero_to_five_is_rejected(db: Session) -> None:
    book = make_book(db)
    db.add(BookRating(book_id=book.id, source=RatingSource.HARDCOVER, rating=9.9))
    with pytest.raises(IntegrityError):
        db.flush()


def test_one_book_carries_ratings_from_several_sources(db: Session) -> None:
    """PK is (book_id, source), which is what keeps the provider choice
    reversible -- sources coexist rather than overwrite.
    """
    book = make_book(db)
    db.add_all(
        [
            BookRating(
                book_id=book.id, source=RatingSource.HARDCOVER, rating=4.26, ratings_count=2946
            ),
            BookRating(
                book_id=book.id, source=RatingSource.OPEN_LIBRARY, rating=4.1, ratings_count=19
            ),
        ]
    )
    db.flush()

    assert {r.source for r in book.ratings} == {RatingSource.HARDCOVER, RatingSource.OPEN_LIBRARY}


def test_same_source_cannot_be_recorded_twice_for_one_book(db: Session) -> None:
    book = make_book(db)
    db.add(BookRating(book_id=book.id, source=RatingSource.HARDCOVER, rating=4.0))
    db.flush()
    db.add(BookRating(book_id=book.id, source=RatingSource.HARDCOVER, rating=4.5))
    with pytest.raises(IntegrityError):
        db.flush()


def test_shelf_slug_is_unique_per_user_not_globally(db: Session) -> None:
    first, second = make_user(db, "a@example.com"), make_user(db, "b@example.com")

    db.add_all(
        [
            Shelf(user_id=first.id, name="Favourites", slug="favourites"),
            Shelf(user_id=second.id, name="Favourites", slug="favourites"),
        ]
    )
    db.flush()  # different users, same slug -- allowed

    db.add(Shelf(user_id=first.id, name="Favourites again", slug="favourites"))
    with pytest.raises(IntegrityError):
        db.flush()


def test_book_can_be_on_several_shelves_with_one_reading_status(db: Session) -> None:
    """The property the whole shelves/status split exists to provide."""
    user, book = make_user(db), make_book(db)
    shelves = [
        Shelf(user_id=user.id, name="Sci-fi", slug="sci-fi"),
        Shelf(user_id=user.id, name="Owned", slug="owned"),
        Shelf(user_id=user.id, name="Gifts", slug="gifts"),
    ]
    db.add_all(shelves)
    db.flush()
    db.add_all(ShelfItem(shelf_id=s.id, book_id=book.id) for s in shelves)
    db.add(UserBook(user_id=user.id, book_id=book.id, status=ReadingStatus.READING))
    db.flush()

    assert db.query(ShelfItem).filter_by(book_id=book.id).count() == 3
    assert db.query(UserBook).filter_by(book_id=book.id).one().status is ReadingStatus.READING


def test_authors_keep_cover_order(db: Session) -> None:
    book = make_book(db, "Good Omens")
    pratchett = Author(name="Terry Pratchett")
    gaiman = Author(name="Neil Gaiman")
    db.add_all([pratchett, gaiman])
    db.flush()

    # Added out of order on purpose; the relationship sorts by position.
    db.add_all(
        [
            BookAuthor(book_id=book.id, author_id=gaiman.id, position=1),
            BookAuthor(book_id=book.id, author_id=pratchett.id, position=0),
        ]
    )
    db.flush()
    db.refresh(book)

    assert [ba.author.name for ba in book.authors] == ["Terry Pratchett", "Neil Gaiman"]


def test_deleting_a_user_removes_their_shelves(db: Session) -> None:
    user = make_user(db)
    db.add(Shelf(user_id=user.id, name="Temp", slug="temp"))
    db.flush()

    db.delete(user)
    db.flush()

    assert db.query(Shelf).count() == 0


def test_finished_before_started_is_rejected(db: Session) -> None:
    from datetime import date

    user, book = make_user(db), make_book(db)
    db.add(
        UserBook(
            user_id=user.id,
            book_id=book.id,
            started_at=date(2026, 5, 1),
            finished_at=date(2026, 4, 1),
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()
