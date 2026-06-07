"""Authorization helpers.

Two pure predicates wrap every "can this user do that" decision in the
capture stage. They consult the auth stub for the current user; when
real auth lands we swap the stub and these stay put.

Both predicates collapse to True for admins. `is_owner_or_admin` checks
workflow-level ownership. `can_edit_source` adds the "did this user
contribute the source?" branch so collaborators can manage their own
contributions without giving them blanket edit rights over a workflow.

A null `created_by` (legacy row that never had a creator) is treated as
owner-only-is-admin: no member can ever pass the gate by accident.
"""
from __future__ import annotations

from app.core.auth_stub import get_current_user
from app.models.db import WorkflowRow


def is_owner_or_admin(row: WorkflowRow) -> bool:
    user = get_current_user()
    if user.role == "admin":
        return True
    if row.created_by is None:
        return False
    return row.created_by == user.id


def can_edit_source(row: WorkflowRow, source_added_by: str | None) -> bool:
    """The contributor, the workflow owner, or an admin can edit a source.

    A source whose `added_by` is unknown (null) can only be edited by the
    workflow owner or an admin – the safe default when provenance is
    missing.
    """
    user = get_current_user()
    if user.role == "admin":
        return True
    if row.created_by is not None and row.created_by == user.id:
        return True
    if source_added_by is None:
        return False
    return source_added_by == user.id
