"""Enumerations stored as VARCHAR + CHECK, not native Postgres enum types.

A native enum can gain values but never lose one, and altering it mid-migration
has transaction restrictions. RatingSource in particular is expected to grow
(google, goodreads via Apify), so the constraint-swap approach is cheaper.

Every model that uses these passes native_enum=False to sqlalchemy.Enum.
"""

from enum import StrEnum


class ReadingStatus(StrEnum):
    """Where a user is with a book. Orthogonal to which shelves it sits on."""

    WANT_TO_READ = "want_to_read"
    READING = "reading"
    READ = "read"
    DNF = "dnf"


class RatingSource(StrEnum):
    """Which provider a rating came from. One book carries several at once."""

    HARDCOVER = "hardcover"
    GOOGLE = "google"
    OPEN_LIBRARY = "open_library"
    GOODREADS = "goodreads"
    STORYGRAPH = "storygraph"
