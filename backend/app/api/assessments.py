from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_stub import get_current_user
from app.core.authz import is_owner_or_admin
from app.db.session import get_db
from app.db.workforce import latest_assessment, list_worker_profiles
from app.db.workflows import require_workflow_row
from app.db.collaborators import get_collaborator_role, list_collaborators
from app.models.db import OrganisationalAssessmentRow
from app.models.graph import Workflow
from app.models.workforce import OrganisationalAssessment
from app.skills.organisational_assessment import assess_organisation


router = APIRouter(prefix="/workflows/{workflow_id}/assessment", tags=["assessment"])


class AssessmentResponse(BaseModel):
    id: str
    workflow_id: str
    workflow_version: int
    report: OrganisationalAssessment
    created_by: str
    created_at: datetime


def _view(row: OrganisationalAssessmentRow) -> AssessmentResponse:
    return AssessmentResponse(
        id=str(row.id),
        workflow_id=str(row.workflow_id),
        workflow_version=row.workflow_version,
        report=OrganisationalAssessment.model_validate(row.report),
        created_by=row.created_by,
        created_at=row.created_at,
    )


@router.get("", response_model=AssessmentResponse | None)
async def get_latest_assessment(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
) -> AssessmentResponse | None:
    try:
        await require_workflow_row(db, workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    row = await latest_assessment(db, workflow_id)
    return _view(row) if row else None


@router.post("", response_model=AssessmentResponse)
async def create_assessment(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
) -> AssessmentResponse:
    user = get_current_user()
    try:
        workflow_row = await require_workflow_row(db, workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if workflow_row.graph is None:
        raise HTTPException(status_code=409, detail="Extract the workflow before assessing it.")
    collaborator_role = await get_collaborator_role(db, workflow_row.id, user.id)
    if not (is_owner_or_admin(workflow_row) or collaborator_role in {"reviewer", "approver"}):
        raise HTTPException(
            status_code=403,
            detail="Only the workflow owner, a reviewer, an approver or an admin can assess it.",
        )

    collaborator_rows = await list_collaborators(db, workflow_row.id)
    relevant_member_ids = {row.member_id for row in collaborator_rows}
    if workflow_row.created_by:
        relevant_member_ids.add(workflow_row.created_by)
    worker_rows = [
        row
        for row in await list_worker_profiles(db)
        if row.status == "confirmed" and row.member_id in relevant_member_ids
    ]
    workers = [
        {
            "worker_id": row.member_id,
            "name": row.name,
            "current_role": row.current_role,
            "summary": row.summary,
            "skills": row.skills,
            "experience": row.experience,
            "qualifications": row.qualifications,
            "career_preferences": row.career_preferences,
            "profile_status": row.status,
        }
        for row in worker_rows
    ]
    workflow = Workflow.model_validate(workflow_row.graph)
    report = await assess_organisation(workflow, workers)
    report.workflow_id = str(workflow_row.id)
    row = OrganisationalAssessmentRow(
        workflow_id=UUID(str(workflow_row.id)),
        workflow_version=workflow_row.version,
        report=report.model_dump(mode="json"),
        created_by=user.id,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _view(row)
