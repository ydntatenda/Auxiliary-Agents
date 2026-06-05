# delta_extraction

Update-time companion to `workflow_extraction`. Where the first extraction
reads a transcript with no prior graph, delta extraction reads a transcript
WITH the existing graph as context and must respect a declared scope: the
operator tells Modus which steps this update touches.

## Public surface

```python
async def extract_delta(
    workflow: Workflow,
    new_transcript: str,
    scope: DeltaScope,
) -> DeltaResult

def apply_delta(
    workflow: Workflow,
    delta: DeltaResult,
    scope: DeltaScope,
) -> Workflow
```

Plus the `DeltaResult` and `DeltaScope` types. The API layer never calls
the LLM directly and never mutates the graph; it composes these two
functions and persists the result.

## DeltaScope

- `scope = "step"`: only the named `step_ids` may be modified or removed.
  New steps can still be added, but only ones that hang off the named
  region.
- `scope = "section"`: the named steps plus their immediate neighbours.
- `scope = "full"`: anything. Use sparingly.

`apply_delta` enforces the scope independently of the LLM. If the model
tries to touch a step outside scope, `apply_delta` raises
`DeltaApplyError` and the caller bails before any DB write.

## Gap re-opening

When `apply_delta` modifies a step, any resolved gaps whose `step_id`
matches that step are reset (`resolved=False`, `resolution=None`). The
old resolution may no longer apply to the new step shape, so a human or
the clarification stage has to re-judge it. Gaps that hang off removed
steps are dropped entirely.

## Model

Same model as `workflow_extraction` (`OPENAI_EXTRACTION_MODEL`). Uses
`client.responses.parse(text_format=DeltaResult)` so the wire shape is
structurally enforced by Pydantic. No streaming, single round-trip.

## Why this is its own skill rather than a flag on `workflow_extraction`

The prompt is different (current graph in context, scope constraint),
the typed apply layer is different (existence + scope enforcement, gap
reopening), and the API endpoints are different. Folding them would
require runtime branching inside one prompt for "first capture" vs
"update", which is the kind of branching the one-skill-one-job rule
exists to avoid.
