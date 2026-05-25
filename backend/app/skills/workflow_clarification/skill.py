import json
import logging
import re

from app.db.workflows import load_workflow

from .apply import apply_turn, get_clarification_provider, list_unresolved_gaps
from .types import ClarificationMessage, ClarificationResult, ClarificationTurn

logger = logging.getLogger(__name__)

_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*\n?(.*?)\n?```\s*$", re.DOTALL | re.IGNORECASE)


def _strip_code_fence(text: str) -> str:
    """Some providers wrap JSON in ```json ... ``` even when a JSON response_format is set.
    Strip the fence if present; return text unchanged otherwise."""
    if not text:
        return text
    match = _FENCE_RE.match(text)
    if match:
        return match.group(1).strip()
    return text.strip()


_SCALAR_FIELDS_NORMALIZE = {"approver", "description", "notes", "title"}
_LIST_FIELDS_NORMALIZE = {"inputs", "outputs", "tools_used"}
_BOOL_FIELDS_NORMALIZE = {"terminal"}

# Known shorthand key aliases models use. Map from alias -> canonical name.
# A rename only fires when the canonical key is NOT already present.
_STEP_ID_ALIASES = {
    "source_step_id": "step_id",
    "from_step_id": "step_id",
}


def _rename_keys(item, aliases: dict[str, str]):
    """Rename keys in a dict if the canonical key isn't already present.
    Idempotent for already-canonical items."""
    if not isinstance(item, dict):
        return item
    for old_key, new_key in aliases.items():
        if old_key in item and new_key not in item:
            item[new_key] = item.pop(old_key)
    return item


def _normalize_patch_shorthand(item, allowed_fields: set[str]):
    """Convert {step_id: X, <field_name>: Y} shorthand to {step_id, field, value}.

    Some models (notably non-OpenAI ones via OpenRouter) ignore the schema and
    use the field name as a key. If the item already matches the canonical
    shape (has 'field' and 'value'), it's returned unchanged.
    """
    if not isinstance(item, dict):
        return item
    if "field" in item and "value" in item:
        return item
    step_id = item.get("step_id")
    candidates = [k for k in item.keys() if k != "step_id" and k in allowed_fields]
    if step_id and len(candidates) == 1:
        field = candidates[0]
        return {"step_id": step_id, "field": field, "value": item[field]}
    return item


def _normalize_resolved_gap(item):
    """Convert bare gap_id strings into {gap_id, resolution} objects.

    Some models emit `resolved_gaps: ["gap_1"]` instead of the schema shape.
    """
    if isinstance(item, str):
        return {"gap_id": item, "resolution": "(no resolution text provided)"}
    return item


def _normalize_shorthand(data: dict) -> dict:
    """Rewrite common shorthand shapes emitted by drifty models into canonical form.

    Idempotent: data already in canonical form passes through unchanged. Only
    transforms items where the shorthand pattern is unambiguous.
    """
    if not isinstance(data, dict):
        return data

    patches = data.get("scalar_patches")
    if isinstance(patches, list):
        data["scalar_patches"] = [
            _normalize_patch_shorthand(_rename_keys(p, _STEP_ID_ALIASES), _SCALAR_FIELDS_NORMALIZE)
            for p in patches
        ]

    appends = data.get("list_appends")
    if isinstance(appends, list):
        data["list_appends"] = [
            _normalize_patch_shorthand(_rename_keys(a, _STEP_ID_ALIASES), _LIST_FIELDS_NORMALIZE)
            for a in appends
        ]

    flags = data.get("step_flags")
    if isinstance(flags, list):
        data["step_flags"] = [
            _normalize_patch_shorthand(_rename_keys(f, _STEP_ID_ALIASES), _BOOL_FIELDS_NORMALIZE)
            for f in flags
        ]

    new_rules = data.get("new_decision_rules")
    if isinstance(new_rules, list):
        data["new_decision_rules"] = [_rename_keys(r, _STEP_ID_ALIASES) for r in new_rules]

    rule_edits = data.get("decision_rule_edits")
    if isinstance(rule_edits, list):
        data["decision_rule_edits"] = [_rename_keys(e, _STEP_ID_ALIASES) for e in rule_edits]

    removed_rules = data.get("removed_decision_rules")
    if isinstance(removed_rules, list):
        data["removed_decision_rules"] = [_rename_keys(r, _STEP_ID_ALIASES) for r in removed_rules]

    resolved = data.get("resolved_gaps")
    if isinstance(resolved, list):
        data["resolved_gaps"] = [_normalize_resolved_gap(r) for r in resolved]

    return data


def _strictify(schema: dict) -> dict:
    """Walk a Pydantic-generated JSON schema in place to make it OpenAI strict-mode compliant:
    every object gets `additionalProperties: false` and every property listed in `required`.
    Recurses into `properties`, `$defs`, array `items`, and `anyOf`.
    """
    if not isinstance(schema, dict):
        return schema
    if schema.get("type") == "object" and "properties" in schema:
        schema["additionalProperties"] = False
        schema["required"] = list(schema["properties"].keys())
    for value in schema.get("properties", {}).values():
        _strictify(value)
    for value in schema.get("$defs", {}).values():
        _strictify(value)
    if "items" in schema:
        _strictify(schema["items"])
    for option in schema.get("anyOf", []):
        _strictify(option)
    return schema


CLARIFICATION_TURN_SCHEMA = _strictify(ClarificationTurn.model_json_schema())
RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "ClarificationTurn",
        "strict": True,
        "schema": CLARIFICATION_TURN_SCHEMA,
    },
}

MAX_CLARIFICATION_QUESTIONS = 25

SYSTEM_PROMPT = """\
You are clarifying a workflow graph built from an employee's walkthrough of an
operational procedure. Your job each turn:

1. If the conversation history ends with a user answer, translate that answer
   into structured changes to the graph:
     - scalar_patches: set approver/description/notes/title on a step
     - list_appends: add an item to inputs/outputs/tools_used on a step
     - new_decision_rules: add a conditional branch between two existing steps
     - resolved_gaps: close every gap the user's answer addressed
2. Then decide what to do next:
     - To ask the next question, set next_question to one focused, anchored
       question about the next unresolved gap. Leave finalize_reason null.
     - To stop clarification, set next_question to null AND populate
       finalize_reason with a short explanation. Never write completion text
       into next_question.

Rules:
- Ask about EVERY unresolved gap. Do not stop just because the remaining gaps
  are minor — every gap should be asked and either resolved or explicitly
  acknowledged by the user.
- Severity order is for prioritization only, not for filtering: ask critical
  gaps first, then important, then minor. Do not skip minors.
- Stop (set next_question=null, populate finalize_reason) only when:
    * Every gap in the list is resolved, OR
    * The user explicitly asks to stop, OR
    * The question count has reached the cap.
- One question per turn. Never bundle.
- Don't ask about anything already present in the graph; check first.
- Don't invent step IDs. Only reference step IDs that exist in the provided graph.
- Use stable gap IDs from the gap list when populating resolved_gaps.
- Use only the field literals defined in the schema. Anything else is rejected.

Phrasing — make questions readable for non-technical users:
- When a question refers to a step, include the step's title alongside the ID
  so the user knows what you're asking about.
  - Good: "In step_6 (Evaluate violation type), if the appeal is under $50 but
    the reason isn't reasonable, what happens?"
  - Bad: "For step_6, what happens if the appeal is under $50?"
- When referring to another step in the same question, include both: "...forward
  to step_8 (Review escalated appeal)..."
- Don't pad — only include titles when the question would be hard to parse
  without them.

Output:
- Conform exactly to the JSON schema attached as the response_format.
- Exactly one of `next_question` and `finalize_reason` is non-null. The other is null.

Good question example:
  "You mentioned forwarding appeals over $200 — is that to the assistant
  director or to the manager?"
Bad question example:
  "Tell me more about approvals."
"""


def _format_history(history: list[ClarificationMessage]) -> str:
    if not history:
        return "No clarification history yet."
    lines = []
    for item in history:
        label = "Question" if item.role == "question" else "Answer"
        lines.append(f"{label}: {item.content}")
    return "\n".join(lines)


def _question_count(history: list[ClarificationMessage]) -> int:
    return sum(1 for item in history if item.role == "question")


def _serialize_graph_for_prompt(workflow) -> str:
    """Compact JSON of the workflow with only the fields the model needs."""
    payload = {
        "name": workflow.name,
        "unit": workflow.unit,
        "steps": [
            {
                "id": step.id,
                "title": step.title,
                "description": step.description,
                "inputs": step.inputs,
                "outputs": step.outputs,
                "tools_used": step.tools_used,
                "approver": step.approver,
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
    return json.dumps(payload, indent=2)


async def get_next_question(
    workflow_id: str,
    history: list[ClarificationMessage],
) -> ClarificationResult:
    question_count = _question_count(history)
    if question_count >= MAX_CLARIFICATION_QUESTIONS:
        return ClarificationResult(
            question=None,
            done=True,
            message=f"Clarification stopped after {MAX_CLARIFICATION_QUESTIONS} questions. The graph is ready for SOP rendering.",
        )

    workflow = await load_workflow(workflow_id)
    unresolved_gaps = await list_unresolved_gaps(workflow_id)

    user_prompt = f"""\
Workflow graph (current state):
{_serialize_graph_for_prompt(workflow)}

Unresolved gaps (sorted by severity):
{json.dumps(unresolved_gaps, indent=2)}

Conversation history:
{_format_history(history)}

Questions asked so far: {question_count} of {MAX_CLARIFICATION_QUESTIONS}.

Produce one ClarificationTurn.
"""

    client, model, provider = get_clarification_provider()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    if provider == "openai":
        # OpenAI native strict structured outputs: SDK auto-builds the strict schema
        # from the Pydantic class, sets strict=true (so the model is sampling-constrained
        # against the schema), and auto-validates the response. No drift, no normalizer.
        completion = await client.chat.completions.parse(
            model=model,
            messages=messages,
            response_format=ClarificationTurn,
        )
        chat_message = completion.choices[0].message
        refusal = getattr(chat_message, "refusal", None)
        if refusal:
            logger.error("Clarification model refused: %s", refusal)
            raise RuntimeError(f"Clarification model refused: {refusal}")
        turn = chat_message.parsed
        if turn is None:
            raise RuntimeError("Clarification model returned no parsed output")
    else:
        # OpenRouter / other providers: passthrough-mode strict schema, with manual
        # fence-strip + shorthand normalize + Pydantic validation as the safety net.
        completion = await client.chat.completions.create(
            model=model,
            messages=messages,
            response_format=RESPONSE_FORMAT,
        )
        chat_message = completion.choices[0].message
        refusal = getattr(chat_message, "refusal", None)
        if refusal:
            logger.error("Clarification model refused: %s", refusal)
            raise RuntimeError(f"Clarification model refused: {refusal}")
        raw = _strip_code_fence(chat_message.content or "")
        if not raw:
            raise RuntimeError("Clarification model returned empty content")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error("Clarification model returned invalid JSON. Raw content: %s", raw)
            raise RuntimeError(f"Clarification model returned invalid JSON: {exc}") from exc
        normalized = _normalize_shorthand(data)
        if normalized != data:
            logger.warning(
                "Clarification model emitted schema shorthand; normalized before validation."
            )
        try:
            turn = ClarificationTurn.model_validate(normalized)
        except Exception as exc:
            logger.error("Failed to validate clarification turn. Raw content: %s", raw)
            raise RuntimeError(f"Failed to parse clarification turn: {exc}") from exc

    warnings = await apply_turn(workflow_id, turn)
    if warnings:
        logger.warning("apply_turn warnings for workflow %s: %s", workflow_id, warnings)

    if turn.next_question:
        return ClarificationResult(question=turn.next_question, done=False)

    message = turn.finalize_reason or "Clarification complete."
    return ClarificationResult(question=None, done=True, message=message)
