# sop_rendering

Renders a finalized `Workflow` graph into a markdown SOP document for human readers.

## Public surface

```python
from app.skills.sop_rendering import render_sop

markdown: str = await render_sop(workflow)
```

Called by `GET /workflows/{id}/sop` and `/sop/download` ([api/sop.py](../../api/sop.py)).

## Model

`gpt-5` (configurable via `OPENAI_RENDER_MODEL`). Plain `client.responses.create` — no structured output, output is freeform markdown.

## Why a model and not a template

A template would be cheaper and deterministic, but the graph contains free-text fields (`description`, `notes`, `decision_rules.condition`) that need to be woven into prose. The model:

- Rephrases narration into imperative SOP voice ("Open T2 Flex and search by citation number." not "I open T2 Flex...")
- Inlines decision rules as natural English ("If the appeal is over $200, proceed to Step 7. Otherwise, continue.")
- Surfaces unresolved gaps as `> **TODO:**` callouts at the right step

A template can't do those without a second LLM pass anyway.

## Prompt contract (see `skill.py`)

Output structure is fixed:

```
# {name}
**Unit:** {unit}
## Overview
## Roles
## Procedure
### Step N: {title}
## Path Summary
## Open Questions
```

Rationale for each section:
- **Roles** — surfaces every approver in the graph, plus the implied operator role and any system that acts autonomously (e.g. T2 Flex sending emails). Reviewers consistently complained that ownership was unclear; this section answers "who does what" before the procedure starts.
- **Procedure** — the numbered step body. Same step format as before (inputs, outputs, tools, approver, decision rules, notes).
- **Path Summary** — every terminal path through the graph as a bullet list (e.g. `Late appeal: Step 1 -> 2 -> 3 -> 13`). Forces the renderer to verify every branch lands on a closing step. Orphaned paths get logged in Open Questions.
- **Open Questions** — *all* TODOs land here, not inline in steps. Includes unresolved `workflow.gaps` and any TODOs the renderer generated itself (e.g. inferred operator role, orphaned paths).

Rules baked into the prompt:
- **Sentence case throughout.** No ALL CAPS, no Title Case headings.
- **Imperative mood** in step bodies.
- **Never inline a TODO in a step.** All open questions go in the Open Questions section at the end. This fixed a usability complaint: inline TODOs interrupted the procedure flow.
- **Don't invent details.** The only inference allowed is the operator role (and the renderer must flag it as a TODO if it inferred).
- **Markdown only, no HTML.** The frontend renders via a markdown component; HTML would leak through unstyled.

## Inputs

The full `Workflow` is dumped to JSON via `workflow.model_dump_json(indent=2)` and inlined into the prompt. This means **any field on `Step` / `Workflow` is visible to the renderer**, even ones the template doesn't explicitly mention. Add fields without updating this prompt and they'll appear as the model sees fit — usually fine, sometimes ugly. If a new field needs specific formatting, update the prompt.

## Known failure modes

1. **Long workflows get truncated.** A 15-step graph with rich descriptions can produce a long markdown response. No streaming, no chunking — if you hit the model's output limit, the SOP gets cut off mid-step. Solution if it bites: split rendering by section.
2. **Decision rule prose drifts.** The prompt template suggests "If [condition], proceed to Step N. Otherwise, continue." Model sometimes deviates. Low-impact.
3. **No idempotency.** Each `GET /sop` re-renders — same input may produce slightly different markdown. Acceptable for now since the user-facing flow is "render once, download."

## No caching — by design (for now)

The endpoint re-renders every GET. Reasons:
- The graph can mutate (a future "back to clarify" flow would invalidate a cache).
- MVP scale doesn't justify a cache table.

If you add caching, key on the graph hash, not the workflow ID. Bust on any `save_workflow` call.

## When extending

- New section in the SOP → update the prompt structure block.
- Localization → not currently supported. Would mean a `locale` param threaded through the API → skill → prompt.
- Streaming responses → switch to `client.responses.stream` and surface chunks through a server-sent-events endpoint. Frontend `Sop.tsx` would need to consume incrementally.
