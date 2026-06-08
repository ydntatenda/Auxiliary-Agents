"""Capture API.

A workflow is now an empty shell that accepts MANY sources. Each source
has one modality (text, voice, screen, document, chat, or one day
connector), one raw artifact, and one assembled_text produced by the
ingestion skill. The workflow's assembled_transcript is the ordered
concatenation of every ready source, cached on the row.

The old single-shot /capture/text|voice|screen endpoints remain as thin
shims that create a workflow plus one source plus assemble, so the
frontend can migrate without breaking. They are deprecated.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.assembly import assemble_transcript
from app.core.auth_stub import get_current_user
from app.core.authz import can_edit_source
from app.core.background import ingest_source_task
from app.db.session import get_db
from app.db.sources import (
    create_source_row,
    delete_source,
    list_sources,
    require_source,
)
from app.db.workflows import (
    create_workflow_row,
    require_workflow_row,
    update_status,
)
from app.models.db import SourceRow
from app.skills.source_ingestion import ingest_source


router = APIRouter(tags=["capture"])

Modality = Literal["text", "voice", "screen", "document", "chat", "connector"]
ContributorRole = Literal["operator", "approver", "observer"]
ReorderDirection = Literal["up", "down"]

_FILE_MODALITIES = {"voice", "screen", "document"}
_DEFAULT_EXT = {"voice": ".webm", "screen": ".webm", "document": ".pdf"}


class CreateWorkflowPayload(BaseModel):
    name: str = Field(..., min_length=1)
    unit: str = Field(..., min_length=1)
    contributor_role: ContributorRole | None = None


class CreateWorkflowResponse(BaseModel):
    workflow_id: str
    status: str


class SourceResponse(BaseModel):
    """Wire shape consumed by the capture UI.

    The frontend derives the assembled transcript preview client-side, so the
    full assembled_text travels with each row. `id` matches the spec's Source
    type; the legacy field name source_id is gone.
    """

    id: str
    workflow_id: str
    order: int
    modality: str
    label: str | None
    contributor_role: str | None
    added_by: str | None
    status: str
    error: str | None
    meta: dict | None
    assembled_text: str | None


class AssembleResponse(BaseModel):
    workflow_id: str
    assembled_transcript: str
    source_count: int


class CaptureResponse(BaseModel):
    """Legacy single-shot response shape preserved for the deprecated shims."""

    workflow_id: str
    status: str


class UpdateSourcePayload(BaseModel):
    """PATCH body. Either field may be present; both are optional.

    `label` rewrites the source's display label. `move` swaps the source's
    order with its neighbour in the requested direction, which is enough for
    the up/down arrow UX the spec calls for.
    """

    label: str | None = None
    move: ReorderDirection | None = None


def _to_source_response(row: SourceRow) -> SourceResponse:
    return SourceResponse(
        id=str(row.id),
        workflow_id=str(row.workflow_id),
        order=row.order,
        modality=row.modality,
        label=row.label,
        contributor_role=row.contributor_role,
        added_by=row.added_by,
        status=row.status,
        error=row.error,
        meta=row.meta,
        assembled_text=row.assembled_text,
    )


async def _save_upload(
    workflow_id: str, source_id: str, upload: UploadFile, default_ext: str
) -> str:
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(upload.filename or "").suffix or default_ext
    path = settings.upload_dir / f"{workflow_id}_{source_id}{suffix}"
    path.write_bytes(await upload.read())
    return str(path)


# -- New multi-source endpoints -----------------------------------------------


@router.post("/workflows", response_model=CreateWorkflowResponse, status_code=201)
async def create_workflow(
    payload: CreateWorkflowPayload,
    db: AsyncSession = Depends(get_db),
) -> CreateWorkflowResponse:
    """Create the workflow shell.

    The current user is recorded as `created_by` (the owner). For the
    auth-stub MVP this is whichever member is hardcoded as logged in.

    contributor_role is accepted for API symmetry with the source endpoint,
    but it is the source row that records the role; the frontend re-sends it
    on each subsequent add_source call. No workflow-level column.
    """
    user = get_current_user()
    row = await create_workflow_row(
        session=db,
        name=payload.name,
        unit=payload.unit,
        status="capturing",
        created_by=user.id,
    )
    return CreateWorkflowResponse(workflow_id=str(row.id), status=row.status)


@router.get("/workflows/{workflow_id}/sources", response_model=list[SourceResponse])
async def get_sources(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[SourceResponse]:
    try:
        await require_workflow_row(db, workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    rows = await list_sources(db, UUID(workflow_id))
    return [_to_source_response(row) for row in rows]


@router.post(
    "/workflows/{workflow_id}/sources",
    response_model=SourceResponse,
    status_code=201,
)
async def add_source(
    workflow_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> SourceResponse:
    """Add one source to a workflow.

    Dispatches on Content-Type:
    - application/json for text and chat sources (no file payload), with
      fields {modality, raw_text?, chat_messages?, label?, contributor_role?}.
    - multipart/form-data for voice, screen, and document uploads.
    """
    try:
        workflow_row = await require_workflow_row(db, workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    workflow_uuid = workflow_row.id
    content_type = (request.headers.get("content-type") or "").lower()

    if content_type.startswith("application/json"):
        return await _add_source_json(
            request=request,
            workflow_uuid=workflow_uuid,
            db=db,
        )
    if content_type.startswith("multipart/form-data"):
        return await _add_source_multipart(
            request=request,
            workflow_uuid=workflow_uuid,
            db=db,
            background_tasks=background_tasks,
        )
    raise HTTPException(
        status_code=415,
        detail="Content-Type must be application/json or multipart/form-data",
    )


async def _add_source_json(
    *,
    request: Request,
    workflow_uuid: UUID,
    db: AsyncSession,
) -> SourceResponse:
    try:
        body = await request.json()
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"invalid JSON: {exc.msg}") from exc
    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="JSON body must be an object")

    modality = body.get("modality")
    label = body.get("label")
    contributor_role = body.get("contributor_role")
    added_by = get_current_user().id

    if modality == "connector":
        raise HTTPException(
            status_code=501,
            detail="Connector ingestion is the future seam. No implementation yet.",
        )
    if modality == "text":
        raw_text = body.get("raw_text")
        if not isinstance(raw_text, str) or not raw_text.strip():
            raise HTTPException(
                status_code=422,
                detail="text modality requires a non-empty raw_text field",
            )
        result = await ingest_source("text", raw_text=raw_text)
        source = await create_source_row(
            session=db,
            workflow_id=workflow_uuid,
            modality="text",
            label=label,
            raw_path=None,
            contributor_role=contributor_role,
            assembled_text=result.assembled_text,
            status="ready",
            meta=result.meta,
            added_by=added_by,
        )
        await assemble_transcript(workflow_uuid)
        return _to_source_response(source)
    if modality == "chat":
        chat_messages = body.get("chat_messages")
        if not isinstance(chat_messages, list):
            raise HTTPException(
                status_code=422,
                detail="chat modality requires chat_messages as a list",
            )
        normalised = _normalise_chat_messages(chat_messages)
        result = await ingest_source("chat", chat_messages=normalised)
        source = await create_source_row(
            session=db,
            workflow_id=workflow_uuid,
            modality="chat",
            label=label,
            raw_path=None,
            contributor_role=contributor_role,
            assembled_text=result.assembled_text,
            status="ready",
            meta=result.meta,
            added_by=added_by,
        )
        await assemble_transcript(workflow_uuid)
        return _to_source_response(source)
    if modality in _FILE_MODALITIES:
        raise HTTPException(
            status_code=415,
            detail=f"{modality} modality requires multipart/form-data with a file upload",
        )
    raise HTTPException(status_code=422, detail=f"unsupported modality {modality!r}")


async def _add_source_multipart(
    *,
    request: Request,
    workflow_uuid: UUID,
    db: AsyncSession,
    background_tasks: BackgroundTasks,
) -> SourceResponse:
    form = await request.form()
    modality = form.get("modality")
    label = form.get("label") or None
    contributor_role = form.get("contributor_role") or None
    upload = form.get("file")
    added_by = get_current_user().id

    if modality == "connector":
        raise HTTPException(
            status_code=501,
            detail="Connector ingestion is the future seam. No implementation yet.",
        )
    if modality == "text":
        raw_text = form.get("raw_text") or form.get("text")
        if not raw_text:
            raise HTTPException(
                status_code=422,
                detail="text modality requires raw_text",
            )
        result = await ingest_source("text", raw_text=str(raw_text))
        source = await create_source_row(
            session=db,
            workflow_id=workflow_uuid,
            modality="text",
            label=label,
            raw_path=None,
            contributor_role=contributor_role,
            assembled_text=result.assembled_text,
            status="ready",
            meta=result.meta,
            added_by=added_by,
        )
        await assemble_transcript(workflow_uuid)
        return _to_source_response(source)
    if modality == "chat":
        chat_messages_raw = form.get("chat_messages")
        if not chat_messages_raw:
            raise HTTPException(
                status_code=422,
                detail="chat modality requires chat_messages as JSON",
            )
        try:
            chat_messages = json.loads(str(chat_messages_raw))
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=422,
                detail=f"chat_messages must be valid JSON: {exc.msg}",
            ) from exc
        if not isinstance(chat_messages, list):
            raise HTTPException(
                status_code=422,
                detail="chat_messages must be a JSON array",
            )
        normalised = _normalise_chat_messages(chat_messages)
        result = await ingest_source("chat", chat_messages=normalised)
        source = await create_source_row(
            session=db,
            workflow_id=workflow_uuid,
            modality="chat",
            label=label,
            raw_path=None,
            contributor_role=contributor_role,
            assembled_text=result.assembled_text,
            status="ready",
            meta=result.meta,
            added_by=added_by,
        )
        await assemble_transcript(workflow_uuid)
        return _to_source_response(source)
    if modality in _FILE_MODALITIES:
        if not isinstance(upload, UploadFile):
            raise HTTPException(
                status_code=422,
                detail=f"{modality} modality requires a file upload",
            )
        source = await create_source_row(
            session=db,
            workflow_id=workflow_uuid,
            modality=str(modality),
            label=label,
            raw_path=None,
            contributor_role=contributor_role,
            status="pending",
            added_by=added_by,
        )
        raw_path = await _save_upload(
            str(workflow_uuid),
            str(source.id),
            upload,
            _DEFAULT_EXT[str(modality)],
        )
        source.raw_path = raw_path
        await db.commit()
        await db.refresh(source)
        background_tasks.add_task(
            ingest_source_task,
            workflow_uuid,
            source.id,
            str(modality),
            raw_path=raw_path,
        )
        return _to_source_response(source)
    raise HTTPException(status_code=422, detail=f"unsupported modality {modality!r}")


@router.patch(
    "/workflows/{workflow_id}/sources/{source_id}",
    response_model=SourceResponse,
)
async def update_source(
    workflow_id: str,
    source_id: str,
    payload: UpdateSourcePayload,
    db: AsyncSession = Depends(get_db),
) -> SourceResponse:
    """Edit a source's label or move it up/down in the assembly order.

    Only the user who added the source, the workflow owner, or an admin
    may change it. Other collaborators see the controls disabled in the
    UI; the 403 here is the backend stop.

    Reordering is expressed as a swap with the immediate neighbour, which is
    what the up/down arrow UI needs. Anything fancier (drag-and-drop, jump
    to position) is a future change to this same endpoint.
    """
    try:
        workflow_row = await require_workflow_row(db, workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        source = await require_source(db, UUID(workflow_id), UUID(source_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if not can_edit_source(workflow_row, source.added_by):
        raise HTTPException(
            status_code=403,
            detail=(
                "Only the person who added this source, the workflow owner, "
                "or an admin can change it."
            ),
        )

    touched = False

    if payload.label is not None:
        source.label = payload.label.strip() or None
        touched = True

    if payload.move is not None:
        neighbour = await _find_swap_neighbour(db, UUID(workflow_id), source, payload.move)
        if neighbour is not None:
            source.order, neighbour.order = neighbour.order, source.order
            touched = True

    if touched:
        await db.commit()
        await db.refresh(source)
        await assemble_transcript(UUID(workflow_id))

    return _to_source_response(source)


async def _find_swap_neighbour(
    db: AsyncSession,
    workflow_id: UUID,
    source: SourceRow,
    direction: ReorderDirection,
) -> SourceRow | None:
    rows = await list_sources(db, workflow_id)
    idx = next((i for i, row in enumerate(rows) if row.id == source.id), None)
    if idx is None:
        return None
    target_idx = idx - 1 if direction == "up" else idx + 1
    if target_idx < 0 or target_idx >= len(rows):
        return None
    return rows[target_idx]


@router.delete(
    "/workflows/{workflow_id}/sources/{source_id}",
    status_code=204,
)
async def remove_source(
    workflow_id: str,
    source_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        workflow_row = await require_workflow_row(db, workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        source = await require_source(db, UUID(workflow_id), UUID(source_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if not can_edit_source(workflow_row, source.added_by):
        raise HTTPException(
            status_code=403,
            detail=(
                "Only the person who added this source, the workflow owner, "
                "or an admin can remove it."
            ),
        )

    deleted = await delete_source(db, UUID(workflow_id), UUID(source_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="Source not found")
    await assemble_transcript(UUID(workflow_id))


@router.post(
    "/workflows/{workflow_id}/sources/{source_id}/retry",
    response_model=SourceResponse,
)
async def retry_source(
    workflow_id: str,
    source_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> SourceResponse:
    try:
        await require_workflow_row(db, workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        source = await require_source(db, UUID(workflow_id), UUID(source_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if source.modality in {"text", "chat"}:
        raise HTTPException(
            status_code=409,
            detail="Only sources with a saved raw artifact can be retried.",
        )
    if not source.raw_path:
        raise HTTPException(
            status_code=409,
            detail="Source has no raw_path on disk to retry from.",
        )
    background_tasks.add_task(
        ingest_source_task,
        UUID(workflow_id),
        UUID(source_id),
        source.modality,
        raw_path=source.raw_path,
    )
    return _to_source_response(source)


@router.post("/workflows/{workflow_id}/assemble", response_model=AssembleResponse)
async def assemble(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
) -> AssembleResponse:
    try:
        await require_workflow_row(db, workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    assembled = await assemble_transcript(UUID(workflow_id))
    sources = await list_sources(db, UUID(workflow_id))
    if assembled:
        await update_status(workflow_id=workflow_id, status="transcribed")
    return AssembleResponse(
        workflow_id=workflow_id,
        assembled_transcript=assembled,
        source_count=len(sources),
    )


# -- Legacy single-shot shims (deprecated) -----------------------------------
# These keep the old frontend working until it migrates to the multi-source
# flow. Each one creates a workflow, attaches a single source, assembles, and
# returns the legacy CaptureResponse shape. New frontend code should call the
# multi-source endpoints above directly.


class TextCapturePayload(BaseModel):
    name: str = Field(..., min_length=1)
    unit: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)


@router.post("/capture/text", response_model=CaptureResponse, deprecated=True)
async def capture_text(
    payload: TextCapturePayload,
    db: AsyncSession = Depends(get_db),
) -> CaptureResponse:
    user = get_current_user()
    workflow_row = await create_workflow_row(
        session=db,
        name=payload.name,
        unit=payload.unit,
        status="capturing",
        created_by=user.id,
    )
    result = await ingest_source("text", raw_text=payload.text)
    await create_source_row(
        session=db,
        workflow_id=workflow_row.id,
        modality="text",
        label=None,
        raw_path=None,
        contributor_role=None,
        assembled_text=result.assembled_text,
        status="ready",
        meta=result.meta,
        added_by=user.id,
    )
    await assemble_transcript(workflow_row.id)
    await update_status(workflow_id=workflow_row.id, status="transcribed")
    return CaptureResponse(workflow_id=str(workflow_row.id), status="transcribed")


@router.post("/capture/voice", response_model=CaptureResponse, deprecated=True)
async def capture_voice(
    background_tasks: BackgroundTasks,
    name: str = Form(...),
    unit: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> CaptureResponse:
    return await _legacy_media_capture(
        modality="voice",
        default_ext=".webm",
        name=name,
        unit=unit,
        file=file,
        db=db,
        background_tasks=background_tasks,
    )


@router.post("/capture/screen", response_model=CaptureResponse, deprecated=True)
async def capture_screen(
    background_tasks: BackgroundTasks,
    name: str = Form(...),
    unit: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> CaptureResponse:
    return await _legacy_media_capture(
        modality="screen",
        default_ext=".webm",
        name=name,
        unit=unit,
        file=file,
        db=db,
        background_tasks=background_tasks,
    )


async def _legacy_media_capture(
    *,
    modality: str,
    default_ext: str,
    name: str,
    unit: str,
    file: UploadFile,
    db: AsyncSession,
    background_tasks: BackgroundTasks,
) -> CaptureResponse:
    user = get_current_user()
    workflow_row = await create_workflow_row(
        session=db,
        name=name,
        unit=unit,
        status="transcribing",
        created_by=user.id,
    )
    source = await create_source_row(
        session=db,
        workflow_id=workflow_row.id,
        modality=modality,
        label=None,
        raw_path=None,
        contributor_role=None,
        status="pending",
        added_by=user.id,
    )
    raw_path = await _save_upload(str(workflow_row.id), str(source.id), file, default_ext)
    source.raw_path = raw_path
    await db.commit()
    background_tasks.add_task(
        ingest_source_task,
        workflow_row.id,
        source.id,
        modality,
        raw_path=raw_path,
    )
    return CaptureResponse(workflow_id=str(workflow_row.id), status=workflow_row.status)


def _normalise_chat_messages(messages: list[Any]) -> list[dict[str, Any]]:
    """Accept both spec-style {question, answer} pairs and {role, content} turns.

    The spec's frontend sends a list of {question, answer} objects. The
    chat_source skill expects {role, content}. Translate here so both wire
    shapes work.
    """
    normalised: list[dict[str, Any]] = []
    for entry in messages:
        if not isinstance(entry, dict):
            continue
        if "question" in entry or "answer" in entry:
            question = entry.get("question")
            answer = entry.get("answer")
            if question:
                normalised.append({"role": "question", "content": str(question)})
            if answer:
                normalised.append({"role": "answer", "content": str(answer)})
        else:
            normalised.append(entry)
    return normalised
