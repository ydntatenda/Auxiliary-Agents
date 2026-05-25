from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.artifacts import write_json_artifact
from app.db.session import get_db
from app.db.workflows import (
    load_clarification_history,
    log_clarification_message,
    require_workflow_row,
    update_status,
)
from app.skills.workflow_clarification import (
    ClarificationMessage,
    ClarificationResult,
    get_next_question,
)


router = APIRouter(prefix="/workflows/{workflow_id}/clarify", tags=["clarification"])


class AnswerPayload(BaseModel):
    answer: str = Field(..., min_length=1)


class ClarifyResponse(BaseModel):
    question: str | None
    done: bool
    message: str | None = None


def _to_messages(rows: list) -> list[ClarificationMessage]:
    return [
        ClarificationMessage(role=row.role, content=row.content, created_at=row.created_at)
        for row in rows
    ]


def _latest_open_question(history: list[ClarificationMessage]) -> str | None:
    if history and history[-1].role == "question":
        return history[-1].content
    return None


@router.post("", response_model=ClarifyResponse)
async def start_clarification(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
) -> ClarifyResponse:
    try:
        await require_workflow_row(db, workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    history = _to_messages(await load_clarification_history(db, workflow_id))
    open_question = _latest_open_question(history)
    if open_question:
        return ClarifyResponse(question=open_question, done=False)

    result: ClarificationResult = await get_next_question(workflow_id, history)
    if result.done:
        await update_status(workflow_id=workflow_id, status="reviewing")
    elif result.question:
        await log_clarification_message(db, workflow_id, "question", result.question)
    write_json_artifact(workflow_id, "latest_clarification_result.json", result.model_dump(mode="json"))
    return ClarifyResponse(**result.model_dump())


@router.post("/answer", response_model=ClarifyResponse)
async def submit_answer(
    workflow_id: str,
    payload: AnswerPayload,
    db: AsyncSession = Depends(get_db),
) -> ClarifyResponse:
    try:
        await require_workflow_row(db, workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    await log_clarification_message(db, workflow_id, "answer", payload.answer)
    history = _to_messages(await load_clarification_history(db, workflow_id))
    result: ClarificationResult = await get_next_question(workflow_id, history)
    if result.done:
        await update_status(workflow_id=workflow_id, status="reviewing")
    elif result.question:
        await log_clarification_message(db, workflow_id, "question", result.question)
    write_json_artifact(workflow_id, "latest_clarification_result.json", result.model_dump(mode="json"))
    return ClarifyResponse(**result.model_dump())
