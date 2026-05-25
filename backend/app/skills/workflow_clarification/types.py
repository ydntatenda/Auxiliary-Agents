from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

_STRICT = ConfigDict(extra="forbid")


class ClarificationMessage(BaseModel):
    role: Literal["question", "answer"]
    content: str
    created_at: datetime


class ClarificationResult(BaseModel):
    question: str | None
    done: bool
    message: str | None = None


class StepPatch(BaseModel):
    """Overwrite a single scalar (string) field on one step."""

    model_config = _STRICT

    step_id: str
    field: Literal["approver", "description", "notes", "title"]
    value: str


class StepListAppend(BaseModel):
    """Append one item to a list field on a step (inputs, outputs, or tools_used)."""

    model_config = _STRICT

    step_id: str
    field: Literal["inputs", "outputs", "tools_used"]
    value: str


class NewDecisionRule(BaseModel):
    """Add a conditional branch from one step to another. Both step IDs must already exist."""

    model_config = _STRICT

    step_id: str
    condition: str
    then_step_id: str
    else_step_id: str | None = None


class GapResolution(BaseModel):
    """Close a gap once the user's answer has been applied to the graph."""

    model_config = _STRICT

    gap_id: str
    resolution: str


class StepFlag(BaseModel):
    """Set a boolean flag on a step (currently only `terminal`)."""

    model_config = _STRICT

    step_id: str
    field: Literal["terminal"]
    value: bool


class NewStep(BaseModel):
    """Add a new step to the workflow. Order is appended at the end if not specified."""

    model_config = _STRICT

    step_id: str
    title: str
    description: str = ""
    approver: str | None = None
    terminal: bool = False


class DecisionRuleEdit(BaseModel):
    """Modify an existing decision rule on a step, identified by its position index in the
    step's `decision_rules` list. Fields set to null are left unchanged. To clear
    else_step_id (set it back to None), pass the sentinel string '__null__'."""

    model_config = _STRICT

    step_id: str
    rule_index: int
    condition: str | None = None
    then_step_id: str | None = None
    else_step_id: str | None = None


class RemovedDecisionRule(BaseModel):
    """Delete a specific decision rule from a step, identified by its position index."""

    model_config = _STRICT

    step_id: str
    rule_index: int


class ClarificationTurn(BaseModel):
    """One turn of clarification: apply prior answer, then ask the next question or finalize.

    Termination is a typed field, not prose: set next_question=null and populate
    finalize_reason to end the clarification loop. Never write completion text into
    next_question.
    """

    model_config = _STRICT

    scalar_patches: list[StepPatch] = Field(default_factory=list)
    list_appends: list[StepListAppend] = Field(default_factory=list)
    new_decision_rules: list[NewDecisionRule] = Field(default_factory=list)
    decision_rule_edits: list[DecisionRuleEdit] = Field(default_factory=list)
    removed_decision_rules: list[RemovedDecisionRule] = Field(default_factory=list)
    step_flags: list[StepFlag] = Field(default_factory=list)
    new_steps: list[NewStep] = Field(default_factory=list)
    removed_step_ids: list[str] = Field(default_factory=list)
    resolved_gaps: list[GapResolution] = Field(default_factory=list)
    next_question: str | None = None
    finalize_reason: str | None = None
