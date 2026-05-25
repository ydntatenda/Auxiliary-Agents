# screen_analysis

Converts a screen recording with voice narration into a chronological log of UI actions and spoken narration, ready for `workflow_extraction` to consume as a "transcript."

## Public surface

```python
from app.skills.screen_analysis import analyze_screen_recording

log: str = await analyze_screen_recording(file_path)
```

`file_path` is a local `.webm` produced by [ScreenRecorder.tsx](../../../../frontend/src/components/ScreenRecorder.tsx) (display media + mic, VP9, 5 fps, ≤15 min). Called from `analyze_screen_capture` in [core/background.py](../../core/background.py).

## Model

`gemini-2.5-pro` (configurable via `GEMINI_VIDEO_MODEL`). Uses the `genai` SDK: upload the video file, then `generate_content([uploaded, prompt])`.

## Why Gemini, not OpenAI

OpenAI's audio models don't do video understanding. GPT-4o accepts images but not video. Gemini 2.5 Pro natively ingests video + audio together — it sees UI clicks and hears narration in one pass. That joint understanding is essential: a narration like "I open the appeals tab" is meaningless without seeing *which* tab.

The split is deliberate: every other LLM call in this system goes through OpenAI. Don't unify "just to be tidy" — you'd lose video.

## Inputs and SDK quirks

- `client.files.upload` and `client.models.generate_content` are **sync** in the genai SDK. Both are wrapped in `asyncio.to_thread` to avoid blocking the event loop.
- Uploads can take several seconds for multi-minute recordings. The background task pattern hides this latency from the user — they see "transcribing" in the UI.
- Frontend caps recordings at 15 min / VP9 / 5 fps. The 5 fps choice trades motion smoothness for file size — Gemini doesn't need 30 fps to see clicks. Don't bump fps without checking ingestion cost.

## Output format (set by prompt)

Two interleaved tracks:

```
ACTIONS: [MM:SS] <actor> <verb> <object>
NARRATION: [MM:SS] "<verbatim quote>"
```

Plus a trailing `TOOLS:` line listing apps/systems used.

The output is fed into `workflow_extraction` as a transcript — the extraction prompt is told to treat text/voice/screen transcripts identically. So this skill's job is **to produce something that looks like a written walkthrough**, just richer.

## Prompt contract

- **Describe field values by role, not literal value.** "enters the appellant's name" not "enters Jennifer Martinez." PII leakage matters for citation data.
- **Mark unclear items** as `[unclear: <best guess>]` rather than fabricating.
- **No invented actions.** If it's not visible or audible, don't log it.

## Known failure modes

1. **Audio drift.** If narration runs ahead of or behind the action it describes, the interleaved timeline can mislead extraction. Mostly self-corrects because extraction looks at semantic flow, not exact timestamps.
2. **Long recordings hit Gemini limits.** The 15-min cap is conservative for 2.5 Pro but not unlimited. If users push limits, switch to chunked analysis.
3. **Off-screen actions** (Alt-Tab to another window not in capture) appear as gaps in the action log. Narration sometimes fills them in.
4. **PII leakage despite the prompt.** Model occasionally transcribes a visible name verbatim. Not currently scrubbed. If this matters, add a post-processing step here — don't push it onto extraction.

## When extending

- **Real-time analysis** (chunked upload during recording) → would require switching to Gemini's Live API. Big change; current batch flow is fine for MVP scale.
- **Multi-monitor capture** → browser MediaRecorder picks one display. To support multi-monitor, change `ScreenRecorder.tsx` and add reasoning in the prompt about per-monitor context.
- **Screenshot extraction at key moments** → would benefit the SOP rendering step (visual references in the final doc). Currently the screenshots aren't surfaced anywhere downstream.
