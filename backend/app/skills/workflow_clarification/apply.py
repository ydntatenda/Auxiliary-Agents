from openai import AsyncOpenAI

from app.config import get_settings
from app.db.workflows import load_workflow, save_workflow
from app.models.graph import DecisionRule, Step

from .types import ClarificationTurn

SCALAR_STEP_FIELDS = {"approver", "description", "notes", "title"}
LIST_STEP_FIELDS = {"inputs", "outputs", "tools_used"}
BOOL_STEP_FIELDS = {"terminal"}
SEVERITY_ORDER = {"critical": 0, "important": 1, "minor": 2}


def active_clarification_model() -> dict[str, str]:
    """Return the provider + model the clarification skill is currently wired to."""
    settings = get_settings()
    if settings.clarification_provider == "openrouter":
        return {
            "provider": "openrouter",
            "model": settings.openrouter_clarification_model,
            "base_url": settings.openrouter_base_url,
        }
    return {
        "provider": "openai",
        "model": settings.openai_clarification_model,
    }


def get_clarification_client_and_model() -> tuple[AsyncOpenAI, str]:
    """Return the (client, model_id) for the active clarification provider."""
    client, model, _ = get_clarification_provider()
    return client, model


def get_clarification_provider() -> tuple[AsyncOpenAI, str, str]:
    """Return the (client, model_id, provider_name) for the active clarification provider.

    provider_name is 'openai' or 'openrouter' — callers branch on this to choose
    between the strict-schema `.parse()` path (OpenAI) and the normalize+validate
    path (OpenRouter / others).
    """
    settings = get_settings()
    if settings.clarification_provider == "openrouter":
        if not settings.openrouter_api_key:
            raise RuntimeError(
                "clarification_provider=openrouter but OPENROUTER_API_KEY is not set"
            )
        client = AsyncOpenAI(
            base_url=settings.openrouter_base_url,
            api_key=settings.openrouter_api_key,
        )
        return client, settings.openrouter_clarification_model, "openrouter"
    return (
        AsyncOpenAI(api_key=settings.openai_api_key),
        settings.openai_clarification_model,
        "openai",
    )


async def list_unresolved_gaps(workflow_id: str) -> list[dict]:
    """Return unresolved gaps sorted by severity (critical first)."""
    workflow = await load_workflow(workflow_id)
    unresolved = [gap for gap in workflow.gaps if not gap.resolved]
    ordered = sorted(unresolved, key=lambda gap: SEVERITY_ORDER[gap.severity])
    return [gap.model_dump(mode="json") for gap in ordered]


async def apply_turn(workflow_id: str, turn: ClarificationTurn) -> list[str]:
    """Apply every mutation in a ClarificationTurn atomically.

    Validates step/gap existence and field whitelists before saving. Returns a
    list of human-readable warnings for entries that were skipped (e.g. unknown
    step IDs). Raises only on programmer errors (e.g. invalid field literal,
    which Pydantic should already prevent).
    """
    workflow = await load_workflow(workflow_id)
    warnings: list[str] = []

    for patch in turn.scalar_patches:
        if patch.field not in SCALAR_STEP_FIELDS:
            warnings.append(f"Skipped scalar_patch: unknown field '{patch.field}'")
            continue
        step = workflow.find_step(patch.step_id)
        if step is None:
            warnings.append(f"Skipped scalar_patch: step '{patch.step_id}' not found")
            continue
        setattr(step, patch.field, patch.value)

    for flag in turn.step_flags:
        if flag.field not in BOOL_STEP_FIELDS:
            warnings.append(f"Skipped step_flag: unknown field '{flag.field}'")
            continue
        step = workflow.find_step(flag.step_id)
        if step is None:
            warnings.append(f"Skipped step_flag: step '{flag.step_id}' not found")
            continue
        setattr(step, flag.field, flag.value)

    for append in turn.list_appends:
        if append.field not in LIST_STEP_FIELDS:
            warnings.append(f"Skipped list_append: unknown field '{append.field}'")
            continue
        step = workflow.find_step(append.step_id)
        if step is None:
            warnings.append(f"Skipped list_append: step '{append.step_id}' not found")
            continue
        getattr(step, append.field).append(append.value)

    for rule in turn.new_decision_rules:
        step = workflow.find_step(rule.step_id)
        if step is None:
            warnings.append(f"Skipped decision_rule: step '{rule.step_id}' not found")
            continue
        if workflow.find_step(rule.then_step_id) is None:
            warnings.append(
                f"Skipped decision_rule on '{rule.step_id}': then_step_id '{rule.then_step_id}' not found"
            )
            continue
        if rule.else_step_id is not None and workflow.find_step(rule.else_step_id) is None:
            warnings.append(
                f"Skipped decision_rule on '{rule.step_id}': else_step_id '{rule.else_step_id}' not found"
            )
            continue
        step.decision_rules.append(
            DecisionRule(
                condition=rule.condition,
                then_step_id=rule.then_step_id,
                else_step_id=rule.else_step_id,
            )
        )

    for new_step in turn.new_steps:
        if workflow.find_step(new_step.step_id) is not None:
            warnings.append(f"Skipped new_step: step '{new_step.step_id}' already exists")
            continue
        next_order = max((s.order for s in workflow.steps), default=0) + 1
        workflow.steps.append(
            Step(
                id=new_step.step_id,
                order=next_order,
                title=new_step.title,
                description=new_step.description,
                approver=new_step.approver,
                terminal=new_step.terminal,
            )
        )

    for edit in turn.decision_rule_edits:
        step = workflow.find_step(edit.step_id)
        if step is None:
            warnings.append(f"Skipped rule_edit: step '{edit.step_id}' not found")
            continue
        if not (0 <= edit.rule_index < len(step.decision_rules)):
            warnings.append(
                f"Skipped rule_edit on '{edit.step_id}': rule_index {edit.rule_index} out of range"
            )
            continue
        rule = step.decision_rules[edit.rule_index]
        if edit.condition is not None:
            rule.condition = edit.condition
        if edit.then_step_id is not None:
            if workflow.find_step(edit.then_step_id) is None:
                warnings.append(
                    f"Skipped rule_edit on '{edit.step_id}'[{edit.rule_index}]: then_step_id '{edit.then_step_id}' not found"
                )
                continue
            rule.then_step_id = edit.then_step_id
        if edit.else_step_id is not None:
            # Sentinel "__null__" clears else_step_id; any other value sets it.
            if edit.else_step_id == "__null__":
                rule.else_step_id = None
            else:
                if workflow.find_step(edit.else_step_id) is None:
                    warnings.append(
                        f"Skipped rule_edit on '{edit.step_id}'[{edit.rule_index}]: else_step_id '{edit.else_step_id}' not found"
                    )
                    continue
                rule.else_step_id = edit.else_step_id

    # Process rule deletions in reverse-index order per step so earlier indexes stay valid.
    deletions_by_step: dict[str, list[int]] = {}
    for removal in turn.removed_decision_rules:
        deletions_by_step.setdefault(removal.step_id, []).append(removal.rule_index)
    for step_id, indexes in deletions_by_step.items():
        step = workflow.find_step(step_id)
        if step is None:
            warnings.append(f"Skipped removed_decision_rule: step '{step_id}' not found")
            continue
        for idx in sorted(set(indexes), reverse=True):
            if not (0 <= idx < len(step.decision_rules)):
                warnings.append(
                    f"Skipped removed_decision_rule on '{step_id}': rule_index {idx} out of range"
                )
                continue
            del step.decision_rules[idx]

    # Step removal: also prune any decision rules pointing at the removed step.
    removed_ids = set(turn.removed_step_ids)
    for step_id in removed_ids:
        if workflow.find_step(step_id) is None:
            warnings.append(f"Skipped removed_step: step '{step_id}' not found")
    workflow.steps = [s for s in workflow.steps if s.id not in removed_ids]
    for step in workflow.steps:
        before = len(step.decision_rules)
        step.decision_rules = [
            r
            for r in step.decision_rules
            if r.then_step_id not in removed_ids
            and (r.else_step_id is None or r.else_step_id not in removed_ids)
        ]
        if len(step.decision_rules) < before:
            warnings.append(
                f"Pruned {before - len(step.decision_rules)} decision rule(s) on '{step.id}' that referenced removed steps"
            )

    gaps_by_id = {gap.id: gap for gap in workflow.gaps}
    for resolution in turn.resolved_gaps:
        gap = gaps_by_id.get(resolution.gap_id)
        if gap is None:
            warnings.append(f"Skipped resolve: gap '{resolution.gap_id}' not found")
            continue
        gap.resolved = True
        gap.resolution = resolution.resolution

    await save_workflow(workflow)
    return warnings
