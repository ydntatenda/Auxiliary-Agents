from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.artifacts import write_json_artifact, write_text_artifact
from app.core.auth_stub import get_current_user, get_member
from app.core.authz import is_owner_or_admin
from app.core.background import embed_workflow_task
from app.db.collaborators import (
    get_collaborator_role,
    list_collaborators,
)
from app.db.library import count_collaborators, count_sources
from app.db.session import async_session, get_db
from app.db.versions import list_versions
from app.db.workflows import require_workflow_row, save_workflow
from app.models.db import WorkflowRow
from app.models.graph import Workflow
from app.skills.delta_extraction import (
    DeltaResult,
    DeltaScope,
    apply_delta,
    extract_delta,
)
from app.skills.delta_extraction.apply import DeltaApplyError
from app.skills.workflow_extraction import extract_workflow


router = APIRouter(prefix="/workflows", tags=["workflows"])


class WorkflowStatusResponse(BaseModel):
    workflow_id: str
    status: str
    has_transcript: bool
    gaps_total: int = 0
    gaps_resolved: int = 0


class WorkflowResponse(BaseModel):
    workflow_id: str
    name: str
    unit: str
    description: str | None
    assembled_transcript: str | None
    status: str
    version: int
    approved_at: datetime | None
    approved_by: str | None
    archived: bool
    graph: Workflow | None


class CollaboratorView(BaseModel):
    member_id: str
    name: str
    avatar: str
    contribution_role: str
    added_by: str
    notified: bool


class VersionView(BaseModel):
    id: str
    version: int
    change_summary: str | None
    changed_by: str
    created_at: datetime


class WorkflowSummary(BaseModel):
    id: str
    name: str
    unit: str
    description: str | None
    status: str
    version: int
    approved_at: datetime | None
    archived: bool
    created_by: str | None
    collaborators: list[CollaboratorView]
    versions: list[VersionView]
    source_count: int
    collaborator_count: int
    current_user_role: str | None


class DuplicateResponse(BaseModel):
    workflow_id: str


class EditWorkflowPayload(BaseModel):
    """PATCH body for workflow identity. All fields optional, server-side
    rules: name/unit cannot be blank if provided, description can be set
    to empty string to clear it.
    """

    name: str | None = None
    unit: str | None = None
    description: str | None = None


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
) -> WorkflowResponse:
    try:
        row = await require_workflow_row(db, workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    graph = Workflow.model_validate(row.graph) if row.graph else None
    return WorkflowResponse(
        workflow_id=str(row.id),
        name=row.name,
        unit=row.unit,
        description=row.description,
        assembled_transcript=row.assembled_transcript,
        status=row.status,
        version=row.version,
        approved_at=row.approved_at,
        approved_by=row.approved_by,
        archived=row.archived,
        graph=graph,
    )


@router.get("/{workflow_id}/status", response_model=WorkflowStatusResponse)
async def get_status(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
) -> WorkflowStatusResponse:
    try:
        row = await require_workflow_row(db, workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    graph = Workflow.model_validate(row.graph) if row.graph else None
    gaps = graph.gaps if graph else []
    return WorkflowStatusResponse(
        workflow_id=str(row.id),
        status=row.status,
        has_transcript=bool(row.assembled_transcript),
        gaps_total=len(gaps),
        gaps_resolved=sum(1 for gap in gaps if gap.resolved),
    )


@router.get("/{workflow_id}/summary", response_model=WorkflowSummary)
async def get_summary(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
) -> WorkflowSummary:
    """Everything the workflow-detail screen needs in a single call."""
    user = get_current_user()
    try:
        row = await require_workflow_row(db, workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    collab_rows = await list_collaborators(db, row.id)
    collab_views: list[CollaboratorView] = []
    for collab in collab_rows:
        member = get_member(collab.member_id)
        collab_views.append(
            CollaboratorView(
                member_id=collab.member_id,
                name=member.name if member else collab.member_id,
                avatar=member.avatar if member else collab.member_id[:2].upper(),
                contribution_role=collab.contribution_role,
                added_by=collab.added_by,
                notified=collab.notified,
            )
        )

    version_rows = await list_versions(db, row.id)
    version_views = [
        VersionView(
            id=str(version.id),
            version=version.version,
            change_summary=version.change_summary,
            changed_by=version.changed_by,
            created_at=version.created_at,
        )
        for version in version_rows
    ]

    return WorkflowSummary(
        id=str(row.id),
        name=row.name,
        unit=row.unit,
        description=row.description,
        status=row.status,
        version=row.version,
        approved_at=row.approved_at,
        archived=row.archived,
        created_by=row.created_by,
        collaborators=collab_views,
        versions=version_views,
        source_count=await count_sources(db, row.id),
        collaborator_count=await count_collaborators(db, row.id),
        current_user_role=await get_collaborator_role(db, row.id, user.id),
    )


@router.post("/{workflow_id}/extract", response_model=Workflow)
async def extract(
    workflow_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> Workflow:
    try:
        row = await require_workflow_row(db, workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not row.assembled_transcript:
        raise HTTPException(status_code=409, detail="Assembled transcript is empty")
    if row.graph:
        return Workflow.model_validate(row.graph)

    row.status = "extracting"
    await db.commit()

    workflow = await extract_workflow(row.name, row.unit, row.assembled_transcript)
    workflow.id = row.id
    workflow.name = row.name
    workflow.unit = row.unit
    workflow.source_modality = "text"
    workflow.source_transcript = row.assembled_transcript
    workflow.created_at = row.created_at or datetime.now(timezone.utc)
    workflow.updated_at = datetime.now(timezone.utc)
    await save_workflow(workflow, status="clarifying")

    # Persist the description to the workflow row so the library can
    # surface it without having to round-trip through the Pydantic graph.
    # If an owner or admin has already typed a description via PATCH
    # /workflows/{id}, the operator-set value wins; extraction never
    # silently overwrites it.
    async with async_session() as session:
        live = await session.get(WorkflowRow, row.id)
        if live is not None and live.description is None:
            live.description = workflow.description
            await session.commit()

    background_tasks.add_task(embed_workflow_task, row.id)
    write_text_artifact(str(row.id), "assembled_transcript.txt", row.assembled_transcript)
    write_json_artifact(str(row.id), "extracted_workflow.json", workflow.model_dump(mode="json"))
    return workflow


class DeltaExtractPayload(BaseModel):
    scope: str
    step_ids: list[str] | None = None
    change_description: str | None = None


@router.post("/{workflow_id}/delta-extract", response_model=Workflow)
async def delta_extract(
    workflow_id: str,
    payload: DeltaExtractPayload,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> Workflow:
    """Run a scoped delta extraction over the assembled transcript.

    Reads the current graph, calls the delta extraction skill with the
    new transcript and the declared scope, applies the result through the
    typed apply layer, and persists. Status returns to 'clarifying' so
    the operator can resolve any new gaps before re-approving.
    """
    try:
        row = await require_workflow_row(db, workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if row.graph is None:
        raise HTTPException(
            status_code=409,
            detail="Workflow has no existing graph to delta-extract against.",
        )
    if not row.assembled_transcript:
        raise HTTPException(
            status_code=409,
            detail="No new transcript to extract a delta from.",
        )
    if payload.scope not in {"step", "section", "full"}:
        raise HTTPException(status_code=422, detail="scope must be step, section, or full")

    existing = Workflow.model_validate(row.graph)
    scope = DeltaScope(
        scope=payload.scope,  # type: ignore[arg-type]
        step_ids=payload.step_ids,
        change_description=payload.change_description,
    )

    delta: DeltaResult = await extract_delta(existing, row.assembled_transcript, scope)
    try:
        merged = apply_delta(existing, delta, scope)
    except DeltaApplyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # The operator's typed name and unit are canonical. Defensively clamp
    # them on the merged graph so the LLM cannot rename a workflow even
    # if the prior graph drifted from the row.
    merged.name = row.name
    merged.unit = row.unit
    merged.updated_at = datetime.now(timezone.utc)
    await save_workflow(merged, status="clarifying")

    # Mirror description back to the row only if the row has none set; an
    # owner-set description survives a delta extraction.
    async with async_session() as session:
        live = await session.get(WorkflowRow, row.id)
        if live is not None and live.description is None:
            live.description = merged.description
            await session.commit()
    background_tasks.add_task(embed_workflow_task, row.id)

    write_json_artifact(
        str(row.id),
        f"delta_v{row.version}.json",
        {
            "scope": scope.model_dump(mode="json"),
            "result": delta.model_dump(mode="json"),
        },
    )
    return merged


@router.post("/{workflow_id}/duplicate", response_model=DuplicateResponse)
async def duplicate_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
) -> DuplicateResponse:
    """Create a fresh workflow row with the same graph, no collaborators."""
    try:
        source = await require_workflow_row(db, workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    new_id = uuid4()
    clone = WorkflowRow(
        id=new_id,
        name=f"{source.name} (copy)",
        unit=source.unit,
        description=source.description,
        assembled_transcript=None,
        status="done",
        graph=source.graph,
        version=1,
        embedding=None,
        approved_at=None,
        approved_by=None,
        archived=False,
    )
    db.add(clone)
    await db.commit()
    return DuplicateResponse(workflow_id=str(new_id))


@router.delete("/{workflow_id}", status_code=204)
async def archive_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Soft-delete: flip archived and stamp archived_at.

    Only the workflow's owner (creator) or an admin can archive. Random
    org members get 403.
    """
    try:
        row = await require_workflow_row(db, workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not is_owner_or_admin(row):
        raise HTTPException(
            status_code=403,
            detail="Only the workflow owner or an admin can archive this workflow.",
        )
    row.archived = True
    row.archived_at = datetime.now(timezone.utc)
    await db.commit()


@router.patch("/{workflow_id}", response_model=WorkflowSummary)
async def edit_workflow(
    workflow_id: str,
    payload: EditWorkflowPayload,
    db: AsyncSession = Depends(get_db),
) -> WorkflowSummary:
    """Update a workflow's name, unit, or description.

    Owner or admin only. If name or unit changes and the workflow already
    has a graph, the graph's name/unit are kept in sync so the SOP header
    stays consistent, and the SOP cache is invalidated so the next render
    reflects the new values. An empty PATCH (no fields) is a 200 no-op.
    """
    try:
        row = await require_workflow_row(db, workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not is_owner_or_admin(row):
        raise HTTPException(
            status_code=403,
            detail="Only the workflow owner or an admin can edit identity.",
        )

    name_unit_changed = False

    if payload.name is not None:
        stripped = payload.name.strip()
        if not stripped:
            raise HTTPException(status_code=422, detail="name cannot be blank")
        if stripped != row.name:
            row.name = stripped
            name_unit_changed = True

    if payload.unit is not None:
        stripped = payload.unit.strip()
        if not stripped:
            raise HTTPException(status_code=422, detail="unit cannot be blank")
        if stripped != row.unit:
            row.unit = stripped
            name_unit_changed = True

    if payload.description is not None:
        cleaned = payload.description.strip() or None
        row.description = cleaned

    if name_unit_changed and row.graph is not None:
        # Sync the graph's name/unit so a subsequent extraction or render
        # sees the operator-set values.
        graph_dict = dict(row.graph)
        graph_dict["name"] = row.name
        graph_dict["unit"] = row.unit
        row.graph = graph_dict
        # Cache is invalid: a different name/unit would change the SOP
        # header. Drop both so the next /sop GET re-renders.
        row.sop_cache = None
        row.sop_cache_graph_hash = None

    await db.commit()
    await db.refresh(row)

    # Re-use the summary builder so the response shape matches GET /summary.
    return await get_summary(workflow_id, db)
