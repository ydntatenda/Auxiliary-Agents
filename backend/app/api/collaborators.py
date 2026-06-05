"""Collaborator API.

Two surfaces in one router: a member lookup against the auth stub for
the autocomplete UI, and the per-workflow collaborator list with add /
remove operations. Adding a collaborator also creates a notification of
type 'added_as_collaborator' for them.
"""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_stub import find_member, get_current_user, get_member
from app.db.collaborators import (
    list_collaborators,
    remove_collaborator,
    upsert_collaborator,
)
from app.db.notifications import create_notification
from app.db.session import get_db
from app.db.workflows import require_workflow_row


router = APIRouter(tags=["collaborators"])


ContributionRole = Literal["contributor", "reviewer", "approver"]


class MemberView(BaseModel):
    id: str
    name: str
    avatar: str
    role: str


class CollaboratorView(BaseModel):
    member_id: str
    name: str
    avatar: str
    contribution_role: str
    added_by: str
    notified: bool


class AddCollaboratorPayload(BaseModel):
    member_id: str = Field(..., min_length=1)
    contribution_role: ContributionRole


def _to_member_view(member) -> MemberView:
    return MemberView(id=member.id, name=member.name, avatar=member.avatar, role=member.role)


async def _collaborator_views(session: AsyncSession, workflow_id: UUID) -> list[CollaboratorView]:
    rows = await list_collaborators(session, workflow_id)
    views: list[CollaboratorView] = []
    for row in rows:
        member = get_member(row.member_id)
        views.append(
            CollaboratorView(
                member_id=row.member_id,
                name=member.name if member else row.member_id,
                avatar=member.avatar if member else row.member_id[:2].upper(),
                contribution_role=row.contribution_role,
                added_by=row.added_by,
                notified=row.notified,
            )
        )
    return views


@router.get("/collaborators/members", response_model=list[MemberView])
async def search_members(
    q: str = Query("", description="Substring of the member's name."),
) -> list[MemberView]:
    return [_to_member_view(member) for member in find_member(q)]


@router.get(
    "/workflows/{workflow_id}/collaborators",
    response_model=list[CollaboratorView],
)
async def get_workflow_collaborators(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[CollaboratorView]:
    try:
        await require_workflow_row(db, workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return await _collaborator_views(db, UUID(workflow_id))


@router.post(
    "/workflows/{workflow_id}/collaborators",
    response_model=list[CollaboratorView],
)
async def add_workflow_collaborator(
    workflow_id: str,
    payload: AddCollaboratorPayload,
    db: AsyncSession = Depends(get_db),
) -> list[CollaboratorView]:
    user = get_current_user()
    try:
        workflow_row = await require_workflow_row(db, workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    member = get_member(payload.member_id)
    if member is None:
        raise HTTPException(status_code=404, detail=f"Member {payload.member_id} not found")

    await upsert_collaborator(
        session=db,
        workflow_id=workflow_row.id,
        member_id=member.id,
        contribution_role=payload.contribution_role,
        added_by=user.id,
    )

    if member.id != user.id:
        await create_notification(
            session=db,
            member_id=member.id,
            workflow_id=workflow_row.id,
            type="added_as_collaborator",
            message=f"You were added to {workflow_row.name} as {payload.contribution_role}.",
        )

    return await _collaborator_views(db, workflow_row.id)


@router.delete(
    "/workflows/{workflow_id}/collaborators/{member_id}",
    status_code=204,
    response_class=None,
)
async def delete_workflow_collaborator(
    workflow_id: str,
    member_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await require_workflow_row(db, workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    removed = await remove_collaborator(db, UUID(workflow_id), member_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Collaborator not found")
