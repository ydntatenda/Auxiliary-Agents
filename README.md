# Auxiliary Agents

**Capture an operational walkthrough. Get back a structured workflow graph and a polished SOP.**

A typed pipeline that turns how an employee actually does a recurring task — described by text, voice, or screen recording — into a machine-readable workflow graph, then into a clean Standard Operating Procedure. First production target: Georgia Tech Parking & Transportation citation appeals.

```
capture (text / voice / screen) → transcribe → extract graph → clarify → render SOP
```

- **Capture**: paste a typed walkthrough, record a voice narration, or record your screen + mic.
- **Transcribe**: voice → OpenAI Whisper; screen → Gemini 2.5 Pro (video + audio in one pass).
- **Extract**: structured-output LLM call turns the transcript into a typed `Workflow` graph (steps, inputs/outputs, decision rules, gaps).
- **Clarify**: an Agents-SDK clarification loop asks targeted questions about gaps and patches the graph in place through a typed tool surface.
- **Render**: GPT writes a markdown SOP from the finalized graph.

Architecture rules and per-skill design notes live in [AGENTS.md](AGENTS.md) and the `SKILL.md` file inside each `backend/app/skills/*/` folder.

## Repository layout

```
backend/         FastAPI + Pydantic v2 + SQLAlchemy 2.0 (async) + Alembic
frontend/        React + TypeScript + Vite + Tailwind
AA/              Earlier standalone HTML/JSX prototype of the capture flow (kept for reference)
docker-compose.yml
AGENTS.md        Architectural rules + per-skill index
```

## Prerequisites

The easiest path is **Docker Desktop** — installed once, runs everything (Postgres + backend + frontend) with one command. If you'd rather run locally without Docker, see [Local development without Docker](#local-development-without-docker) below.

You will need API keys for at least:

| Provider | Required for | Where to get it |
|---|---|---|
| **OpenAI** | extraction, clarification, SOP rendering, voice transcription | https://platform.openai.com/api-keys |
| **Google AI Studio** | screen recording analysis (skip if you only use text/voice) | https://aistudio.google.com/apikey |
| **OpenRouter** (optional) | running clarification through alternative models like Claude or Kimi | https://openrouter.ai/keys |

## Quick start (Docker)

```bash
# 1. Clone
git clone https://github.com/<your-username>/Auxiliary-Agents.git
cd Auxiliary-Agents

# 2. Create a local secrets file (gitignored)
cp backend/.env.example backend/.env.local
# Edit backend/.env.local and fill in:
#   OPENAI_API_KEY=sk-...
#   GOOGLE_API_KEY=...               (only if using screen capture)
#   OPENROUTER_API_KEY=sk-or-...     (only if using OpenRouter)

# 3. Start everything
docker compose up --build

# 4. In a second terminal, run migrations once
docker compose exec backend alembic upgrade head

# 5. Open the app
open http://localhost:5173
```

The backend will be reachable at http://localhost:8000 and Postgres on `localhost:5432`.

## Verify it's working

```bash
curl http://localhost:8000/health | jq
```

Expected output (model values may differ depending on your config):

```json
{
  "status": "ok",
  "clarification": {
    "provider": "openai",
    "model": "gpt-5.4"
  }
}
```

Then visit http://localhost:5173, click **Text**, paste a short walkthrough (a paragraph describing how you do a recurring task), and step through capture → processing → clarify → SOP.

## Configuration

Configuration is loaded from `backend/.env` (template defaults) and `backend/.env.local` (your secrets and overrides). `.env.local` takes precedence and is gitignored — **never put API keys in `.env.example`**.

### Required

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | All OpenAI calls (extraction, rendering, transcription, default clarification). |
| `GOOGLE_API_KEY` | Required only if you use screen-recording capture (Gemini handles video). |

### Models (defaults shown — override as needed)

| Variable | Default | Used by |
|---|---|---|
| `OPENAI_EXTRACTION_MODEL` | `gpt-5.4` | Workflow extraction |
| `OPENAI_RENDER_MODEL` | `gpt-5.4` | SOP markdown rendering |
| `OPENAI_CLARIFICATION_MODEL` | `gpt-5.4` | Clarification (when provider is openai) |
| `OPENAI_TRANSCRIPTION_MODEL` | `whisper-1` | Voice transcription |
| `GEMINI_VIDEO_MODEL` | `gemini-2.5-pro` | Screen recording analysis |

### Switching the clarification provider to OpenRouter

The clarification skill supports a runtime swap to OpenRouter, which lets you A/B test models like Claude or Kimi K2 without code changes:

```bash
# in backend/.env.local
CLARIFICATION_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_CLARIFICATION_MODEL=anthropic/claude-opus-4.7   # or moonshotai/kimi-k2.6, etc.
```

Restart the backend. Verify with `curl http://localhost:8000/health` — `clarification.provider` should now read `openrouter` and `clarification.model` should reflect your chosen slug.

Find available model slugs at https://openrouter.ai/models.

## Local development without Docker

If you prefer not to use Docker, you'll need:

- Python 3.11+ (3.14 works), Node 20+, PostgreSQL 15+

```bash
# Start a local Postgres matching what docker-compose would create
createuser agentic_ops --pwprompt        # password: agentic_ops
createdb agentic_ops -O agentic_ops

# Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env.local               # then fill in API keys
alembic upgrade head
uvicorn app.main:app --reload            # http://localhost:8000

# Frontend (in another terminal)
cd frontend
npm install
npm run dev                              # http://localhost:5173
```

## Project structure

```
backend/app/
  api/           FastAPI routes (capture, workflows, clarify, sop)
  core/          Background tasks, artifact filesystem helpers
  db/            Async SQLAlchemy + Alembic migrations
  models/        Pydantic graph (graph.py) + SQLAlchemy tables (db.py)
  services/      LLM client singletons (openai_client, gemini_client)
  skills/        LLM capabilities — one Python package per skill
                   workflow_extraction, workflow_clarification, sop_rendering,
                   voice_transcription, screen_analysis, diagram_review
  config.py      Pydantic Settings (env-driven)
  main.py        FastAPI app + CORS + router registration

frontend/src/
  pages/         Stage components: Capture, Processing, Clarify, Sop
  components/    TextCapture, VoiceRecorder, ScreenRecorder, etc.
  api/client.ts  Typed fetch wrapper, 1:1 with backend endpoints
```

Read [AGENTS.md](AGENTS.md) for the architectural rules and per-skill design rationale.

## Troubleshooting

**`docker compose exec backend alembic upgrade head` fails with "database does not exist"** — the Postgres container hasn't finished initializing. Wait a few seconds after `up --build` and retry.

**`/health` returns 500 or hangs at startup** — `backend/.env.local` is missing a required key, or the value is malformed. Check the backend container logs: `docker compose logs backend`.

**Clarification returns empty content / refuses** — your provider key is invalid or out of credits. Verify with `curl http://localhost:8000/health` that the active model is what you expect, then test the provider key independently with their API.

**Frontend shows "Failed to fetch" on capture** — backend isn't reachable on `localhost:8000`. Check `docker compose ps`; rebuild if the backend container is unhealthy.

**Voice or screen capture button does nothing** — browsers block mic/screen access on non-HTTPS origins. `localhost` is an exception but some corporate proxies break this. Try directly in Chrome with no extensions.

**OpenRouter clarification crashes with a parse error** — some open models freestyle the schema. Check the backend logs for the raw response. The system will log the bad content; usually swapping to a stricter model (Claude Opus, GPT-4.1) resolves it.

## Architecture rules (the short version)

These exist because the codebase rots fast if they break. The long version is in [AGENTS.md](AGENTS.md).

1. **One public function per skill.** Each `backend/app/skills/<name>/` exposes exactly one typed `async` function from `__init__.py`.
2. **API code never calls LLMs directly.** All LLM work goes through a skill.
3. **The workflow graph is the source of truth.** Don't introduce parallel representations.
4. **Clarification mutations go through `apply_turn`** — the model emits a typed `ClarificationTurn`, backend applies it deterministically. No prose-as-tool-call patterns.
5. **LLM model split is intentional**: OpenAI for text/audio, Gemini for video. Don't unify without discussion.

## License

Proprietary. All rights reserved. See [LICENSE](LICENSE).
