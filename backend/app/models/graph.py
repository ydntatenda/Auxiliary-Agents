from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DecisionRule(BaseModel):
    """A conditional that determines flow control between steps."""

    condition: str = Field(..., description="The condition in plain language")
    then_step_id: str = Field(..., description="Step ID to route to if true")
    else_step_id: str | None = Field(None, description="Step ID if false; null = continue")


class Step(BaseModel):
    id: str = Field(..., description="Stable identifier within this workflow")
    order: int
    title: str = Field(..., description="Short imperative title")
    description: str
    executor: Literal["human", "agent", "hybrid"] = "human"
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    decision_rules: list[DecisionRule] = Field(default_factory=list)
    approver: str | None = None
    tools_used: list[str] = Field(default_factory=list)
    notes: str | None = None
    terminal: bool = False


class Gap(BaseModel):
    id: str
    step_id: str | None = None
    field: str | None = None
    description: str
    severity: Literal["critical", "important", "minor"]
    resolved: bool = False
    resolution: str | None = None


class Workflow(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    description: str
    unit: str
    steps: list[Step]
    gaps: list[Gap] = Field(default_factory=list)
    source_modality: Literal["text", "voice", "screen"]
    source_transcript: str
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    def find_step(self, step_id: str) -> Step | None:
        return next((step for step in self.steps if step.id == step_id), None)

