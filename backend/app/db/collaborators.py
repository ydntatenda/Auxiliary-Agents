from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session
from app.models.db import WorkflowCollaboratorRow


ContributionRole = Literal["contributor", "reviewer", "approver"]


async def list_collaborators(
    session: AsyncSession, workflow_id: UUID
) -> list[WorkflowCollaboratorRow]:
    stmt = (
        select(WorkflowCollaboratorRow)
        .where(WorkflowCollaboratorRow.workflow_id == workflow_id)
        .order_by(WorkflowCollaboratorRow.added_at.asc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def upsert_collaborator(
    *,
    session: AsyncSession,
    workflow_id: UUID,
    member_id: str,
    contribution_role: ContributionRole,
    added_by: str,
) -> WorkflowCollaboratorRow:
    """Insert or update a collaborator row.

    The (workflow_id, member_id) uniqueness constraint means at most one
    row per member per workflow; if they're already on the workflow this
    just updates their role.
    """
    stmt = select(WorkflowCollaboratorRow).where(
        WorkflowCollaboratorRow.workflow_id == workflow_id,
        WorkflowCollaboratorRow.member_id == member_id,
    )
    existing = (await session.execute(stmt)).scalar_one_or_none()
    if existing is not None:
        existing.contribution_role = contribution_role
        await session.commit()
        await session.refresh(existing)
        return existing
    row = WorkflowCollaboratorRow(
        workflow_id=workflow_id,
        member_id=member_id,
        contribution_role=contribution_role,
        added_by=added_by,
        notified=False,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def remove_collaborator(
    session: AsyncSession, workflow_id: UUID, member_id: str
) -> bool:
    stmt = select(WorkflowCollaboratorRow).where(
        WorkflowCollaboratorRow.workflow_id == workflow_id,
        WorkflowCollaboratorRow.member_id == member_id,
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        return False
    await session.delete(row)
    await session.commit()
    return True


async def get_collaborator_role(
    session: AsyncSession, workflow_id: UUID, member_id: str
) -> str | None:
    stmt = select(WorkflowCollaboratorRow.contribution_role).where(
        WorkflowCollaboratorRow.workflow_id == workflow_id,
        WorkflowCollaboratorRow.member_id == member_id,
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def count_collaborators(workflow_id: UUID) -> int:
    """Count helper used by the library listing."""
    from sqlalchemy import func

    async with async_session() as session:
        stmt = select(func.count(WorkflowCollaboratorRow.id)).where(
            WorkflowCollaboratorRow.workflow_id == workflow_id
        )
        return int((await session.execute(stmt)).scalar() or 0)
