from typing import Literal

from pydantic import BaseModel, Field


class EvidenceRef(BaseModel):
    source: str
    excerpt: str


class SkillClaim(BaseModel):
    name: str
    level: Literal["foundational", "working", "advanced", "expert"] = "working"
    evidence: list[EvidenceRef] = Field(default_factory=list)


class ExperienceItem(BaseModel):
    organisation: str | None = None
    role: str
    period: str | None = None
    achievements: list[str] = Field(default_factory=list)
    evidence: list[EvidenceRef] = Field(default_factory=list)


class Qualification(BaseModel):
    name: str
    issuer: str | None = None
    date: str | None = None
    evidence: list[EvidenceRef] = Field(default_factory=list)


class ExtractedWorkerProfile(BaseModel):
    name: str
    current_role: str | None = None
    summary: str
    skills: list[SkillClaim] = Field(default_factory=list)
    experience: list[ExperienceItem] = Field(default_factory=list)
    qualifications: list[Qualification] = Field(default_factory=list)
    career_preferences: list[str] = Field(default_factory=list)


class AutomationOpportunity(BaseModel):
    step_id: str
    step_title: str
    disposition: Literal["human", "assist", "automate_with_approval", "automate"]
    automation_score: int = Field(ge=0, le=100)
    rationale: str
    evidence: list[str] = Field(default_factory=list)
    required_capabilities: list[str] = Field(default_factory=list)
    controls: list[str] = Field(default_factory=list)


class WorkflowGap(BaseModel):
    description: str
    severity: Literal["critical", "important", "minor"]
    evidence: list[str] = Field(default_factory=list)
    proposed_resolution: str


class RoleTransition(BaseModel):
    worker_id: str
    worker_name: str
    current_role: str | None = None
    proposed_role: str
    retained_responsibilities: list[str] = Field(default_factory=list)
    removed_or_assisted_tasks: list[str] = Field(default_factory=list)
    new_responsibilities: list[str] = Field(default_factory=list)
    transferable_skills: list[str] = Field(default_factory=list)
    development_needs: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    requires_human_review: bool = True


class OrganisationalAssessment(BaseModel):
    workflow_id: str
    executive_summary: str
    current_state_risks: list[str] = Field(default_factory=list)
    opportunities: list[AutomationOpportunity] = Field(default_factory=list)
    gaps: list[WorkflowGap] = Field(default_factory=list)
    role_transitions: list[RoleTransition] = Field(default_factory=list)
    future_workflow: list[str] = Field(default_factory=list)
    knowledge_updates: list[str] = Field(default_factory=list)
    success_metrics: list[str] = Field(default_factory=list)
    deployment_prerequisites: list[str] = Field(default_factory=list)
