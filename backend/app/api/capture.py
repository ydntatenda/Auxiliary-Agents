from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.artifacts import write_text_artifact
from app.core.background import analyze_screen_capture, transcribe_voice_capture
from app.db.session import get_db
from app.db.workflows import create_workflow_row


router = APIRouter(prefix="/capture", tags=["capture"])


class TextCapturePayload(BaseModel):
    name: str = Field(..., min_length=1)
    unit: str = "GT P&T"
    text: str = Field(..., min_length=1)


class CaptureResponse(BaseModel):
    workflow_id: str
    status: str


async def _save_upload(workflow_id: str, upload: UploadFile, default_ext: str) -> str:
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(upload.filename or "").suffix or default_ext
    path = settings.upload_dir / f"{workflow_id}{suffix}"
    path.write_bytes(await upload.read())
    return str(path)


@router.post("/text", response_model=CaptureResponse)
async def capture_text(
    payload: TextCapturePayload,
    db: AsyncSession = Depends(get_db),
) -> CaptureResponse:
    row = await create_workflow_row(
        session=db,
        name=payload.name,
        unit=payload.unit,
        source_modality="text",
        source_transcript=payload.text,
        status="transcribed",
    )
    write_text_artifact(str(row.id), "source_transcript.txt", payload.text)
    return CaptureResponse(workflow_id=str(row.id), status=row.status)


@router.post("/voice", response_model=CaptureResponse)
async def capture_voice(
    background_tasks: BackgroundTasks,
    name: str = Form(...),
    unit: str = Form("GT P&T"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> CaptureResponse:
    row = await create_workflow_row(
        session=db,
        name=name,
        unit=unit,
        source_modality="voice",
        source_transcript=None,
        status="transcribing",
    )
    path = await _save_upload(str(row.id), file, ".webm")
    background_tasks.add_task(transcribe_voice_capture, row.id, path)
    return CaptureResponse(workflow_id=str(row.id), status=row.status)


@router.post("/screen", response_model=CaptureResponse)
async def capture_screen(
    background_tasks: BackgroundTasks,
    name: str = Form(...),
    unit: str = Form("GT P&T"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> CaptureResponse:
    row = await create_workflow_row(
        session=db,
        name=name,
        unit=unit,
        source_modality="screen",
        source_transcript=None,
        status="transcribing",
    )
    path = await _save_upload(str(row.id), file, ".webm")
    background_tasks.add_task(analyze_screen_capture, row.id, path)
    return CaptureResponse(workflow_id=str(row.id), status=row.status)
