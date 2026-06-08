"""Unit tests for the deterministic terminal post-processing pass.

The pass sets every step's `terminal` to match the structural invariant:
true iff the step has no outbound decision_rule target AND no other step
has a higher `order`. Demotion and promotion are symmetric; both happen.
The tests build Workflow instances by hand so they run offline; no
OpenAI key is touched.
"""
from app.models.graph import DecisionRule, Step, Workflow
from app.skills.workflow_extraction.skill import _correct_terminals


def _wf(steps: list[Step]) -> Workflow:
    return Workflow(
        name="x",
        description="",
        unit="u",
        source_modality="text",
        source_transcript="...",
        steps=steps,
        gaps=[],
    )


def _step(
    sid: str,
    order: int,
    *,
    terminal: bool = False,
    decision_rules: list[DecisionRule] | None = None,
) -> Step:
    return Step(
        id=sid,
        order=order,
        title=sid,
        description="",
        terminal=terminal,
        decision_rules=decision_rules or [],
    )


def test_demotes_and_promotes_when_extractor_picks_wrong_terminal() -> None:
    """The extractor marks an intermediate step terminal and leaves the
    final step non-terminal. The pass demotes the intermediate and
    promotes the final.
    """
    wf = _wf(
        steps=[
            _step("a", 1, terminal=True),
            _step("b", 2, terminal=False),
        ]
    )
    out = _correct_terminals(wf)
    assert out.steps[0].terminal is False
    assert out.steps[1].terminal is True


def test_demotes_terminal_when_step_has_outbound_decision_rule() -> None:
    wf = _wf(
        steps=[
            _step(
                "a",
                1,
                terminal=True,
                decision_rules=[
                    DecisionRule(condition="x", then_step_id="b"),
                ],
            ),
            _step("b", 2, terminal=False),
        ]
    )
    out = _correct_terminals(wf)
    assert out.steps[0].terminal is False
    # b is the highest-order step with no outbound rule, so it is
    # promoted to terminal even though the extractor left it False.
    assert out.steps[1].terminal is True


def test_leaves_terminal_when_no_successor_and_no_outbound_rule() -> None:
    """The final step in a single-terminal workflow stays terminal."""
    wf = _wf(
        steps=[
            _step("a", 1, terminal=False),
            _step("b", 2, terminal=True),
        ]
    )
    out = _correct_terminals(wf)
    assert out.steps[0].terminal is False
    assert out.steps[1].terminal is True


def test_promotes_when_only_final_step_was_left_non_terminal() -> None:
    """The pass now promotes: the highest-order step with no outbound
    decision_rules becomes terminal even if the extractor did not mark it.
    """
    wf = _wf(
        steps=[
            _step("a", 1, terminal=False),
            _step("b", 2, terminal=False),  # extractor missed this one
        ]
    )
    out = _correct_terminals(wf)
    assert out.steps[1].terminal is True


def test_multi_terminal_limitation_is_observable() -> None:
    """Pins the documented limitation.

    In a workflow where two legitimately-terminal steps sit at different
    orders (an approve branch ends at order 2, a deny branch ends at
    order 3), the rule wrongly demotes the earlier one because a
    higher-order step exists. This test makes the limitation observable
    so the failure surface when a multi-terminal fixture arrives.
    """
    wf = _wf(
        steps=[
            _step(
                "decide",
                1,
                decision_rules=[
                    DecisionRule(condition="approve", then_step_id="approve_end"),
                    DecisionRule(condition="deny", then_step_id="deny_end"),
                ],
            ),
            _step("approve_end", 2, terminal=True),
            _step("deny_end", 3, terminal=True),
        ]
    )
    out = _correct_terminals(wf)
    # Wrongly demoted because a higher-order step exists.
    approve = next(s for s in out.steps if s.id == "approve_end")
    deny = next(s for s in out.steps if s.id == "deny_end")
    assert approve.terminal is False
    assert deny.terminal is True


def test_empty_workflow_passes_through() -> None:
    wf = _wf(steps=[])
    out = _correct_terminals(wf)
    assert out.steps == []


def test_no_change_returns_same_workflow_instance() -> None:
    """When nothing needed demotion, the pass returns the input unchanged."""
    wf = _wf(
        steps=[
            _step("a", 1, terminal=False),
            _step("b", 2, terminal=True),
        ]
    )
    out = _correct_terminals(wf)
    assert out is wf
