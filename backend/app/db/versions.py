from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import WorkflowVersionRow


async def list_versions(
    session: AsyncSession, workflow_id: UUID
) -> list[WorkflowVersionRow]:
    stmt = (
        select(WorkflowVersionRow)
        .where(WorkflowVersionRow.workflow_id == workflow_id)
        .order_by(WorkflowVersionRow.version.asc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def snapshot_version(
    *,
    session: AsyncSession,
    workflow_id: UUID,
    version: int,
    graph_snapshot: dict,
    sop_snapshot: str | None,
    change_summary: str | None,
    changed_by: str,
) -> WorkflowVersionRow:
    row = WorkflowVersionRow(
        workflow_id=workflow_id,
        version=version,
        graph_snapshot=graph_snapshot,
        sop_snapshot=sop_snapshot,
        change_summary=change_summary,
        changed_by=changed_by,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row
