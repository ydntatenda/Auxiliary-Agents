from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.auth_stub import get_current_user, get_member
from app.db.session import get_db
from app.db.workforce import get_worker_profile, list_worker_profiles
from app.models.db import WorkerProfileRow
from app.models.workforce import ExperienceItem, Qualification, SkillClaim
from app.skills.source_ingestion import ingest_source
from app.skills.workforce_profile import extract_worker_profile


router = APIRouter(prefix="/workers", tags=["workforce"])
_ALLOWED_EXTENSIONS = {".pdf", ".docx"}
_MAX_BYTES = 15 * 1024 * 1024


class WorkerProfileResponse(BaseModel):
    id: str
    member_id: str
    name: str
    current_role: str | None
    summary: str | None
    skills: list
    experience: list
    qualifications: list
    career_preferences: list[str]
    provenance: list
    source_filename: str | None
    status: str
    confirmed_at: datetime | None
    updated_at: datetime


class WorkerProfilePatch(BaseModel):
    name: str | None = None
    current_role: str | None = None
    summary: str | None = None
    skills: list[SkillClaim] | None = None
    experience: list[ExperienceItem] | None = None
    qualifications: list[Qualification] | None = None
    career_preferences: list[str] | None = None


def _view(row: WorkerProfileRow) -> WorkerProfileResponse:
    return WorkerProfileResponse(
        id=str(row.id),
        member_id=row.member_id,
        name=row.name,
        current_role=row.current_role,
        summary=row.summary,
        skills=row.skills,
        experience=row.experience,
        qualifications=row.qualifications,
        career_preferences=row.career_preferences,
        provenance=row.provenance,
        source_filename=row.source_filename,
        status=row.status,
        confirmed_at=row.confirmed_at,
        updated_at=row.updated_at,
    )


def _can_manage(member_id: str) -> bool:
    user = get_current_user()
    return user.role == "admin" or user.id == member_id


@router.get("", response_model=list[WorkerProfileResponse])
async def list_profiles(db: AsyncSession = Depends(get_db)) -> list[WorkerProfileResponse]:
    user = get_current_user()
    rows = await list_worker_profiles(db)
    if user.role != "admin":
        rows = [row for row in rows if row.member_id == user.id]
    return [_view(row) for row in rows]


@router.post("/cv", response_model=WorkerProfileResponse)
async def upload_cv(
    file: UploadFile = File(...),
    member_id: str | None = Form(None),
    db: AsyncSession = Depends(get_db),
) -> WorkerProfileResponse:
    user = get_current_user()
    target_member_id = member_id or user.id
    if not _can_manage(target_member_id):
        raise HTTPException(status_code=403, detail="You cannot manage this worker profile.")
    member = get_member(target_member_id)
    if member is None:
        raise HTTPException(status_code=404, detail="Worker not found.")

    filename = Path(file.filename or "resume").name
    suffix = Path(filename).suffix.lower()
    if suffix not in _ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Upload a PDF or DOCX CV.")
    content = await file.read(_MAX_BYTES + 1)
    if len(content) > _MAX_BYTES:
        raise HTTPException(status_code=413, detail="CV must be 15 MB or smaller.")

    directory = get_settings().upload_dir / "workers" / target_member_id
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{uuid4()}{suffix}"
    path.write_bytes(content)

    ingested = await ingest_source("document", raw_path=str(path))
    if not ingested.assembled_text.strip():
        raise HTTPException(status_code=422, detail="No readable text was found in the CV.")
    extracted = await extract_worker_profile(filename, ingested.assembled_text)
    provenance = [
        {
            "source": filename,
            "kind": "cv",
            "char_count": len(ingested.assembled_text),
            "extracted_at": datetime.now(timezone.utc).isoformat(),
        }
    ]

    row = await get_worker_profile(db, target_member_id)
    if row is None:
        row = WorkerProfileRow(member_id=target_member_id, name=extracted.name or member.name)
        db.add(row)
    row.name = extracted.name or member.name
    row.current_role = extracted.current_role
    row.summary = extracted.summary
    row.skills = [item.model_dump(mode="json") for item in extracted.skills]
    row.experience = [item.model_dump(mode="json") for item in extracted.experience]
    row.qualifications = [item.model_dump(mode="json") for item in extracted.qualifications]
    row.career_preferences = extracted.career_preferences
    row.provenance = provenance
    row.source_filename = filename
    row.source_path = str(path)
    row.source_text = ingested.assembled_text
    row.status = "draft"
    row.confirmed_at = None
    await db.commit()
    await db.refresh(row)
    return _view(row)


@router.patch("/{member_id}", response_model=WorkerProfileResponse)
async def update_profile(
    member_id: str,
    payload: WorkerProfilePatch,
    db: AsyncSession = Depends(get_db),
) -> WorkerProfileResponse:
    if not _can_manage(member_id):
        raise HTTPException(status_code=403, detail="You cannot manage this worker profile.")
    row = await get_worker_profile(db, member_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Worker profile not found.")
    changes = payload.model_dump(exclude_unset=True, mode="json")
    if "name" in changes and not str(changes["name"] or "").strip():
        raise HTTPException(status_code=422, detail="Name cannot be blank.")
    for field, value in changes.items():
        setattr(row, field, value)
    row.status = "draft"
    row.confirmed_at = None
    await db.commit()
    await db.refresh(row)
    return _view(row)


@router.post("/{member_id}/confirm", response_model=WorkerProfileResponse)
async def confirm_profile(
    member_id: str,
    db: AsyncSession = Depends(get_db),
) -> WorkerProfileResponse:
    if not _can_manage(member_id):
        raise HTTPException(status_code=403, detail="You cannot confirm this worker profile.")
    row = await get_worker_profile(db, member_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Worker profile not found.")
    row.status = "confirmed"
    row.confirmed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(row)
    return _view(row)


@router.delete("/{member_id}", status_code=204)
async def delete_profile(
    member_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    if not _can_manage(member_id):
        raise HTTPException(status_code=403, detail="You cannot delete this worker profile.")
    row = await get_worker_profile(db, member_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Worker profile not found.")
    source_path = Path(row.source_path) if row.source_path else None
    await db.delete(row)
    await db.commit()
    if source_path and source_path.is_file():
        source_path.unlink()
