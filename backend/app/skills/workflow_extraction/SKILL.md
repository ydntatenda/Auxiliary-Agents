# workflow_extraction

Converts a transcript (text, voice, or screen+narration) into a structured `Workflow` graph.

## Public surface

```python
from app.skills.workflow_extraction import extract_workflow

workflow: Workflow = await extract_workflow(name, unit, transcript)
```

Single function, typed return. Called by `POST /workflows/{id}/extract` ([api/workflows.py](../../api/workflows.py)).

## Model

`gpt-5` (configurable via `OPENAI_EXTRACTION_MODEL`). Uses `client.responses.parse(text_format=Workflow)` — OpenAI's structured-output mode, so the Pydantic `Workflow` model **is the schema**. The LLM cannot return malformed graphs; if a required field is missing, the call fails.

## Why GPT-5 and not a cheaper model

Extraction is the most semantically demanding step in the pipeline. It has to:
- Infer step boundaries from rambling narration
- Spot unstated branches and mark them as gaps
- Distinguish a "tool used" from an "input" from an "output"
- Produce stable IDs (`step_1`, `verify_identity`) the clarification agent can reference later

A weaker model produces noisier graphs that the clarification turn count can't recover from in 7 questions. If you swap models, run on a few real transcripts and check gap quality, not just structural validity.

## Prompt contract (see `skill.py`)

- **8–15 steps target.** Not every click is a step. Under 8 usually means the model collapsed too much; over 15 means it transcribed instead of abstracted.
- **`executor` is always `"human"`** for MVP. If you add automated executors later, update the prompt and add a check in `models/graph.py`.
- **Step IDs must be stable** (`step_1`, `verify_identity`). The clarification tools take `step_id` as input — drift breaks the clarification loop.
- **`source_modality` is set to `"text"` by the model** as a placeholder. The API layer overwrites it with the true modality after extraction. Don't try to fix this in the prompt.
- **Gap severity is rated by the model** (`critical` / `important` / `minor`). The clarification agent only asks about critical/important by default — overrating gaps wastes user turns; underrating leaves holes in the SOP.
- **`terminal: bool` per step.** The prompt instructs the model to mark steps that end a path (approvals, denials, closures, finalize-and-notify). The diagram renderer skips the implicit fall-through edge for terminal steps and draws them with a stadium shape. False is the safe default — the reviewer can fix it on the Review page via the AI edit textbox.

## Known failure modes

1. **Walkthrough describes one path through a branching workflow.** Model is told to infer branches and mark unknowns as gaps. Quality varies — clarification fills the rest.
2. **Implicit approvers.** "I send it up" → model often misses that an approver exists. Show up as gaps if at all.
3. **Tools vs. inputs confusion.** "I open T2 Flex and look up the citation" — citation number is an input, T2 Flex is a tool. Model sometimes flips them. Clarification can fix via `append_to_step_list`.

## When extending

- Adding a new field to `Step` or `Workflow`: update [models/graph.py](../../models/graph.py), add prompt guidance here, and decide whether clarification needs a tool to patch it (see [`workflow_clarification/SKILL.md`](../workflow_clarification/SKILL.md)).
- Don't add post-processing in this skill. If the output needs cleanup, prefer fixing the prompt or the Pydantic model's validators.
