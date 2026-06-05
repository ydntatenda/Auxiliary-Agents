"""Typed structures the delta extraction skill produces and consumes.

DeltaResult is the structured-output shape the LLM emits. DeltaScope is
the input contract from the API: which steps the update is allowed to
touch. The apply layer enforces the scope independently of what the LLM
thinks it should change.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.models.graph import Gap, Step


class DeltaScope(BaseModel):
    scope: Literal["step", "section", "full"]
    step_ids: list[str] | None = None
    change_description: str | None = None


class DeltaResult(BaseModel):
    """What the delta extractor returns after reading the new transcript.

    `modified_steps` carry the new state for a step that already exists in
    the graph, keyed by `Step.id`. `added_steps` are brand new steps to
    insert. `removed_step_ids` reference existing step ids to delete.
    `new_gaps` are gaps the extractor discovered while reading the delta.
    `change_summary` is a one or two sentence plain-language description of
    what this update changed, used in the version timeline.
    """

    modified_steps: list[Step] = Field(default_factory=list)
    added_steps: list[Step] = Field(default_factory=list)
    removed_step_ids: list[str] = Field(default_factory=list)
    new_gaps: list[Gap] = Field(default_factory=list)
    change_summary: str = ""
