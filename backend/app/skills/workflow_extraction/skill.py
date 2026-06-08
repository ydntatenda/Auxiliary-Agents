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
- A review or inspection action that lets the operator go back and fix
  something is its own step. Distinct UI surfaces traversed in sequence
  (selecting a template, reviewing the populated result, sending it) are
  separate steps, not one combined action. Only the step that completes
  the workflow is terminal.
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
- When a gap describes a downstream concern triggered by an upstream
  condition (a 10-day hold triggered by a name mismatch; an additional
  information request triggered by that same mismatch), name the trigger
  in the gap description. A gap without its trigger is unactionable.
- Set source_modality to "text" as a placeholder; the application will preserve
  the original capture modality after extraction.
- Set source_transcript to the transcript exactly as provided.

Step kind:
- Classify each step's kind as one of: procedure, exception, policy, handoff.
  This is a positive classification, not a filter. Include the step in the
  graph and label it; misclassification is recoverable later by the
  clarification stage, omission is not.
- procedure: a step the operator performs in the normal sequence of work.
  Generic example: "Verify the customer's identity against the order record."
- exception: a step that runs only when a specific trigger described in the
  transcript fires. Real operator action, real trigger, off the main flow.
  Generic example: "When the address on the package does not match the
  order, open a customer-clarification ticket and place the shipment on
  hold."
- policy: an eligibility or constraint rule the operator applies rather than
  an action they perform. A statement about who is or is not allowed, or
  about a limit or threshold.
  Generic example: "External applicants are not eligible for the same-day
  service tier."
- handoff: work the transcript explicitly attributes to someone other than
  this operator (a sibling team, an automated system, an external party).
  The transcript may say something like "that goes to X, not me".
  Generic example: "Complaints about delivery are routed to the carrier
  support desk, not handled here."
- Default to procedure when the operator describes themself performing the
  action in the normal sequence.

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
- An automatic shortcut or skip-ahead is a branch. When a verification or
  intake step describes a failure case that jumps past intermediate steps
  to a closing step ("if X fails, dismiss automatically and go straight to
  the letter"), emit a decision_rule whose then_step_id points to the skip
  target and let the implicit success case continue in order.
  Wrong (flattened): the verification step's decision_rules is empty and
  the description says "I check the plate and continue, unless it does
  not match, in which case I jump to the letter". Right (branched): the
  same step has one decision_rule with condition "plate on citation does
  not match the photos", then_step_id pointing to the letter step id, and
  else_step_id null; the success case continues to the next step in order
  without a rule entry.
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
        temperature=0,
    )
    return _correct_terminals(response.output_parsed)


def _correct_terminals(workflow: Workflow) -> Workflow:
    """Set every step's terminal flag to match the structural invariant.

    A procedure step is terminal iff it has no outbound decision_rule
    target and no other procedure step has a higher order. The pass
    rebuilds any step whose `terminal` value disagrees with the
    invariant, through Pydantic model_copy.

    The procedure-step filter is the load-bearing addition. Without it,
    an exception, policy, or handoff step at a higher order than the
    real procedural terminal would block promotion of the procedure
    terminal and would itself get crowned, which is the
    terminal-displacement defect the kind field exists to fix. Filtering
    promotion candidates to kind == "procedure" lets the structurally
    final procedure step become terminal regardless of where the
    non-procedure steps sit in the order.

    Non-procedure steps (exception, policy, handoff) keep whatever
    terminal flag the extractor set, with one structural exception: a
    step with outbound decision_rules cannot be terminal regardless of
    kind, because "terminal" means "no continuation" and outbound rules
    specify continuation. So a non-procedure step with outbound rules is
    demoted if currently marked terminal; otherwise its flag is left
    alone.

    Known limitation. The single-terminal assumption still holds in
    both directions for procedure steps. In a genuine multi-terminal
    workflow with two or more legitimately-terminal procedure steps at
    different orders (an approve branch ends at step 5, a deny branch
    ends at step 7), the rule still has the same two failures:

    - On the demote side, the earlier real procedure terminal is
      wrongly demoted because a higher-order procedure step exists.
    - On the promote side, only the highest-order procedure step is
      crowned, so one of the real procedure terminals is left
      non-terminal.

    The rule is correct for single-terminal workflows like the
    citation appeals fixture. When a multi-terminal fixture arrives,
    terminal_correctness on that fixture will regress and the rule
    refines then, rather than silently mis-scoring the fixture now.
    """
    if not workflow.steps:
        return workflow

    procedure_steps = [step for step in workflow.steps if step.kind == "procedure"]
    max_procedure_order: int | None = (
        max(step.order for step in procedure_steps) if procedure_steps else None
    )

    new_steps: list = []
    changed = False
    for step in workflow.steps:
        has_outbound_target = any(
            rule.then_step_id for rule in step.decision_rules
        )
        if step.kind == "procedure" and max_procedure_order is not None:
            has_higher_procedure = step.order < max_procedure_order
            should_be_terminal = (
                not has_outbound_target and not has_higher_procedure
            )
        else:
            # Non-procedure: keep the extractor's flag unless it conflicts
            # with outbound rules.
            should_be_terminal = step.terminal and not has_outbound_target
        if step.terminal == should_be_terminal:
            new_steps.append(step)
            continue
        new_steps.append(step.model_copy(update={"terminal": should_be_terminal}))
        changed = True
    if not changed:
        return workflow
    return workflow.model_copy(update={"steps": new_steps})
