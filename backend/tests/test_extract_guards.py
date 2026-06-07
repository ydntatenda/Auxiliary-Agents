"""Tests for the 'extraction never clobbers operator-set identity' guard.

We mock `extract_workflow` and `extract_delta` so the test does not call
OpenAI, and assert that the workflow's name and unit on the saved Pydantic
graph always match the row's values, regardless of what the LLM returned.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.api import workflows
from app.models.graph import Gap, Step, Workflow
from app.skills.delta_extraction.types import DeltaResult


def _row(
    *,
    name: str = "Citation appeals",
    unit: str = "P&T",
    description: str | None = None,
    graph: dict | None = None,
    assembled: str = "operator described the workflow",
):
    return SimpleNamespace(
        id=uuid4(),
        name=name,
        unit=unit,
        description=description,
        graph=graph,
        version=1,
        assembled_transcript=assembled,
        status="transcribed",
        created_at=None,
    )


def _llm_workflow(
    *,
    name: str,
    unit: str,
    description: str = "LLM guess at the description.",
) -> Workflow:
    return Workflow(
        name=name,
        description=description,
        unit=unit,
        source_modality="text",
        source_transcript="...",
        steps=[Step(id="s1", order=1, title="Do thing", description="d")],
        gaps=[],
    )


async def test_extract_keeps_operator_name_and_unit(monkeypatch) -> None:
    row = _row(name="Citation appeals", unit="P&T")
    monkeypatch.setattr(workflows, "require_workflow_row", AsyncMock(return_value=row))

    llm_out = _llm_workflow(name="LLM Renamed Process", unit="LLM Department")
    monkeypatch.setattr(workflows, "extract_workflow", AsyncMock(return_value=llm_out))

    saved: dict = {}

    async def fake_save(workflow, status=None):
        saved["workflow"] = workflow
        saved["status"] = status

    monkeypatch.setattr(workflows, "save_workflow", fake_save)
    monkeypatch.setattr(workflows, "write_text_artifact", lambda *a, **k: None)
    monkeypatch.setattr(workflows, "write_json_artifact", lambda *a, **k: None)
    monkeypatch.setattr(workflows, "embed_workflow_task", AsyncMock())

    # The description-mirror block opens its own session; fake it.
    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, *args, **kwargs):
            return row

        async def commit(self):
            return None

    monkeypatch.setattr(workflows, "async_session", lambda: FakeSession())

    background = SimpleNamespace(add_task=lambda *a, **k: None)
    session = SimpleNamespace(commit=AsyncMock())
    await workflows.extract("wf", background, db=session)

    assert saved["workflow"].name == "Citation appeals"
    assert saved["workflow"].unit == "P&T"


async def test_extract_does_not_overwrite_existing_description(monkeypatch) -> None:
    """If the row already carries a description (set via PATCH), extraction
    must not silently replace it with the LLM's guess."""
    row = _row(description="Owner set this explicitly.")
    monkeypatch.setattr(workflows, "require_workflow_row", AsyncMock(return_value=row))

    llm_out = _llm_workflow(
        name="Citation appeals",
        unit="P&T",
        description="The LLM would describe it like this.",
    )
    monkeypatch.setattr(workflows, "extract_workflow", AsyncMock(return_value=llm_out))
    monkeypatch.setattr(workflows, "save_workflow", AsyncMock())
    monkeypatch.setattr(workflows, "write_text_artifact", lambda *a, **k: None)
    monkeypatch.setattr(workflows, "write_json_artifact", lambda *a, **k: None)
    monkeypatch.setattr(workflows, "embed_workflow_task", AsyncMock())

    captured_descriptions: list[str | None] = []

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, *args, **kwargs):
            return row

        async def commit(self):
            captured_descriptions.append(row.description)
            return None

    monkeypatch.setattr(workflows, "async_session", lambda: FakeSession())

    background = SimpleNamespace(add_task=lambda *a, **k: None)
    session = SimpleNamespace(commit=AsyncMock())
    await workflows.extract("wf", background, db=session)

    assert row.description == "Owner set this explicitly."


async def test_extract_populates_description_when_row_has_none(monkeypatch) -> None:
    row = _row(description=None)
    monkeypatch.setattr(workflows, "require_workflow_row", AsyncMock(return_value=row))

    llm_out = _llm_workflow(
        name="Citation appeals", unit="P&T", description="The LLM said."
    )
    monkeypatch.setattr(workflows, "extract_workflow", AsyncMock(return_value=llm_out))
    monkeypatch.setattr(workflows, "save_workflow", AsyncMock())
    monkeypatch.setattr(workflows, "write_text_artifact", lambda *a, **k: None)
    monkeypatch.setattr(workflows, "write_json_artifact", lambda *a, **k: None)
    monkeypatch.setattr(workflows, "embed_workflow_task", AsyncMock())

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, *args, **kwargs):
            return row

        async def commit(self):
            return None

    monkeypatch.setattr(workflows, "async_session", lambda: FakeSession())

    background = SimpleNamespace(add_task=lambda *a, **k: None)
    session = SimpleNamespace(commit=AsyncMock())
    await workflows.extract("wf", background, db=session)

    assert row.description == "The LLM said."


async def test_delta_extract_clamps_name_and_unit(monkeypatch) -> None:
    """The delta path must also force row.name / row.unit onto the merged
    graph, defending against an existing graph that drifted from the row
    after a PATCH or a misbehaving prior extraction."""
    existing_graph = Workflow(
        name="Stale graph name",
        description="x",
        unit="Stale unit",
        source_modality="text",
        source_transcript="...",
        steps=[Step(id="s1", order=1, title="t", description="d")],
        gaps=[],
    ).model_dump(mode="json")
    row = _row(graph=existing_graph)
    monkeypatch.setattr(workflows, "require_workflow_row", AsyncMock(return_value=row))
    monkeypatch.setattr(
        workflows,
        "extract_delta",
        AsyncMock(return_value=DeltaResult(change_summary="noop")),
    )

    saved: dict = {}

    async def fake_save(workflow, status=None):
        saved["workflow"] = workflow

    monkeypatch.setattr(workflows, "save_workflow", fake_save)
    monkeypatch.setattr(workflows, "write_json_artifact", lambda *a, **k: None)
    monkeypatch.setattr(workflows, "embed_workflow_task", AsyncMock())

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, *args, **kwargs):
            return row

        async def commit(self):
            return None

    monkeypatch.setattr(workflows, "async_session", lambda: FakeSession())

    payload = workflows.DeltaExtractPayload(
        scope="full", step_ids=None, change_description=None
    )
    background = SimpleNamespace(add_task=lambda *a, **k: None)
    session = SimpleNamespace(commit=AsyncMock())
    await workflows.delta_extract("wf", payload, background, db=session)

    assert saved["workflow"].name == "Citation appeals"
    assert saved["workflow"].unit == "P&T"
