import json

from app.config import get_settings
from app.models.graph import Workflow
from app.services.openai_client import get_openai_client


RENDER_PROMPT = """
You are generating a Standard Operating Procedure (SOP) document from a
structured workflow graph. The SOP will be read by employees as the
authoritative guide for how this work is done.

The graph has already been clarified — every gap was either resolved or
explicitly accepted by the workflow owner. Treat the graph as the final
authoritative spec. Do not flag uncertainty, do not add TODOs, do not
add an Open Questions section, and do not surface unresolved details.

Produce a clear, professional SOP in markdown with EXACTLY this structure
and section order:

# {workflow_name}

**Unit:** {workflow_unit}

## Overview

[1-2 paragraph description of what this workflow accomplishes and when
it's triggered, derived from workflow.description and source_transcript.]

## Roles

[Collect every distinct approver across the graph plus the implied
operator role. Render as a bulleted list:
- **Approver(s):** comma-separated list of unique approver values found
  in the graph (e.g. "Assistant director, Campus parking committee").
  Omit this bullet if no step has an approver.
- **Operator:** the role performing non-approver steps. Infer from
  workflow.unit and step content if the graph doesn't name one
  explicitly (e.g. "Appeals staff", "Citations officer"). Pick a clean
  job title; do not flag this as uncertain.
- **Systems acting autonomously:** any tool that the graph describes as
  sending notifications, processing refunds, etc., on its own (e.g.
  "T2 Flex (system-generated emails and refund processing)"). Omit
  if not applicable.]

## Procedure

[Numbered steps in graph order. For each step:
- ### Step N: {{step.title}}
- Description in prose, imperative mood.
- If inputs exist, render exactly:
  **Required inputs:**
  - [input]
  - [input]
- If outputs exist, render exactly:
  **Produces:**
  - [output]
  - [output]
- If tools exist, render exactly:
  **Tools:** Tool A, Tool B
- If approver is set, render exactly:
  **Approver:** [approver]
- Decision rules rendered as "If [condition], proceed to Step N. Otherwise, continue."
- Notes called out as a "**Note:**" callout if present.]

## Path Summary

[Enumerate every distinct terminal path through the graph as a bullet
list. A path is a sequence of step numbers from the entry step to a
closing/finalization step, including which branch of each decision was
taken. Use the decision_rules to walk branches. Example shape:
- Late appeal: Step 1 -> Step 2 -> Step 3 -> Step 13
- Closed lot: Step 1 -> Step 2 -> Step 4 -> Step 5 -> Step 10 -> Step 13
- ...]

Rules:
- Sentence case throughout, no ALL CAPS, no Title Case headings.
- Imperative mood in step descriptions.
- NEVER emit an "Open Questions" section, a TODO callout, a "please confirm"
  note, or any other prompt for follow-up. The SOP is the final deliverable.
- NEVER inline placeholder text like "[TBD]", "TBD", "TODO", or "?" in any
  field value. If a value is genuinely missing from the graph, omit that line
  rather than render a placeholder.
- Never write multiline field values as bare lines. Any multiline value
  must be a proper Markdown bullet list under a bold label.
- Don't invent details not in the graph. The only inference allowed is
  the operator role in the Roles section.
- Markdown only, no HTML.

Workflow graph JSON (clarified, final):
{workflow_json}
"""


async def render_sop(workflow: Workflow) -> str:
    client = get_openai_client()
    settings = get_settings()
    # Strip gaps before serialization so the renderer can't surface them. The
    # graph has already been clarified — gaps are review-time metadata, not
    # part of the published SOP.
    graph_for_rendering = workflow.model_dump(mode="json")
    graph_for_rendering.pop("gaps", None)
    response = await client.responses.create(
        model=settings.openai_render_model,
        input=RENDER_PROMPT.format(
            workflow_name=workflow.name,
            workflow_unit=workflow.unit,
            workflow_json=json.dumps(graph_for_rendering, indent=2),
        ),
    )
    return response.output_text
