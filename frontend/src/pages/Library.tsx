import {
  ArrowRight,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Copy,
  FilePlus,
  Pencil,
  Search,
  Trash2,
  Users,
  X as XIcon,
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  Collaborator,
  CurrentUser,
  DeltaScope,
  SearchResult,
  WorkflowDetail,
  WorkflowSummary,
  approveWorkflow,
  archiveWorkflow,
  duplicateWorkflow,
  editWorkflow,
  getWorkflowSummary,
  listWorkflows,
  requestUpdate,
  searchWorkflows,
} from "../api/client";
import CollaboratorPanel from "../components/CollaboratorPanel";
import DiagramView from "../components/DiagramView";
import ScopePanel from "../components/ScopePanel";
import VersionTimeline from "../components/VersionTimeline";

type Props = {
  user: CurrentUser;
  initialWorkflowId?: string | null;
  onNewWorkflow: () => void;
  onUpdateFlow: (workflowId: string, scope: DeltaScope, ownerId: string | null) => void;
  onAddSources: (workflowId: string, ownerId: string | null) => void;
};

type Sub = "home" | "search" | "detail";

function statusLabel(status: string): string {
  return status
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function timeAgo(iso: string): string {
  try {
    const then = new Date(iso).getTime();
    const seconds = Math.max(1, Math.round((Date.now() - then) / 1000));
    if (seconds < 60) return `just now`;
    const minutes = Math.round(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.round(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.round(hours / 24);
    if (days < 30) return `${days}d ago`;
    return new Date(iso).toLocaleDateString();
  } catch {
    return iso;
  }
}

export default function Library({
  user,
  initialWorkflowId,
  onNewWorkflow,
  onUpdateFlow,
  onAddSources,
}: Props) {
  const [sub, setSub] = useState<Sub>(initialWorkflowId ? "detail" : "home");
  const [workflows, setWorkflows] = useState<WorkflowSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);

  const [openId, setOpenId] = useState<string | null>(initialWorkflowId ?? null);
  const [detail, setDetail] = useState<WorkflowDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const [selectedSteps, setSelectedSteps] = useState<string[]>([]);
  const [scopeOpen, setScopeOpen] = useState(false);

  // Initial library load.
  useEffect(() => {
    let alive = true;
    setLoading(true);
    listWorkflows()
      .then((data) => {
        if (alive) setWorkflows(data);
      })
      .catch((err) => {
        if (alive) setError(err instanceof Error ? err.message : "Could not load library.");
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  // Debounced search.
  useEffect(() => {
    if (sub !== "search" || !query.trim()) {
      setResults([]);
      return;
    }
    setSearching(true);
    const handle = window.setTimeout(async () => {
      try {
        const hits = await searchWorkflows(query.trim());
        setResults(hits);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Search failed.");
      } finally {
        setSearching(false);
      }
    }, 400);
    return () => window.clearTimeout(handle);
  }, [query, sub]);

  // Detail load.
  useEffect(() => {
    if (sub !== "detail" || !openId) return;
    let alive = true;
    setDetailLoading(true);
    setSelectedSteps([]);
    setScopeOpen(false);
    getWorkflowSummary(openId)
      .then((data) => {
        if (alive) setDetail(data);
      })
      .catch((err) => {
        if (alive) setError(err instanceof Error ? err.message : "Could not load workflow.");
      })
      .finally(() => {
        if (alive) setDetailLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [sub, openId]);

  function open(id: string) {
    setOpenId(id);
    setSub("detail");
  }

  function back() {
    setOpenId(null);
    setDetail(null);
    setSub("home");
  }

  if (sub === "detail" && openId) {
    return (
      <Detail
        workflowId={openId}
        detail={detail}
        loading={detailLoading}
        currentUser={user}
        selectedSteps={selectedSteps}
        scopeOpen={scopeOpen}
        onBack={back}
        onAddSources={() => onAddSources(openId, detail?.created_by ?? null)}
        onApprove={async () => {
          try {
            await approveWorkflow(openId);
            const fresh = await getWorkflowSummary(openId);
            setDetail(fresh);
          } catch (err) {
            setError(err instanceof Error ? err.message : "Approve failed.");
          }
        }}
        onRequestUpdate={async () => {
          try {
            await requestUpdate(openId);
            const fresh = await getWorkflowSummary(openId);
            setDetail(fresh);
          } catch (err) {
            setError(err instanceof Error ? err.message : "Could not request update.");
          }
        }}
        onArchive={async () => {
          if (!window.confirm("Archive this workflow? It can be restored later by ID.")) {
            return;
          }
          try {
            await archiveWorkflow(openId);
            back();
            const list = await listWorkflows();
            setWorkflows(list);
          } catch (err) {
            setError(err instanceof Error ? err.message : "Archive failed.");
          }
        }}
        onDuplicate={async () => {
          try {
            await duplicateWorkflow(openId);
            const list = await listWorkflows();
            setWorkflows(list);
            back();
          } catch (err) {
            setError(err instanceof Error ? err.message : "Duplicate failed.");
          }
        }}
        onToggleStep={(stepId) => {
          setSelectedSteps((current) =>
            current.includes(stepId)
              ? current.filter((id) => id !== stepId)
              : [...current, stepId],
          );
          setScopeOpen(true);
        }}
        onClearSelection={() => {
          setSelectedSteps([]);
          setScopeOpen(false);
        }}
        onConfirmScope={(scope) => {
          onUpdateFlow(openId, scope, detail?.created_by ?? null);
        }}
        onCollaboratorsChange={(next) => {
          setDetail((current) =>
            current ? { ...current, collaborators: next, collaborator_count: next.length } : current,
          );
        }}
        onDetailUpdated={(next) => {
          setDetail(next);
          // Also refresh the home listing so a rename shows up immediately
          // when the user goes back.
          void listWorkflows().then(setWorkflows).catch(() => undefined);
        }}
        error={error}
      />
    );
  }

  if (sub === "search") {
    return (
      <SearchScreen
        query={query}
        results={results}
        searching={searching}
        onBack={() => {
          setQuery("");
          setSub("home");
        }}
        onQuery={setQuery}
        onOpen={open}
        onNew={onNewWorkflow}
      />
    );
  }

  return (
    <Home
      user={user}
      workflows={workflows}
      loading={loading}
      error={error}
      onNew={onNewWorkflow}
      onSearch={() => setSub("search")}
      onOpen={open}
    />
  );
}

// -- Home sub-screen ---------------------------------------------------

function Home({
  user,
  workflows,
  loading,
  error,
  onNew,
  onSearch,
  onOpen,
}: {
  user: CurrentUser;
  workflows: WorkflowSummary[];
  loading: boolean;
  error: string | null;
  onNew: () => void;
  onSearch: () => void;
  onOpen: (id: string) => void;
}) {
  return (
    <div className="workarea">
      <div className="canvas wide">
        <div className="step-eyebrow">
          <span className="num">Library</span>
          <span>{user.org_name}</span>
        </div>
        <h1 className="page-title">Workflows.</h1>
        <p className="page-sub">
          Every recurring task this team has documented, in one place.
          Start a new one, or pick an existing workflow to update.
        </p>

        <div className="lib-cta">
          <button type="button" className="lib-action" onClick={onNew}>
            <FilePlus size={18} />
            <div>
              <div className="lib-action-title">Document a new workflow</div>
              <div className="lib-action-sub">
                Start from scratch with sources of any kind.
              </div>
            </div>
            <ArrowRight size={14} />
          </button>
          <button type="button" className="lib-action" onClick={onSearch}>
            <Search size={18} />
            <div>
              <div className="lib-action-title">Update an existing workflow</div>
              <div className="lib-action-sub">
                Find one by name or describe what it does.
              </div>
            </div>
            <ArrowRight size={14} />
          </button>
        </div>

        {error && <div className="error">{error}</div>}

        {loading ? (
          <div className="lib-state">Loading workflows.</div>
        ) : workflows.length === 0 ? (
          <div className="lib-empty">
            <h3>No workflows documented yet.</h3>
            <p>Start by documenting your first process.</p>
            <button type="button" className="btn btn-primary" onClick={onNew}>
              <FilePlus size={13} />
              Document a workflow
            </button>
          </div>
        ) : (
          <WorkflowTable workflows={workflows} onOpen={onOpen} />
        )}
      </div>
    </div>
  );
}

function WorkflowTable({
  workflows,
  onOpen,
}: {
  workflows: WorkflowSummary[];
  onOpen: (id: string) => void;
}) {
  return (
    <div className="lib-table">
      <div className="lib-table-head">
        <span>Workflow</span>
        <span>Unit</span>
        <span>Status</span>
        <span>Version</span>
        <span>Updated</span>
        <span>Team</span>
      </div>
      {workflows.map((row) => (
        <button
          key={row.id}
          type="button"
          className="lib-table-row"
          onClick={() => onOpen(row.id)}
        >
          <div className="lib-row-name">
            <div className="lib-row-title">{row.name}</div>
            {row.description && (
              <div className="lib-row-desc">{row.description}</div>
            )}
            {row.current_user_role && (
              <div className="lib-row-mine">you: {row.current_user_role}</div>
            )}
          </div>
          <div>{row.unit}</div>
          <div>
            <StatusPill status={row.status} />
          </div>
          <div className="lib-row-version">v{row.version}</div>
          <div className="lib-row-updated">{timeAgo(row.updated_at)}</div>
          <div className="lib-row-team">
            <Users size={12} />
            <span>{row.collaborator_count}</span>
            <span className="lib-row-sources label-mono">
              · {row.source_count} sources
            </span>
          </div>
        </button>
      ))}
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const className = `sc-pill status-${status.replace("_", "-")}`;
  return <span className={className}>{statusLabel(status)}</span>;
}

// -- Search sub-screen -------------------------------------------------

function SearchScreen({
  query,
  results,
  searching,
  onBack,
  onQuery,
  onOpen,
  onNew,
}: {
  query: string;
  results: SearchResult[];
  searching: boolean;
  onBack: () => void;
  onQuery: (q: string) => void;
  onOpen: (id: string) => void;
  onNew: () => void;
}) {
  return (
    <div className="workarea">
      <div className="canvas wide">
        <div className="step-eyebrow">
          <button type="button" className="back-chev" onClick={onBack}>
            <ChevronLeft size={14} />
            Library
          </button>
        </div>
        <h1 className="page-title">Find the workflow.</h1>
        <p className="page-sub">
          Type its name or describe what it does. We match by name and by
          description, ranked by relevance.
        </p>

        <div className="search-row">
          <Search size={16} />
          <input
            className="text-input"
            value={query}
            onChange={(event) => onQuery(event.target.value)}
            placeholder="Describe the workflow or type its name..."
            autoFocus
          />
        </div>

        {searching && <div className="lib-state">Searching.</div>}

        {!searching && query.trim() && results.length === 0 && (
          <div className="lib-empty">
            <h3>No workflows match.</h3>
            <p>Want to document this as a new workflow?</p>
            <button type="button" className="btn btn-primary" onClick={onNew}>
              <FilePlus size={13} />
              Document "{query.trim()}"
            </button>
          </div>
        )}

        <div className="search-results">
          {results.map((result) => (
            <button
              key={result.id}
              type="button"
              className="search-result"
              onClick={() => onOpen(result.id)}
            >
              <div className="search-result-head">
                <div>
                  <div className="lib-row-title">{result.name}</div>
                  <div className="label-mono">{result.unit}</div>
                </div>
                <StatusPill status={result.status} />
              </div>
              <div className="search-reason label-mono">
                {result.match_reason}
              </div>
              {result.description && (
                <div className="search-excerpt">{result.description}</div>
              )}
              <span className="search-open">
                Open
                <ChevronRight size={12} />
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

// -- Workflow detail sub-screen ----------------------------------------

function Detail({
  workflowId,
  detail,
  loading,
  currentUser,
  selectedSteps,
  scopeOpen,
  onBack,
  onAddSources,
  onApprove,
  onRequestUpdate,
  onArchive,
  onDuplicate,
  onToggleStep,
  onClearSelection,
  onConfirmScope,
  onCollaboratorsChange,
  onDetailUpdated,
  error,
}: {
  workflowId: string;
  detail: WorkflowDetail | null;
  loading: boolean;
  currentUser: CurrentUser;
  selectedSteps: string[];
  scopeOpen: boolean;
  onBack: () => void;
  onAddSources: () => void;
  onApprove: () => void;
  onRequestUpdate: () => void;
  onArchive: () => void;
  onDuplicate: () => void;
  onToggleStep: (id: string) => void;
  onClearSelection: () => void;
  onConfirmScope: (scope: DeltaScope) => void;
  onCollaboratorsChange: (next: Collaborator[]) => void;
  onDetailUpdated: (next: WorkflowDetail) => void;
  error: string | null;
}) {
  const role = detail?.current_user_role;
  // The current user "manages" a workflow when they are an admin, or when
  // they created it. Owner = creator; there is no separate owner role.
  const canManage =
    !!detail &&
    (currentUser.role === "admin" || detail.created_by === currentUser.id);
  const canApprove =
    !!detail &&
    (currentUser.role === "admin" || role === "approver") &&
    ["clarifying", "reviewing", "done"].includes(detail.status);
  // Reviewers often have first-hand knowledge of the work and should be
  // able to contribute new sources, even though their primary role is to
  // approve. The backend agrees: it accepts adds from anyone.
  const canContribute =
    !!detail &&
    (currentUser.role === "admin" ||
      role === "contributor" ||
      role === "reviewer" ||
      role === "approver");
  // Request update: any collaborator, the owner, or admin. Backend
  // enforces the same; we hide the button to match.
  const canRequestUpdate =
    !!detail && (canManage || role !== null);
  const [editing, setEditing] = useState(false);

  const stepList = useMemo(() => {
    const graph = (detail as unknown as { graph?: { steps?: { id: string; title: string }[] } })?.graph;
    return graph?.steps?.map((step) => ({ id: step.id, title: step.title })) ?? [];
  }, [detail]);

  return (
    <div className="workarea">
      <div className="canvas wide">
        <div className="step-eyebrow">
          <button type="button" className="back-chev" onClick={onBack}>
            <ChevronLeft size={14} />
            Library
          </button>
        </div>

        {loading || !detail ? (
          <div className="lib-state">Loading workflow.</div>
        ) : (
          <>
            <div className="detail-head">
              <div>
                {editing ? (
                  <IdentityEditor
                    detail={detail}
                    onSave={(next) => {
                      onDetailUpdated(next);
                      setEditing(false);
                    }}
                    onCancel={() => setEditing(false)}
                  />
                ) : (
                  <>
                    <div className="detail-name-row">
                      <h1 className="page-title">{detail.name}</h1>
                      {canManage && (
                        <button
                          type="button"
                          className="sc-iconbtn"
                          onClick={() => setEditing(true)}
                          title="Edit name, unit, or description"
                          aria-label="Edit workflow identity"
                        >
                          <Pencil size={13} />
                        </button>
                      )}
                    </div>
                    <div className="detail-meta">
                      <span>{detail.unit}</span>
                      <StatusPill status={detail.status} />
                      <span className="label-mono">v{detail.version}</span>
                      {detail.approved_at && (
                        <span className="label-mono">
                          approved {timeAgo(detail.approved_at)}
                        </span>
                      )}
                    </div>
                    {detail.description && (
                      <p className="page-sub">{detail.description}</p>
                    )}
                  </>
                )}
              </div>
              <div className="detail-actions">
                {canContribute && (
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={onAddSources}
                  >
                    Add my knowledge
                  </button>
                )}
                {canApprove && (
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={onApprove}
                  >
                    <CheckCircle2 size={13} />
                    Approve this version
                  </button>
                )}
                {detail.status === "approved" && canRequestUpdate && (
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={onRequestUpdate}
                  >
                    Request update
                  </button>
                )}
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={onDuplicate}
                  title="Duplicate this workflow"
                >
                  <Copy size={13} />
                  Duplicate
                </button>
                {canManage && (
                  <button
                    type="button"
                    className="btn btn-ghost"
                    onClick={onArchive}
                    title="Archive this workflow"
                  >
                    <Trash2 size={13} />
                    Archive
                  </button>
                )}
              </div>
            </div>

            {error && <div className="error">{error}</div>}

            <div className="detail-grid">
              <div className="detail-main">
                <DiagramView
                  workflowId={workflowId}
                  selectedStepIds={selectedSteps}
                  onToggleStep={onToggleStep}
                  onClear={onClearSelection}
                />
                <VersionTimeline versions={detail.versions} />
              </div>
              <aside className="detail-side">
                <CollaboratorPanel
                  workflowId={workflowId}
                  collaborators={detail.collaborators}
                  onChange={onCollaboratorsChange}
                />
              </aside>
            </div>

            {scopeOpen && selectedSteps.length > 0 && (
              <ScopePanel
                selectedStepIds={selectedSteps}
                steps={stepList}
                onCancel={onClearSelection}
                onConfirm={onConfirmScope}
              />
            )}
          </>
        )}
      </div>
    </div>
  );
}

// -- Inline identity editor -------------------------------------------

function IdentityEditor({
  detail,
  onSave,
  onCancel,
}: {
  detail: WorkflowDetail;
  onSave: (next: WorkflowDetail) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(detail.name);
  const [unit, setUnit] = useState(detail.unit);
  const [description, setDescription] = useState(detail.description ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!name.trim() || !unit.trim()) {
      setError("Name and unit cannot be blank.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const next = await editWorkflow(detail.id, {
        name: name.trim(),
        unit: unit.trim(),
        description: description.trim() ? description.trim() : null,
      });
      onSave(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="identity-editor" onSubmit={submit}>
      <div className="identity-editor-row">
        <label className="label-mono" htmlFor="identity-name">
          Name
        </label>
        <input
          id="identity-name"
          className="text-input"
          value={name}
          onChange={(event) => setName(event.target.value)}
          disabled={busy}
          autoFocus
        />
      </div>
      <div className="identity-editor-row">
        <label className="label-mono" htmlFor="identity-unit">
          Unit
        </label>
        <input
          id="identity-unit"
          className="text-input"
          value={unit}
          onChange={(event) => setUnit(event.target.value)}
          disabled={busy}
        />
      </div>
      <div className="identity-editor-row">
        <label className="label-mono" htmlFor="identity-desc">
          Description
        </label>
        <textarea
          id="identity-desc"
          className="text-input"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          disabled={busy}
          placeholder="One sentence on what this workflow does."
          rows={2}
        />
      </div>
      {error && <div className="error">{error}</div>}
      <div className="identity-editor-actions">
        <button
          type="button"
          className="btn btn-ghost"
          onClick={onCancel}
          disabled={busy}
        >
          <XIcon size={13} />
          Cancel
        </button>
        <button type="submit" className="btn btn-primary" disabled={busy}>
          <CheckCircle2 size={13} />
          {busy ? "Saving" : "Save"}
        </button>
      </div>
    </form>
  );
}
