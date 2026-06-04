# CLAUDE.md

Read this first, every session. These are non-negotiable. If a change would
break one, stop and surface the conflict instead of proceeding.

## What Modus is

Modus turns how a team actually does a recurring task into a structured
workflow graph, then renders surfaces from that one graph. Today the shipped
pipeline is capture → extract → clarify → review/diagram → SOP. First
production target: Georgia Tech Parking & Transportation, citation appeals.

The full architectural rationale lives in `AGENTS.md` and the per-skill
`backend/app/skills/*/SKILL.md` files. Read the relevant ones before editing
a skill.

## The five hard rules (from AGENTS.md, repeated because they are load-bearing)

1. **One public function per skill.** Each `backend/app/skills/<name>/`
   package exposes exactly one typed `async` function via `__init__.py`.
   API and core code import only that function, never internals.
2. **API/orchestration never calls LLMs directly.** All LLM work goes through
   a skill. A new OpenAI/Gemini call in `api/` or `core/` is a bug.
3. **The workflow graph is the source of truth.** No parallel representation.
   New step metadata goes on the Pydantic models in `models/graph.py`.
4. **Graph mutations go through the typed apply layer** (`apply_turn` /
   `ClarificationTurn`), never direct DB writes from API code. The tools
   enforce field whitelists and step-existence checks.
5. **LLM model split is intentional:** OpenAI for text/audio, Gemini for
   video. Do not unify without an explicit decision.

## The capture invariant (new, this is what the current work establishes)

A workflow has MANY sources. Each source has one modality, one raw artifact,
and one assembled text. The workflow's transcript is the ordered
concatenation of its ready sources, cached on the row. Sources are the truth;
the assembled transcript is a cache, regenerated whenever a source changes.
A connector is just another source type behind the same interface, never a
special case wired into the workflow row.

## House style (applies to all prose, comments, docs, commit messages)

- No em dashes anywhere. Use commas, parentheses, or full stops.
- British punctuation conventions.
- Prose over bullets in any user-facing or doc text.
- Avoid "delve", "tapestry", "navigate the landscape".

## The discipline

- Do not introduce LangChain, CrewAI, or another agent framework.
  Clarification is committed to the OpenAI Agents SDK.
- Do not add retry logic to background tasks without idempotency.
- Do not create documentation files unless explicitly asked.
- Every non-trivial change ships with the test or eval that proves it.
  This repo has thin coverage; an agent-driven change is only as safe as
  the test guarding it.
