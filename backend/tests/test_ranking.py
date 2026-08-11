"""Guards the search re-ranking heuristic against regressions.

Cases are drawn from real Hardcover responses recorded while validating the
provider, so these encode actual failures rather than invented ones.
"""

from app.services.ranking import score_candidate


def test_rejects_parasitic_editions() -> None:
    assert (
        score_candidate("The Body Keeps the Score", "Workbook for The Body Keeps Score", [], 0, 1)
        is None
    )
    assert score_candidate("Stoner", "Stoner by John Williams: Summary", [], 0, 1) is None


def test_loosely_related_title_is_outranked_not_rejected() -> None:
    """'Superman for Tomorrow' ranks #0 for this query on Hardcover.

    It survives the overlap filter -- repeated words collapse under set
    tokenization, so the query is only {tomorrow, and} and a single shared
    token clears 50%. Popularity is what demotes it, which is the intended
    division of labour: the filter drops junk, the score orders the rest.
    """
    wrong = score_candidate("Tomorrow and Tomorrow and Tomorrow", "Superman for Tomorrow", [], 4, 0)
    right = score_candidate(
        "Tomorrow and Tomorrow and Tomorrow",
        "Tomorrow, and Tomorrow, and Tomorrow",
        ["Gabrielle Zevin"],
        2631,
        5,
    )
    assert wrong is not None and right is not None
    assert right > wrong


def test_popular_correct_edition_beats_sparse_duplicate() -> None:
    """'Piranesi' returns an art-history book at #0 and Susanna Clarke at #1."""
    wrong = score_candidate("Piranesi", "Piranesi", ["Giovanni Battista Piranesi"], 0, 0)
    right = score_candidate("Piranesi", "Piranesi", ["Susanna Clarke"], 2946, 1)
    assert wrong is not None and right is not None
    assert right > wrong


def test_author_tokens_count_toward_overlap() -> None:
    """'James Percival Everett' -- the author name carries most of the signal."""
    assert (
        score_candidate("James Percival Everett", "James", ["Percival Everett"], 616, 2) is not None
    )


def test_deeper_correct_hit_beats_shallow_noise() -> None:
    noise = score_candidate("Sapiens", "Sapiens", ["Silvana Condemi"], 0, 0)
    real = score_candidate(
        "Sapiens", "Sapiens: A Brief History of Humankind", ["Yuval Noah Harari"], 2084, 9
    )
    assert real is not None
    assert noise is None or real > noise
