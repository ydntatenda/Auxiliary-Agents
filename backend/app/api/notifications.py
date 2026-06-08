"""Notifications API.

Surfaces only the unread inbox for the currently-stubbed user. Items are
marked read either individually or all at once. The library page uses
this to drive the notification bell in the topbar.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_stub import get_current_user
from app.db.notifications import list_unread_for, mark_all_read, mark_read
from app.db.session import get_db
from app.models.db import WorkflowRow


router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationView(BaseModel):
    id: str
    member_id: str
    workflow_id: str
    workflow_name: str
    type: str
    message: str
    read: bool
    created_at: datetime


async def _enrich(session: AsyncSession, row) -> NotificationView:
    workflow = await session.get(WorkflowRow, row.workflow_id)
    return NotificationView(
        id=str(row.id),
        member_id=row.member_id,
        workflow_id=str(row.workflow_id),
        workflow_name=workflow.name if workflow else "(deleted workflow)",
        type=row.type,
        message=row.message,
        read=row.read,
        created_at=row.created_at,
    )


@router.get("", response_model=list[NotificationView])
async def list_notifications(
    db: AsyncSession = Depends(get_db),
) -> list[NotificationView]:
    user = get_current_user()
    rows = await list_unread_for(db, user.id)
    return [await _enrich(db, row) for row in rows]


@router.post("/{notification_id}/read", status_code=204)
async def read_one(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    user = get_current_user()
    ok = await mark_read(db, UUID(notification_id), user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Notification not found")


@router.post("/read-all")
async def read_all() -> dict[str, int]:
    user = get_current_user()
    count = await mark_all_read(user.id)
    return {"marked_read": count}
