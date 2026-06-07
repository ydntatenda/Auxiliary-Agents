"""Fixture types and loader.

A fixture is a workflow name, a unit, either a single transcript file or
an ordered list of sources, plus a `scoring` block that the scorers read
to decide pass / fail.

The transcript the extractor sees is built here. For a multi-source
fixture we reuse `_format_header` from `app.core.assembly` so the bytes
the eval feeds to the extractor are identical to what the live pipeline
would produce. That import is intentional: the cache key for "what the
extractor reads" should not drift between production and the eval.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.core.assembly import _format_header


# -- Pydantic types ---------------------------------------------------


class GoldenStep(BaseModel):
    """One step the eval expects to find in the extracted graph.

    `concept` is a stable handle used in reports; it never has to appear
    in the extracted graph. `keywords` must all match (case-insensitive
    substring) inside the candidate's title + description. Keep keyword
    lists discriminating: a single generic word like 'review' or 'check'
    will collide with multiple steps and produce false matches.
    """

    concept: str
    keywords: list[str]
    terminal: bool = False
    has_decision_rules: bool = False
    expected_min_branches: int = 0

    @model_validator(mode="after")
    def _discriminating_keywords(self) -> "GoldenStep":
        if not self.keywords:
            raise ValueError(
                f"golden step {self.concept!r} needs at least one keyword"
            )
        return self


class GoldenGap(BaseModel):
    concept: str
    keywords: list[str]
    severity: Literal["critical", "important", "minor"]

    @model_validator(mode="after")
    def _discriminating_keywords(self) -> "GoldenGap":
        if not self.keywords:
            raise ValueError(
                f"golden gap {self.concept!r} needs at least one keyword"
            )
        return self


class FixtureScoring(BaseModel):
    """Per-fixture scoring expectations. All thresholds inline."""

    step_count_band: tuple[int, int]
    expected_steps: list[GoldenStep] = Field(default_factory=list)
    expected_gaps: list[GoldenGap] = Field(default_factory=list)
    gap_recall_threshold: float = 0.8
    gap_severity_threshold: float = 0.8
    terminal_threshold: float = 0.8
    decision_rule_threshold: float = 0.8

    @model_validator(mode="after")
    def _band_well_formed(self) -> "FixtureScoring":
        lo, hi = self.step_count_band
        if lo < 0 or hi < lo:
            raise ValueError(
                f"step_count_band {self.step_count_band!r} is not a valid range"
            )
        return self


class FixtureSource(BaseModel):
    label: str
    modality: Literal["text", "voice", "screen", "document", "chat"]
    contributor_role: Literal["operator", "approver", "observer"] | None = None
    transcript_path: str


class Fixture(BaseModel):
    id: str
    description: str
    workflow_name: str
    unit: str
    transcript_path: str | None = None
    sources: list[FixtureSource] | None = None
    scoring: FixtureScoring

    @model_validator(mode="after")
    def _exactly_one_transcript_shape(self) -> "Fixture":
        single = self.transcript_path is not None
        multi = self.sources is not None and len(self.sources) > 0
        if single == multi:
            raise ValueError(
                "fixture must set exactly one of transcript_path or sources"
            )
        return self


@dataclass
class LoadedFixture:
    """A parsed Fixture paired with the directory its transcripts resolve against."""

    fixture: Fixture
    base_dir: Path

    @property
    def id(self) -> str:
        return self.fixture.id


# -- Loader -----------------------------------------------------------


class FixtureLoadError(ValueError):
    pass


def load_fixture(path: Path) -> LoadedFixture:
    """Load a single fixture.json into a LoadedFixture.

    `path` may be the fixture.json file itself or its parent directory.
    """
    fixture_file = _resolve_fixture_file(path)
    try:
        payload = json.loads(fixture_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise FixtureLoadError(
            f"{fixture_file}: invalid JSON: {exc.msg}"
        ) from exc
    try:
        fixture = Fixture.model_validate(payload)
    except Exception as exc:  # noqa: BLE001  Pydantic raises ValidationError
        raise FixtureLoadError(f"{fixture_file}: {exc}") from exc
    return LoadedFixture(fixture=fixture, base_dir=fixture_file.parent)


def discover_fixtures(path: Path) -> list[LoadedFixture]:
    """Find every fixture under `path`.

    A path that points at a fixture.json (or a directory containing one
    at its root) yields exactly one fixture. A path that points at a
    directory without a fixture.json walks recursively and loads every
    fixture.json found, sorted by id for stable reporting.
    """
    if path.is_file():
        return [load_fixture(path)]
    direct = path / "fixture.json"
    if direct.exists():
        return [load_fixture(direct)]
    found = sorted(path.rglob("fixture.json"))
    if not found:
        return []
    loaded = [load_fixture(p) for p in found]
    loaded.sort(key=lambda lf: lf.id)
    return loaded


def _resolve_fixture_file(path: Path) -> Path:
    if path.is_dir():
        candidate = path / "fixture.json"
        if not candidate.exists():
            raise FixtureLoadError(
                f"{path} does not contain a fixture.json"
            )
        return candidate
    if not path.exists():
        raise FixtureLoadError(f"{path} does not exist")
    return path


# -- Transcript builder ----------------------------------------------


def build_assembled_transcript(loaded: LoadedFixture) -> str:
    """Return the string the extractor will read.

    For a single-source fixture we return the file contents unchanged.
    For a multi-source fixture we replicate the assembly the live
    pipeline produces, header-per-source, joined by a blank line.
    """
    fixture = loaded.fixture
    if fixture.transcript_path is not None:
        return _read_transcript(loaded.base_dir, fixture.transcript_path)
    assert fixture.sources is not None  # guarded by the validator
    parts: list[str] = []
    for source in fixture.sources:
        text = _read_transcript(loaded.base_dir, source.transcript_path).strip()
        if not text:
            continue
        header = _format_header(source.modality, source.label, source.contributor_role)
        parts.append(f"{header}\n{text}")
    return "\n\n".join(parts)


def _read_transcript(base_dir: Path, relative: str) -> str:
    target = (base_dir / relative).resolve()
    try:
        return target.read_text(encoding="utf-8")
    except OSError as exc:
        raise FixtureLoadError(
            f"transcript file {target} could not be read: {exc}"
        ) from exc
