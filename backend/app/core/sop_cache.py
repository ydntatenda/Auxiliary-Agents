"""SOP cache coordinator.

Sits between the API layer and the SOP renderer skill so every endpoint
that needs SOP markdown goes through one place. Reads the cached
markdown off the workflow row when the graph hasn't changed since the
last render; otherwise calls the skill, writes the result back to the
row, and returns the fresh markdown. The cache write happens on the
session the caller already holds, so the renderer's output and the
cache update commit together.

This module never calls the LLM directly. It calls `render_sop`, which
is the public surface of the SOP rendering skill.
"""
from __future__ import annotations

from app.models.db import WorkflowRow
from app.models.graph import Workflow
from app.skills.sop_rendering import render_sop, sop_graph_hash


class SopRenderError(ValueError):
    """Raised when a workflow has no graph to render an SOP from."""


async def render_or_load_sop(row: WorkflowRow) -> tuple[str, bool]:
    """Return (markdown, cache_hit) for a workflow row.

    Mutates `row.sop_cache` and `row.sop_cache_graph_hash` when the cache
    is refreshed, but does NOT commit. The caller already holds the
    session and is expected to commit after any other coordinated
    mutations land, which keeps the renderer's output atomic with
    whatever surrounding work the endpoint is doing.
    """
    if row.graph is None:
        raise SopRenderError(
            f"Workflow {row.id} has no graph to render an SOP from."
        )

    workflow = Workflow.model_validate(row.graph)
    current_hash = sop_graph_hash(workflow)

    if row.sop_cache and row.sop_cache_graph_hash == current_hash:
        return row.sop_cache, True

    markdown = await render_sop(workflow)
    row.sop_cache = markdown
    row.sop_cache_graph_hash = current_hash
    return markdown, False
