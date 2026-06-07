import { ArrowRight, ChevronDown, ChevronRight } from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  CurrentUser,
  DeltaScope,
  Source,
  createWorkflow,
  deleteSource,
  deltaExtract,
  extractWorkflow,
  listSources,
  retrySource,
  updateSource,
} from "../api/client";
import AddSourcePanel from "../components/AddSourcePanel";
import SourceCard from "../components/SourceCard";

type Props = {
  currentUser: CurrentUser;
  onCaptured: (workflowId: string, needsTranscription: boolean) => void;
  updateContext?: {
    workflowId: string;
    scope: DeltaScope | null;
    ownerId: string | null;
  } | null;
};

type ContributorRole = "operator" | "approver" | "observer";

const ROLE_OPTIONS: ReadonlyArray<{ value: ContributorRole; label: string }> = [
  { value: "operator", label: "I do this task" },
  { value: "approver", label: "I approve this task" },
  { value: "observer", label: "I observe this task" },
] as const;

type Stage = "identity" | "assembly";

const POLL_MS = 2000;

function isSettling(sources: Source[]): boolean {
  return sources.some(
    (source) => source.status === "pending" || source.status === "processing",
  );
}

function hasReady(sources: Source[]): boolean {
  return sources.some((source) => source.status === "ready");
}

function modalityLabel(modality: string): string {
  return modality.charAt(0).toUpperCase() + modality.slice(1);
}

function buildAssembled(sources: Source[]): string {
  return sources
    .filter((source) => source.status === "ready" && source.assembled_text)
    .map((source) => {
      const label = source.label?.trim() || "(no label)";
      const role = source.contributor_role;
      const descriptor = role ? `${source.modality}, ${role}` : source.modality;
      const header = `=== Source: ${label} (${descriptor}) ===`;
      return `${header}\n${source.assembled_text!.trim()}`;
    })
    .join("\n\n");
}

export default function Capture({ currentUser, onCaptured, updateContext }: Props) {
  const inUpdateMode = !!updateContext;
  const [stage, setStage] = useState<Stage>(inUpdateMode ? "assembly" : "identity");
  // In new-workflow mode the current user is trivially the owner, so any
  // source they add is theirs to edit. In update mode the owner is passed
  // in by App.tsx from the workflow-detail data.
  const workflowOwnerId = inUpdateMode
    ? updateContext?.ownerId ?? null
    : currentUser.id;

  function canEditSource(source: Source): boolean {
    if (currentUser.role === "admin") return true;
    if (workflowOwnerId !== null && workflowOwnerId === currentUser.id) {
      return true;
    }
    return source.added_by !== null && source.added_by === currentUser.id;
  }

  // Identity sub-stage state.
  const [name, setName] = useState("");
  const [unit, setUnit] = useState("");
  const [role, setRole] = useState<ContributorRole | "">("");
  const [startingError, setStartingError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  // Assembly sub-stage state.
  const [workflowId, setWorkflowId] = useState<string | null>(
    updateContext?.workflowId ?? null,
  );
  const [sources, setSources] = useState<Source[]>([]);
  const [assemblyError, setAssemblyError] = useState<string | null>(null);
  const [extracting, setExtracting] = useState(false);
  const [transcriptOpen, setTranscriptOpen] = useState(false);

  async function startWorkflow(event: FormEvent) {
    event.preventDefault();
    if (!name.trim() || !unit.trim() || !role) {
      setStartingError("Name, unit, and role are required.");
      return;
    }
    setStarting(true);
    setStartingError(null);
    try {
      const created = await createWorkflow(name.trim(), unit.trim(), role);
      setWorkflowId(created.workflow_id);
      setStage("assembly");
    } catch (err) {
      setStartingError(err instanceof Error ? err.message : "Could not start workflow.");
    } finally {
      setStarting(false);
    }
  }

  // Poll sources while anything is still settling.
  useEffect(() => {
    if (!workflowId) return;
    if (!isSettling(sources)) return;
    const handle = window.setInterval(async () => {
      try {
        const next = await listSources(workflowId);
        setSources(next);
      } catch {
        // Swallow polling errors; the next tick will retry. A persistent
        // failure is visible because the failed source's pill stays put.
      }
    }, POLL_MS);
    return () => window.clearInterval(handle);
  }, [workflowId, sources]);

  const sortedSources = useMemo(
    () => [...sources].sort((a, b) => a.order - b.order),
    [sources],
  );
  const settling = isSettling(sortedSources);
  const ready = hasReady(sortedSources);
  const canExtract = ready && !settling && !extracting;
  const assembledPreview = useMemo(() => buildAssembled(sortedSources), [sortedSources]);

  const handleSourceAdded = useCallback(async (source: Source) => {
    setSources((current) => {
      const without = current.filter((row) => row.id !== source.id);
      return [...without, source];
    });
    // The just-added file source is pending; refresh in 2 seconds via the
    // polling effect. For text and chat sources, the server has already
    // updated the assembled_text cache on the workflow row, so a quick
    // refetch keeps the preview in sync.
    if (workflowId && source.status === "ready") {
      try {
        const fresh = await listSources(workflowId);
        setSources(fresh);
      } catch {
        // Non-fatal; the next interaction reloads.
      }
    }
  }, [workflowId]);

  async function handleRemove(sourceId: string) {
    if (!workflowId) return;
    const previous = sources;
    setSources((current) => current.filter((row) => row.id !== sourceId));
    try {
      await deleteSource(workflowId, sourceId);
      const fresh = await listSources(workflowId);
      setSources(fresh);
    } catch (err) {
      setSources(previous);
      setAssemblyError(err instanceof Error ? err.message : "Could not remove source.");
    }
  }

  async function handleRetry(sourceId: string) {
    if (!workflowId) return;
    try {
      const fresh = await retrySource(workflowId, sourceId);
      setSources((current) =>
        current.map((row) => (row.id === sourceId ? fresh : row)),
      );
    } catch (err) {
      setAssemblyError(err instanceof Error ? err.message : "Retry failed.");
    }
  }

  async function handleLabelChange(sourceId: string, label: string) {
    if (!workflowId) return;
    try {
      const fresh = await updateSource(workflowId, sourceId, { label });
      setSources((current) =>
        current.map((row) => (row.id === sourceId ? fresh : row)),
      );
    } catch (err) {
      setAssemblyError(err instanceof Error ? err.message : "Could not rename.");
    }
  }

  async function handleMove(sourceId: string, direction: "up" | "down") {
    if (!workflowId) return;
    try {
      await updateSource(workflowId, sourceId, { move: direction });
      const fresh = await listSources(workflowId);
      setSources(fresh);
    } catch (err) {
      setAssemblyError(err instanceof Error ? err.message : "Could not reorder.");
    }
  }

  async function handleExtract() {
    if (!workflowId || !canExtract) return;
    setExtracting(true);
    setAssemblyError(null);
    try {
      if (updateContext?.scope) {
        await deltaExtract(workflowId, updateContext.scope);
      } else if (updateContext) {
        // Adding sources to an existing workflow without a scope: treat as
        // a "full" delta against the assembled additions.
        await deltaExtract(workflowId, {
          scope: "full",
          step_ids: null,
          change_description: null,
        });
      } else {
        await extractWorkflow(workflowId);
      }
      onCaptured(workflowId, false);
    } catch (err) {
      setAssemblyError(err instanceof Error ? err.message : "Extract failed.");
      setExtracting(false);
    }
  }

  if (stage === "identity") {
    return (
      <div className="workarea">
        <div className="canvas">
          <div className="step-eyebrow">
            <span className="num">01 / 03</span>
            <span>Workflow identity</span>
          </div>
          <h1 className="page-title">Name the workflow you are capturing.</h1>
          <p className="page-sub">
            Modus turns a recurring task into a structured workflow graph.
            Tell us what this is, who runs it, and your relationship to it.
            You will add sources of any kind in the next step.
          </p>

          <form onSubmit={startWorkflow}>
            <div className="field-row">
              <label className="field-label" htmlFor="workflow-name">
                Workflow name
                <span className="req">*</span>
                <span className="hint">Short and specific. "Citation appeals", not "Appeals".</span>
              </label>
              <input
                id="workflow-name"
                className="text-input"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="What is this workflow called?"
                disabled={starting}
                autoFocus
              />
            </div>

            <div className="field-row">
              <label className="field-label" htmlFor="workflow-unit">
                Department or unit
                <span className="req">*</span>
                <span className="hint">The team that owns this work.</span>
              </label>
              <input
                id="workflow-unit"
                className="text-input"
                value={unit}
                onChange={(event) => setUnit(event.target.value)}
                placeholder="e.g. Parking & Transportation"
                disabled={starting}
              />
            </div>

            <div className="field-row">
              <label className="field-label">
                Your role
                <span className="req">*</span>
                <span className="hint">How you relate to this task. Sources you add are tagged with this.</span>
              </label>
              <div className="role-options">
                {ROLE_OPTIONS.map(({ value, label }) => (
                  <button
                    key={value}
                    type="button"
                    className={`role-option${role === value ? " selected" : ""}`}
                    onClick={() => setRole(value)}
                    disabled={starting}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            {startingError && <div className="error">{startingError}</div>}

            <div className="actions">
              <span className="label-mono">Step 1 of 3</span>
              <div className="right">
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={starting || !name.trim() || !unit.trim() || !role}
                >
                  {starting ? "Starting..." : "Start"}
                  <ArrowRight size={13} />
                </button>
              </div>
            </div>
          </form>
        </div>
      </div>
    );
  }

  if (!workflowId) return null;

  return (
    <div className="workarea">
      <div className="canvas">
        <div className="step-eyebrow">
          <span className="num">{inUpdateMode ? "Update" : "02 / 03"}</span>
          <span>{inUpdateMode ? "Add new sources" : "Source assembly"}</span>
        </div>
        <h1 className="page-title">
          {inUpdateMode
            ? "What's new since the last version?"
            : "Add whatever you have, in any form."}
        </h1>
        <p className="page-sub">
          {inUpdateMode
            ? "Add sources covering only what changed. We will run a scoped delta against the current graph when you hit extract."
            : "Sources can be text you type, a voice walkthrough, a screen recording, a document, or a short guided Q&A. Add as many as you need. They assemble in order into one transcript that Modus reads next."}
        </p>

        <div className="source-list">
          {sortedSources.length === 0 && (
            <div className="source-empty">
              No sources yet. Add one below to begin.
            </div>
          )}
          {sortedSources.map((source, index) => (
            <SourceCard
              key={source.id}
              source={source}
              isFirst={index === 0}
              isLast={index === sortedSources.length - 1}
              canEdit={canEditSource(source)}
              onRemove={() => void handleRemove(source.id)}
              onRetry={() => void handleRetry(source.id)}
              onLabelChange={(label) => void handleLabelChange(source.id, label)}
              onMove={(direction) => void handleMove(source.id, direction)}
            />
          ))}
        </div>

        <AddSourcePanel
          workflowId={workflowId}
          contributorRole={role || null}
          onSourceAdded={handleSourceAdded}
        />

        {ready && (
          <section className="transcript-panel">
            <button
              type="button"
              className="transcript-head"
              onClick={() => setTranscriptOpen((open) => !open)}
            >
              {transcriptOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              <span className="label-mono">
                Assembled transcript, {sortedSources.filter((s) => s.status === "ready").length}{" "}
                {sortedSources.filter((s) => s.status === "ready").length === 1 ? "source" : "sources"}
              </span>
            </button>
            {transcriptOpen && (
              <pre className="transcript-body">{assembledPreview}</pre>
            )}
          </section>
        )}

        {assemblyError && <div className="error">{assemblyError}</div>}

        <div className="extract-row">
          <button
            type="button"
            className="btn btn-primary btn-block"
            onClick={() => void handleExtract()}
            disabled={!canExtract}
            title={
              settling
                ? "Wait for sources to finish processing."
                : !ready
                  ? "Add at least one source first."
                  : undefined
            }
          >
            {extracting
              ? "Extracting..."
              : settling
                ? "Waiting for sources to finish..."
                : `Extract from ${sortedSources.filter((s) => s.status === "ready").length} ${
                    sortedSources.filter((s) => s.status === "ready").length === 1 ? "source" : "sources"
                  }`}
            <ArrowRight size={13} />
          </button>
          <span className="label-mono extract-caption">
            Modality:{" "}
            {[...new Set(sortedSources.map((s) => modalityLabel(s.modality)))].join(", ") || "none yet"}
          </span>
        </div>
      </div>
    </div>
  );
}
