"""Pin the atomicity contract on assemble_transcript.

The cache write must happen inside the same AsyncSession that read the
sources, so a concurrent mutation between read and write cannot leave
the cache reflecting a state no point in time ever held. These tests
mock async_session to count opens and to prove no commit fires on the
failure path.
"""
from __future__ import annotations

import contextlib
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core import assembly


@pytest.fixture
def captured_session(monkeypatch):
    """Mock async_session and return a SimpleNamespace carrying counters.

    The returned namespace exposes `opens` (how many sessions were started),
    `commits` (how many commits ran), and `row` (the WorkflowRow the writer
    mutates, so a test can inspect what got written).
    """
    state = SimpleNamespace(opens=0, commits=0, row=None)

    @contextlib.asynccontextmanager
    async def fake_session():
        state.opens += 1
        session = SimpleNamespace()

        async def commit():
            state.commits += 1

        session.commit = commit
        yield session

    row = SimpleNamespace(assembled_transcript=None)
    state.row = row

    monkeypatch.setattr(assembly, "async_session", fake_session)
    monkeypatch.setattr(
        assembly,
        "require_workflow_row",
        AsyncMock(return_value=row),
    )
    return state


@pytest.fixture
def sources_fn(monkeypatch):
    """Replace list_sources with a settable mock so tests can choose the read."""
    mock = AsyncMock(return_value=[])
    monkeypatch.setattr(assembly, "list_sources", mock)
    return mock


@pytest.fixture(autouse=True)
def silent_artifact(monkeypatch, tmp_path):
    """Redirect the artifact write so disk side-effects do not leak."""
    monkeypatch.setattr(
        assembly,
        "write_text_artifact",
        lambda *args, **kwargs: tmp_path / "ignored.txt",
    )


def _source(text: str, *, modality: str = "text", label: str = "src") -> SimpleNamespace:
    return SimpleNamespace(
        modality=modality,
        label=label,
        contributor_role=None,
        status="ready",
        assembled_text=text,
    )


async def test_single_session_open_for_read_and_write(captured_session, sources_fn):
    sources_fn.return_value = [_source("first"), _source("second")]
    out = await assembly.assemble_transcript(uuid4())
    assert captured_session.opens == 1
    assert captured_session.commits == 1
    assert captured_session.row.assembled_transcript == out
    assert "first" in out and "second" in out


async def test_empty_source_set_still_persists_empty_cache(
    captured_session, sources_fn
):
    sources_fn.return_value = []
    out = await assembly.assemble_transcript(uuid4())
    assert out == ""
    # Empty cache still gets committed so a removed-last-source case clears
    # the stale value left behind.
    assert captured_session.commits == 1
    assert captured_session.row.assembled_transcript == ""


async def test_failure_inside_block_skips_commit(monkeypatch, captured_session):
    boom = AsyncMock(side_effect=RuntimeError("listing exploded"))
    monkeypatch.setattr(assembly, "list_sources", boom)
    with pytest.raises(RuntimeError, match="listing exploded"):
        await assembly.assemble_transcript(uuid4())
    assert captured_session.opens == 1
    assert captured_session.commits == 0
    # The row attribute the writer would have touched stays untouched.
    assert captured_session.row.assembled_transcript is None
