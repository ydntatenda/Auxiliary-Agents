"""Chat source ingestion.

A chat source is a structured list of question/answer turns (typically the
discovery dialogue the operator just had with the system). The ingestor
flattens it into a clean narrative transcript that reads the same way a
voice walkthrough would, so extraction can treat every source identically.

This is intentionally deterministic, no LLM call. The dialogue is already
clean text; the only job here is shaping.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .skill import IngestResult


def assemble_chat_transcript(messages: list[dict]) -> "IngestResult":
    from .skill import IngestResult  # local import avoids circular dep at module load

    lines: list[str] = []
    turn_count = 0
    for message in messages:
        role = (message.get("role") or "").strip().lower()
        content = (message.get("content") or "").strip()
        if not content:
            continue
        if role == "question":
            lines.append(f"Q: {content}")
        elif role == "answer":
            lines.append(f"A: {content}")
        else:
            lines.append(content)
        turn_count += 1

    assembled = "\n".join(lines)
    return IngestResult(
        assembled_text=assembled,
        meta={"turn_count": turn_count, "char_count": len(assembled)},
    )
