"""Unit tests for the authorization helper.

Pure predicates over WorkflowRow + member id, easy to pin without
spinning up a database. The auth stub's current user is swapped via
monkeypatch in each test so we can exercise admin override, owner,
non-owner, and the source-editor branches.
"""
from types import SimpleNamespace

from app.core import auth_stub
from app.core.auth_stub import Member
from app.core.authz import can_edit_source, is_owner_or_admin


def _row(created_by: str | None) -> SimpleNamespace:
    return SimpleNamespace(created_by=created_by)


def _stub_user(monkeypatch, *, id: str, role: str = "member") -> Member:
    member = Member(id=id, name=id.title(), role=role, avatar=id[:2].upper())
    monkeypatch.setattr(auth_stub, "get_current_user", lambda: member)
    # The authz module imports `get_current_user` at module import time,
    # so the monkeypatch also needs to land on the authz module reference.
    from app.core import authz

    monkeypatch.setattr(authz, "get_current_user", lambda: member)
    return member


def test_is_owner_or_admin_passes_creator(monkeypatch) -> None:
    _stub_user(monkeypatch, id="tatenda")
    assert is_owner_or_admin(_row("tatenda")) is True


def test_is_owner_or_admin_rejects_non_creator(monkeypatch) -> None:
    _stub_user(monkeypatch, id="chidubem")
    assert is_owner_or_admin(_row("tatenda")) is False


def test_admin_passes_even_when_not_creator(monkeypatch) -> None:
    _stub_user(monkeypatch, id="some_admin", role="admin")
    assert is_owner_or_admin(_row("tatenda")) is True


def test_null_created_by_blocks_non_admin(monkeypatch) -> None:
    """Legacy row with no recorded owner: only admins get through."""
    _stub_user(monkeypatch, id="tatenda")
    assert is_owner_or_admin(_row(None)) is False

    _stub_user(monkeypatch, id="tatenda", role="admin")
    assert is_owner_or_admin(_row(None)) is True


def test_can_edit_source_when_user_added_it(monkeypatch) -> None:
    _stub_user(monkeypatch, id="aanya")
    assert can_edit_source(_row("tatenda"), source_added_by="aanya") is True


def test_can_edit_source_when_user_is_workflow_owner(monkeypatch) -> None:
    _stub_user(monkeypatch, id="tatenda")
    assert can_edit_source(_row("tatenda"), source_added_by="aanya") is True


def test_can_edit_source_admin_override(monkeypatch) -> None:
    _stub_user(monkeypatch, id="some_admin", role="admin")
    assert can_edit_source(_row("tatenda"), source_added_by=None) is True
    assert can_edit_source(_row(None), source_added_by="aanya") is True


def test_can_edit_source_rejects_random_member(monkeypatch) -> None:
    _stub_user(monkeypatch, id="chidubem")
    assert can_edit_source(_row("tatenda"), source_added_by="aanya") is False


def test_can_edit_source_with_null_added_by_blocks_random_member(monkeypatch) -> None:
    """Legacy source with no recorded contributor: owner + admin only."""
    _stub_user(monkeypatch, id="chidubem")
    assert can_edit_source(_row("tatenda"), source_added_by=None) is False
