# source_ingestion

Why this skill exists rather than per-modality ingestion in `api/capture.py`:
a workflow has many sources of many shapes, and the set of shapes is going
to grow (Slack threads, Drive folders, T2 Flex exports). One typed function
behind a registry keeps every modality on the same interface, so a future
connector slots in by adding a row to the registry, not by re-architecting
capture.

## Public surface

```python
async def ingest_source(
    modality: str,
    *,
    raw_path: str | None = None,
    raw_text: str | None = None,
    chat_messages: list[dict] | None = None,
) -> IngestResult
```

Returns a Pydantic `IngestResult` with `assembled_text: str` and `meta: dict`.
The assembly step (in `api/capture.py`) concatenates every ready source's
`assembled_text` in `order` to produce the workflow's
`assembled_transcript`, which is the only input extraction reads.

## Modalities

- **text** -- returns `raw_text` unchanged, meta carries `char_count`.
- **voice** -- delegates to `voice_transcription.transcribe_audio` (Whisper).
- **screen** -- delegates to `screen_analysis.analyze_screen_recording` (Gemini).
- **document** -- PDF via pypdf, docx via python-docx, images via Gemini.
  Scanned PDFs (where pypdf returns empty text on every page) fall back to
  sending the PDF straight to Gemini for OCR-style read. Meta carries
  `ocr_used` and `page_count`.
- **chat** -- structured Q&A list rendered as a clean `Q:`/`A:` transcript.
  Deterministic, no LLM call.
- **connector** -- raises `NotImplementedError`. The seam exists so that a
  Slack or Drive connector lands as one new dispatch entry, not as new
  branching in the API layer.

## Model split

OpenAI keeps text and audio (text passthrough, Whisper). Gemini gets images
and video. PDFs only reach Gemini when the embedded-text path comes up
empty; born-digital PDFs stay entirely local.

## Failure model

Each handler raises on bad input or on an upstream API failure. The
background task in `core/background.py` wraps the call with bounded retry
and writes terminal `failed` status with an error message if all attempts
fail. Re-running ingestion on the same source overwrites `assembled_text`
cleanly, never appends, so retries are idempotent.

## Not in scope

Live connectors. The connector handler is a `NotImplementedError` until
the first real integration ships.
