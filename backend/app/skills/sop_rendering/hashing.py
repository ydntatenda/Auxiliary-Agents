"""Stable hash of the graph payload the SOP renderer actually reads.

Lives next to `render_sop` so the renderer's view of the workflow and
the cache key for that view stay in lock-step. If the renderer ever
starts paying attention to a new field or stops paying attention to one
it currently reads, this is the one place that changes.
"""
from __future__ import annotations

import hashlib
import json

from app.models.graph import Workflow


def sop_graph_hash(workflow: Workflow) -> str:
    """Return the SHA-256 hex of the workflow as the renderer sees it.

    `gaps` is stripped before hashing because the SOP renderer drops it
    before sending the graph to the LLM. Adding, removing, or resolving
    gaps therefore does not invalidate a cached render; any other graph
    change does.
    """
    payload = workflow.model_dump(mode="json")
    payload.pop("gaps", None)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
