"""Auth surface.

For now this is a thin wrapper around the auth stub: a single GET /auth/me
that returns whichever member is hardcoded as 'logged in' in
`core/auth_stub.py`. When real auth lands, this endpoint becomes the
session lookup and nothing else in the API has to change.
"""
from fastapi import APIRouter
from pydantic import BaseModel

from app.core.auth_stub import ORG_NAME, ORG_SLUG, get_current_user


router = APIRouter(tags=["auth"])


class CurrentUserResponse(BaseModel):
    id: str
    name: str
    avatar: str
    role: str
    org_name: str
    org_slug: str


@router.get("/auth/me", response_model=CurrentUserResponse)
async def me() -> CurrentUserResponse:
    user = get_current_user()
    return CurrentUserResponse(
        id=user.id,
        name=user.name,
        avatar=user.avatar,
        role=user.role,
        org_name=ORG_NAME,
        org_slug=ORG_SLUG,
    )
