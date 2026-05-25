"""Diagram-review skill.

Two responsibilities:
  1. Render the canonical Workflow graph as Mermaid flowchart syntax (deterministic, no LLM).
  2. Apply a free-text user edit instruction by translating it into a typed
     ClarificationTurn and routing it through the existing apply_turn pipeline.

The graph remains the source of truth; this skill is the editing surface during review.
"""
import json
import logging
import re

from app.db.workflows import load_workflow
from app.models.graph import Workflow
from app.skills.workflow_clarification.apply import apply_turn, get_clarification_provider
from app.skills.workflow_clarification.skill import (
    RESPONSE_FORMAT,
    _normalize_shorthand,
    _strip_code_fence,
)
from app.skills.workflow_clarification.types import ClarificationTurn

logger = logging.getLogger(__name__)

_LABEL_UNSAFE_RE = re.compile(r'["`]')


def _escape_mermaid_label(text: str) -> str:
    """Mermaid node labels are wrapped in double quotes; escape internal quotes
    and backticks. Keep it minimal — Mermaid is permissive with most characters
    inside quoted labels."""
    return _LABEL_UNSAFE_RE.sub("'", text)


def _node_label(step) -> str:
    """Short label for a node: title + role/approver hint."""
    parts = [f"Step {step.order}: {step.title}"]
    if step.approver:
        parts.append(f"Approver: {step.approver}")
    return _escape_mermaid_label("\\n".join(parts))


def to_mermaid(workflow: Workflow) -> str:
    """Render a Workflow as Mermaid flowchart syntax.

    Rules:
      - Top-down flowchart.
      - One node per step, labeled with order + title (+ approver if set).
      - For each step, edges out are:
          * For every decision rule: an edge to then_step_id labeled with the
            condition; if else_step_id is set, also an edge to else_step_id
            labeled "else".
          * If the step has no decision rules and is not the last step,
            an unlabeled edge to the next step in order.
      - Steps referenced by decision rules but missing from the graph are
        rendered as warning nodes so reviewers can spot bad references.
    """
    if not workflow.steps:
        return "flowchart TD\n    empty[\"No steps yet\"]"

    sorted_steps = sorted(workflow.steps, key=lambda s: s.order)
    known_ids = {step.id for step in sorted_steps}
    lines = ["flowchart TD"]

    for step in sorted_steps:
        label = _node_label(step)
        if step.terminal:
            # Stadium shape signals an end-state node.
            lines.append(f'    {step.id}(["{label}"])')
        else:
            lines.append(f'    {step.id}["{label}"]')

    referenced_missing: set[str] = set()
    for index, step in enumerate(sorted_steps):
        if step.decision_rules:
            for rule in step.decision_rules:
                if rule.then_step_id not in known_ids:
                    referenced_missing.add(rule.then_step_id)
                if rule.else_step_id is not None and rule.else_step_id not in known_ids:
                    referenced_missing.add(rule.else_step_id)
                condition = _escape_mermaid_label(rule.condition)
                lines.append(f'    {step.id} -- "{condition}" --> {rule.then_step_id}')
                if rule.else_step_id is not None:
                    lines.append(f'    {step.id} -- "else" --> {rule.else_step_id}')
        elif step.terminal:
            # Terminal steps end the path — no outgoing edge.
            continue
        elif index < len(sorted_steps) - 1:
            next_step = sorted_steps[index + 1]
            # Dashed edge = implicit "next step in order" guess by the renderer.
            # Solid edges only appear when an explicit decision_rule routes the flow.
            lines.append(f"    {step.id} -. implicit .-> {next_step.id}")

    for missing_id in sorted(referenced_missing):
        label = _escape_mermaid_label(f"MISSING: {missing_id}")
        lines.append(f'    {missing_id}["{label}"]:::missing')

    if referenced_missing:
        lines.append("    classDef missing fill:#fee,stroke:#c33,color:#c33;")

    return "\n".join(lines) + "\n"


EDIT_SYSTEM_PROMPT = """\
You are applying a user's free-text edit instruction to a workflow graph that
the user is reviewing as a diagram.

Translate the instruction into the typed patches defined by the response_format
schema. Use the same field literals as the clarification flow:
  - scalar_patches.field: "approver", "description", "notes", "title"
  - list_appends.field: "inputs", "outputs", "tools_used"
  - step_flags.field: "terminal" (value is boolean)

Use step_flags when the user marks a step as a terminal/end-state (e.g.
"mark step_5 as terminal", "step_3 is the end of the deny path"). Set
value=true. To un-mark a terminal, set value=false.

Constraints:
  - Only emit patches for changes the instruction clearly asks for.
  - Never invent step IDs. Only reference step IDs that exist in the provided graph.
  - For decision rules, both then_step_id and else_step_id must reference existing steps.
  - This is a one-shot edit, not a dialogue. Always set next_question = null and
    finalize_reason to a one-line summary of what you changed.
  - If the instruction is ambiguous or cannot be satisfied with the available
    field literals, emit empty patch arrays and set finalize_reason to explain
    what's missing or unclear. Do not guess.
"""


async def apply_user_edit(
    workflow_id: str,
    instruction: str,
    step_id: str | None = None,
) -> ClarificationTurn:
    """Translate a free-text edit instruction into a typed patch and apply it.

    Returns the ClarificationTurn produced by the model (after application).
    finalize_reason will summarize what changed or explain why nothing did.
    """
    workflow = await load_workflow(workflow_id)
    graph_snapshot = {
        "name": workflow.name,
        "unit": workflow.unit,
        "steps": [
            {
                "id": step.id,
                "order": step.order,
                "title": step.title,
                "description": step.description,
                "approver": step.approver,
                "inputs": step.inputs,
                "outputs": step.outputs,
                "tools_used": step.tools_used,
                "notes": step.notes,
                "terminal": step.terminal,
                "decision_rules": [
                    {
                        "condition": rule.condition,
                        "then_step_id": rule.then_step_id,
                        "else_step_id": rule.else_step_id,
                    }
                    for rule in step.decision_rules
                ],
            }
            for step in workflow.steps
        ],
    }

    focus_line = f"Focus step (the user is hovering on this one): {step_id}\n" if step_id else ""
    user_prompt = f"""\
Current workflow graph:
{json.dumps(graph_snapshot, indent=2)}

{focus_line}User's edit instruction:
{instruction}

Produce a ClarificationTurn that applies this edit. Set next_question = null and
finalize_reason to a one-line summary.
"""

    client, model, provider = get_clarification_provider()
    messages = [
        {"role": "system", "content": EDIT_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    if provider == "openai":
        completion = await client.chat.completions.parse(
            model=model,
            messages=messages,
            response_format=ClarificationTurn,
        )
        chat_message = completion.choices[0].message
        refusal = getattr(chat_message, "refusal", None)
        if refusal:
            logger.error("Edit model refused: %s", refusal)
            raise RuntimeError(f"Edit model refused: {refusal}")
        turn = chat_message.parsed
        if turn is None:
            raise RuntimeError("Edit model returned no parsed output")
    else:
        completion = await client.chat.completions.create(
            model=model,
            messages=messages,
            response_format=RESPONSE_FORMAT,
        )
        chat_message = completion.choices[0].message
        refusal = getattr(chat_message, "refusal", None)
        if refusal:
            logger.error("Edit model refused: %s", refusal)
            raise RuntimeError(f"Edit model refused: {refusal}")
        raw = _strip_code_fence(chat_message.content or "")
        if not raw:
            raise RuntimeError("Edit model returned empty content")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error("Edit model returned invalid JSON. Raw content: %s", raw)
            raise RuntimeError(f"Edit model returned invalid JSON: {exc}") from exc
        normalized = _normalize_shorthand(data)
        if normalized != data:
            logger.warning("Edit model emitted schema shorthand; normalized before validation.")
        try:
            turn = ClarificationTurn.model_validate(normalized)
        except Exception as exc:
            logger.error("Failed to validate edit turn. Raw content: %s", raw)
            raise RuntimeError(f"Failed to parse edit turn: {exc}") from exc

    warnings = await apply_turn(workflow_id, turn)
    if warnings:
        logger.warning("apply_user_edit warnings for workflow %s: %s", workflow_id, warnings)

    return turn
