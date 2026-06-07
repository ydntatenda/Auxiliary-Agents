"""Eval runner.

Reads a fixture (or a directory of fixtures), calls `extract_workflow`
once per fixture, runs every scorer in order, and prints a stacked
per-fixture report. Exit code is 0 when every axis on every fixture
passes (skips count as pass), 1 otherwise.

The runner is the only file in the harness that touches the live
extraction skill. CLAUDE.md rule 2 is preserved: extraction itself is a
skill, the runner is test-side orchestration, and nothing in api/ or
core/ has gained a new LLM call.

Invocation, from the backend/ directory:

    python -m tests.eval.runner tests/fixtures/citation_appeals
    python -m tests.eval.runner tests/fixtures/

The first runs one fixture. The second walks the directory, runs every
fixture.json under it, and stacks the reports.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from app.skills.workflow_extraction import extract_workflow

from .fixtures import (
    FixtureLoadError,
    LoadedFixture,
    build_assembled_transcript,
    discover_fixtures,
)
from .report import EvalReport, format_report
from .scorers import all_scorers


async def run_one(loaded: LoadedFixture) -> EvalReport:
    transcript = build_assembled_transcript(loaded)
    extracted = await extract_workflow(
        loaded.fixture.workflow_name,
        loaded.fixture.unit,
        transcript,
    )
    results = [
        scorer(extracted, loaded.fixture.scoring) for scorer in all_scorers()
    ]
    return EvalReport(fixture_id=loaded.fixture.id, results=results)


async def run_all(loaded: list[LoadedFixture]) -> list[EvalReport]:
    reports: list[EvalReport] = []
    for entry in loaded:
        reports.append(await run_one(entry))
    return reports


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if len(args) != 1:
        print(
            "usage: python -m tests.eval.runner <fixture-path-or-directory>",
            file=sys.stderr,
        )
        return 2
    path = Path(args[0]).resolve()
    try:
        loaded = discover_fixtures(path)
    except FixtureLoadError as exc:
        print(f"fixture load error: {exc}", file=sys.stderr)
        return 2
    if not loaded:
        print(f"no fixtures found at {path}", file=sys.stderr)
        return 2

    reports = asyncio.run(run_all(loaded))
    overall_pass = True
    for index, report in enumerate(reports):
        if index > 0:
            print()
        print(format_report(report))
        if not report.passed:
            overall_pass = False
    print()
    failing = sum(1 for r in reports if not r.passed)
    if overall_pass:
        print(f"All {len(reports)} fixtures passed.")
    else:
        print(f"{failing} of {len(reports)} fixtures failed.")
    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
