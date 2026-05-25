from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import capture, clarify, review, sop, workflows
from app.config import get_settings
from app.skills.workflow_clarification import active_clarification_model


settings = get_settings()

app = FastAPI(title="Agentic Ops MVP", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(capture.router)
app.include_router(workflows.router)
app.include_router(clarify.router)
app.include_router(review.router)
app.include_router(sop.router)


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "clarification": active_clarification_model(),
    }

