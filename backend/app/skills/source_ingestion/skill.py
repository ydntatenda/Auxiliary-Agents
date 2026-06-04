"""Source ingestion skill.

One public async function, `ingest_source`, dispatches on modality to an
internal registry. Each modality maps a raw artifact (text, audio file,
video file, document file, structured chat) into a single assembled string
plus a small metadata dictionary. The workflow's assembled_transcript is
the ordered concatenation of every ready source's assembled_text.

The registry is the single place a future connector slots in. Today's
modalities reuse the existing voice and screen skills directly; documents
and chat are implemented here because they are general capabilities, not
per-customer integrations.
"""
from __future__ import annotations

from typing import Awaitable, Callable

from pydantic import BaseModel, Field

from app.skills.screen_analysis import analyze_screen_recording
from app.skills.voice_transcription import transcribe_audio

from .chat import assemble_chat_transcript
from .document import ingest_document


class IngestResult(BaseModel):
    assembled_text: str
    meta: dict = Field(default_factory=dict)


IngestFn = Callable[..., Awaitable[IngestResult]]


async def _ingest_text(
    *,
    raw_path: str | None,
    raw_text: str | None,
    chat_messages: list[dict] | None,
) -> IngestResult:
    if raw_text is None:
        raise ValueError("text modality requires raw_text")
    return IngestResult(assembled_text=raw_text, meta={"char_count": len(raw_text)})


async def _ingest_voice(
    *,
    raw_path: str | None,
    raw_text: str | None,
    chat_messages: list[dict] | None,
) -> IngestResult:
    if not raw_path:
        raise ValueError("voice modality requires raw_path")
    transcript = await transcribe_audio(raw_path)
    return IngestResult(
        assembled_text=transcript,
        meta={"char_count": len(transcript)},
    )


async def _ingest_screen(
    *,
    raw_path: str | None,
    raw_text: str | None,
    chat_messages: list[dict] | None,
) -> IngestResult:
    if not raw_path:
        raise ValueError("screen modality requires raw_path")
    transcript = await analyze_screen_recording(raw_path)
    return IngestResult(
        assembled_text=transcript,
        meta={"char_count": len(transcript)},
    )


async def _ingest_document(
    *,
    raw_path: str | None,
    raw_text: str | None,
    chat_messages: list[dict] | None,
) -> IngestResult:
    if not raw_path:
        raise ValueError("document modality requires raw_path")
    return await ingest_document(raw_path)


async def _ingest_chat(
    *,
    raw_path: str | None,
    raw_text: str | None,
    chat_messages: list[dict] | None,
) -> IngestResult:
    if chat_messages is None:
        raise ValueError("chat modality requires chat_messages")
    return assemble_chat_transcript(chat_messages)


async def _ingest_connector(
    *,
    raw_path: str | None,
    raw_text: str | None,
    chat_messages: list[dict] | None,
) -> IngestResult:
    raise NotImplementedError(
        "connector ingestion is the future seam for Slack / Drive / T2 Flex. "
        "No implementation yet, by design."
    )


_REGISTRY: dict[str, IngestFn] = {
    "text": _ingest_text,
    "voice": _ingest_voice,
    "screen": _ingest_screen,
    "document": _ingest_document,
    "chat": _ingest_chat,
    "connector": _ingest_connector,
}


SUPPORTED_MODALITIES = tuple(_REGISTRY.keys())


async def ingest_source(
    modality: str,
    *,
    raw_path: str | None = None,
    raw_text: str | None = None,
    chat_messages: list[dict] | None = None,
) -> IngestResult:
    handler = _REGISTRY.get(modality)
    if handler is None:
        raise ValueError(
            f"unknown source modality {modality!r}; expected one of {SUPPORTED_MODALITIES}"
        )
    return await handler(
        raw_path=raw_path,
        raw_text=raw_text,
        chat_messages=chat_messages,
    )
