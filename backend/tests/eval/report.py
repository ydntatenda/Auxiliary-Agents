"""ScorerResult, EvalReport, and a terminal renderer.

The renderer aims for one fixed-width line per axis, with the optional
per-axis messages indented underneath, so a multi-fixture run stacks
cleanly. Everything here is pure formatting; no I/O.

When `format_report` is called with `show_gaps=True`, the rendered
output gains a diagnostic block listing every gap the extractor
actually surfaced, with severity and verbatim description, before the
axis lines. This is so a reviewer can see whether a missed gap was
genuinely not surfaced or was surfaced in different words.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExtractedGapView:
    """A single gap exactly as the extractor returned it.

    Carried on `EvalReport` so the diagnostic dump can render without
    plumbing the original Workflow through the renderer.
    """

    description: str
    severity: str
    step_id: str | None = None


@dataclass
class ScorerResult:
    """One axis's verdict.

    `passed` reflects whether the axis cleared its per-fixture
    threshold. `score` is 0..1 for downstream aggregation. `skipped`
    distinguishes a pass-by-default (the field or expectation does not
    apply) from a genuine pass; the renderer marks skipped axes with
    SKIP rather than PASS so the report does not look misleadingly
    green.
    """

    name: str
    passed: bool
    score: float
    details: dict[str, Any] = field(default_factory=dict)
    messages: list[str] = field(default_factory=list)
    skipped: bool = False


@dataclass
class EvalReport:
    fixture_id: str
    results: list[ScorerResult]
    extracted_gaps: list[ExtractedGapView] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(result.passed for result in self.results)


_AXIS_COL = 28


def _status_marker(result: ScorerResult) -> str:
    if result.skipped:
        return "SKIP"
    return "PASS" if result.passed else "FAIL"


def _format_axis_line(result: ScorerResult) -> str:
    name = result.name.ljust(_AXIS_COL)
    marker = _status_marker(result)
    head = f"  {name}{marker}  score={result.score:.2f}"
    extras = _axis_extras(result)
    if extras:
        head = f"{head}  {extras}"
    return head


def _axis_extras(result: ScorerResult) -> str:
    """Per-axis one-line summary built from the structured details."""
    name = result.name
    d = result.details
    if name == "step_count_band":
        band = d.get("band")
        count = d.get("count")
        if band is not None and count is not None:
            return f"count={count} (band {band[0]}-{band[1]})"
    if name == "gap_recall_severity":
        bits = []
        if "recall" in d:
            bits.append(f"recall={d['recall']:.2f}")
        if "severity_accuracy" in d:
            bits.append(f"severity={d['severity_accuracy']:.2f}")
        return " ".join(bits)
    if name == "terminal_correctness":
        bits = []
        if "precision" in d:
            bits.append(f"precision={d['precision']:.2f}")
        if "recall" in d:
            bits.append(f"recall={d['recall']:.2f}")
        return " ".join(bits)
    if name == "decision_rule_structure":
        if "preserved" in d and "total" in d:
            return f"preserved={d['preserved']}/{d['total']}"
    if name == "automatability":
        if not d.get("field_present"):
            return "field not yet defined on Step"
        return f"labelled={d.get('labelled', 0)}/{d.get('total', 0)}"
    return ""


def format_gap_dump(report: EvalReport) -> str:
    """Render the diagnostic block listing every extractor-surfaced gap.

    A quiet extractor produces a distinct line so its silence does not
    look like the absence of the flag itself.
    """
    if not report.extracted_gaps:
        return "  Extractor surfaced no gaps."
    lines = [f"  Extractor surfaced {len(report.extracted_gaps)} gaps:"]
    for view in report.extracted_gaps:
        lines.append(f'    [{view.severity}] "{view.description}"')
    return "\n".join(lines)


def format_report(report: EvalReport, *, show_gaps: bool = False) -> str:
    lines = [f"Fixture: {report.fixture_id}"]
    if show_gaps:
        lines.append(format_gap_dump(report))
    for result in report.results:
        lines.append(_format_axis_line(result))
        for message in result.messages:
            lines.append(f"    {message}")
    failing = sum(1 for r in report.results if not r.passed)
    if report.passed:
        lines.append(f"Overall: PASS (all {len(report.results)} axes passing)")
    else:
        lines.append(
            f"Overall: FAIL ({failing} of {len(report.results)} axes failing)"
        )
    return "\n".join(lines)


def report_to_dict(report: EvalReport) -> dict[str, Any]:
    return {
        "fixture_id": report.fixture_id,
        "passed": report.passed,
        "results": [
            {
                "name": r.name,
                "passed": r.passed,
                "score": r.score,
                "skipped": r.skipped,
                "details": r.details,
                "messages": r.messages,
            }
            for r in report.results
        ],
    }
