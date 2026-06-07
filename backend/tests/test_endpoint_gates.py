"""Route-level tests for the authorization gates added in capture hardening.

These call the FastAPI handler functions directly with mocked sessions and
rows, so they pin the 403/422 contracts without needing a real database.
The handlers are async and accept a session argument we can stub; what
matters is whether they raise HTTPException with the right status code,
and whether they touch the row when they shouldn't.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api import capture, library, workflows
from app.core import auth_stub
from app.core.auth_stub import Member


def _stub_user(monkeypatch, *, id: str, role: str = "member") -> Member:
    member = Member(id=id, name=id.title(), role=role, avatar=id[:2].upper())
    monkeypatch.setattr(auth_stub, "get_current_user", lambda: member)
    from app.core import authz

    monkeypatch.setattr(authz, "get_current_user", lambda: member)
    return member


def _workflow_row(*, created_by: str, status: str = "approved") -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        name="Citation appeals",
        unit="P&T",
        description=None,
        status=status,
        version=1,
        graph={"steps": []},
        approved_at=None,
        approved_by=None,
        archived=False,
        archived_at=None,
        created_by=created_by,
        sop_cache=None,
        sop_cache_graph_hash=None,
    )


def _source_row(*, added_by: str | None) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        workflow_id=uuid4(),
        order=0,
        modality="text",
        label=None,
        contributor_role=None,
        added_by=added_by,
        status="ready",
        error=None,
        meta=None,
        assembled_text="anything",
    )


# -- Archive gate ------------------------------------------------------


async def test_archive_rejects_non_owner_non_admin(monkeypatch) -> None:
    _stub_user(monkeypatch, id="chidubem")
    row = _workflow_row(created_by="tatenda")
    monkeypatch.setattr(workflows, "require_workflow_row", AsyncMock(return_value=row))

    session = SimpleNamespace(commit=AsyncMock())
    with pytest.raises(HTTPException) as exc:
        await workflows.archive_workflow("any-id", db=session)
    assert exc.value.status_code == 403
    assert "archive" in exc.value.detail
    assert row.archived is False
    session.commit.assert_not_called()


async def test_archive_owner_passes(monkeypatch) -> None:
    _stub_user(monkeypatch, id="tatenda")
    row = _workflow_row(created_by="tatenda")
    monkeypatch.setattr(workflows, "require_workflow_row", AsyncMock(return_value=row))

    session = SimpleNamespace(commit=AsyncMock())
    await workflows.archive_workflow("any-id", db=session)
    assert row.archived is True
    session.commit.assert_awaited()


async def test_archive_admin_passes_even_without_ownership(monkeypatch) -> None:
    _stub_user(monkeypatch, id="some_admin", role="admin")
    row = _workflow_row(created_by="tatenda")
    monkeypatch.setattr(workflows, "require_workflow_row", AsyncMock(return_value=row))

    session = SimpleNamespace(commit=AsyncMock())
    await workflows.archive_workflow("any-id", db=session)
    assert row.archived is True


# -- Source-delete gate ------------------------------------------------


async def test_source_delete_rejects_non_contributor(monkeypatch) -> None:
    _stub_user(monkeypatch, id="chidubem")
    row = _workflow_row(created_by="tatenda")
    source = _source_row(added_by="aanya")
    monkeypatch.setattr(capture, "require_workflow_row", AsyncMock(return_value=row))
    monkeypatch.setattr(capture, "require_source", AsyncMock(return_value=source))
    delete_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(capture, "delete_source", delete_mock)

    session = SimpleNamespace()
    with pytest.raises(HTTPException) as exc:
        await capture.remove_source(str(uuid4()), str(uuid4()), db=session)
    assert exc.value.status_code == 403
    delete_mock.assert_not_called()


async def test_source_delete_contributor_passes(monkeypatch) -> None:
    _stub_user(monkeypatch, id="aanya")
    row = _workflow_row(created_by="tatenda")
    source = _source_row(added_by="aanya")
    monkeypatch.setattr(capture, "require_workflow_row", AsyncMock(return_value=row))
    monkeypatch.setattr(capture, "require_source", AsyncMock(return_value=source))
    monkeypatch.setattr(capture, "delete_source", AsyncMock(return_value=True))
    monkeypatch.setattr(capture, "assemble_transcript", AsyncMock())

    session = SimpleNamespace()
    # Should not raise.
    await capture.remove_source(str(uuid4()), str(uuid4()), db=session)


async def test_source_delete_workflow_owner_passes(monkeypatch) -> None:
    _stub_user(monkeypatch, id="tatenda")
    row = _workflow_row(created_by="tatenda")
    # Source added by someone else.
    source = _source_row(added_by="aanya")
    monkeypatch.setattr(capture, "require_workflow_row", AsyncMock(return_value=row))
    monkeypatch.setattr(capture, "require_source", AsyncMock(return_value=source))
    monkeypatch.setattr(capture, "delete_source", AsyncMock(return_value=True))
    monkeypatch.setattr(capture, "assemble_transcript", AsyncMock())

    session = SimpleNamespace()
    await capture.remove_source(str(uuid4()), str(uuid4()), db=session)


# -- Identity PATCH gate -----------------------------------------------


async def test_patch_workflow_rejects_non_owner(monkeypatch) -> None:
    _stub_user(monkeypatch, id="chidubem")
    row = _workflow_row(created_by="tatenda")
    monkeypatch.setattr(workflows, "require_workflow_row", AsyncMock(return_value=row))

    payload = workflows.EditWorkflowPayload(name="New name")
    session = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
    with pytest.raises(HTTPException) as exc:
        await workflows.edit_workflow("wf", payload, db=session)
    assert exc.value.status_code == 403
    assert row.name == "Citation appeals"
    session.commit.assert_not_called()


async def test_patch_workflow_blank_name_rejected(monkeypatch) -> None:
    _stub_user(monkeypatch, id="tatenda")
    row = _workflow_row(created_by="tatenda")
    monkeypatch.setattr(workflows, "require_workflow_row", AsyncMock(return_value=row))

    payload = workflows.EditWorkflowPayload(name="   ")
    session = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
    with pytest.raises(HTTPException) as exc:
        await workflows.edit_workflow("wf", payload, db=session)
    assert exc.value.status_code == 422


async def test_patch_workflow_name_change_invalidates_sop_cache(monkeypatch) -> None:
    _stub_user(monkeypatch, id="tatenda")
    row = _workflow_row(created_by="tatenda")
    row.graph = {"name": "Citation appeals", "unit": "P&T", "steps": []}
    row.sop_cache = "# Cached"
    row.sop_cache_graph_hash = "deadbeef"
    monkeypatch.setattr(workflows, "require_workflow_row", AsyncMock(return_value=row))
    # get_summary is called at the end; stub it to a passthrough.
    summary_stub = AsyncMock(
        return_value=workflows.WorkflowSummary(
            id=str(row.id),
            name="New name",
            unit=row.unit,
            description=None,
            status=row.status,
            version=row.version,
            approved_at=None,
            archived=False,
            created_by=row.created_by,
            collaborators=[],
            versions=[],
            source_count=0,
            collaborator_count=0,
            current_user_role=None,
        )
    )
    monkeypatch.setattr(workflows, "get_summary", summary_stub)

    payload = workflows.EditWorkflowPayload(name="New name")
    session = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
    await workflows.edit_workflow("wf", payload, db=session)

    assert row.name == "New name"
    assert row.graph["name"] == "New name"
    assert row.sop_cache is None
    assert row.sop_cache_graph_hash is None


async def test_patch_workflow_description_only_does_not_bust_cache(monkeypatch) -> None:
    _stub_user(monkeypatch, id="tatenda")
    row = _workflow_row(created_by="tatenda")
    row.graph = {"name": "Citation appeals", "unit": "P&T", "steps": []}
    row.sop_cache = "# Cached"
    row.sop_cache_graph_hash = "deadbeef"
    monkeypatch.setattr(workflows, "require_workflow_row", AsyncMock(return_value=row))
    summary_stub = AsyncMock(
        return_value=workflows.WorkflowSummary(
            id=str(row.id),
            name=row.name,
            unit=row.unit,
            description="hello",
            status=row.status,
            version=row.version,
            approved_at=None,
            archived=False,
            created_by=row.created_by,
            collaborators=[],
            versions=[],
            source_count=0,
            collaborator_count=0,
            current_user_role=None,
        )
    )
    monkeypatch.setattr(workflows, "get_summary", summary_stub)

    payload = workflows.EditWorkflowPayload(description="hello")
    session = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
    await workflows.edit_workflow("wf", payload, db=session)

    assert row.description == "hello"
    # Cache untouched: description does not appear in the SOP header.
    assert row.sop_cache == "# Cached"
    assert row.sop_cache_graph_hash == "deadbeef"


# -- request_update gate ----------------------------------------------


async def test_request_update_rejects_random_member(monkeypatch) -> None:
    _stub_user(monkeypatch, id="chidubem")
    row = _workflow_row(created_by="tatenda", status="approved")
    monkeypatch.setattr(library, "require_workflow_row", AsyncMock(return_value=row))
    monkeypatch.setattr(library, "get_collaborator_role", AsyncMock(return_value=None))

    session = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
    with pytest.raises(HTTPException) as exc:
        await library.request_update("wf", db=session)
    assert exc.value.status_code == 403
    assert row.status == "approved"
    session.commit.assert_not_called()


async def test_request_update_collaborator_passes(monkeypatch) -> None:
    _stub_user(monkeypatch, id="chidubem")
    row = _workflow_row(created_by="tatenda", status="approved")
    monkeypatch.setattr(library, "require_workflow_row", AsyncMock(return_value=row))
    monkeypatch.setattr(
        library, "get_collaborator_role", AsyncMock(return_value="contributor")
    )
    monkeypatch.setattr(library, "list_collaborators", AsyncMock(return_value=[]))
    monkeypatch.setattr(library, "create_notification", AsyncMock())
    monkeypatch.setattr(
        library,
        "_summarise",
        AsyncMock(
            return_value=library.WorkflowSummary(
                id=str(row.id),
                name=row.name,
                unit=row.unit,
                description=None,
                status="pending_update",
                version=row.version,
                created_at=__import__("datetime").datetime.now(),
                updated_at=__import__("datetime").datetime.now(),
                approved_at=None,
                archived=False,
                created_by=row.created_by,
                collaborator_count=0,
                source_count=0,
                current_user_role="contributor",
            )
        ),
    )

    session = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
    await library.request_update("wf", db=session)
    assert row.status == "pending_update"
