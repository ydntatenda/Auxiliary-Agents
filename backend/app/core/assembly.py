"""Assembled transcript builder.

The workflow's assembled_transcript is the ordered concatenation of every
ready source's assembled_text, with a labelled header per source so the
extractor can tell which fragment came from which artifact. This module is
the only writer of assembled_transcript on the workflow row.
"""
from __future__ import annotations

from uuid import UUID

from app.core.artifacts import write_text_artifact
from app.db.session import async_session
from app.db.sources import list_sources
from app.db.workflows import set_assembled_transcript


def _format_header(modality: str, label: str | None, role: str | None) -> str:
    bits = [modality]
    if role:
        bits.append(role)
    descriptor = ", ".join(bits)
    label_part = label or "(no label)"
    return f"=== Source: {label_part} ({descriptor}) ==="


async def assemble_transcript(workflow_id: UUID) -> str:
    async with async_session() as session:
        sources = await list_sources(session, workflow_id)

    parts: list[str] = []
    for source in sources:
        if source.status != "ready" or not source.assembled_text:
            continue
        header = _format_header(source.modality, source.label, source.contributor_role)
        parts.append(f"{header}\n{source.assembled_text.strip()}")

    assembled = "\n\n".join(parts)
    await set_assembled_transcript(workflow_id, assembled)
    if assembled:
        write_text_artifact(str(workflow_id), "assembled_transcript.txt", assembled)
    return assembled
