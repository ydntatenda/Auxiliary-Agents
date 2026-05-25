from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.core.artifacts import write_text_artifact
from app.core.pdf import markdown_to_pdf_bytes
from app.db.workflows import load_workflow
from app.skills.sop_rendering import render_sop


router = APIRouter(prefix="/workflows/{workflow_id}/sop", tags=["sop"])


@router.get("")
async def get_sop(workflow_id: str) -> dict[str, str]:
    try:
        workflow = await load_workflow(workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    markdown = await render_sop(workflow)
    write_text_artifact(str(workflow.id), "sop.md", markdown)
    return {"workflow_id": str(workflow.id), "sop": markdown}


@router.get("/download")
async def download_sop(workflow_id: str) -> Response:
    try:
        workflow = await load_workflow(workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    markdown = await render_sop(workflow)
    write_text_artifact(str(workflow.id), "sop.md", markdown)
    filename = f"{workflow.name.lower().replace(' ', '-')}-sop.md"
    return Response(
        content=markdown,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/pdf")
async def download_sop_pdf(workflow_id: str) -> Response:
    try:
        workflow = await load_workflow(workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    markdown = await render_sop(workflow)
    write_text_artifact(str(workflow.id), "sop.md", markdown)
    pdf_bytes = markdown_to_pdf_bytes(markdown, title=workflow.name, unit=workflow.unit)
    filename = f"{workflow.name.lower().replace(' ', '-')}-sop.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
