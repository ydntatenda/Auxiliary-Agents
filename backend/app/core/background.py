"""Background source ingestion with bounded retry.

A failed Whisper or Gemini call must not lose the raw artifact (which is
already on disk). We retry the skill call with exponential backoff up to
INGEST_MAX_ATTEMPTS times, and on terminal failure persist the error on
the source row so the operator can hit the retry endpoint without
re-uploading. Re-running ingestion overwrites assembled_text; it never
appends, so retries are idempotent.
"""
from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from app.core.assembly import assemble_transcript
from app.db.sources import get_source_raw_path, update_source_status
from app.skills.source_ingestion import IngestResult, ingest_source


logger = logging.getLogger(__name__)

INGEST_MAX_ATTEMPTS = 3
INGEST_BACKOFF_SECONDS = 2.0


async def ingest_source_task(
    workflow_id: UUID,
    source_id: UUID,
    modality: str,
    *,
    raw_path: str | None = None,
    raw_text: str | None = None,
    chat_messages: list[dict] | None = None,
) -> None:
    """Run the source ingestion skill, then refresh the assembled transcript.

    Always finishes by either marking the source 'ready' (and updating the
    cached assembled_transcript on the workflow) or 'failed' (preserving
    the error so a retry can pick up from the same raw_path).
    """
    await update_source_status(source_id=source_id, status="processing")
    last_error: Exception | None = None

    for attempt in range(1, INGEST_MAX_ATTEMPTS + 1):
        try:
            result: IngestResult = await ingest_source(
                modality,
                raw_path=raw_path,
                raw_text=raw_text,
                chat_messages=chat_messages,
            )
            await update_source_status(
                source_id=source_id,
                status="ready",
                assembled_text=result.assembled_text,
                meta=result.meta,
                error=None,
            )
            await assemble_transcript(workflow_id)
            return
        except NotImplementedError:
            raise
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            logger.warning(
                "source ingestion failed (attempt %s/%s) for source %s: %s",
                attempt,
                INGEST_MAX_ATTEMPTS,
                source_id,
                exc,
            )
            if attempt < INGEST_MAX_ATTEMPTS:
                await asyncio.sleep(INGEST_BACKOFF_SECONDS * attempt)

    await update_source_status(
        source_id=source_id,
        status="failed",
        error=str(last_error) if last_error else "unknown ingestion error",
    )


async def retry_source_ingestion(workflow_id: UUID, source_id: UUID) -> None:
    """Re-run ingestion for a source using its saved raw_path.

    Chat and text sources cannot be retried this way because their input is
    not on disk; for those, the operator deletes and re-adds.
    """
    modality, raw_path = await get_source_raw_path(source_id)
    if modality in {"text", "chat"}:
        raise ValueError(
            "retry only works for sources with a saved raw artifact "
            "(voice, screen, document)"
        )
    await ingest_source_task(
        workflow_id=workflow_id,
        source_id=source_id,
        modality=modality,
        raw_path=raw_path,
    )
