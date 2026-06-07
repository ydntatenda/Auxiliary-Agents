"""Five pure scorers, one per evaluation axis.

Each scorer takes the extracted `Workflow` and the fixture's `scoring`
block, returns a `ScorerResult`, and never touches the network, the
database, or the file system. They are designed to be exercised with
hand-built `Workflow` instances in unit tests, so scorer logic is
verifiable without an LLM call.

Pairing extracted steps and gaps to golden ones uses keyword
conjunction by substring: every keyword in the golden entry's list must
appear (case-insensitive) in the candidate's title + description (for
steps) or description (for gaps). Discriminating keyword lists are the
fixture author's responsibility; the loader rejects empty lists, and the
spec calls out that a single generic word will cause false matches.
"""
from __future__ import annotations

import re
from collections import Counter

from app.models.graph import Gap, Step, Workflow

from .fixtures import FixtureScoring, GoldenGap, GoldenStep
from .report import ScorerResult


# -- Matching primitives ---------------------------------------------


def _match_step(steps: list[Step], keywords: list[str]) -> Step | None:
    if not keywords:
        return None
    needles = [kw.lower() for kw in keywords]
    for step in steps:
        haystack = f"{step.title}\n{step.description}".lower()
        if all(needle in haystack for needle in needles):
            return step
    return None


def _match_gap(gaps: list[Gap], keywords: list[str]) -> Gap | None:
    if not keywords:
        return None
    needles = [kw.lower() for kw in keywords]
    for gap in gaps:
        haystack = gap.description.lower()
        if all(needle in haystack for needle in needles):
            return gap
    return None


# -- Axis 1: step count band ----------------------------------------


def score_step_count_band(
    extracted: Workflow, scoring: FixtureScoring
) -> ScorerResult:
    count = len(extracted.steps)
    lo, hi = scoring.step_count_band
    passed = lo <= count <= hi
    if passed:
        score = 1.0
    else:
        distance = lo - count if count < lo else count - hi
        band_width = max(hi - lo, 1)
        score = max(0.0, 1.0 - distance / band_width)

    near_dups = _near_duplicate_prefixes(extracted.steps)

    details = {
        "count": count,
        "band": [lo, hi],
        "near_duplicate_prefixes": near_dups,
    }
    messages: list[str] = []
    if not passed:
        messages.append(
            f"extracted step count {count} is outside band [{lo}, {hi}]"
        )
    if near_dups:
        dup_count = sum(n for _, n in near_dups)
        messages.append(
            f"{dup_count} steps share leading words with another step; possible "
            f"concatenation of overlapping sources rather than reconciliation"
        )
    return ScorerResult(
        name="step_count_band",
        passed=passed,
        score=round(score, 3),
        details=details,
        messages=messages,
    )


_WORD_RE = re.compile(r"[a-z0-9]+")


def _near_duplicate_prefixes(
    steps: list[Step], prefix_words: int = 3
) -> list[tuple[str, int]]:
    """Group steps by the first `prefix_words` words of their title.

    Returns groups with two or more members. The signal is informational,
    not part of the band's pass condition.
    """
    prefixes: list[str] = []
    for step in steps:
        tokens = _WORD_RE.findall(step.title.lower())
        if not tokens:
            continue
        prefixes.append(" ".join(tokens[:prefix_words]))
    counter = Counter(prefixes)
    return [(prefix, n) for prefix, n in counter.items() if n >= 2]


# -- Axis 2: gap recall + severity accuracy --------------------------


def score_gap_recall_severity(
    extracted: Workflow, scoring: FixtureScoring
) -> ScorerResult:
    expected = scoring.expected_gaps
    if not expected:
        return ScorerResult(
            name="gap_recall_severity",
            passed=True,
            score=1.0,
            details={"recall": 1.0, "severity_accuracy": 1.0, "total": 0},
            messages=["fixture declares no expected gaps; axis skipped"],
            skipped=True,
        )

    matched = 0
    correct_severity = 0
    per_gap: list[dict] = []
    for golden in expected:
        match = _match_gap(extracted.gaps, golden.keywords)
        if match is None:
            per_gap.append(
                {
                    "concept": golden.concept,
                    "matched": False,
                    "severity_expected": golden.severity,
                    "severity_found": None,
                }
            )
            continue
        matched += 1
        severity_ok = match.severity == golden.severity
        if severity_ok:
            correct_severity += 1
        per_gap.append(
            {
                "concept": golden.concept,
                "matched": True,
                "severity_expected": golden.severity,
                "severity_found": match.severity,
                "severity_correct": severity_ok,
            }
        )

    total = len(expected)
    recall = matched / total
    severity_accuracy = correct_severity / matched if matched else 0.0
    passed = (
        recall >= scoring.gap_recall_threshold
        and severity_accuracy >= scoring.gap_severity_threshold
    )
    score = (recall + severity_accuracy) / 2

    messages: list[str] = []
    if recall < scoring.gap_recall_threshold:
        messages.append(
            f"gap recall {recall:.2f} below threshold {scoring.gap_recall_threshold:.2f}"
        )
    if matched and severity_accuracy < scoring.gap_severity_threshold:
        messages.append(
            f"severity accuracy {severity_accuracy:.2f} below threshold "
            f"{scoring.gap_severity_threshold:.2f}"
        )
    for entry in per_gap:
        if not entry["matched"]:
            messages.append(
                f"gap \"{entry['concept']}\" not matched in extracted graph"
            )
        elif not entry.get("severity_correct", True):
            messages.append(
                f"gap \"{entry['concept']}\" matched, severity expected "
                f"{entry['severity_expected']}, found {entry['severity_found']}"
            )

    return ScorerResult(
        name="gap_recall_severity",
        passed=passed,
        score=round(score, 3),
        details={
            "recall": round(recall, 3),
            "severity_accuracy": round(severity_accuracy, 3),
            "matched": matched,
            "total": total,
            "per_gap": per_gap,
        },
        messages=messages,
    )


# -- Axis 3: terminal correctness ------------------------------------


def score_terminal_correctness(
    extracted: Workflow, scoring: FixtureScoring
) -> ScorerResult:
    golden_steps = scoring.expected_steps
    golden_terminals = [g for g in golden_steps if g.terminal]
    if not golden_terminals and not any(s.terminal for s in extracted.steps):
        return ScorerResult(
            name="terminal_correctness",
            passed=True,
            score=1.0,
            details={"note": "no expected or extracted terminals"},
            messages=["no terminal expectations in fixture; axis skipped"],
            skipped=True,
        )

    tp = 0
    fn = 0
    fp = 0
    per_step: list[dict] = []
    matched_extracted_ids: set[str] = set()

    for golden in golden_steps:
        match = _match_step(extracted.steps, golden.keywords)
        entry = {
            "concept": golden.concept,
            "golden_terminal": golden.terminal,
            "matched": match is not None,
        }
        if match is None:
            if golden.terminal:
                fn += 1
            entry["extracted_terminal"] = None
            per_step.append(entry)
            continue
        matched_extracted_ids.add(match.id)
        entry["extracted_terminal"] = match.terminal
        entry["matched_step_title"] = match.title
        if golden.terminal and match.terminal:
            tp += 1
        elif golden.terminal and not match.terminal:
            fn += 1
        elif not golden.terminal and match.terminal:
            fp += 1
        per_step.append(entry)

    # Extracted terminals that did not match any golden concept are
    # treated as unknown, not as false positives, so the eval does not
    # punish workflows that surface steps the fixture did not enumerate.

    extracted_terminal_count = tp + fp
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    precision = tp / extracted_terminal_count if extracted_terminal_count else 1.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    passed = f1 >= scoring.terminal_threshold

    messages: list[str] = []
    if recall < 1.0:
        for entry in per_step:
            if entry["golden_terminal"] and not entry.get("extracted_terminal"):
                if entry["matched"]:
                    messages.append(
                        f"golden terminal \"{entry['concept']}\" matched step "
                        f"\"{entry['matched_step_title']}\" but not flagged terminal"
                    )
                else:
                    messages.append(
                        f"golden terminal \"{entry['concept']}\" not matched in extracted graph"
                    )
    for entry in per_step:
        if not entry["golden_terminal"] and entry.get("extracted_terminal"):
            messages.append(
                f"step \"{entry['matched_step_title']}\" marked terminal but golden "
                f"concept \"{entry['concept']}\" is non-terminal"
            )

    return ScorerResult(
        name="terminal_correctness",
        passed=passed,
        score=round(f1, 3),
        details={
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "per_step": per_step,
        },
        messages=messages,
    )


# -- Axis 4: decision-rule structure ---------------------------------


def score_decision_rule_structure(
    extracted: Workflow, scoring: FixtureScoring
) -> ScorerResult:
    golden_decisions = [g for g in scoring.expected_steps if g.has_decision_rules]
    if not golden_decisions:
        return ScorerResult(
            name="decision_rule_structure",
            passed=True,
            score=1.0,
            details={"note": "no expected decision points"},
            messages=["fixture declares no decision points; axis skipped"],
            skipped=True,
        )

    preserved = 0
    per_decision: list[dict] = []
    for golden in golden_decisions:
        match = _match_step(extracted.steps, golden.keywords)
        if match is None:
            per_decision.append(
                {
                    "concept": golden.concept,
                    "matched": False,
                    "expected_min_branches": golden.expected_min_branches,
                    "found_branches": 0,
                    "flattened_to_one": False,
                    "preserved": False,
                }
            )
            continue
        branches = len(match.decision_rules)
        ok = branches >= golden.expected_min_branches
        if ok:
            preserved += 1
        per_decision.append(
            {
                "concept": golden.concept,
                "matched": True,
                "matched_step_title": match.title,
                "expected_min_branches": golden.expected_min_branches,
                "found_branches": branches,
                "flattened_to_one": branches == 1 and golden.expected_min_branches >= 2,
                "preserved": ok,
            }
        )

    total = len(golden_decisions)
    score = preserved / total
    passed = score >= scoring.decision_rule_threshold

    messages: list[str] = []
    if not passed:
        messages.append(
            f"decision-rule preservation {score:.2f} below threshold "
            f"{scoring.decision_rule_threshold:.2f}"
        )
    for entry in per_decision:
        if entry.get("flattened_to_one"):
            messages.append(
                f"decision point \"{entry['concept']}\" flattened to a single "
                f"branch (expected at least {entry['expected_min_branches']})"
            )
        elif entry["matched"] and not entry["preserved"]:
            messages.append(
                f"decision point \"{entry['concept']}\" has {entry['found_branches']} "
                f"branches (expected at least {entry['expected_min_branches']})"
            )
        elif not entry["matched"]:
            messages.append(
                f"decision point \"{entry['concept']}\" not matched in extracted graph"
            )

    return ScorerResult(
        name="decision_rule_structure",
        passed=passed,
        score=round(score, 3),
        details={"preserved": preserved, "total": total, "per_decision": per_decision},
        messages=messages,
    )


# -- Axis 5: automatability label coverage ---------------------------


def _has_automatability_field() -> bool:
    """Indirection so unit tests can simulate the field's later arrival."""
    return "automatability" in Step.model_fields


def score_automatability(
    extracted: Workflow, scoring: FixtureScoring
) -> ScorerResult:
    if not _has_automatability_field():
        return ScorerResult(
            name="automatability",
            passed=True,
            score=1.0,
            details={"field_present": False},
            messages=[
                "automatability field not yet defined on Step; check skipped"
            ],
            skipped=True,
        )
    total = len(extracted.steps)
    if total == 0:
        return ScorerResult(
            name="automatability",
            passed=True,
            score=1.0,
            details={"field_present": True, "labelled": 0, "total": 0},
            messages=["no extracted steps to label; axis skipped"],
            skipped=True,
        )
    labelled = sum(
        1
        for step in extracted.steps
        if getattr(step, "automatability", None) is not None
    )
    score = labelled / total
    passed = score >= 1.0
    messages: list[str] = []
    if not passed:
        unlabelled = [
            step.title
            for step in extracted.steps
            if getattr(step, "automatability", None) is None
        ]
        messages.append(
            f"{len(unlabelled)} of {total} steps missing automatability label"
        )
        for title in unlabelled[:3]:
            messages.append(f"step \"{title}\" missing automatability")
    return ScorerResult(
        name="automatability",
        passed=passed,
        score=round(score, 3),
        details={"field_present": True, "labelled": labelled, "total": total},
        messages=messages,
    )


# -- Public composite -----------------------------------------------


def all_scorers() -> list:
    """Ordered list of scorer callables. The runner calls these in order."""
    return [
        score_step_count_band,
        score_gap_recall_severity,
        score_terminal_correctness,
        score_decision_rule_structure,
        score_automatability,
    ]


__all__ = [
    "all_scorers",
    "score_step_count_band",
    "score_gap_recall_severity",
    "score_terminal_correctness",
    "score_decision_rule_structure",
    "score_automatability",
    "GoldenStep",
    "GoldenGap",
]
