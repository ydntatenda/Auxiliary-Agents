from uuid import UUID

from app.core.artifacts import write_text_artifact
from app.db.workflows import update_status
from app.skills.screen_analysis import analyze_screen_recording
from app.skills.voice_transcription import transcribe_audio


async def transcribe_voice_capture(workflow_id: UUID, file_path: str) -> None:
    try:
        transcript = await transcribe_audio(file_path)
        await update_status(workflow_id=workflow_id, status="transcribed", source_transcript=transcript)
        write_text_artifact(str(workflow_id), "source_transcript.txt", transcript)
    except Exception:
        await update_status(workflow_id=workflow_id, status="failed")
        raise


async def analyze_screen_capture(workflow_id: UUID, file_path: str) -> None:
    try:
        transcript = await analyze_screen_recording(file_path)
        await update_status(workflow_id=workflow_id, status="transcribed", source_transcript=transcript)
        write_text_artifact(str(workflow_id), "source_transcript.txt", transcript)
    except Exception:
        await update_status(workflow_id=workflow_id, status="failed")
        raise
