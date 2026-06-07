"""Round-trip tests for the fixture loader and the multi-source assembler.

These exercise the loader without an LLM, without a database, and
without the actual citation appeals content. The fixture data is built
inline in `tmp_path` so the test stays portable.
"""
import json
from pathlib import Path

import pytest

from tests.eval.fixtures import (
    Fixture,
    FixtureLoadError,
    GoldenStep,
    build_assembled_transcript,
    discover_fixtures,
    load_fixture,
)


def _minimal_fixture_payload(
    *, transcript_path: str = "transcript.txt", sources: list | None = None
) -> dict:
    payload: dict = {
        "id": "test_fixture",
        "description": "round-trip",
        "workflow_name": "Test workflow",
        "unit": "Test unit",
        "scoring": {
            "step_count_band": [3, 7],
            "expected_steps": [
                {
                    "concept": "intake",
                    "keywords": ["intake", "form"],
                    "terminal": False,
                }
            ],
            "expected_gaps": [],
        },
    }
    if sources is not None:
        payload["sources"] = sources
    else:
        payload["transcript_path"] = transcript_path
    return payload


def test_round_trip_single_source(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "fix1"
    fixture_dir.mkdir()
    (fixture_dir / "transcript.txt").write_text(
        "Operator describes a generic process.", encoding="utf-8"
    )
    (fixture_dir / "fixture.json").write_text(
        json.dumps(_minimal_fixture_payload()), encoding="utf-8"
    )

    loaded = load_fixture(fixture_dir)
    assert loaded.fixture.id == "test_fixture"
    assert loaded.base_dir == fixture_dir
    transcript = build_assembled_transcript(loaded)
    assert transcript == "Operator describes a generic process."


def test_round_trip_multi_source_uses_assembly_format(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "fix2"
    (fixture_dir / "sources").mkdir(parents=True)
    (fixture_dir / "sources" / "op.txt").write_text(
        "Operator walks through the steps.", encoding="utf-8"
    )
    (fixture_dir / "sources" / "policy.txt").write_text(
        "Approver describes the edge case.", encoding="utf-8"
    )
    payload = _minimal_fixture_payload(
        sources=[
            {
                "label": "operator walkthrough",
                "modality": "voice",
                "contributor_role": "operator",
                "transcript_path": "sources/op.txt",
            },
            {
                "label": "approver policy",
                "modality": "text",
                "contributor_role": "approver",
                "transcript_path": "sources/policy.txt",
            },
        ]
    )
    payload.pop("transcript_path", None)
    (fixture_dir / "fixture.json").write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_fixture(fixture_dir)
    transcript = build_assembled_transcript(loaded)

    # Both source bodies must appear, prefixed by headers in the live
    # assembly format. Joined by a blank line, in order.
    assert "=== Source: operator walkthrough (voice, operator) ===" in transcript
    assert "Operator walks through the steps." in transcript
    assert "=== Source: approver policy (text, approver) ===" in transcript
    assert "Approver describes the edge case." in transcript
    op_idx = transcript.index("operator walkthrough")
    approver_idx = transcript.index("approver policy")
    assert op_idx < approver_idx


def test_load_fixture_rejects_both_single_and_multi(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "bad"
    fixture_dir.mkdir()
    (fixture_dir / "transcript.txt").write_text("x", encoding="utf-8")
    (fixture_dir / "sources").mkdir()
    (fixture_dir / "sources" / "a.txt").write_text("y", encoding="utf-8")
    payload = _minimal_fixture_payload(
        sources=[
            {
                "label": "a",
                "modality": "text",
                "transcript_path": "sources/a.txt",
            }
        ]
    )
    payload["transcript_path"] = "transcript.txt"
    (fixture_dir / "fixture.json").write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(FixtureLoadError):
        load_fixture(fixture_dir)


def test_load_fixture_rejects_neither_set(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "bad2"
    fixture_dir.mkdir()
    payload = _minimal_fixture_payload()
    payload.pop("transcript_path", None)
    (fixture_dir / "fixture.json").write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(FixtureLoadError):
        load_fixture(fixture_dir)


def test_golden_step_requires_keywords() -> None:
    with pytest.raises(Exception):
        GoldenStep(concept="x", keywords=[])


def test_fixture_scoring_band_rejects_inverted_range(tmp_path: Path) -> None:
    payload = _minimal_fixture_payload()
    payload["scoring"]["step_count_band"] = [10, 5]
    with pytest.raises(Exception):
        Fixture.model_validate(payload)


def test_discover_fixtures_walks_directory(tmp_path: Path) -> None:
    for slug in ("alpha", "beta"):
        d = tmp_path / slug
        d.mkdir()
        (d / "transcript.txt").write_text("x", encoding="utf-8")
        payload = _minimal_fixture_payload()
        payload["id"] = slug
        (d / "fixture.json").write_text(json.dumps(payload), encoding="utf-8")

    found = discover_fixtures(tmp_path)
    ids = [lf.fixture.id for lf in found]
    assert ids == ["alpha", "beta"]


def test_discover_fixtures_single_directory_with_fixture(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "single"
    fixture_dir.mkdir()
    (fixture_dir / "transcript.txt").write_text("x", encoding="utf-8")
    (fixture_dir / "fixture.json").write_text(
        json.dumps(_minimal_fixture_payload()), encoding="utf-8"
    )
    found = discover_fixtures(fixture_dir)
    assert len(found) == 1


def test_discover_fixtures_empty_returns_empty(tmp_path: Path) -> None:
    assert discover_fixtures(tmp_path) == []
