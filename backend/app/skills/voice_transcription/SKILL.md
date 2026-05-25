# voice_transcription

Transcribes a recorded voice walkthrough (`.webm` from the browser MediaRecorder) into plain text.

## Public surface

```python
from app.skills.voice_transcription import transcribe_audio

text: str = await transcribe_audio(file_path)
```

`file_path` is a local filesystem path to the uploaded recording. Called from the background task in [core/background.py](../../core/background.py).

## Model

`whisper-1` (configurable via `OPENAI_TRANSCRIPTION_MODEL`). Plain audio-in, text-out. No diarization, no timestamps — this MVP is single-speaker narration.

## Why Whisper and not Gemini

Both can transcribe. Whisper is cheaper, lower-latency, and battle-tested for English speech in noisy conditions. Gemini is reserved for cases where audio + video need joint understanding (see [`screen_analysis/SKILL.md`](../screen_analysis/SKILL.md)).

## Inputs

Browser produces `audio/webm` via `MediaRecorder` ([VoiceRecorder.tsx](../../../../frontend/src/components/VoiceRecorder.tsx)). Whisper accepts webm directly — no transcoding needed.

## Failure modes

1. **Silent or near-silent recordings** return empty strings. The background task currently treats empty as success and writes it to `source_transcript`. Extraction then fails to produce a useful graph. If this becomes a recurring issue, validate non-empty output here and set `status="failed"`.
2. **Background noise** degrades quality but doesn't fail. Whisper is good with mediocre input.
3. **Files >25MB** are rejected by the OpenAI API. The browser recorder doesn't cap voice length — long sessions could hit this. Not currently enforced.

## Background execution

This skill is called by `transcribe_voice_capture` in [core/background.py](../../core/background.py), kicked off from `POST /capture/voice` via FastAPI `BackgroundTasks`. Fire-and-forget — no retry. Failures set `workflow.status="failed"`.

## When extending

- Add language detection / multi-language → pass `language` param to `client.audio.transcriptions.create`.
- Add diarization → switch to `whisper-large-v3` via another provider, or use `gpt-4o-transcribe` with a structured prompt. Diarization is meaningful only if workflows start involving multiple speakers (e.g. two employees walking through together).
- Add timestamps → request `response_format="verbose_json"` and pass through to extraction. Useful if extraction starts struggling with step ordering.
