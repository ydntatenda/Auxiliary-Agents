# Handoff: extraction eval and the `kind` fix

For Dubem. This covers what landed on `main` over the last session so you can orient before picking up. Everything below is pushed to origin. Capture stage was already done before this; all of this is the extraction stage plus two environment fixes.

## Getting in

Repo: https://github.com/ydntatenda/Auxiliary-Agents (private; accept the collaborator invite first or the link will 404).

    git clone https://github.com/ydntatenda/Auxiliary-Agents.git
    cd Auxiliary-Agents

You will need your own OpenAI key to run the eval against the real extractor. Put it in `backend/.env.local` as `OPENAI_API_KEY=sk-...`. Mine is not in the repo (it is gitignored, by design), so bring your own. The offline test suite runs without any key.

Everything is on `main`. There is a stale `eval-harness` branch behind main that you can ignore.

## The short version

The extraction stage now has a regression eval, and the extractor itself got materially better against it. The eval is domain-agnostic and runs offline; it only needs an OpenAI key when you want it to call the real extractor. The headline change is a new `kind` field on `Step` that fixed the extractor's worst structural problem. Two environment annoyances are also gone: the `.env` BOM issue and the `/docs` 500.

## Commits on main (most recent last)

- `2127638` Add extraction eval harness with citation-appeals golden fixture
- `f0697e2` Loosen gap matching and add gap-dump diagnostic
- `29482c1` Tighten extractor: terminal post-processor, prompt edits, threshold tune
- `346e223` Fix unreliable env loading: BOM tolerance and absolute paths
- `48fe61f` Fix /docs 500 by removing invalid response_class=None
- `4b64b83` Add step kind classification to fix step-miscategorisation

## What the eval is and how to run it

The harness lives under `backend/tests/eval/` (fixtures.py, scorers.py, report.py, runner.py) with fixture data under `backend/tests/fixtures/`. There are two fixtures, both built from the real GT P&T citation-appeals SOP: a single-source one and a multi-source variant that tests whether the extractor reconciles overlapping sources rather than concatenating them.

It scores extractor output against a golden graph on five independent axes: step-count band, gap recall and severity, terminal correctness, decision-rule structure, and an automatability check that currently skips green because the field does not exist yet. Each axis is a pure function scored against a hand-built or extracted graph.

Run the offline scorer tests, no key needed:

    cd backend
    py -3.11 -m pytest tests/

Run the eval against the real extractor, needs OPENAI_API_KEY in backend/.env.local:

    py -3.11 -m tests.eval.runner tests/fixtures/citation_appeals
    py -3.11 -m tests.eval.runner tests/fixtures/citation_appeals_multisource
    py -3.11 -m tests.eval.runner tests/fixtures/

The runner takes a single fixture path or a directory, stacks per-fixture reports, and exits non-zero on any axis failure, so it can drop into CI later. Add `--show-gaps` to dump the verbatim gaps the extractor surfaced, which is how you tell a genuinely missed gap from a paraphrased one.

One design rule to respect: the eval is the ruler. Do not tune the scorers or thresholds to make the extractor look better. If an axis fails, that is information about the extractor, not a problem with the eval.

## The main extractor change: `kind` on Step

The defect we found: the extractor was surfacing exception handlers, policy facts, and out-of-scope handoffs as if they were main-flow procedure steps, because `Step` offered only one bucket for operator content. This inflated step counts (13 to 17 against a real 11) and let non-procedure steps sit at the highest order, where the terminal post-processor wrongly crowned them. Terminal recall was 0 in four runs out of five.

The fix: `Step` now carries `kind: Literal["procedure", "exception", "policy", "handoff"]`, defaulting to `procedure`. The graph lives as JSONB so no migration was needed. The extractor classifies each step rather than cramming everything into procedure, and the terminal post-processor (`_correct_terminals` in the extraction skill) now filters promotion candidates to procedure steps only. Over five runs after the change, terminal recall went to 1.00 in every run, and procedure count dropped toward the real 11.

Why it was done as a schema field and not a prompt clause: the content was real, it was just miscategorised, so suppressing it via prose would have deleted real workflow knowledge. Categorising keeps it and makes mislabels recoverable. The four categories are generic process-modelling categories, deliberately not citation-appeals-specific, so this generalises to any workflow.

## What is deliberately still red (not bugs, understood and left)

- Terminal precision sits at 0.50 most runs: the extractor still sometimes merges the review-letter and send-letter steps into one, marking an intermediate step terminal. F1 is 0.67+ on every run, up from 0 mode. This is the chronic letter-merge and it needs a step-splitting fix that prose has not reliably landed.
- Decision-rule structure is stable 2/3: the skip-ahead branch (verify step short-circuits on a mismatch) lands reliably; the conditional-UI branch (a downstream step only appears for one prior choice) is the unrecovered case. We left it unrecovered on purpose because every deterministic detector for it was fixture-shaped, which is the failure mode we are avoiding.
- Gap severity often fails the 0.6 bar: the extractor rates gap impact more leniently than the golden. Accepted as honest disagreement on a subjective axis.

A recurring lesson from the session, worth knowing before you touch the extractor: prose clauses nudge this model but do not pin it. We confirmed this several times. Deterministic guards (like the terminal post-processor) are far more reliable than prompt wording for structural invariants, but only where the invariant is genuinely generic. Where it is not generic, a fixture-shaped guard is worse than an honest failing axis.

Also: the extractor is non-deterministic even at temperature 0, because structured-output and internal reasoning add variance the temperature does not control. So always run the eval three to five times and read the spread, never a single run.

## The two environment fixes

- `.env` loading: the file had a UTF-8 BOM that made pydantic-settings read `DATABASE_URL` as a BOM-prefixed key name and silently drop it, falling back to the default DB. Separately the env_file paths were relative so they only resolved from `backend/`. Fixed by switching to `utf-8-sig` encoding and absolute paths in `backend/app/config.py`. You no longer need to set env vars by hand each session.
- `/docs` 500: four routes passed `response_class=None`, which crashed OpenAPI schema generation. Removed the argument; behaviour unchanged (still 204, no body).

## Where to pick up

The immediate, self-contained next task: the SOP and diagram renderers do not yet respect the new `kind` field, so a policy fact or exception handler still renders inline as a numbered main-flow step. The renderers should set non-procedure steps apart from the numbered procedure flow. This is keyless and contained.

The higher-value strategic task: a second golden fixture from a genuinely different (non-campus) domain. Everything we learned about the extractor's weaknesses came from one process. A second real fixture is the only way to tell whether the step-miscategorisation tendency and the decision-rule surface-form sensitivity are citation-appeals quirks or real extractor properties. This needs a real process with known ground truth; do not invent one, that reintroduces the circularity the eval was built to avoid.

Deferred and downstream: the `automatability` field on Step (the bridge to the agent surface, cleaner to add now that structure sits on a trustworthy schema), then the three unbuilt surfaces (queryable knowledge base, running agents, drift detection).
