"""Shelves, reading status, and the persistence they trigger.

Phase 6 is the first write path into the domain tables, so most of what matters
here is idempotency: shelving a book twice, or onto two shelves, must not
duplicate the book or its authors.
"""

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Author, Book, BookAuthor, BookRating, RatingSource, UserBook
from app.providers.hardcover import HardcoverClient
from app.services.book_persistence import ensure_book
from app.services.shelves import slugify, unique_slug

FIXTURES = Path(__file__).parent / "fixtures"
PIRANESI_ID = "175280"
CREDENTIALS = {"email": "shelver@example.com", "password": "correct-horse-battery"}


def load(name: str) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads((FIXTURES / f"hardcover_book_{name}.json").read_text())
    return payload


class CountingClient(HardcoverClient):
    def __init__(self, payload: dict[str, Any]) -> None:
        self.calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            self.calls += 1
            return httpx.Response(200, json=payload)

        super().__init__(transport=httpx.MockTransport(handler))


@pytest.fixture
def signed_in(client: TestClient) -> TestClient:
    client.post("/api/v1/auth/register", json=CREDENTIALS)
    return client


# --- slugs -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Favourites", "favourites"),
        ("Sci-Fi & Fantasy", "sci-fi-fantasy"),
        ("  Read in 2026  ", "read-in-2026"),
        ("!!!", "shelf"),
    ],
)
def test_slugify(name: str, expected: str) -> None:
    assert slugify(name) == expected


def test_slug_collisions_get_a_suffix(db: Session, signed_in: TestClient) -> None:
    signed_in.post("/api/v1/shelves", json={"name": "Favourites"})
    second = signed_in.post("/api/v1/shelves", json={"name": "Favourites"})

    assert second.status_code == 201
    assert second.json()["slug"] == "favourites-2"


def test_slugs_only_collide_within_one_user(db: Session) -> None:
    """Uniqueness is per user, so two people can both have "favourites"."""
    assert unique_slug(db, user_id=1, name="Favourites") == "favourites"
    assert unique_slug(db, user_id=2, name="Favourites") == "favourites"


# --- persistence -----------------------------------------------------------


def test_shelving_creates_the_book_and_its_authors(db: Session) -> None:
    book = ensure_book(db, PIRANESI_ID, client=CountingClient(load("piranesi")))

    assert book is not None
    assert book.title == "Piranesi"
    assert book.description and len(book.description) > 100
    assert [link.author.name for link in book.authors] == ["Susanna Clarke"]


def test_ensure_book_is_idempotent(db: Session) -> None:
    """Shelving onto a second shelf must not create a second book row."""
    provider = CountingClient(load("piranesi"))

    first = ensure_book(db, PIRANESI_ID, client=provider)
    second = ensure_book(db, PIRANESI_ID, client=provider)

    assert first is not None and second is not None
    assert first.id == second.id
    assert db.scalar(select(func.count()).select_from(Book)) == 1
    assert db.scalar(select(func.count()).select_from(Author)) == 1
    assert db.scalar(select(func.count()).select_from(BookAuthor)) == 1


def test_authors_are_shared_between_books(db: Session) -> None:
    """Matching on the provider id is what makes an author reusable rather than
    re-created per book.
    """
    ensure_book(db, PIRANESI_ID, client=CountingClient(load("piranesi")))

    other = load("piranesi")
    other["data"]["books"][0]["id"] = 999001
    other["data"]["books"][0]["title"] = "Jonathan Strange & Mr Norrell"
    ensure_book(db, "999001", client=CountingClient(other))

    assert db.scalar(select(func.count()).select_from(Book)) == 2
    assert db.scalar(select(func.count()).select_from(Author)) == 1


def test_rating_is_stored_against_its_source(db: Session) -> None:
    """The (book_id, source) key is what lets other providers coexist later."""
    book = ensure_book(db, PIRANESI_ID, client=CountingClient(load("piranesi")))
    assert book is not None

    rating = db.scalar(select(BookRating).where(BookRating.book_id == book.id))
    assert rating is not None
    assert rating.source is RatingSource.HARDCOVER
    assert rating.ratings_count is not None and rating.ratings_count > 0


def test_unknown_book_is_not_persisted(db: Session) -> None:
    provider = CountingClient({"data": {"books": []}})

    assert ensure_book(db, "999999999", client=provider) is None
    assert db.scalar(select(func.count()).select_from(Book)) == 0


# --- shelves ---------------------------------------------------------------


def test_shelves_require_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/shelves").status_code == 401


def test_create_list_rename_delete(signed_in: TestClient) -> None:
    created = signed_in.post("/api/v1/shelves", json={"name": "Sci-fi"})
    assert created.status_code == 201
    shelf_id = created.json()["id"]

    listed = signed_in.get("/api/v1/shelves").json()
    assert [s["name"] for s in listed] == ["Sci-fi"]
    assert listed[0]["book_count"] == 0

    renamed = signed_in.patch(f"/api/v1/shelves/{shelf_id}", json={"name": "Science Fiction"})
    assert renamed.json()["slug"] == "science-fiction"

    assert signed_in.delete(f"/api/v1/shelves/{shelf_id}").status_code == 204
    assert signed_in.get("/api/v1/shelves").json() == []


def test_another_users_shelf_is_not_found(signed_in: TestClient, db: Session) -> None:
    """404 rather than 403 -- existence is not a stranger's business."""
    from app.models import Shelf, User

    stranger = User(email="stranger@example.com", password_hash="x")
    db.add(stranger)
    db.flush()
    theirs = Shelf(user_id=stranger.id, name="Private", slug="private")
    db.add(theirs)
    db.flush()

    assert signed_in.get(f"/api/v1/shelves/{theirs.id}").status_code == 404


def test_deleting_a_shelf_keeps_the_book(signed_in: TestClient, db: Session) -> None:
    ensure_book(db, PIRANESI_ID, client=CountingClient(load("piranesi")))
    shelf_id = signed_in.post("/api/v1/shelves", json={"name": "Temp"}).json()["id"]
    signed_in.post(f"/api/v1/shelves/{shelf_id}/books", json={"hardcover_id": PIRANESI_ID})

    signed_in.delete(f"/api/v1/shelves/{shelf_id}")

    assert db.scalar(select(func.count()).select_from(Book)) == 1


def test_adding_the_same_book_twice_is_harmless(signed_in: TestClient, db: Session) -> None:
    ensure_book(db, PIRANESI_ID, client=CountingClient(load("piranesi")))
    shelf_id = signed_in.post("/api/v1/shelves", json={"name": "Sci-fi"}).json()["id"]

    signed_in.post(f"/api/v1/shelves/{shelf_id}/books", json={"hardcover_id": PIRANESI_ID})
    signed_in.post(f"/api/v1/shelves/{shelf_id}/books", json={"hardcover_id": PIRANESI_ID})

    shelf = signed_in.get(f"/api/v1/shelves/{shelf_id}").json()
    assert len(shelf["books"]) == 1
    assert shelf["books"][0]["authors"] == ["Susanna Clarke"]


def test_one_book_on_several_shelves(signed_in: TestClient, db: Session) -> None:
    ensure_book(db, PIRANESI_ID, client=CountingClient(load("piranesi")))
    first = signed_in.post("/api/v1/shelves", json={"name": "Sci-fi"}).json()["id"]
    second = signed_in.post("/api/v1/shelves", json={"name": "Owned"}).json()["id"]

    for shelf_id in (first, second):
        signed_in.post(f"/api/v1/shelves/{shelf_id}/books", json={"hardcover_id": PIRANESI_ID})

    assert db.scalar(select(func.count()).select_from(Book)) == 1
    assert len(signed_in.get(f"/api/v1/shelves/{first}").json()["books"]) == 1
    assert len(signed_in.get(f"/api/v1/shelves/{second}").json()["books"]) == 1


def test_contains_flags_which_shelves_hold_a_book(signed_in: TestClient, db: Session) -> None:
    ensure_book(db, PIRANESI_ID, client=CountingClient(load("piranesi")))
    on_it = signed_in.post("/api/v1/shelves", json={"name": "Sci-fi"}).json()["id"]
    signed_in.post("/api/v1/shelves", json={"name": "Owned"})
    signed_in.post(f"/api/v1/shelves/{on_it}/books", json={"hardcover_id": PIRANESI_ID})

    shelves = signed_in.get("/api/v1/shelves", params={"contains": PIRANESI_ID}).json()

    assert {s["name"]: s["contains_book"] for s in shelves} == {"Sci-fi": True, "Owned": False}


def test_contains_is_false_without_the_parameter(signed_in: TestClient, db: Session) -> None:
    """Absent the question, the answer is not "no" -- it is "not asked". False
    keeps the field honest for callers that do not care.
    """
    ensure_book(db, PIRANESI_ID, client=CountingClient(load("piranesi")))
    shelf_id = signed_in.post("/api/v1/shelves", json={"name": "Sci-fi"}).json()["id"]
    signed_in.post(f"/api/v1/shelves/{shelf_id}/books", json={"hardcover_id": PIRANESI_ID})

    assert signed_in.get("/api/v1/shelves").json()[0]["contains_book"] is False


def test_contains_does_not_leak_across_users(signed_in: TestClient, db: Session) -> None:
    """Membership is per user, which is why it lives here and not on the book
    detail response -- that one is cached and shared by everyone.
    """
    from app.models import Shelf, ShelfItem, User

    book = ensure_book(db, PIRANESI_ID, client=CountingClient(load("piranesi")))
    assert book is not None

    stranger = User(email="stranger2@example.com", password_hash="x")
    db.add(stranger)
    db.flush()
    theirs = Shelf(user_id=stranger.id, name="Theirs", slug="theirs")
    db.add(theirs)
    db.flush()
    db.add(ShelfItem(shelf_id=theirs.id, book_id=book.id))
    db.flush()

    mine = signed_in.post("/api/v1/shelves", json={"name": "Mine"}).json()["id"]
    shelves = signed_in.get("/api/v1/shelves", params={"contains": PIRANESI_ID}).json()

    assert [s["id"] for s in shelves] == [mine]
    assert shelves[0]["contains_book"] is False


def test_removing_a_book_leaves_the_shelf(signed_in: TestClient, db: Session) -> None:
    ensure_book(db, PIRANESI_ID, client=CountingClient(load("piranesi")))
    shelf_id = signed_in.post("/api/v1/shelves", json={"name": "Sci-fi"}).json()["id"]
    book_id = signed_in.post(
        f"/api/v1/shelves/{shelf_id}/books", json={"hardcover_id": PIRANESI_ID}
    ).json()["id"]

    assert signed_in.delete(f"/api/v1/shelves/{shelf_id}/books/{book_id}").status_code == 204
    assert signed_in.get(f"/api/v1/shelves/{shelf_id}").json()["books"] == []


# --- reading status --------------------------------------------------------


def test_shelving_does_not_imply_a_reading_status(signed_in: TestClient, db: Session) -> None:
    """Shelves and status are orthogonal: "Owned" makes no claim about reading."""
    ensure_book(db, PIRANESI_ID, client=CountingClient(load("piranesi")))
    shelf_id = signed_in.post("/api/v1/shelves", json={"name": "Owned"}).json()["id"]
    signed_in.post(f"/api/v1/shelves/{shelf_id}/books", json={"hardcover_id": PIRANESI_ID})

    assert db.scalar(select(func.count()).select_from(UserBook)) == 0
    assert signed_in.get("/api/v1/me/books").json() == []


def test_setting_a_status_persists_the_book(signed_in: TestClient, db: Session) -> None:
    """Recording a status is the other write path -- no shelf required."""
    response = signed_in.put(
        f"/api/v1/me/books/{PIRANESI_ID}",
        json={"status": "reading", "started_at": "2026-08-01"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "reading"
    assert response.json()["book"]["title"] == "Piranesi"


def test_partial_update_leaves_other_fields_alone(signed_in: TestClient) -> None:
    signed_in.put(
        f"/api/v1/me/books/{PIRANESI_ID}",
        json={"status": "read", "review": "Extraordinary."},
    )
    updated = signed_in.put(f"/api/v1/me/books/{PIRANESI_ID}", json={"rating": 5}).json()

    assert updated["rating"] == 5
    assert updated["review"] == "Extraordinary."
    assert updated["status"] == "read"


def test_a_book_keeps_one_status_across_many_shelves(signed_in: TestClient, db: Session) -> None:
    for name in ("Sci-fi", "Owned", "Gifts"):
        shelf_id = signed_in.post("/api/v1/shelves", json={"name": name}).json()["id"]
        signed_in.post(f"/api/v1/shelves/{shelf_id}/books", json={"hardcover_id": PIRANESI_ID})
    signed_in.put(f"/api/v1/me/books/{PIRANESI_ID}", json={"status": "read"})

    entries = signed_in.get("/api/v1/me/books").json()
    assert len(entries) == 1
    assert entries[0]["status"] == "read"


def test_rating_outside_range_is_rejected(signed_in: TestClient) -> None:
    assert signed_in.put(f"/api/v1/me/books/{PIRANESI_ID}", json={"rating": 9}).status_code == 422


def test_clearing_status_keeps_the_book_and_its_shelves(signed_in: TestClient, db: Session) -> None:
    shelf_id = signed_in.post("/api/v1/shelves", json={"name": "Sci-fi"}).json()["id"]
    signed_in.post(f"/api/v1/shelves/{shelf_id}/books", json={"hardcover_id": PIRANESI_ID})
    signed_in.put(f"/api/v1/me/books/{PIRANESI_ID}", json={"status": "read"})

    assert signed_in.delete(f"/api/v1/me/books/{PIRANESI_ID}").status_code == 204
    assert signed_in.get("/api/v1/me/books").json() == []
    assert len(signed_in.get(f"/api/v1/shelves/{shelf_id}").json()["books"]) == 1
