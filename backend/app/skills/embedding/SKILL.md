# embedding

Single-purpose skill that returns the embedding vector for a piece of text.
Used by the library to power semantic workflow search.

## Public surface

```python
async def embed_text(text: str) -> list[float]
```

Empty or whitespace-only input returns an empty list, never raises; the
caller treats "no embedding yet" and "input was blank" identically.

## Model choice

`text-embedding-3-small`. Cheap, fast, 1536 dimensions, perfectly adequate
for the < 1000 workflows the library will ever hold in this MVP. Override
via `OPENAI_EMBEDDING_MODEL`.

## Where this fits

After extraction sets a workflow's `description`, the background task in
`core/background.py` calls `embed_text(name + "\n" + description)` and
stores the result on `workflows.embedding`. The library search ranks
matches by cosine similarity computed in Python. If the workflow count
ever crosses a few hundred we move to pgvector and an ivfflat index.
