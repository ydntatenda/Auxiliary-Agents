import inspect

from app.skills import (
    screen_analysis,
    sop_rendering,
    source_ingestion,
    voice_transcription,
    workflow_extraction,
)
from app.skills.workflow_clarification import ClarificationMessage, ClarificationResult, get_next_question


def test_skill_packages_export_public_contracts_only() -> None:
    assert workflow_extraction.__all__ == ["extract_workflow"]
    assert sop_rendering.__all__ == ["render_sop"]
    assert voice_transcription.__all__ == ["transcribe_audio"]
    assert screen_analysis.__all__ == ["analyze_screen_recording"]
    # source_ingestion exposes one public async function plus the typed result.
    assert set(source_ingestion.__all__) == {"ingest_source", "IngestResult"}


def test_clarification_package_exports_contract_types() -> None:
    assert inspect.isclass(ClarificationMessage)
    assert inspect.isclass(ClarificationResult)
    assert inspect.iscoroutinefunction(get_next_question)

