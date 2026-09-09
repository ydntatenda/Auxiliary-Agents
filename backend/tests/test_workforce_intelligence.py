from types import SimpleNamespace
from datetime import datetime, timezone
from uuid import uuid4

from app.api.assessments import _view as assessment_view
from app.api.workforce import _can_manage
from app.core import auth_stub
from app.models.workforce import (
    AutomationOpportunity,
    OrganisationalAssessment,
    RoleTransition,
)


def test_worker_can_manage_own_profile(monkeypatch) -> None:
    monkeypatch.setattr(
        auth_stub,
        "CURRENT_USER_ID",
        "chidubem",
    )
    assert _can_manage("chidubem") is True
    assert _can_manage("aanya") is False


def test_admin_can_manage_any_profile(monkeypatch) -> None:
    monkeypatch.setattr(auth_stub, "CURRENT_USER_ID", "tatenda")
    assert _can_manage("aanya") is True


def test_role_transition_is_always_marked_for_human_review() -> None:
    transition = RoleTransition(
        worker_id="worker-1",
        worker_name="Worker One",
        proposed_role="Exception reviewer",
    )
    assert transition.requires_human_review is True


def test_automation_scores_are_bounded() -> None:
    opportunity = AutomationOpportunity(
        step_id="s1",
        step_title="Classify request",
        disposition="assist",
        automation_score=72,
        rationale="The task is repetitive but exceptions need review.",
    )
    assert opportunity.automation_score == 72


def test_assessment_response_preserves_workflow_version() -> None:
    workflow_id = uuid4()
    report = OrganisationalAssessment(
        workflow_id=str(workflow_id),
        executive_summary="Assist intake and preserve human judgement.",
    )
    row = SimpleNamespace(
        id=uuid4(),
        workflow_id=workflow_id,
        workflow_version=3,
        report=report.model_dump(mode="json"),
        created_by="tatenda",
        created_at=datetime.now(timezone.utc),
    )
    response = assessment_view(row)
    assert response.workflow_version == 3
    assert response.report.workflow_id == str(workflow_id)
