"""Runner test with a stubbed extractor.

Verifies the orchestration end to end without an OpenAI key: the runner
loads a fixture, calls a fake `extract_workflow` that returns a
hand-built Workflow, runs every scorer, prints a stacked report, and
returns the right exit code. The fixture content is built in `tmp_path`
so the test does not depend on the actual citation-appeals fixture
landing yet.
"""
import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.models.graph import DecisionRule, Gap, Step, Workflow
from tests.eval import runner
from tests.eval.fixtures import LoadedFixture, load_fixture
from tests.eval.report import EvalReport, format_report


def _good_extracted() -> Workflow:
    return Workflow(
        name="test workflow",
        description="",
        unit="test unit",
        source_modality="text",
        source_transcript="x",
        steps=[
            Step(
                id="intake",
                order=1,
                title="receive the citation appeal",
                description="intake form arrives",
            ),
            Step(
                id="decide",
                order=2,
                title="decide on the appeal outcome",
                description="three branches",
                decision_rules=[
                    DecisionRule(condition="grant", then_step_id="grant"),
                    DecisionRule(condition="deny", then_step_id="deny"),
                ],
            ),
            Step(
                id="deny",
                order=3,
                title="deny the appeal",
                description="closes the path",
                terminal=True,
            ),
        ],
        gaps=[
            Gap(
                id="g1",
                description="Threshold for senior approval is unclear.",
                severity="critical",
            )
        ],
    )


def _bad_extracted() -> Workflow:
    """Same shape but with the terminal flag stripped and one branch only."""
    return Workflow(
        name="test workflow",
        description="",
        unit="test unit",
        source_modality="text",
        source_transcript="x",
        steps=[
            Step(
                id="intake",
                order=1,
                title="receive the citation appeal",
                description="x",
            ),
            Step(
                id="decide",
                order=2,
                title="decide on the appeal outcome",
                description="flattened",
                decision_rules=[
                    DecisionRule(condition="grant", then_step_id="grant"),
                ],
            ),
            Step(id="deny", order=3, title="deny the appeal", description="x"),
        ],
        gaps=[],
    )


def _scoring_payload() -> dict:
    return {
        "step_count_band": [2, 4],
        "expected_steps": [
            {"concept": "intake", "keywords": ["receive", "appeal"]},
            {
                "concept": "outcome_decision",
                "keywords": ["decide", "appeal outcome"],
                "has_decision_rules": True,
                "expected_min_branches": 2,
            },
            {"concept": "deny", "keywords": ["deny", "appeal"], "terminal": True},
        ],
        "expected_gaps": [
            {
                "concept": "approval_threshold",
                "keywords": ["threshold", "senior approval"],
                "severity": "critical",
            }
        ],
        "gap_recall_threshold": 0.8,
        "gap_severity_threshold": 0.8,
        "terminal_threshold": 0.8,
        "decision_rule_threshold": 0.8,
    }


def _build_fixture(tmp_path: Path, slug: str) -> Path:
    fixture_dir = tmp_path / slug
    fixture_dir.mkdir(parents=True)
    (fixture_dir / "transcript.txt").write_text(
        "Operator describes the workflow.", encoding="utf-8"
    )
    payload = {
        "id": slug,
        "description": "synthetic for runner test",
        "workflow_name": "Test workflow",
        "unit": "Test unit",
        "transcript_path": "transcript.txt",
        "scoring": _scoring_payload(),
    }
    (fixture_dir / "fixture.json").write_text(json.dumps(payload), encoding="utf-8")
    return fixture_dir


async def test_run_one_with_good_extraction_passes(tmp_path, monkeypatch) -> None:
    fixture_dir = _build_fixture(tmp_path, "good")
    monkeypatch.setattr(runner, "extract_workflow", AsyncMock(return_value=_good_extracted()))
    loaded = load_fixture(fixture_dir)
    report = await runner.run_one(loaded)
    assert isinstance(report, EvalReport)
    assert report.passed is True
    # Five axes: step_count, gaps, terminal, decision, automatability (skip).
    assert len(report.results) == 5


async def test_run_one_with_bad_extraction_fails(tmp_path, monkeypatch) -> None:
    fixture_dir = _build_fixture(tmp_path, "bad")
    monkeypatch.setattr(runner, "extract_workflow", AsyncMock(return_value=_bad_extracted()))
    loaded = load_fixture(fixture_dir)
    report = await runner.run_one(loaded)
    assert report.passed is False
    failing_names = {r.name for r in report.results if not r.passed}
    # The bad workflow drops the terminal flag and flattens the decision.
    assert "terminal_correctness" in failing_names
    assert "decision_rule_structure" in failing_names


def test_main_single_fixture_pass(tmp_path, monkeypatch, capsys) -> None:
    fixture_dir = _build_fixture(tmp_path, "good")
    monkeypatch.setattr(runner, "extract_workflow", AsyncMock(return_value=_good_extracted()))
    code = runner.main([str(fixture_dir)])
    captured = capsys.readouterr()
    assert code == 0
    assert "Fixture: good" in captured.out
    assert "Overall: PASS" in captured.out


def test_main_directory_runs_all_stacked(tmp_path, monkeypatch, capsys) -> None:
    _build_fixture(tmp_path, "alpha")
    _build_fixture(tmp_path, "beta")
    monkeypatch.setattr(runner, "extract_workflow", AsyncMock(return_value=_good_extracted()))
    code = runner.main([str(tmp_path)])
    captured = capsys.readouterr()
    assert code == 0
    assert "Fixture: alpha" in captured.out
    assert "Fixture: beta" in captured.out
    assert "All 2 fixtures passed." in captured.out


def test_main_directory_one_fails_overall_fails(tmp_path, monkeypatch, capsys) -> None:
    _build_fixture(tmp_path, "alpha")
    _build_fixture(tmp_path, "beta")
    call_count = {"n": 0}

    async def alternating(name, unit, transcript):
        call_count["n"] += 1
        return _good_extracted() if call_count["n"] == 1 else _bad_extracted()

    monkeypatch.setattr(runner, "extract_workflow", alternating)
    code = runner.main([str(tmp_path)])
    captured = capsys.readouterr()
    assert code == 1
    assert "fixtures failed." in captured.out


def test_main_no_fixtures_returns_2(tmp_path, capsys) -> None:
    code = runner.main([str(tmp_path)])
    captured = capsys.readouterr()
    assert code == 2
    assert "no fixtures found" in captured.err


def test_main_bad_usage_returns_2(capsys) -> None:
    code = runner.main([])
    captured = capsys.readouterr()
    assert code == 2
    assert "usage:" in captured.err


def test_format_report_renders_skip_and_pass(tmp_path, monkeypatch) -> None:
    fixture_dir = _build_fixture(tmp_path, "good")
    monkeypatch.setattr(runner, "extract_workflow", AsyncMock(return_value=_good_extracted()))
    loaded = load_fixture(fixture_dir)
    report = asyncio.run(runner.run_one(loaded))
    rendered = format_report(report)
    # Five axes lines; automatability is a skip.
    assert "SKIP" in rendered
    assert "PASS" in rendered
    assert "Fixture: good" in rendered
