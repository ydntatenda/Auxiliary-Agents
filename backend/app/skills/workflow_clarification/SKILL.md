# workflow_clarification

Multi-turn dialogue that closes gaps in a freshly extracted `Workflow` graph by asking the user targeted questions and patching the graph in-place.

## Public surface

```python
from app.skills.workflow_clarification import get_next_question, active_clarification_model

result: ClarificationResult = await get_next_question(workflow_id, history)
# result.question is the next question, or result.done=True with a message

info: dict = active_clarification_model()
# {"provider": "openai" | "openrouter", "model": "...", ...}
```

Called by `POST /workflows/{id}/clarify` and `.../clarify/answer` ([api/clarify.py](../../api/clarify.py)). `active_clarification_model()` is also surfaced through `/health` for debugging.

## Architecture: structured-output, not agent

One LLM call per turn. The model returns a typed `ClarificationTurn` (see [types.py](types.py)) whose Pydantic schema *is* the contract:

```python
class ClarificationTurn(BaseModel):
    scalar_patches: list[StepPatch]           # set approver/description/notes/title
    list_appends: list[StepListAppend]        # add to inputs/outputs/tools_used
    new_decision_rules: list[NewDecisionRule] # add a branch
    step_flags: list[StepFlag]                # set boolean fields (currently: terminal)
    resolved_gaps: list[GapResolution]        # close gaps the answer addressed
    next_question: str | None                  # null = stop
    finalize_reason: str | None                # required iff next_question is null
```

Backend code in [apply.py](apply.py) deterministically applies the mutations, validates step/gap existence, and persists the graph. The model never calls a tool — every effect is a data field that's either present or absent in the JSON.

### Why this replaced the previous agent design

The earlier version used the OpenAI Agents SDK with `@function_tool`s. Two repeated failure modes drove the rewrite:

1. **Prose finalize.** The model would emit text like "Clarification is complete..." as its final output instead of calling the `finalize_clarification` tool, so the controller couldn't detect termination. Reproduced on GPT-5 and on Kimi K2.6 via OpenRouter — confirming it's a property of chat models, not any specific provider.
2. **Skipped patches.** The model would answer the user's prior question conversationally but never call the patch/resolve tools, leaving the graph stale even as the conversation moved on.

Both failure modes are designed out by structured output: a missing patch is a missing JSON field, and termination is `next_question: None` — both directly observable.

Other wins:
- One LLM call per turn instead of up to 5 internal agent steps.
- Works identically on OpenAI and OpenRouter through `chat.completions.parse`.
- No `openai-agents` dependency (removed when the agent was deleted).
- No `ContextVar` finalize-signal hack.

## Provider toggle

`clarification_provider` in [config.py](../../config.py) chooses between OpenAI and OpenRouter at runtime. The same code path runs for both — `get_clarification_client_and_model()` in [apply.py](apply.py) returns the right `AsyncOpenAI` client and model slug.

| Setting | OpenAI default | OpenRouter |
|---|---|---|
| `clarification_provider` | `openai` | `openrouter` |
| Model setting | `openai_clarification_model` | `openrouter_clarification_model` |
| Default model | `gpt-5.4` | `moonshotai/kimi-k2.6` |
| Key required | `OPENAI_API_KEY` | `OPENROUTER_API_KEY` |

Switch by setting env vars in `.env.local`; no code change. Verify via `GET /health`.

## Question quality rules (in the system prompt)

- One question per turn — never bundle.
- Anchor questions to a specific step/field/approver/role/tool/edge case.
- Don't ask about fields already populated in the provided graph snapshot.
- Severity (`critical > important > minor`) drives prioritization, not filtering: every unresolved gap is asked, in severity order.

## Termination

`get_next_question` returns `done=True` when any of:
1. The model returns `next_question=None` with a `finalize_reason` (normal stop — every gap resolved or user explicitly asked to stop).
2. The question count in history hits `MAX_CLARIFICATION_QUESTIONS` (25). Backstop in [skill.py](skill.py) checked before the LLM call. The cap is a safety net, not a target — most workflows finalize earlier.
3. Model returns `next_question=None` *without* `finalize_reason` — treated as done with a generic "Clarification complete." message. Shouldn't happen if the prompt is followed.

## Validation and warnings

`apply_turn` is defensive: unknown step IDs, unknown gap IDs, or malformed fields are *skipped* and logged as warnings rather than crashing the turn. Whitelists for scalar (`approver/description/notes/title`) and list (`inputs/outputs/tools_used`) fields are enforced in code in addition to the Pydantic `Literal[...]` constraint, in case the model emits something off-schema.

## Known failure modes

1. **Strict JSON schema on non-OpenAI providers.** `chat.completions.parse` defaults to `strict=true` for OpenAI; OpenRouter forwards `response_format` to the underlying model. Kimi K2 supports JSON schema mode, but if you swap to a smaller model that doesn't, the call will fail. Surface as a `RuntimeError` from `get_next_question`.
2. **Refusals.** If `message.parsed` is `None` and `message.refusal` is set, the model declined to produce output. `skill.py` raises a `RuntimeError` with the refusal text rather than silently failing.
3. **Question count drift.** The 8-question cap is checked from `history` length, which is server-persisted. If the frontend stops calling `/answer`, the cap doesn't auto-fire — the next call simply enforces it.

## When extending

- **New patchable field on a Step**: add it to `models/graph.py`, then add it to the appropriate `Literal[...]` in [types.py](types.py) (`StepPatch.field` for scalars, `StepListAppend.field` for lists) and the matching set in [apply.py](apply.py).
- **New mutation kind** (e.g. delete a step): add a new field to `ClarificationTurn`, handle it in `apply_turn`.
- **Change the question cap**: edit `MAX_CLARIFICATION_QUESTIONS` in [skill.py](skill.py).
- **Streaming**: would require switching from `parse` to manual JSON parsing with `chat.completions.stream`. Probably not worth it at MVP scale — each turn already finishes in a few seconds.
