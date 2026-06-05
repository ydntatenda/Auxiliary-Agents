from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.core.artifacts import write_text_artifact
from app.core.pdf import markdown_to_pdf_bytes
from app.core.sop_cache import SopRenderError, render_or_load_sop
from app.db.session import async_session
from app.db.workflows import require_workflow_row
from app.models.graph import Workflow


router = APIRouter(prefix="/workflows/{workflow_id}/sop", tags=["sop"])


async def _resolve_markdown(workflow_id: str) -> tuple[str, Workflow]:
    """Return (markdown, workflow) for a workflow, using the cache when valid.

    Opens one session, fetches the row, asks the SOP cache coordinator
    for the markdown (which renders fresh and writes the cache fields if
    they're stale), commits, and returns the result. The artifact mirror
    and any HTTP packaging happen outside this helper.
    """
    async with async_session() as session:
        try:
            row = await require_workflow_row(session, workflow_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        try:
            markdown, _cache_hit = await render_or_load_sop(row)
        except SopRenderError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        workflow = Workflow.model_validate(row.graph)
        await session.commit()
    return markdown, workflow


@router.get("")
async def get_sop(workflow_id: str) -> dict[str, str]:
    markdown, workflow = await _resolve_markdown(workflow_id)
    write_text_artifact(str(workflow.id), "sop.md", markdown)
    return {"workflow_id": str(workflow.id), "sop": markdown}


@router.get("/download")
async def download_sop(workflow_id: str) -> Response:
    markdown, workflow = await _resolve_markdown(workflow_id)
    write_text_artifact(str(workflow.id), "sop.md", markdown)
    filename = f"{workflow.name.lower().replace(' ', '-')}-sop.md"
    return Response(
        content=markdown,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/pdf")
async def download_sop_pdf(workflow_id: str) -> Response:
    markdown, workflow = await _resolve_markdown(workflow_id)
    write_text_artifact(str(workflow.id), "sop.md", markdown)
    pdf_bytes = markdown_to_pdf_bytes(markdown, title=workflow.name, unit=workflow.unit)
    filename = f"{workflow.name.lower().replace(' ', '-')}-sop.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
