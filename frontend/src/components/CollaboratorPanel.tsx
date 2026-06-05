import { Search, UserPlus, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  Collaborator,
  Member,
  addWorkflowCollaborator,
  removeWorkflowCollaborator,
  searchMembers,
} from "../api/client";

type ContributionRole = "contributor" | "reviewer" | "approver";

type Props = {
  workflowId: string;
  collaborators: Collaborator[];
  onChange: (next: Collaborator[]) => void;
};

const ROLE_OPTIONS: ContributionRole[] = ["contributor", "reviewer", "approver"];

export default function CollaboratorPanel({
  workflowId,
  collaborators,
  onChange,
}: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Member[]>([]);
  const [role, setRole] = useState<ContributionRole>("contributor");
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  // Debounce member search.
  useEffect(() => {
    if (!open) return;
    const handle = window.setTimeout(async () => {
      try {
        const members = await searchMembers(query);
        setResults(members);
      } catch {
        // Non-fatal; UI shows the latest good list.
      }
    }, 200);
    return () => window.clearTimeout(handle);
  }, [query, open]);

  const existingIds = useMemo(
    () => new Set(collaborators.map((c) => c.member_id)),
    [collaborators],
  );

  async function add(memberId: string) {
    setBusy(true);
    setError(null);
    try {
      const next = await addWorkflowCollaborator(workflowId, memberId, role);
      onChange(next);
      setQuery("");
      setOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add.");
    } finally {
      setBusy(false);
    }
  }

  async function remove(memberId: string) {
    setBusy(true);
    setError(null);
    try {
      await removeWorkflowCollaborator(workflowId, memberId);
      onChange(collaborators.filter((c) => c.member_id !== memberId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not remove.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="collab-panel">
      <div className="collab-head">
        <span className="label-mono">Collaborators</span>
        <button
          type="button"
          className="btn btn-secondary btn-tight"
          onClick={() => {
            setOpen((value) => !value);
            window.setTimeout(() => inputRef.current?.focus(), 0);
          }}
        >
          <UserPlus size={13} />
          Add
        </button>
      </div>

      {open && (
        <div className="collab-search">
          <div className="collab-search-row">
            <Search size={13} />
            <input
              ref={inputRef}
              className="text-input"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Type a name to search the team..."
              disabled={busy}
            />
            <select
              className="collab-role"
              value={role}
              onChange={(event) =>
                setRole(event.target.value as ContributionRole)
              }
              disabled={busy}
            >
              {ROLE_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </div>
          <ul className="collab-results">
            {results.map((member) => {
              const already = existingIds.has(member.id);
              return (
                <li key={member.id}>
                  <button
                    type="button"
                    className="collab-result"
                    onClick={() => (already ? null : add(member.id))}
                    disabled={already || busy}
                  >
                    <span className="avatar small">{member.avatar}</span>
                    <span className="collab-result-name">{member.name}</span>
                    <span className="label-mono">
                      {already ? "already added" : "add as " + role}
                    </span>
                  </button>
                </li>
              );
            })}
            {!results.length && (
              <li className="collab-empty">No matches.</li>
            )}
          </ul>
        </div>
      )}

      <ul className="collab-list">
        {collaborators.map((collab) => (
          <li key={collab.member_id} className="collab-item">
            <span className="avatar small">{collab.avatar}</span>
            <div className="collab-meta">
              <div className="collab-name">{collab.name}</div>
              <div className="label-mono">{collab.contribution_role}</div>
            </div>
            <button
              type="button"
              className="sc-iconbtn danger"
              onClick={() => remove(collab.member_id)}
              aria-label="Remove collaborator"
              disabled={busy}
            >
              <X size={13} />
            </button>
          </li>
        ))}
        {!collaborators.length && (
          <li className="collab-empty">No collaborators yet.</li>
        )}
      </ul>

      {error && <div className="error">{error}</div>}
    </section>
  );
}
