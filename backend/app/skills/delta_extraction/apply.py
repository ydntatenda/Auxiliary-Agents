"""Typed apply layer for delta extraction.

CLAUDE.md rule 4 says graph mutations go through a typed apply layer that
enforces field whitelists and step-existence checks. This module is that
layer for delta extraction: it takes a Workflow plus a DeltaResult and
returns the merged Workflow, enforcing the declared scope and reopening
resolved gaps on any step the update touches.

The API never edits the graph directly. It calls `extract_delta`, then
`apply_delta`, then persists.
"""
from __future__ import annotations

from app.models.graph import Gap, Step, Workflow

from .types import DeltaResult, DeltaScope


class DeltaApplyError(ValueError):
    """Raised when the delta cannot be applied safely."""


def apply_delta(
    workflow: Workflow,
    delta: DeltaResult,
    scope: DeltaScope,
) -> Workflow:
    """Merge a DeltaResult into the workflow under the declared scope.

    Returns a new Workflow. The function does not mutate the input in
    place, so callers can compare before/after if they need to.
    """
    allowed_ids = _allowed_modifiable_ids(workflow, scope)

    existing_by_id = {step.id: step for step in workflow.steps}

    touched_step_ids: set[str] = set()

    # Validate: every modified step id must exist, and must be in scope.
    for step in delta.modified_steps:
        if step.id not in existing_by_id:
            raise DeltaApplyError(
                f"modified step {step.id!r} does not exist in the current graph"
            )
        if allowed_ids is not None and step.id not in allowed_ids:
            raise DeltaApplyError(
                f"modified step {step.id!r} is outside the declared scope"
            )
        touched_step_ids.add(step.id)

    # Validate: every removed step id must exist; in 'step' scope it must
    # also be one of the explicitly named ids.
    for removed_id in delta.removed_step_ids:
        if removed_id not in existing_by_id:
            raise DeltaApplyError(
                f"removed step {removed_id!r} does not exist in the current graph"
            )
        if allowed_ids is not None and removed_id not in allowed_ids:
            raise DeltaApplyError(
                f"removed step {removed_id!r} is outside the declared scope"
            )
        touched_step_ids.add(removed_id)

    # Added steps: enforce id uniqueness.
    for new_step in delta.added_steps:
        if new_step.id in existing_by_id:
            raise DeltaApplyError(
                f"added step {new_step.id!r} clashes with an existing step id"
            )

    # Build the new step list. Order: take all existing steps in their
    # current order, apply modifications by id, drop removals, then append
    # added steps. The clarification stage can renumber if it wants to.
    removed = set(delta.removed_step_ids)
    new_steps: list[Step] = []
    for step in workflow.steps:
        if step.id in removed:
            continue
        replacement = next(
            (mod for mod in delta.modified_steps if mod.id == step.id),
            None,
        )
        new_steps.append(replacement if replacement is not None else step)
    new_steps.extend(delta.added_steps)

    # Reopen any resolved gaps that sat on a step the delta touched: the
    # resolution may no longer apply to the new step shape, so a human or
    # the clarification agent has to look again.
    new_gaps: list[Gap] = []
    for gap in workflow.gaps:
        if gap.step_id and gap.step_id in removed:
            # Drop gaps whose owning step is gone.
            continue
        if gap.step_id and gap.step_id in touched_step_ids and gap.resolved:
            new_gaps.append(
                gap.model_copy(update={"resolved": False, "resolution": None})
            )
        else:
            new_gaps.append(gap)

    # Merge in new gaps, deduplicating by id.
    existing_gap_ids = {gap.id for gap in new_gaps}
    for fresh in delta.new_gaps:
        if fresh.id in existing_gap_ids:
            continue
        new_gaps.append(fresh)
        existing_gap_ids.add(fresh.id)

    return workflow.model_copy(update={"steps": new_steps, "gaps": new_gaps})


def _allowed_modifiable_ids(
    workflow: Workflow,
    scope: DeltaScope,
) -> set[str] | None:
    """Return the set of step ids the delta may touch, or None for unbounded.

    For "full" we return None so apply_delta short-circuits the scope
    check entirely. For "step" and "section" we return whatever the
    operator named (defaulting to nothing if step_ids is None).
    """
    if scope.scope == "full":
        return None
    return set(scope.step_ids or [])
