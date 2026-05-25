from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.workflows import load_workflow, require_workflow_row, update_status
from app.skills.diagram_review import apply_user_edit, to_mermaid
from app.skills.workflow_clarification.apply import apply_turn
from app.skills.workflow_clarification.types import ClarificationTurn

router = APIRouter(prefix="/workflows/{workflow_id}/review", tags=["review"])


class DiagramResponse(BaseModel):
    workflow_id: str
    status: str
    mermaid: str
    graph: dict


class EditPayload(BaseModel):
    instruction: str = Field(..., min_length=1)
    step_id: str | None = None


class EditResponse(BaseModel):
    summary: str | None
    mermaid: str
    graph: dict


class MutateResponse(BaseModel):
    warnings: list[str]
    mermaid: str
    graph: dict


class ApproveResponse(BaseModel):
    workflow_id: str
    status: str


@router.get("/diagram", response_model=DiagramResponse)
async def get_diagram(workflow_id: str, db: AsyncSession = Depends(get_db)) -> DiagramResponse:
    try:
        row = await require_workflow_row(db, workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if row.graph is None:
        raise HTTPException(
            status_code=409,
            detail="Workflow has no graph yet — finish extraction first.",
        )
    workflow = await load_workflow(workflow_id)
    return DiagramResponse(
        workflow_id=str(row.id),
        status=row.status,
        mermaid=to_mermaid(workflow),
        graph=workflow.model_dump(mode="json"),
    )


@router.post("/edit", response_model=EditResponse)
async def edit_diagram(
    workflow_id: str,
    payload: EditPayload,
    db: AsyncSession = Depends(get_db),
) -> EditResponse:
    try:
        await require_workflow_row(db, workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    turn = await apply_user_edit(workflow_id, payload.instruction, payload.step_id)
    workflow = await load_workflow(workflow_id)
    return EditResponse(
        summary=turn.finalize_reason,
        mermaid=to_mermaid(workflow),
        graph=workflow.model_dump(mode="json"),
    )


@router.post("/mutate", response_model=MutateResponse)
async def mutate_graph(
    workflow_id: str,
    turn: ClarificationTurn,
    db: AsyncSession = Depends(get_db),
) -> MutateResponse:
    """Apply a typed ClarificationTurn directly, no LLM in the loop.

    Used by the graph editor for deterministic UI actions (drag-to-connect,
    click-to-delete, etc.). The payload is the same `ClarificationTurn` schema
    used by the LLM-driven edit endpoint, just supplied by the client instead.
    """
    try:
        await require_workflow_row(db, workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    warnings = await apply_turn(workflow_id, turn)
    workflow = await load_workflow(workflow_id)
    return MutateResponse(
        warnings=warnings,
        mermaid=to_mermaid(workflow),
        graph=workflow.model_dump(mode="json"),
    )


@router.post("/approve", response_model=ApproveResponse)
async def approve_diagram(workflow_id: str, db: AsyncSession = Depends(get_db)) -> ApproveResponse:
    try:
        await require_workflow_row(db, workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await update_status(workflow_id=workflow_id, status="done")
    return ApproveResponse(workflow_id=workflow_id, status="done")
