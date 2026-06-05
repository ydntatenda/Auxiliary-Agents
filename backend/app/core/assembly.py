"""Assembled transcript builder.

The workflow's assembled_transcript is the ordered concatenation of every
ready source's assembled_text, with a labelled header per source so the
extractor can tell which fragment came from which artifact. This module is
the only writer of assembled_transcript on the workflow row, and it does
the read and the write inside one session so the cached value is always
atomic with the source rows that produced it.
"""
from __future__ import annotations

from uuid import UUID

from app.core.artifacts import write_text_artifact
from app.db.session import async_session
from app.db.sources import list_sources
from app.db.workflows import require_workflow_row


def _format_header(modality: str, label: str | None, role: str | None) -> str:
    bits = [modality]
    if role:
        bits.append(role)
    descriptor = ", ".join(bits)
    label_part = label or "(no label)"
    return f"=== Source: {label_part} ({descriptor}) ==="


async def assemble_transcript(workflow_id: UUID) -> str:
    """Rebuild the workflow's assembled_transcript from its ready sources.

    Read and write share one AsyncSession, so the cached transcript is
    committed in the same transaction that observed the sources. Without
    this, a concurrent source mutation between the read and the write
    could leave the cache reflecting a state that no single point in time
    ever held.

    The artifact file write happens after the commit on purpose: the
    transcript on disk is a debugging convenience, not part of the
    database invariant, and we do not want a file-system error to abort a
    transaction that successfully captured the truth.
    """
    async with async_session() as session:
        sources = await list_sources(session, workflow_id)

        parts: list[str] = []
        for source in sources:
            if source.status != "ready" or not source.assembled_text:
                continue
            header = _format_header(
                source.modality, source.label, source.contributor_role
            )
            parts.append(f"{header}\n{source.assembled_text.strip()}")
        assembled = "\n\n".join(parts)

        row = await require_workflow_row(session, workflow_id)
        row.assembled_transcript = assembled
        await session.commit()

    if assembled:
        write_text_artifact(str(workflow_id), "assembled_transcript.txt", assembled)
    return assembled
