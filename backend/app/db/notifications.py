from typing import Literal
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session
from app.models.db import WorkflowNotificationRow


NotificationType = Literal[
    "added_as_collaborator",
    "update_requested",
    "approved",
    "needs_review",
]


async def create_notification(
    *,
    session: AsyncSession,
    member_id: str,
    workflow_id: UUID,
    type: NotificationType,
    message: str,
) -> WorkflowNotificationRow:
    row = WorkflowNotificationRow(
        member_id=member_id,
        workflow_id=workflow_id,
        type=type,
        message=message,
        read=False,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def list_unread_for(
    session: AsyncSession, member_id: str
) -> list[WorkflowNotificationRow]:
    stmt = (
        select(WorkflowNotificationRow)
        .where(
            WorkflowNotificationRow.member_id == member_id,
            WorkflowNotificationRow.read.is_(False),
        )
        .order_by(WorkflowNotificationRow.created_at.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def mark_read(
    session: AsyncSession, notification_id: UUID, member_id: str
) -> bool:
    stmt = (
        update(WorkflowNotificationRow)
        .where(
            WorkflowNotificationRow.id == notification_id,
            WorkflowNotificationRow.member_id == member_id,
        )
        .values(read=True)
    )
    result = await session.execute(stmt)
    await session.commit()
    return (result.rowcount or 0) > 0


async def mark_all_read(member_id: str) -> int:
    async with async_session() as session:
        stmt = (
            update(WorkflowNotificationRow)
            .where(
                WorkflowNotificationRow.member_id == member_id,
                WorkflowNotificationRow.read.is_(False),
            )
            .values(read=True)
        )
        result = await session.execute(stmt)
        await session.commit()
        return int(result.rowcount or 0)
