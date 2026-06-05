"""Delta extraction: turn a new transcript into a structured graph diff.

This is the update-time companion to `workflow_extraction`. Where the
original extraction reads a transcript with no prior graph, delta
extraction reads a transcript WITH the existing graph as context, and
must respect a declared scope: which steps the operator says this update
touches. The output is a DeltaResult, applied to the graph by the typed
`apply_delta` helper in this same skill package.

The API layer never calls OpenAI directly and never mutates the graph;
it calls `extract_delta` then `apply_delta`, in that order.
"""
from __future__ import annotations

import json

from app.config import get_settings
from app.models.graph import Workflow
from app.services.openai_client import get_openai_client

from .types import DeltaResult, DeltaScope


DELTA_PROMPT = """
You are updating an already structured workflow graph with new information
the operator has just captured.

You are given:
1. The current graph as JSON. This is the source of truth for everything
   that has not changed.
2. A new transcript carrying only the information about what changed,
   assembled from one or more new sources.
3. A declared scope that constrains what you may touch.

Your job:

- Read the new transcript with the current graph as context.
- Decide which existing steps the new transcript revises, which steps it
  adds, and which it makes obsolete.
- Emit a structured DeltaResult.

Scope rules (non-negotiable):
- scope = "step": only the step ids listed in step_ids may be modified
  or removed. You may still add brand new steps if the transcript clearly
  introduces them, but the new steps must reference the in-scope steps as
  their context (e.g. inserting a sub-step between two scoped steps).
- scope = "section": you may modify any step ids in step_ids, plus
  immediate neighbours required for consistency (e.g. a decision rule
  pointing into the section).
- scope = "full": you may modify anything. Use this sparingly. Prefer
  conservative edits even when the scope is full.

Gap rules:
- Surface contradictions between the new transcript and the existing
  graph as gaps with severity "critical", describing both accounts in the
  gap description so the clarification stage can resolve.
- Do not re-emit gaps that already exist and are still valid.

Output rules:
- modified_steps: include the FULL updated Step, not a patch. The apply
  layer replaces the whole step by id.
- added_steps: complete new Steps with stable ids.
- removed_step_ids: ids only.
- change_summary: one or two sentences in plain language, no markdown,
  no bullet points. This goes into the version timeline.

Current graph (JSON):
{graph_json}

Scope: {scope_json}

New transcript:
{transcript}
"""


async def extract_delta(
    workflow: Workflow,
    new_transcript: str,
    scope: DeltaScope,
) -> DeltaResult:
    client = get_openai_client()
    settings = get_settings()
    graph_payload = workflow.model_dump(mode="json")
    response = await client.responses.parse(
        model=settings.openai_extraction_model,
        input=DELTA_PROMPT.format(
            graph_json=json.dumps(graph_payload, indent=2),
            scope_json=json.dumps(scope.model_dump(mode="json"), indent=2),
            transcript=new_transcript,
        ),
        text_format=DeltaResult,
    )
    return response.output_parsed
