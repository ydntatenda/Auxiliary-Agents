"""Unit tests for the delta apply layer.

Pins the contract that scope is enforced server-side, that resolved
gaps on touched steps are re-opened, and that gaps on removed steps
are dropped entirely.
"""
import pytest

from app.models.graph import Gap, Step, Workflow
from app.skills.delta_extraction.apply import DeltaApplyError, apply_delta
from app.skills.delta_extraction.types import DeltaResult, DeltaScope


def _workflow() -> Workflow:
    return Workflow(
        name="Citation appeals",
        description="Citizens appeal parking citations.",
        unit="Parking & Transportation",
        source_modality="text",
        source_transcript="...",
        steps=[
            Step(id="receive", order=1, title="Receive appeal", description="Intake"),
            Step(id="review", order=2, title="Review", description="Decide"),
            Step(id="notify", order=3, title="Notify", description="Email outcome", terminal=True),
        ],
        gaps=[
            Gap(
                id="g1",
                step_id="review",
                description="Who approves over £200?",
                severity="important",
                resolved=True,
                resolution="Assistant director.",
            ),
            Gap(
                id="g2",
                step_id="notify",
                description="Which template do we use?",
                severity="minor",
                resolved=False,
                resolution=None,
            ),
        ],
    )


def _step(id: str, title: str, *, terminal: bool = False) -> Step:
    return Step(id=id, order=99, title=title, description=title, terminal=terminal)


def test_modify_step_in_scope_replaces_and_reopens_gap() -> None:
    workflow = _workflow()
    new_review = Step(
        id="review",
        order=2,
        title="Review with new threshold",
        description="Decide using updated rules.",
    )
    delta = DeltaResult(modified_steps=[new_review], change_summary="threshold raised")
    scope = DeltaScope(scope="step", step_ids=["review"])

    out = apply_delta(workflow, delta, scope)

    review = out.find_step("review")
    assert review is not None and review.title == "Review with new threshold"
    # g1 sat on review and was resolved; it must be reopened.
    g1 = next(gap for gap in out.gaps if gap.id == "g1")
    assert g1.resolved is False
    assert g1.resolution is None
    # g2 was not on a touched step and should be left alone.
    g2 = next(gap for gap in out.gaps if gap.id == "g2")
    assert g2.resolved is False
    assert g2.resolution is None


def test_modify_step_outside_scope_raises() -> None:
    workflow = _workflow()
    delta = DeltaResult(
        modified_steps=[_step("notify", "Notify (new)")],
        change_summary="x",
    )
    scope = DeltaScope(scope="step", step_ids=["review"])

    with pytest.raises(DeltaApplyError):
        apply_delta(workflow, delta, scope)


def test_full_scope_allows_anything() -> None:
    workflow = _workflow()
    delta = DeltaResult(
        modified_steps=[_step("notify", "Notify (new)")],
        change_summary="reword notify",
    )
    scope = DeltaScope(scope="full")
    out = apply_delta(workflow, delta, scope)
    assert out.find_step("notify").title == "Notify (new)"


def test_remove_step_in_scope_drops_step_and_its_gaps() -> None:
    workflow = _workflow()
    delta = DeltaResult(removed_step_ids=["notify"], change_summary="drop notify")
    scope = DeltaScope(scope="step", step_ids=["notify"])
    out = apply_delta(workflow, delta, scope)
    assert out.find_step("notify") is None
    assert all(gap.id != "g2" for gap in out.gaps)


def test_add_step_rejects_clashing_id() -> None:
    workflow = _workflow()
    delta = DeltaResult(
        added_steps=[_step("review", "Duplicate review")],
        change_summary="x",
    )
    scope = DeltaScope(scope="full")
    with pytest.raises(DeltaApplyError):
        apply_delta(workflow, delta, scope)


def test_remove_outside_scope_raises() -> None:
    workflow = _workflow()
    delta = DeltaResult(removed_step_ids=["notify"], change_summary="x")
    scope = DeltaScope(scope="step", step_ids=["review"])
    with pytest.raises(DeltaApplyError):
        apply_delta(workflow, delta, scope)


def test_modify_nonexistent_step_raises() -> None:
    workflow = _workflow()
    delta = DeltaResult(
        modified_steps=[_step("nope", "Phantom")],
        change_summary="x",
    )
    scope = DeltaScope(scope="full")
    with pytest.raises(DeltaApplyError):
        apply_delta(workflow, delta, scope)


def test_new_gaps_merge_and_dedupe() -> None:
    workflow = _workflow()
    delta = DeltaResult(
        new_gaps=[
            Gap(id="g3", description="A new gap", severity="critical"),
            Gap(id="g1", description="Should not duplicate", severity="minor"),
        ],
        change_summary="surface contradictions",
    )
    scope = DeltaScope(scope="full")
    out = apply_delta(workflow, delta, scope)
    gap_ids = [gap.id for gap in out.gaps]
    assert gap_ids.count("g1") == 1
    assert "g3" in gap_ids
