"""Unit tests for library ranking and cosine similarity.

These pin the behaviour the /library/search endpoint depends on without
needing a database: a name substring always sorts above any semantic
hit, semantic hits are deduplicated, and a missing embedding falls
back to name match only.
"""
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.db.library import cosine_similarity, rank_matches


def _row(
    name: str,
    *,
    description: str | None = None,
    embedding: list[float] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        name=name,
        description=description,
        embedding=embedding,
        updated_at=datetime.now(timezone.utc),
    )


def test_cosine_similarity_basic_cases() -> None:
    assert cosine_similarity([1, 0], [1, 0]) == 1.0
    assert cosine_similarity([1, 0], [0, 1]) == 0.0
    assert cosine_similarity([], [1, 0]) == 0.0
    assert cosine_similarity([1, 0], []) == 0.0
    assert cosine_similarity([1, 1], [2, 2]) > 0.99


def test_name_match_outranks_semantic() -> None:
    name_hit = _row("Citation appeals", embedding=[0.1, 0.2])
    semantic_hit = _row(
        "Tow appeal escalation",
        description="Handles citation appeals over the threshold.",
        embedding=[0.9, 0.1],
    )
    ranked = rank_matches(
        [semantic_hit, name_hit],
        "citation",
        query_embedding=[0.9, 0.1],
    )
    assert [row.name for row, _r, _s in ranked][0] == "Citation appeals"


def test_dedup_when_row_matches_both_ways() -> None:
    row = _row(
        "Citation appeals",
        description="Customers dispute parking citations.",
        embedding=[1.0, 0.0],
    )
    ranked = rank_matches([row], "citation", query_embedding=[1.0, 0.0])
    assert len(ranked) == 1


def test_no_embeddings_falls_back_to_name_only() -> None:
    a = _row("Citation appeals")
    b = _row("Lot closure procedure")
    ranked = rank_matches([a, b], "appeals", query_embedding=None)
    assert [row.name for row, _r, _s in ranked] == ["Citation appeals"]


def test_match_reason_for_description_match_truncates_to_60() -> None:
    long_desc = "x" * 200
    row = _row("Far away workflow", description=long_desc, embedding=[1.0, 0.0])
    ranked = rank_matches([row], "noname", query_embedding=[1.0, 0.0])
    assert ranked
    reason = ranked[0][1]
    assert reason.startswith("description match: ")
    assert len(reason) == len("description match: ") + 60
