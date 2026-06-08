"""Hand-built unit tests for the five eval scorers.

Each scorer is exercised with a `Workflow` (or duck-typed equivalent
for automatability) constructed inline, so the suite runs offline with
no OpenAI key.
"""
from types import SimpleNamespace

import pytest

from app.models.graph import DecisionRule, Gap, Step, Workflow
from tests.eval import scorers
from tests.eval.fixtures import FixtureScoring, GoldenGap, GoldenStep


def _wf(steps: list[Step] | None = None, gaps: list[Gap] | None = None) -> Workflow:
    return Workflow(
        name="test workflow",
        description="",
        unit="test unit",
        source_modality="text",
        source_transcript="...",
        steps=steps or [],
        gaps=gaps or [],
    )


def _step(
    sid: str,
    title: str,
    *,
    description: str = "",
    terminal: bool = False,
    decision_rules: list[DecisionRule] | None = None,
) -> Step:
    return Step(
        id=sid,
        order=1,
        title=title,
        description=description,
        terminal=terminal,
        decision_rules=decision_rules or [],
    )


def _scoring(
    *,
    band: tuple[int, int] = (3, 7),
    steps: list[GoldenStep] | None = None,
    gaps: list[GoldenGap] | None = None,
    gap_recall_threshold: float = 0.8,
    gap_severity_threshold: float = 0.8,
    gap_match_threshold: float = 0.5,
    terminal_threshold: float = 0.8,
    decision_rule_threshold: float = 0.8,
) -> FixtureScoring:
    return FixtureScoring(
        step_count_band=band,
        expected_steps=steps
        or [GoldenStep(concept="placeholder", keywords=["placeholder"])],
        expected_gaps=gaps or [],
        gap_recall_threshold=gap_recall_threshold,
        gap_severity_threshold=gap_severity_threshold,
        gap_match_threshold=gap_match_threshold,
        terminal_threshold=terminal_threshold,
        decision_rule_threshold=decision_rule_threshold,
    )


# -- step_count_band -----------------------------------------------


def test_step_count_band_passes_within_inclusive_range() -> None:
    wf = _wf(steps=[_step(f"s{i}", f"title {i}") for i in range(5)])
    result = scorers.score_step_count_band(wf, _scoring(band=(3, 7)))
    assert result.passed is True
    assert result.score == 1.0
    assert result.details["count"] == 5


def test_step_count_band_fails_above() -> None:
    wf = _wf(steps=[_step(f"s{i}", f"title {i}") for i in range(12)])
    result = scorers.score_step_count_band(wf, _scoring(band=(3, 7)))
    assert result.passed is False
    assert result.score < 1.0
    assert any("outside band" in m for m in result.messages)


def test_step_count_band_fails_below() -> None:
    wf = _wf(steps=[_step("s0", "title 0")])
    result = scorers.score_step_count_band(wf, _scoring(band=(3, 7)))
    assert result.passed is False
    assert result.score < 1.0


def test_step_count_band_surfaces_duplicate_title_hint() -> None:
    wf = _wf(
        steps=[
            _step("a", "review the citation appeal"),
            _step("b", "review the citation appeal again"),
            _step("c", "send notification email"),
        ]
    )
    result = scorers.score_step_count_band(wf, _scoring(band=(2, 5)))
    near = result.details["near_duplicate_prefixes"]
    assert any(n >= 2 for _, n in near)
    assert any("concatenation" in m for m in result.messages)


# -- gap_recall_severity --------------------------------------------


def test_gap_recall_severity_perfect() -> None:
    wf = _wf(
        gaps=[
            Gap(
                id="g1",
                description="Threshold for senior approval is ambiguous.",
                severity="critical",
            )
        ]
    )
    scoring = _scoring(
        gaps=[
            GoldenGap(
                concept="approval_threshold",
                keywords=["threshold", "senior approval"],
                severity="critical",
            )
        ]
    )
    result = scorers.score_gap_recall_severity(wf, scoring)
    assert result.passed is True
    assert result.details["matched"] == 1


def test_gap_recall_below_threshold_fails() -> None:
    wf = _wf(gaps=[])
    scoring = _scoring(
        gaps=[
            GoldenGap(
                concept="approval_threshold",
                keywords=["threshold", "senior approval"],
                severity="critical",
            )
        ]
    )
    result = scorers.score_gap_recall_severity(wf, scoring)
    assert result.passed is False
    assert any("not matched" in m for m in result.messages)


def test_gap_severity_mismatch_flagged() -> None:
    wf = _wf(
        gaps=[
            Gap(
                id="g1",
                description="Threshold for senior approval is ambiguous.",
                severity="important",
            )
        ]
    )
    scoring = _scoring(
        gaps=[
            GoldenGap(
                concept="approval_threshold",
                keywords=["threshold", "senior approval"],
                severity="critical",
            )
        ]
    )
    result = scorers.score_gap_recall_severity(wf, scoring)
    assert result.passed is False
    # Matched, so recall is 1.0; severity accuracy is 0.0 which fails.
    assert any("severity" in m for m in result.messages)


def test_gap_no_expected_gaps_skips() -> None:
    wf = _wf()
    scoring = _scoring(gaps=[])
    result = scorers.score_gap_recall_severity(wf, scoring)
    assert result.skipped is True
    assert result.passed is True


def test_gap_partial_overlap_matches_at_default_threshold() -> None:
    """Default threshold 0.5 accepts two of three keyword hits."""
    wf = _wf(
        gaps=[
            Gap(
                id="g1",
                description="Reduce decisions lack written criteria for the boundary.",
                severity="critical",
            )
        ]
    )
    scoring = _scoring(
        gaps=[
            GoldenGap(
                concept="reduction_criteria",
                keywords=["reduce", "criteria", "dismiss"],
                severity="critical",
            )
        ]
    )
    result = scorers.score_gap_recall_severity(wf, scoring)
    assert result.details["matched"] == 1
    per_gap = result.details["per_gap"][0]
    assert per_gap["matched"] is True
    assert per_gap["matched_keywords"] == ["reduce", "criteria"]
    assert per_gap["overlap"] == round(2 / 3, 3)


def test_gap_partial_overlap_below_threshold_misses() -> None:
    """Threshold 0.75 requires three of four keywords; two hits is not enough."""
    wf = _wf(
        gaps=[
            Gap(
                id="g1",
                description="Reduce decisions need clearer criteria documentation.",
                severity="critical",
            )
        ]
    )
    scoring = _scoring(
        gaps=[
            GoldenGap(
                concept="reduction_criteria",
                keywords=["reduce", "criteria", "dismiss", "uphold"],
                severity="critical",
            )
        ],
        gap_match_threshold=0.75,
    )
    result = scorers.score_gap_recall_severity(wf, scoring)
    assert result.details["matched"] == 0
    per_gap = result.details["per_gap"][0]
    assert per_gap["matched"] is False
    assert per_gap["closest_hits"] == ["reduce", "criteria"]
    assert any("closest extracted gap" in m for m in result.messages)


def test_gap_threshold_one_reproduces_strict_conjunction() -> None:
    """gap_match_threshold = 1.0 means every keyword must hit (old behaviour).

    The same description would match at the default 0.5 threshold (two of
    three keywords), so this test specifically pins the strict bar.
    """
    wf = _wf(
        gaps=[
            Gap(
                id="g1",
                description="Reduce decisions lack written criteria for the boundary.",
                severity="critical",
            )
        ]
    )
    golden = GoldenGap(
        concept="reduction_criteria",
        keywords=["reduce", "criteria", "dismiss"],
        severity="critical",
    )
    # Strict: misses, because "dismiss" is not in the description.
    strict = _scoring(gaps=[golden], gap_match_threshold=1.0)
    strict_result = scorers.score_gap_recall_severity(wf, strict)
    assert strict_result.details["matched"] == 0

    # Default 0.5: matches, two of three keywords present.
    loose = _scoring(gaps=[golden])
    loose_result = scorers.score_gap_recall_severity(wf, loose)
    assert loose_result.details["matched"] == 1


def test_gap_picks_best_overlap_when_multiple_candidates() -> None:
    """When several extracted gaps partially match, the highest-overlap one wins."""
    wf = _wf(
        gaps=[
            Gap(
                id="g_weak",
                description="Dismissal happens automatically on plate mismatch.",
                severity="minor",
            ),
            Gap(
                id="g_strong",
                description="The reduce-versus-dismiss boundary lacks written criteria.",
                severity="critical",
            ),
        ]
    )
    scoring = _scoring(
        gaps=[
            GoldenGap(
                concept="reduction_criteria",
                keywords=["reduce", "criteria", "dismiss"],
                severity="critical",
            )
        ]
    )
    result = scorers.score_gap_recall_severity(wf, scoring)
    per_gap = result.details["per_gap"][0]
    assert per_gap["matched"] is True
    # All three keywords hit on g_strong; only one on g_weak.
    assert sorted(per_gap["matched_keywords"]) == ["criteria", "dismiss", "reduce"]
    assert per_gap["overlap"] == 1.0


def test_gap_match_threshold_loads_default_value() -> None:
    """Existing fixtures without the field still validate at 0.5 default."""
    scoring = _scoring()
    assert scoring.gap_match_threshold == 0.5


# -- terminal_correctness -------------------------------------------


def test_terminal_correctness_perfect_match() -> None:
    wf = _wf(
        steps=[
            _step("s1", "intake the citation appeal", description="receive form"),
            _step("s2", "deny the appeal", description="end of path", terminal=True),
        ]
    )
    scoring = _scoring(
        steps=[
            GoldenStep(concept="intake", keywords=["intake", "appeal"]),
            GoldenStep(concept="deny", keywords=["deny", "appeal"], terminal=True),
        ]
    )
    result = scorers.score_terminal_correctness(wf, scoring)
    assert result.passed is True
    assert result.score == 1.0
    assert result.details["true_positives"] == 1


def test_terminal_correctness_missed_terminal() -> None:
    wf = _wf(
        steps=[
            _step("s1", "deny the appeal", terminal=False),
        ]
    )
    scoring = _scoring(
        steps=[
            GoldenStep(concept="deny", keywords=["deny", "appeal"], terminal=True),
        ]
    )
    result = scorers.score_terminal_correctness(wf, scoring)
    assert result.passed is False
    assert result.details["false_negatives"] == 1
    assert any("not flagged terminal" in m for m in result.messages)


def test_terminal_correctness_false_positive_penalises() -> None:
    wf = _wf(
        steps=[
            _step("s1", "intake the citation appeal", terminal=True),
        ]
    )
    scoring = _scoring(
        steps=[
            GoldenStep(concept="intake", keywords=["intake", "appeal"], terminal=False),
        ]
    )
    result = scorers.score_terminal_correctness(wf, scoring)
    assert result.passed is False
    assert result.details["false_positives"] == 1
    assert any("non-terminal" in m for m in result.messages)


# -- decision_rule_structure ----------------------------------------


def test_decision_rule_structure_passes_when_branches_present() -> None:
    wf = _wf(
        steps=[
            _step(
                "s1",
                "decide on the appeal outcome",
                decision_rules=[
                    DecisionRule(condition="grant", then_step_id="grant"),
                    DecisionRule(condition="deny", then_step_id="deny"),
                ],
            )
        ]
    )
    scoring = _scoring(
        steps=[
            GoldenStep(
                concept="outcome_decision",
                keywords=["decide", "appeal outcome"],
                has_decision_rules=True,
                expected_min_branches=2,
            )
        ]
    )
    result = scorers.score_decision_rule_structure(wf, scoring)
    assert result.passed is True
    assert result.score == 1.0


def test_decision_rule_structure_flattened_flagged() -> None:
    wf = _wf(
        steps=[
            _step(
                "s1",
                "decide on the appeal outcome",
                decision_rules=[
                    DecisionRule(condition="grant", then_step_id="grant"),
                ],
            )
        ]
    )
    scoring = _scoring(
        steps=[
            GoldenStep(
                concept="outcome_decision",
                keywords=["decide", "appeal outcome"],
                has_decision_rules=True,
                expected_min_branches=2,
            )
        ]
    )
    result = scorers.score_decision_rule_structure(wf, scoring)
    assert result.passed is False
    per = result.details["per_decision"][0]
    assert per["flattened_to_one"] is True
    assert any("flattened to a single branch" in m for m in result.messages)


def test_decision_rule_structure_threshold_per_fixture() -> None:
    """One decision point preserved out of two with default 0.8 → fails."""
    wf = _wf(
        steps=[
            _step(
                "s1",
                "decide on the appeal outcome",
                decision_rules=[
                    DecisionRule(condition="grant", then_step_id="grant"),
                    DecisionRule(condition="deny", then_step_id="deny"),
                ],
            ),
            _step(
                "s2",
                "decide whether to escalate to supervisor",
                decision_rules=[
                    DecisionRule(condition="escalate", then_step_id="up"),
                ],
            ),
        ]
    )
    scoring = _scoring(
        steps=[
            GoldenStep(
                concept="outcome_decision",
                keywords=["decide", "appeal outcome"],
                has_decision_rules=True,
                expected_min_branches=2,
            ),
            GoldenStep(
                concept="escalation",
                keywords=["escalate", "supervisor"],
                has_decision_rules=True,
                expected_min_branches=2,
            ),
        ]
    )
    result = scorers.score_decision_rule_structure(wf, scoring)
    assert result.passed is False
    assert result.score == 0.5
    assert result.details["preserved"] == 1


def test_decision_rule_skip_when_no_expectations() -> None:
    wf = _wf()
    scoring = _scoring()
    result = scorers.score_decision_rule_structure(wf, scoring)
    assert result.skipped is True


# -- automatability -------------------------------------------------


def test_automatability_skipped_when_field_absent() -> None:
    wf = _wf(steps=[_step("s1", "x")])
    result = scorers.score_automatability(wf, _scoring())
    assert result.skipped is True
    assert result.passed is True
    assert result.details["field_present"] is False
    assert any("not yet defined" in m for m in result.messages)


def test_automatability_passes_when_field_present_and_all_labelled(monkeypatch) -> None:
    monkeypatch.setattr(scorers, "_has_automatability_field", lambda: True)
    fake_steps = [
        SimpleNamespace(title="s1", automatability="manual"),
        SimpleNamespace(title="s2", automatability="agent"),
    ]
    fake_workflow = SimpleNamespace(steps=fake_steps)
    result = scorers.score_automatability(fake_workflow, _scoring())
    assert result.skipped is False
    assert result.passed is True
    assert result.details == {
        "field_present": True,
        "labelled": 2,
        "total": 2,
    }


def test_automatability_fails_when_field_present_and_partial(monkeypatch) -> None:
    monkeypatch.setattr(scorers, "_has_automatability_field", lambda: True)
    fake_steps = [
        SimpleNamespace(title="s1", automatability="manual"),
        SimpleNamespace(title="s2", automatability=None),
    ]
    fake_workflow = SimpleNamespace(steps=fake_steps)
    result = scorers.score_automatability(fake_workflow, _scoring())
    assert result.passed is False
    assert result.details["labelled"] == 1
    assert any("missing automatability" in m for m in result.messages)


# -- Matching primitives behaviour ----------------------------------


def test_match_step_requires_every_keyword() -> None:
    steps = [
        _step("s1", "review the appeal evidence", description="check documents"),
        _step("s2", "review the supervisor request", description="other"),
    ]
    assert scorers._match_step(steps, ["review", "appeal"]).id == "s1"
    assert scorers._match_step(steps, ["review", "missing"]) is None


def test_match_step_case_insensitive() -> None:
    steps = [_step("s1", "Review the APPEAL", description="x")]
    assert scorers._match_step(steps, ["review", "appeal"]) is not None
