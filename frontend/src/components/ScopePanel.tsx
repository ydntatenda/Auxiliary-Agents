import { ArrowRight, X } from "lucide-react";
import { useState } from "react";

import type { DeltaScope } from "../api/client";

type Step = { id: string; title: string };

type Props = {
  selectedStepIds: string[];
  steps: Step[];
  onCancel: () => void;
  onConfirm: (scope: DeltaScope) => void;
};

const SCOPE_OPTIONS: ReadonlyArray<{ value: DeltaScope["scope"]; label: string }> = [
  { value: "step", label: "Just these steps" },
  { value: "section", label: "This whole section" },
  { value: "full", label: "The entire workflow" },
] as const;

export default function ScopePanel({
  selectedStepIds,
  steps,
  onCancel,
  onConfirm,
}: Props) {
  const [scope, setScope] = useState<DeltaScope["scope"]>("step");
  const [hint, setHint] = useState("");

  const titles = steps
    .filter((step) => selectedStepIds.includes(step.id))
    .map((step) => step.title);

  function confirm() {
    onConfirm({
      scope,
      step_ids: selectedStepIds,
      change_description: hint.trim() || null,
    });
  }

  return (
    <aside className="scope-panel">
      <div className="scope-head">
        <span className="label-mono">Scope your update</span>
        <button
          type="button"
          className="sc-iconbtn"
          onClick={onCancel}
          aria-label="Close scope panel"
        >
          <X size={14} />
        </button>
      </div>

      <div className="scope-section">
        <div className="label-mono">
          {selectedStepIds.length} {selectedStepIds.length === 1 ? "step" : "steps"} selected
        </div>
        <ul className="scope-step-list">
          {titles.map((title, index) => (
            <li key={index}>{title}</li>
          ))}
        </ul>
      </div>

      <div className="scope-section">
        <div className="label-mono">What does this update touch?</div>
        <div className="scope-options">
          {SCOPE_OPTIONS.map(({ value, label }) => (
            <button
              key={value}
              type="button"
              className={`role-option${scope === value ? " selected" : ""}`}
              onClick={() => setScope(value)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="scope-section">
        <label className="label-mono" htmlFor="scope-hint">
          Briefly describe what changed (optional)
        </label>
        <textarea
          id="scope-hint"
          className="text-input"
          value={hint}
          onChange={(event) => setHint(event.target.value)}
          placeholder="e.g. We now route appeals over £500 to the supervisor."
        />
      </div>

      <div className="scope-actions">
        <button type="button" className="btn btn-ghost" onClick={onCancel}>
          Cancel
        </button>
        <button
          type="button"
          className="btn btn-primary"
          onClick={confirm}
          disabled={selectedStepIds.length === 0}
        >
          Add sources for this update
          <ArrowRight size={13} />
        </button>
      </div>
    </aside>
  );
}
