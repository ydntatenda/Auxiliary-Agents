type Stage = "capture" | "processing" | "clarify" | "sop";

export function Topbar() {
  return (
    <div className="topbar">
      <div className="brand">
        <div className="mark" />
        <div className="name">Modus</div>
        <div className="dept">GT - Parking & Transportation</div>
      </div>
      <div className="topbar-right">
        <div className="meta">v0.1 · local</div>
        <div className="avatar">PT</div>
      </div>
    </div>
  );
}

export function Subbar({ stage, workflowId }: { stage: Stage; workflowId: string | null }) {
  const active =
    stage === "capture"
      ? "New capture"
      : stage === "processing"
        ? "Processing"
        : stage === "clarify"
          ? "Clarification"
          : "SOP";

  return (
    <div className="subbar">
      <span className="crumb">Workflows</span>
      <span className="sep">/</span>
      <span className="crumb active">{active}</span>
      {workflowId && (
        <div className="right">
          <span>{workflowId.slice(0, 8)}</span>
        </div>
      )}
    </div>
  );
}
