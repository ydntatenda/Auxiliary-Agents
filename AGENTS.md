# AGENTS.md

Guide for LLM agents working in this repo. Read this first.

## What this project is

**Agentic Ops MVP** turns an employee's walkthrough (text, voice, or screen recording) into a structured workflow graph, then into a polished SOP markdown document. The first target user is Georgia Tech Parking & Transportation; the domain is citation appeal processing.

The pipeline is linear:

```
capture → transcribe (voice/screen only) → extract → clarify (multi-turn) → render SOP
```

The **workflow graph** (`backend/app/models/graph.py`) is the source of truth. Everything else — extraction, clarification, SOP rendering — reads or mutates this graph. Persisted as JSONB on the `workflows` table.

## Hard architectural rules

These exist because the codebase will rot fast if they're broken. If a change would violate one, stop and surface the conflict.

1. **One public function per skill.** Each `backend/app/skills/<name>/` package exposes exactly one typed `async` function via `__init__.py`. API and core code import only that function — never internals.
2. **API/orchestration never calls LLMs directly.** All LLM work goes through a skill. If you're tempted to add an OpenAI call in `api/` or `core/`, it belongs in a skill.
3. **The workflow graph is the source of truth.** Don't introduce a parallel representation. New step metadata goes on the `Step` / `Workflow` Pydantic models in `models/graph.py`.
4. **Graph mutations during clarification go through the agent tools** in `skills/workflow_clarification/tools.py` — not direct DB writes from API code. The tools enforce field whitelists and step-existence checks.
5. **Clarification is the only Agents SDK flow.** Extraction and rendering are plain `client.responses` calls. Don't promote them to agents without a reason.
6. **LLM model split is intentional:** OpenAI (GPT-5, Whisper) for text and audio; Gemini 2.5 Pro for video. Don't unify without discussion — Gemini's video understanding is load-bearing for screen capture.

## Layout

```
backend/app/
  api/           FastAPI routes (capture, workflows, clarify, sop). Thin — orchestration only.
  core/          Background task runners, artifact filesystem helpers.
  db/            Async SQLAlchemy session + workflow CRUD. Alembic migrations.
  models/        Pydantic graph (graph.py) + SQLAlchemy tables (db.py).
  services/      LLM client singletons (openai_client, gemini_client).
  skills/        LLM capabilities. See per-skill SKILL.md.
  config.py      Pydantic Settings, env-driven.
  main.py        FastAPI app + CORS + router registration.

frontend/src/
  pages/         Stage components: Capture, Processing, Clarify, Sop. No URL routing — App.tsx owns stage state.
  components/    TextCapture, VoiceRecorder, ScreenRecorder.
  api/client.ts  Typed fetch wrapper. 1:1 with backend endpoints.
```

## Per-skill docs

When editing or extending a skill, read its `SKILL.md` first. Each one documents *why* — model choice, prompt rationale, known failure modes — not *what*, since the code already shows that.

- [`workflow_extraction/SKILL.md`](backend/app/skills/workflow_extraction/SKILL.md)
- [`workflow_clarification/SKILL.md`](backend/app/skills/workflow_clarification/SKILL.md)
- [`sop_rendering/SKILL.md`](backend/app/skills/sop_rendering/SKILL.md)
- [`voice_transcription/SKILL.md`](backend/app/skills/voice_transcription/SKILL.md)
- [`screen_analysis/SKILL.md`](backend/app/skills/screen_analysis/SKILL.md)
- [`diagram_review/SKILL.md`](backend/app/skills/diagram_review/SKILL.md)

## State machine

Workflow `status` progresses through:

```
capturing → transcribing → transcribed → extracting → clarifying → done
                                                                 ↘ failed
```

- `text` capture skips transcription and lands directly at `transcribed`.
- `voice` / `screen` capture transcribes in a fire-and-forget `BackgroundTask`. No retries — failures set `status="failed"`.
- Extraction is triggered explicitly by `POST /workflows/{id}/extract`. The frontend calls this after polling `/status` sees `transcribed`.
- Clarification mutates the graph in-place per turn. `done=True` returns when the agent calls `finalize_clarification` or no critical/important gaps remain.

## Local dev

```bash
cp backend/.env.example backend/.env.local   # add OPENAI_API_KEY, GOOGLE_API_KEY
docker compose up --build
docker compose exec backend alembic upgrade head
# frontend at http://localhost:5173, backend at http://localhost:8000
```

## Conventions

- Backend: Python 3.12+, async everywhere (SQLAlchemy async, OpenAI async client). No sync DB calls.
- Models: Pydantic v2 for graph types, SQLAlchemy 2.0 declarative for tables.
- Frontend: React + TypeScript + Vite + Tailwind. No state-management library — `useState` in `App.tsx` is the global store.
- Artifacts (transcripts, extracted JSON, SOP) write to `./artifacts/workflows/{id}/` on local FS. No cloud storage yet.
- IDs are UUIDs generated server-side. The frontend never mints workflow IDs.

## Gotchas

- **Clarification history is server-persisted but the UI doesn't refetch it.** The `Clarify` page rebuilds the visible chat from local React state — refreshing mid-flow drops the visible history (the DB row stays).
- **SOP markdown is re-rendered on every GET** — no caching. Calling `/sop` repeatedly bills OpenAI repeatedly.
- **`finalize_clarification` is signaled via a `ContextVar`,** not the agent's return value. If you refactor the clarification runner, preserve `reset_finalize_reason()` / `get_finalize_reason()` around the `Runner.run` call.
- **Screen recordings cap at 15 min, 5 fps, VP9.** Set in `ScreenRecorder.tsx`. Gemini handles the rest.
- **The `Workflow` Pydantic model is what OpenAI parses into** via `responses.parse(text_format=Workflow)`. Changing the model changes the extraction contract — bump prompts if you add required fields.

## What not to do

- Don't add a second public function to a skill package.
- Don't write to `workflow.graph` directly from API code during clarification. Use the tools.
- Don't introduce LangChain, CrewAI, or another agent framework — clarification is committed to OpenAI Agents SDK.
- Don't add retry logic to background tasks without also adding idempotency to the skills.
- Don't create documentation files unless explicitly asked.
