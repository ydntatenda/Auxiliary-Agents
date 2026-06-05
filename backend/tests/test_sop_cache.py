"""Unit tests for the SOP cache key + cache coordinator.

These pin three things the cache contract depends on: the hash is
deterministic, the hash is gap-invariant by design, and the coordinator
serves the cached markdown when the hash matches while skipping the
renderer call entirely.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core import sop_cache
from app.core.sop_cache import SopRenderError, render_or_load_sop
from app.models.graph import Gap, Step, Workflow
from app.skills.sop_rendering import sop_graph_hash


def _workflow() -> Workflow:
    return Workflow(
        name="Citation appeals",
        description="Citizens appeal parking citations.",
        unit="Parking & Transportation",
        source_modality="text",
        source_transcript="...",
        steps=[
            Step(id="receive", order=1, title="Receive appeal", description="Intake"),
            Step(id="review", order=2, title="Review", description="Decide", terminal=True),
        ],
        gaps=[
            Gap(
                id="g1",
                step_id="review",
                description="Who approves?",
                severity="important",
            ),
        ],
    )


def _row(graph_dict: dict | None, *, sop_cache: str | None = None, hash_: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id="00000000-0000-0000-0000-000000000001",
        graph=graph_dict,
        sop_cache=sop_cache,
        sop_cache_graph_hash=hash_,
    )


def test_hash_is_deterministic_for_same_input() -> None:
    workflow = _workflow()
    first = sop_graph_hash(workflow)
    second = sop_graph_hash(workflow.model_copy(deep=True))
    assert first == second
    assert len(first) == 64  # SHA-256 hex


def test_hash_changes_when_a_step_changes() -> None:
    workflow = _workflow()
    before = sop_graph_hash(workflow)

    mutated = workflow.model_copy(deep=True)
    mutated.steps[0].title = "Receive appeal (revised)"
    assert sop_graph_hash(mutated) != before


def test_hash_changes_when_name_or_unit_changes() -> None:
    workflow = _workflow()
    base = sop_graph_hash(workflow)

    renamed = workflow.model_copy(update={"name": "Citation review process"})
    assert sop_graph_hash(renamed) != base

    re_unit = workflow.model_copy(update={"unit": "Compliance"})
    assert sop_graph_hash(re_unit) != base


def test_hash_is_gap_invariant() -> None:
    """Gap edits do not change the SOP output, so they must not bust the cache."""
    workflow = _workflow()
    base = sop_graph_hash(workflow)

    no_gaps = workflow.model_copy(update={"gaps": []})
    assert sop_graph_hash(no_gaps) == base

    resolved = workflow.model_copy(deep=True)
    resolved.gaps[0].resolved = True
    resolved.gaps[0].resolution = "Assistant director."
    assert sop_graph_hash(resolved) == base


async def test_render_or_load_raises_without_graph() -> None:
    row = _row(graph_dict=None)
    with pytest.raises(SopRenderError):
        await render_or_load_sop(row)


async def test_render_or_load_serves_cache_when_hash_matches(monkeypatch) -> None:
    workflow = _workflow()
    canonical_hash = sop_graph_hash(workflow)
    row = _row(
        graph_dict=workflow.model_dump(mode="json"),
        sop_cache="# Cached SOP\n\nbody here.",
        hash_=canonical_hash,
    )
    renderer = AsyncMock()
    monkeypatch.setattr(sop_cache, "render_sop", renderer)

    markdown, cache_hit = await render_or_load_sop(row)

    assert cache_hit is True
    assert markdown == "# Cached SOP\n\nbody here."
    renderer.assert_not_called()
    # Row fields stay put on a cache hit.
    assert row.sop_cache == "# Cached SOP\n\nbody here."
    assert row.sop_cache_graph_hash == canonical_hash


async def test_render_or_load_renders_and_writes_when_hash_misses(monkeypatch) -> None:
    workflow = _workflow()
    stale_hash = "0" * 64
    row = _row(
        graph_dict=workflow.model_dump(mode="json"),
        sop_cache="# Stale\n",
        hash_=stale_hash,
    )
    renderer = AsyncMock(return_value="# Fresh SOP\n")
    monkeypatch.setattr(sop_cache, "render_sop", renderer)

    markdown, cache_hit = await render_or_load_sop(row)

    assert cache_hit is False
    assert markdown == "# Fresh SOP\n"
    renderer.assert_awaited_once()
    # Row is updated, ready for the caller to commit.
    assert row.sop_cache == "# Fresh SOP\n"
    assert row.sop_cache_graph_hash == sop_graph_hash(workflow)
    assert row.sop_cache_graph_hash != stale_hash


async def test_render_or_load_renders_when_no_cache_exists(monkeypatch) -> None:
    workflow = _workflow()
    row = _row(graph_dict=workflow.model_dump(mode="json"))
    renderer = AsyncMock(return_value="# Brand new\n")
    monkeypatch.setattr(sop_cache, "render_sop", renderer)

    markdown, cache_hit = await render_or_load_sop(row)

    assert cache_hit is False
    assert markdown == "# Brand new\n"
    renderer.assert_awaited_once()
