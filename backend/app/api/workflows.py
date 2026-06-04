from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.artifacts import write_json_artifact, write_text_artifact
from app.db.session import get_db
from app.db.workflows import require_workflow_row, save_workflow
from app.models.graph import Workflow
from app.skills.workflow_extraction import extract_workflow


router = APIRouter(prefix="/workflows", tags=["workflows"])


class WorkflowStatusResponse(BaseModel):
    workflow_id: str
    status: str
    has_transcript: bool
    gaps_total: int = 0
    gaps_resolved: int = 0


class WorkflowResponse(BaseModel):
    workflow_id: str
    name: str
    unit: str
    assembled_transcript: str | None
    status: str
    graph: Workflow | None


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
) -> WorkflowResponse:
    try:
        row = await require_workflow_row(db, workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    graph = Workflow.model_validate(row.graph) if row.graph else None
    return WorkflowResponse(
        workflow_id=str(row.id),
        name=row.name,
        unit=row.unit,
        assembled_transcript=row.assembled_transcript,
        status=row.status,
        graph=graph,
    )


@router.get("/{workflow_id}/status", response_model=WorkflowStatusResponse)
async def get_status(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
) -> WorkflowStatusResponse:
    try:
        row = await require_workflow_row(db, workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    graph = Workflow.model_validate(row.graph) if row.graph else None
    gaps = graph.gaps if graph else []
    return WorkflowStatusResponse(
        workflow_id=str(row.id),
        status=row.status,
        has_transcript=bool(row.assembled_transcript),
        gaps_total=len(gaps),
        gaps_resolved=sum(1 for gap in gaps if gap.resolved),
    )


@router.post("/{workflow_id}/extract", response_model=Workflow)
async def extract(workflow_id: str, db: AsyncSession = Depends(get_db)) -> Workflow:
    try:
        row = await require_workflow_row(db, workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not row.assembled_transcript:
        raise HTTPException(status_code=409, detail="Assembled transcript is empty")
    if row.graph:
        return Workflow.model_validate(row.graph)

    row.status = "extracting"
    await db.commit()

    workflow = await extract_workflow(row.name, row.unit, row.assembled_transcript)
    workflow.id = row.id
    workflow.name = row.name
    workflow.unit = row.unit
    # The Pydantic graph still carries source_modality and source_transcript
    # because clarification, diagram, and SOP rendering read them. With
    # multi-source capture, the transcript is the assembled view and the
    # modality field stays as the extractor's placeholder; the truth lives in
    # workflow_sources.
    workflow.source_modality = "text"
    workflow.source_transcript = row.assembled_transcript
    workflow.created_at = row.created_at or datetime.now(timezone.utc)
    workflow.updated_at = datetime.now(timezone.utc)
    await save_workflow(workflow, status="clarifying")
    write_text_artifact(str(row.id), "assembled_transcript.txt", row.assembled_transcript)
    write_json_artifact(str(row.id), "extracted_workflow.json", workflow.model_dump(mode="json"))
    return workflow
