"""Library API.

The library is the surface where users find existing workflows: list, search,
approve, request an update. Operates on the single hardcoded org for now;
multi-tenancy is future work behind the auth stub.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_stub import get_current_user
from app.db.collaborators import (
    get_collaborator_role,
    list_collaborators,
)
from app.db.library import (
    count_collaborators,
    count_sources,
    list_workflows_for_org,
    rank_matches,
)
from app.db.notifications import create_notification
from app.db.session import async_session, get_db
from app.db.versions import snapshot_version
from app.db.workflows import require_workflow_row
from app.models.db import WorkflowRow
from app.skills.embedding import embed_text


router = APIRouter(prefix="/library", tags=["library"])


class WorkflowSummary(BaseModel):
    id: str
    name: str
    unit: str
    description: str | None
    status: str
    version: int
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None
    archived: bool
    collaborator_count: int
    source_count: int
    current_user_role: str | None


class SearchResult(WorkflowSummary):
    match_reason: str


async def _summarise(
    session: AsyncSession,
    row: WorkflowRow,
    current_user_id: str,
) -> WorkflowSummary:
    user_role = await get_collaborator_role(session, row.id, current_user_id)
    return WorkflowSummary(
        id=str(row.id),
        name=row.name,
        unit=row.unit,
        description=row.description,
        status=row.status,
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
        approved_at=row.approved_at,
        archived=row.archived,
        collaborator_count=await count_collaborators(session, row.id),
        source_count=await count_sources(session, row.id),
        current_user_role=user_role,
    )


@router.get("", response_model=list[WorkflowSummary])
async def list_library(
    db: AsyncSession = Depends(get_db),
) -> list[WorkflowSummary]:
    user = get_current_user()
    rows = await list_workflows_for_org(db)
    return [await _summarise(db, row, user.id) for row in rows]


@router.get("/search", response_model=list[SearchResult])
async def search_library(
    q: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
) -> list[SearchResult]:
    user = get_current_user()
    rows = await list_workflows_for_org(db)

    # If any row has an embedding, compute one for the query so we can
    # rank semantically. If none do, fall back to substring only.
    any_embedded = any(row.embedding for row in rows)
    query_embedding: list[float] | None = None
    if any_embedded:
        try:
            query_embedding = await embed_text(q)
        except Exception:  # noqa: BLE001
            query_embedding = None

    ranked = rank_matches(rows, q, query_embedding, top_n=5)
    results: list[SearchResult] = []
    for row, reason, _score in ranked:
        summary = await _summarise(db, row, user.id)
        results.append(SearchResult(**summary.model_dump(), match_reason=reason))
    return results


@router.post("/{workflow_id}/approve", response_model=WorkflowSummary)
async def approve_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
) -> WorkflowSummary:
    """Mark a workflow approved, snapshot its current graph and SOP.

    Increments the version number, snapshots the graph (and the last
    rendered SOP if any) into workflow_versions, sets approved_at /
    approved_by, and fans a notification of type 'approved' out to every
    collaborator on the workflow.
    """
    user = get_current_user()
    try:
        row = await require_workflow_row(db, workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if row.graph is None:
        raise HTTPException(
            status_code=409,
            detail="Workflow has no graph to approve.",
        )

    row.status = "approved"
    row.approved_at = datetime.now(timezone.utc)
    row.approved_by = user.id
    row.version = row.version + 1
    await db.commit()
    await db.refresh(row)

    await snapshot_version(
        session=db,
        workflow_id=row.id,
        version=row.version,
        graph_snapshot=row.graph or {},
        sop_snapshot=None,
        change_summary=None,
        changed_by=user.id,
    )

    collaborators = await list_collaborators(db, row.id)
    for collab in collaborators:
        await create_notification(
            session=db,
            member_id=collab.member_id,
            workflow_id=row.id,
            type="approved",
            message=f"{row.name} was approved (v{row.version}).",
        )

    return await _summarise(db, row, user.id)


@router.post("/{workflow_id}/request_update", response_model=WorkflowSummary)
async def request_update(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
) -> WorkflowSummary:
    """Move a workflow into pending_update and notify owner + reviewers.

    Rejects with 409 if the workflow is already in pending_update; two
    drafts cannot coexist.
    """
    user = get_current_user()
    try:
        row = await require_workflow_row(db, workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if row.status == "pending_update":
        raise HTTPException(
            status_code=409,
            detail="An update is already in progress for this workflow.",
        )

    row.status = "pending_update"
    await db.commit()
    await db.refresh(row)

    collaborators = await list_collaborators(db, row.id)
    notify_targets = {
        collab.member_id
        for collab in collaborators
        if collab.contribution_role in {"reviewer", "approver"}
    }
    if row.approved_by:
        notify_targets.add(row.approved_by)
    for member_id in notify_targets:
        await create_notification(
            session=db,
            member_id=member_id,
            workflow_id=row.id,
            type="update_requested",
            message=f"{user.name} requested an update to {row.name}.",
        )

    return await _summarise(db, row, user.id)
