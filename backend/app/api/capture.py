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

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.assembly import assemble_transcript
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


class CreateWorkflowPayload(BaseModel):
    name: str = Field(..., min_length=1)
    unit: str = Field(..., min_length=1)
    contributor_role: ContributorRole | None = None


class CreateWorkflowResponse(BaseModel):
    workflow_id: str
    status: str


class SourceResponse(BaseModel):
    source_id: str
    workflow_id: str
    order: int
    modality: str
    label: str | None
    contributor_role: str | None
    status: str
    error: str | None
    meta: dict | None
    has_assembled_text: bool


class AssembleResponse(BaseModel):
    workflow_id: str
    assembled_transcript: str
    source_count: int


class CaptureResponse(BaseModel):
    """Legacy single-shot response shape preserved for the deprecated shims."""

    workflow_id: str
    status: str


def _to_source_response(row: SourceRow) -> SourceResponse:
    return SourceResponse(
        source_id=str(row.id),
        workflow_id=str(row.workflow_id),
        order=row.order,
        modality=row.modality,
        label=row.label,
        contributor_role=row.contributor_role,
        status=row.status,
        error=row.error,
        meta=row.meta,
        has_assembled_text=bool(row.assembled_text),
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
    row = await create_workflow_row(
        session=db,
        name=payload.name,
        unit=payload.unit,
        status="capturing",
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
    background_tasks: BackgroundTasks,
    modality: Modality = Form(...),
    label: str | None = Form(None),
    contributor_role: ContributorRole | None = Form(None),
    text: str | None = Form(None),
    chat_messages: str | None = Form(None),
    file: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
) -> SourceResponse:
    """Add one source to a workflow.

    The payload shape depends on modality:
    - text: send `text` (form field).
    - voice / screen / document: send `file` (multipart upload).
    - chat: send `chat_messages` as a JSON-encoded list of {role, content}.
    - connector: not yet implemented; returns 501.

    Text and chat sources land 'ready' synchronously and immediately update
    the workflow's assembled_transcript. Voice, screen, and document sources
    spawn a background ingestion task and return 'processing' / 'pending'.
    """
    try:
        workflow_row = await require_workflow_row(db, workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if modality == "connector":
        raise HTTPException(
            status_code=501,
            detail="Connector ingestion is the future seam. No implementation yet.",
        )

    workflow_uuid = workflow_row.id

    if modality == "text":
        if not text:
            raise HTTPException(status_code=422, detail="text modality requires the text field")
        result = await ingest_source("text", raw_text=text)
        source = await create_source_row(
            session=db,
            workflow_id=workflow_uuid,
            modality=modality,
            label=label,
            raw_path=None,
            contributor_role=contributor_role,
            assembled_text=result.assembled_text,
            status="ready",
            meta=result.meta,
        )
        await assemble_transcript(workflow_uuid)
        return _to_source_response(source)

    if modality == "chat":
        if not chat_messages:
            raise HTTPException(
                status_code=422,
                detail="chat modality requires chat_messages as a JSON-encoded list",
            )
        parsed = _parse_chat_messages(chat_messages)
        result = await ingest_source("chat", chat_messages=parsed)
        source = await create_source_row(
            session=db,
            workflow_id=workflow_uuid,
            modality=modality,
            label=label,
            raw_path=None,
            contributor_role=contributor_role,
            assembled_text=result.assembled_text,
            status="ready",
            meta=result.meta,
        )
        await assemble_transcript(workflow_uuid)
        return _to_source_response(source)

    if modality in {"voice", "screen", "document"}:
        if file is None:
            raise HTTPException(
                status_code=422,
                detail=f"{modality} modality requires a file upload",
            )
        default_ext = {"voice": ".webm", "screen": ".webm", "document": ".pdf"}[modality]
        source = await create_source_row(
            session=db,
            workflow_id=workflow_uuid,
            modality=modality,
            label=label,
            raw_path=None,
            contributor_role=contributor_role,
            status="pending",
        )
        raw_path = await _save_upload(str(workflow_uuid), str(source.id), file, default_ext)
        source.raw_path = raw_path
        await db.commit()
        await db.refresh(source)
        background_tasks.add_task(
            ingest_source_task,
            workflow_uuid,
            source.id,
            modality,
            raw_path=raw_path,
        )
        return _to_source_response(source)

    raise HTTPException(status_code=422, detail=f"unsupported modality {modality!r}")


@router.delete(
    "/workflows/{workflow_id}/sources/{source_id}",
    status_code=204,
    response_class=None,
)
async def remove_source(
    workflow_id: str,
    source_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await require_workflow_row(db, workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
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
    workflow_row = await create_workflow_row(
        session=db,
        name=payload.name,
        unit=payload.unit,
        status="capturing",
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
    workflow_row = await create_workflow_row(
        session=db,
        name=name,
        unit=unit,
        status="transcribing",
    )
    source = await create_source_row(
        session=db,
        workflow_id=workflow_row.id,
        modality=modality,
        label=None,
        raw_path=None,
        contributor_role=None,
        status="pending",
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


def _parse_chat_messages(raw: str) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"chat_messages must be valid JSON: {exc.msg}",
        ) from exc
    if not isinstance(parsed, list):
        raise HTTPException(
            status_code=422,
            detail="chat_messages must be a JSON array of {role, content} objects",
        )
    return parsed
