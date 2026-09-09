from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import OrganisationalAssessmentRow, WorkerProfileRow


async def list_worker_profiles(session: AsyncSession) -> list[WorkerProfileRow]:
    stmt = select(WorkerProfileRow).order_by(WorkerProfileRow.name.asc())
    return list((await session.execute(stmt)).scalars().all())


async def get_worker_profile(session: AsyncSession, member_id: str) -> WorkerProfileRow | None:
    stmt = select(WorkerProfileRow).where(WorkerProfileRow.member_id == member_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def latest_assessment(
    session: AsyncSession, workflow_id: str | UUID
) -> OrganisationalAssessmentRow | None:
    stmt = (
        select(OrganisationalAssessmentRow)
        .where(OrganisationalAssessmentRow.workflow_id == UUID(str(workflow_id)))
        .order_by(OrganisationalAssessmentRow.created_at.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()
