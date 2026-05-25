# diagram_review

Surfaces the canonical `Workflow` graph as a Mermaid flowchart for human review, and applies free-text edit instructions by routing them through the existing typed-patch pipeline.

## Public surface

```python
from app.skills.diagram_review import to_mermaid, apply_user_edit

mermaid: str = to_mermaid(workflow)                   # deterministic, no LLM
turn: ClarificationTurn = await apply_user_edit(
    workflow_id, instruction="rename step_5 to ...", step_id="step_5"
)
```

Called by `GET /workflows/{id}/diagram`, `POST /workflows/{id}/review/edit`, `POST /workflows/{id}/review/approve` ([api/review.py](../../api/review.py)).

## Why this is its own skill (and not part of sop_rendering)

`sop_rendering` produces the final human-readable deliverable from an *approved* graph. `diagram_review` is the **editing surface during review** — different inputs, different output (Mermaid vs SOP markdown), and includes an LLM-driven mutation path that rendering must never have.

## to_mermaid: graph → diagram

Deterministic, no model call. Walks `workflow.steps` in order:

- One Mermaid node per step, labeled with `Step {order}: {title}` plus the approver if set.
- **Terminal steps** (where `step.terminal == True`) are rendered with a stadium/pill shape `(["..."])` and emit **no outgoing edge** — they end the path.
- For steps with decision rules: solid edge per rule to `then_step_id` labeled with the condition, plus an "else" edge to `else_step_id` if present.
- For non-terminal steps without decision rules: a **dashed** edge `-. implicit .->` to the next step in order. The dashed style flags this as the renderer's guess, not data from the graph. Reviewers should resolve it by either setting `terminal=true` on the step or adding an explicit decision rule.
- Any step ID referenced by a decision rule but missing from the graph is rendered as a red "MISSING" node so reviewers can spot bad references at a glance.

Quote and backtick characters in labels are escaped (replaced with single quotes) to keep Mermaid parsers happy.

## apply_user_edit: free-text instruction → typed patch → applied

Single LLM call. The model reads the current graph, the user's instruction, and an optional `step_id` focus, then returns a `ClarificationTurn` (the **same** schema used by clarification — deliberate reuse). The turn is then routed through `workflow_clarification.apply.apply_turn`, which is the only code path that mutates the graph.

The system prompt forbids the model from:
- Inventing step IDs
- Producing patches the instruction doesn't clearly ask for
- Treating this as a dialogue (no `next_question`)

If the instruction can't be satisfied (ambiguous, references a field not in the schema), the model is instructed to emit empty patches and explain why in `finalize_reason` rather than guess.

## Provider

Uses the same client and model as clarification (`get_clarification_client_and_model()`). Switching providers in `.env.local` affects both. This is intentional — the schema is identical so model behavior should be consistent across the two surfaces.

## Known failure modes

1. **Step ID hallucination.** Mitigated by the prompt and by `apply_turn`'s defensive validation (unknown step IDs become skipped warnings, not crashes). The API surfaces those warnings in the response so the frontend can show "I tried to apply X but step Y doesn't exist."
2. **Structural changes the schema can't express.** Adding a new step or deleting one isn't currently in `ClarificationTurn`. The model is told to explain in `finalize_reason` if asked to do something out of scope. If users routinely ask for structural changes, extend `ClarificationTurn` with `new_steps` / `removed_step_ids` fields and update `apply_turn`.
3. **Mermaid syntax errors from unusual labels.** Most special characters are safe inside quoted Mermaid labels; quotes and backticks are stripped. If a step title contains very unusual characters (control codes, weird unicode), Mermaid might still complain — fall back to logging the produced syntax for debugging.

## When extending

- **Support adding/deleting steps**: extend `ClarificationTurn` and `apply_turn`. Already discussed in [workflow_clarification/SKILL.md](../workflow_clarification/SKILL.md).
- **Alternative diagram formats** (e.g. React Flow JSON): add a second renderer alongside `to_mermaid`. Keep them in this skill — both are "diagram representations of the graph."
- **Edit history**: today, edits apply but aren't logged. If you want an audit trail, log the `ClarificationTurn` returned by `apply_user_edit` into a new `workflow_edits` table.
