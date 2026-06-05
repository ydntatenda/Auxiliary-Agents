from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session
from app.models.db import ClarificationHistoryRow, WorkflowRow
from app.models.graph import Workflow


HistoryRole = Literal["question", "answer"]


async def create_workflow_row(
    *,
    session: AsyncSession,
    name: str,
    unit: str,
    status: str = "capturing",
) -> WorkflowRow:
    row = WorkflowRow(
        name=name,
        unit=unit,
        assembled_transcript=None,
        status=status,
        graph=None,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def get_workflow_row(session: AsyncSession, workflow_id: str | UUID) -> WorkflowRow | None:
    return await session.get(WorkflowRow, UUID(str(workflow_id)))


async def require_workflow_row(session: AsyncSession, workflow_id: str | UUID) -> WorkflowRow:
    row = await get_workflow_row(session, workflow_id)
    if row is None:
        raise ValueError(f"Workflow {workflow_id} not found")
    return row


async def update_status(
    *,
    workflow_id: str | UUID,
    status: str,
    assembled_transcript: str | None = None,
    graph: Workflow | None = None,
) -> None:
    async with async_session() as session:
        row = await require_workflow_row(session, workflow_id)
        row.status = status
        if assembled_transcript is not None:
            row.assembled_transcript = assembled_transcript
        if graph is not None:
            row.graph = graph.model_dump(mode="json")
        await session.commit()


async def load_workflow(workflow_id: str | UUID) -> Workflow:
    async with async_session() as session:
        row = await require_workflow_row(session, workflow_id)
        if row.graph is None:
            raise ValueError(f"Workflow {workflow_id} has not been extracted")
        return Workflow.model_validate(row.graph)


async def save_workflow(workflow: Workflow, status: str | None = None) -> None:
    async with async_session() as session:
        row = await require_workflow_row(session, workflow.id)
        row.graph = workflow.model_dump(mode="json")
        row.name = workflow.name
        row.unit = workflow.unit
        if status is not None:
            row.status = status
        await session.commit()


async def log_clarification_message(
    session: AsyncSession,
    workflow_id: str | UUID,
    role: HistoryRole,
    content: str,
) -> ClarificationHistoryRow:
    row = ClarificationHistoryRow(workflow_id=UUID(str(workflow_id)), role=role, content=content)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def load_clarification_history(
    session: AsyncSession, workflow_id: str | UUID
) -> list[ClarificationHistoryRow]:
    stmt = (
        select(ClarificationHistoryRow)
        .where(ClarificationHistoryRow.workflow_id == UUID(str(workflow_id)))
        .order_by(ClarificationHistoryRow.created_at.asc())
    )
    return list((await session.execute(stmt)).scalars().all())
