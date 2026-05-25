from app.config import get_settings
from app.models.graph import Workflow
from app.services.openai_client import get_openai_client


EXTRACTION_PROMPT = """
You are converting an employee's description of a workflow into a structured
graph representation.

The description may be a typed account, a transcribed voice walkthrough, or
a transcript of a screen recording with narration. Treat all three the same.

Your job:

1. Identify the discrete steps the employee performs, in order.
2. For each step, capture:
   - A short imperative title
   - A full description of what happens
   - Inputs needed to begin the step
   - Outputs produced by the step
   - Tools or systems used
   - Approvers required, if any
   - Decision rules that branch to other steps
3. Identify gaps: anything missing or unclear that would prevent another
   employee from following this as an SOP.

Guidelines:
- Aim for 8-15 steps for a typical workflow. Not every mouse click is a step.
- If the employee narrates a single path through a branching workflow, capture
  the branches you can infer and mark unknown branches as gaps.
- Executor should always be "human".
- Use stable step IDs like "step_1", "verify_identity", etc.
- Rate gap severity with a strict rubric:
  - critical = the SOP is unusable without this information.
  - important = the SOP would actively mislead a new hire without this information.
  - minor = everything else, including helpful context, precision, SLAs, names,
    locations, template labels, edge-case polish, or details that improve quality
    but are not required to follow the SOP safely.
- Do not overuse critical or important. Most gaps should be minor unless they
  meet the definitions above.
- Set source_modality to "text" as a placeholder; the application will preserve
  the original capture modality after extraction.
- Set source_transcript to the transcript exactly as provided.

Terminal steps:
- Set `terminal: true` on every step that ends a path through the workflow.
  Default these step types to terminal:
  - Approve / void / refund / finalize / close / archive steps — ALWAYS terminal.
  - Deny / reject steps — ALWAYS terminal.
  - "Forward to <external party> and stop" steps where the next action belongs
    to a party not modeled in this workflow.
- The only non-terminal steps are ones where this workflow itself defines
  the next action.
- Multiple terminal steps per workflow are normal and expected. A typical
  appeals-style workflow has 3-5 terminals: one per outcome path.
- Do NOT default to terminal=false for approve/deny steps. The reviewer can
  correct an over-marked terminal more easily than a missed one — a missing
  terminal silently produces a wrong fallthrough edge in the diagram, while
  an over-marked terminal is visually obvious.

Decision rules:
- Use decision_rules ONLY when the workflow branches.
- For a step with multiple mutually-exclusive outcomes (e.g. "approve",
  "deny", "request more info"), emit ONE decision_rule per outcome with
  else_step_id = null. Do NOT reuse the same else_step_id across multiple
  rules on the same step — each rule should stand alone.
- Set else_step_id to a step ID only when there is one specific alternate
  path for the false case (e.g. classic if/else). If the false case continues
  to the next step in order, or if there is no false case, set else_step_id
  to null.
- Do NOT invent placeholder "continue after decision" or "buffer" steps. If a
  step has three outcomes, emit three decision rules on the source step — do
  not route through an intermediate placeholder.

Workflow name: {name}
Unit: {unit}

Transcript:
{transcript}
"""


async def extract_workflow(name: str, unit: str, transcript: str) -> Workflow:
    client = get_openai_client()
    settings = get_settings()
    response = await client.responses.parse(
        model=settings.openai_extraction_model,
        input=EXTRACTION_PROMPT.format(name=name, unit=unit, transcript=transcript),
        text_format=Workflow,
    )
    return response.output_parsed
