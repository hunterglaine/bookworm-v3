from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession
from app.providers.hardcover import HardcoverError
from app.schemas.book import BookSearchResponse, BookSearchResult
from app.services.book_search import (
    DEFAULT_RESULT_LIMIT,
    MAX_QUERY_LENGTH,
    normalize_query,
    search_books,
)

router = APIRouter(prefix="/books")


@router.get("/search", response_model=BookSearchResponse)
def search(
    current_user: CurrentUser,
    db: DbSession,
    q: Annotated[str, Query(min_length=1, max_length=MAX_QUERY_LENGTH)],
    limit: Annotated[int, Query(ge=1, le=25)] = DEFAULT_RESULT_LIMIT,
) -> BookSearchResponse:
    """Search books by title or author.

    Behind auth so anonymous traffic cannot drain the provider's 60 req/min.
    """
    try:
        hits = search_books(db, q, limit=limit)
    except HardcoverError as exc:
        # The provider failing is not the caller's fault, and not a bug here.
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return BookSearchResponse(
        query=normalize_query(q),
        results=[BookSearchResult(**asdict(hit)) for hit in hits],
    )
