import { ChevronLeft } from "lucide-react";

import { CurrentUser } from "../api/client";
import NotificationBell from "./NotificationBell";

type Stage = "library" | "people" | "capture" | "processing" | "clarify" | "sop";

type TopbarProps = {
  user: CurrentUser | null;
  onOpenWorkflow: (workflowId: string) => void;
  onOpenLibrary?: () => void;
  onOpenPeople?: () => void;
  active?: "workflows" | "people";
};

export function Topbar({ user, onOpenWorkflow, onOpenLibrary, onOpenPeople, active = "workflows" }: TopbarProps) {
  return (
    <div className="topbar">
      <div className="brand">
        <div className="mark" />
        <div className="name">Uropi</div>
        <div className="dept">{user?.org_name ?? "Loading"}</div>
      </div>
      {(onOpenLibrary || onOpenPeople) && (
        <nav className="product-nav" aria-label="Product">
          <button className={active === "workflows" ? "active" : ""} type="button" onClick={onOpenLibrary}>Workflows</button>
          <button className={active === "people" ? "active" : ""} type="button" onClick={onOpenPeople}>People</button>
        </nav>
      )}
      <div className="topbar-right">
        <NotificationBell onOpenWorkflow={onOpenWorkflow} />
        <div className="meta">v0.3 · local</div>
        {user ? (
          <div className="user-chip">
            <div className="avatar">{user.avatar}</div>
            <span className="user-name">{user.name.split(" ")[0]}</span>
          </div>
        ) : (
          <div className="avatar">??</div>
        )}
      </div>
    </div>
  );
}

type SubbarProps = {
  stage: Stage;
  workflowId: string | null;
  onBack: () => void;
};

export function Subbar({ stage, workflowId, onBack }: SubbarProps) {
  const active =
    stage === "library"
      ? "Workflows"
      : stage === "people"
        ? "People"
      : stage === "capture"
        ? "New capture"
        : stage === "processing"
          ? "Processing"
          : stage === "clarify"
            ? "Clarification"
            : "SOP";

  const showBack = stage !== "library";

  return (
    <div className="subbar">
      {showBack && (
        <button type="button" className="back-chev compact" onClick={onBack}>
          <ChevronLeft size={12} />
        </button>
      )}
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
