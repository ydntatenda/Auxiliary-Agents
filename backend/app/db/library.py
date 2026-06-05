"""Library-side data access for workflows.

Lives separately from `db/workflows.py` because the listing query has to
join in source counts and collaborator counts, and the search ranking
runs in Python over stored embeddings. Keeping it here means the
library-specific concerns do not leak back into the core CRUD module.
"""
from __future__ import annotations

import math
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import (
    SourceRow,
    WorkflowCollaboratorRow,
    WorkflowRow,
)


async def list_workflows_for_org(
    session: AsyncSession,
) -> list[WorkflowRow]:
    """Return every non-archived workflow, sorted newest-first.

    For the MVP all workflows in the table belong to the single hardcoded
    org; multi-tenancy is future work behind the auth stub.
    """
    stmt = (
        select(WorkflowRow)
        .where(WorkflowRow.archived.is_(False))
        .order_by(WorkflowRow.updated_at.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def count_sources(session: AsyncSession, workflow_id: UUID) -> int:
    stmt = select(func.count(SourceRow.id)).where(
        SourceRow.workflow_id == workflow_id
    )
    return int((await session.execute(stmt)).scalar() or 0)


async def count_collaborators(session: AsyncSession, workflow_id: UUID) -> int:
    stmt = select(func.count(WorkflowCollaboratorRow.id)).where(
        WorkflowCollaboratorRow.workflow_id == workflow_id
    )
    return int((await session.execute(stmt)).scalar() or 0)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Naive cosine similarity. Returns 0.0 for empty or mismatched vectors.

    Pure Python because the corpus is tiny. If the library ever holds more
    than a couple hundred rows we move to pgvector and let the DB do this.
    """
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def rank_matches(
    workflows: list[WorkflowRow],
    query: str,
    query_embedding: list[float] | None,
    top_n: int = 5,
) -> list[tuple[WorkflowRow, str, float]]:
    """Combine name substring matches with semantic matches.

    Returns up to `top_n` tuples of (row, match_reason, score), deduplicated
    by workflow id and sorted by score descending. Name matches always
    score above 1.0 so they sort ahead of any semantic hit; semantic hits
    are the cosine similarity bounded to [0, 1].
    """
    needle = query.strip().lower()
    seen: dict[UUID, tuple[WorkflowRow, str, float]] = {}

    if needle:
        for row in workflows:
            if needle in (row.name or "").lower():
                seen[row.id] = (row, "name match", 1.0 + _name_bonus(row.name, needle))

    if query_embedding:
        for row in workflows:
            score = cosine_similarity(query_embedding, row.embedding or [])
            if score <= 0.0:
                continue
            existing = seen.get(row.id)
            description_excerpt = (row.description or "").strip().replace("\n", " ")
            reason = (
                f"description match: {description_excerpt[:60]}"
                if description_excerpt
                else "semantic match"
            )
            if existing is None or score > existing[2]:
                seen[row.id] = (row, reason, score)

    ranked = sorted(seen.values(), key=lambda entry: entry[2], reverse=True)
    return ranked[:top_n]


def _name_bonus(name: str | None, needle: str) -> float:
    if not name:
        return 0.0
    lowered = name.lower()
    if lowered == needle:
        return 1.0
    if lowered.startswith(needle):
        return 0.5
    return 0.0
