from typing import Literal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session
from app.models.db import SourceRow


SourceStatus = Literal["pending", "processing", "ready", "failed"]
ContributorRole = Literal["operator", "approver", "observer"]


async def create_source_row(
    *,
    session: AsyncSession,
    workflow_id: UUID,
    modality: str,
    label: str | None,
    raw_path: str | None,
    contributor_role: str | None,
    assembled_text: str | None = None,
    status: SourceStatus = "pending",
    meta: dict | None = None,
) -> SourceRow:
    next_order = await session.scalar(
        select(func.coalesce(func.max(SourceRow.order) + 1, 0)).where(
            SourceRow.workflow_id == workflow_id
        )
    )
    row = SourceRow(
        workflow_id=workflow_id,
        order=int(next_order or 0),
        modality=modality,
        label=label,
        raw_path=raw_path,
        contributor_role=contributor_role,
        assembled_text=assembled_text,
        status=status,
        meta=meta,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def list_sources(
    session: AsyncSession, workflow_id: UUID
) -> list[SourceRow]:
    stmt = (
        select(SourceRow)
        .where(SourceRow.workflow_id == workflow_id)
        .order_by(SourceRow.order.asc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_source(
    session: AsyncSession, workflow_id: UUID, source_id: UUID
) -> SourceRow | None:
    row = await session.get(SourceRow, source_id)
    if row is None or row.workflow_id != workflow_id:
        return None
    return row


async def require_source(
    session: AsyncSession, workflow_id: UUID, source_id: UUID
) -> SourceRow:
    row = await get_source(session, workflow_id, source_id)
    if row is None:
        raise ValueError(f"Source {source_id} not found on workflow {workflow_id}")
    return row


async def delete_source(
    session: AsyncSession, workflow_id: UUID, source_id: UUID
) -> bool:
    row = await get_source(session, workflow_id, source_id)
    if row is None:
        return False
    await session.delete(row)
    await session.commit()
    return True


async def update_source_status(
    *,
    source_id: UUID,
    status: SourceStatus,
    assembled_text: str | None = None,
    meta: dict | None = None,
    error: str | None = None,
) -> None:
    """Single writer for source status transitions used by background tasks.

    Re-running ingestion on a source overwrites assembled_text and meta
    cleanly, never appends. The DB owns updated_at via onupdate.
    """
    async with async_session() as session:
        row = await session.get(SourceRow, source_id)
        if row is None:
            raise ValueError(f"Source {source_id} not found")
        row.status = status
        if assembled_text is not None:
            row.assembled_text = assembled_text
        if meta is not None:
            row.meta = meta
        row.error = error
        await session.commit()


async def get_source_raw_path(source_id: UUID) -> tuple[str, str | None]:
    """Return (modality, raw_path) for a source, looked up by id alone."""
    async with async_session() as session:
        row = await session.get(SourceRow, source_id)
        if row is None:
            raise ValueError(f"Source {source_id} not found")
        return row.modality, row.raw_path
