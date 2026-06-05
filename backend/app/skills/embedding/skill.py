"""Embedding skill.

Wraps OpenAI's text-embedding-3-small. The library uses this to power
semantic search across workflow names and descriptions. Stored on the
workflow row as a JSONB column for now; if the library outgrows naive
cosine similarity in Python we move to pgvector or a vector store.
"""
from __future__ import annotations

from app.config import get_settings
from app.services.openai_client import get_openai_client


async def embed_text(text: str) -> list[float]:
    """Return the embedding vector for a piece of text.

    Empty or whitespace-only text returns an empty list, so callers can
    treat "no embedding yet" and "tried but text was empty" the same way.
    """
    cleaned = text.strip()
    if not cleaned:
        return []
    client = get_openai_client()
    settings = get_settings()
    response = await client.embeddings.create(
        model=settings.openai_embedding_model,
        input=cleaned,
    )
    return list(response.data[0].embedding)
