import pytest

from app.skills.source_ingestion import IngestResult, ingest_source
from app.skills.source_ingestion.chat import assemble_chat_transcript


async def test_text_modality_returns_raw_text_unchanged() -> None:
    result = await ingest_source("text", raw_text="open the appeal and review it")
    assert isinstance(result, IngestResult)
    assert result.assembled_text == "open the appeal and review it"
    assert result.meta["char_count"] == len(result.assembled_text)


async def test_text_modality_requires_raw_text() -> None:
    with pytest.raises(ValueError):
        await ingest_source("text")


async def test_chat_modality_renders_clean_qna_transcript() -> None:
    messages = [
        {"role": "question", "content": "Who approves over £200?"},
        {"role": "answer", "content": "The assistant director."},
        {"role": "question", "content": "What is the SLA?"},
        {"role": "answer", "content": "Three business days."},
    ]
    result = await ingest_source("chat", chat_messages=messages)
    assert result.assembled_text == (
        "Q: Who approves over £200?\n"
        "A: The assistant director.\n"
        "Q: What is the SLA?\n"
        "A: Three business days."
    )
    assert result.meta["turn_count"] == 4


async def test_chat_modality_skips_empty_messages() -> None:
    result = await ingest_source(
        "chat",
        chat_messages=[
            {"role": "question", "content": ""},
            {"role": "answer", "content": "yes"},
        ],
    )
    assert result.assembled_text == "A: yes"
    assert result.meta["turn_count"] == 1


async def test_unknown_modality_raises() -> None:
    with pytest.raises(ValueError):
        await ingest_source("telepathy", raw_text="anything")


async def test_connector_modality_raises_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        await ingest_source("connector")


def test_assemble_chat_transcript_is_deterministic_and_does_not_call_llm() -> None:
    result = assemble_chat_transcript(
        [
            {"role": "question", "content": "x"},
            {"role": "answer", "content": "y"},
        ]
    )
    assert result.assembled_text == "Q: x\nA: y"
