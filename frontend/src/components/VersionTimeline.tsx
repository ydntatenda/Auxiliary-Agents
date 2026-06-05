import { ChevronDown, ChevronRight, GitCommit } from "lucide-react";
import { useState } from "react";

import { WorkflowVersion } from "../api/client";

type Props = {
  versions: WorkflowVersion[];
};

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

export default function VersionTimeline({ versions }: Props) {
  const [open, setOpen] = useState(false);
  const ordered = [...versions].sort((a, b) => b.version - a.version);

  return (
    <section className="version-timeline">
      <button
        type="button"
        className="version-head"
        onClick={() => setOpen((value) => !value)}
      >
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <span className="label-mono">Version history</span>
        <span className="version-count">{ordered.length}</span>
      </button>
      {open && (
        <ol className="version-list">
          {ordered.length === 0 && (
            <li className="version-empty">No versions snapshotted yet.</li>
          )}
          {ordered.map((version) => (
            <li key={version.id} className="version-item">
              <div className="version-dot">
                <GitCommit size={12} />
              </div>
              <div className="version-body">
                <div className="version-row">
                  <span className="version-tag">v{version.version}</span>
                  <span className="label-mono">{formatDate(version.created_at)}</span>
                  <span className="version-by">by {version.changed_by}</span>
                </div>
                {version.change_summary && (
                  <p className="version-summary">{version.change_summary}</p>
                )}
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
