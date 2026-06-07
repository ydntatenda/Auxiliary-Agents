import { useEffect, useState } from "react";

import {
  CurrentUser,
  DeltaScope,
  getMe,
} from "./api/client";
import { Subbar, Topbar } from "./components/Shell";
import Capture from "./pages/Capture";
import Clarify from "./pages/Clarify";
import Library from "./pages/Library";
import Processing from "./pages/Processing";
import Sop from "./pages/Sop";

type Stage = "library" | "capture" | "processing" | "clarify" | "sop";

export type UpdateContext = {
  workflowId: string;
  scope: DeltaScope | null;
  // The workflow's `created_by`. Capture needs this to decide whether the
  // current user can edit (delete, rename, reorder) sources added by
  // earlier collaborators. Null when unknown, which keeps the UI safe.
  ownerId: string | null;
};

export default function App() {
  const [stage, setStage] = useState<Stage>("library");
  const [workflowId, setWorkflowId] = useState<string | null>(null);
  const [needsProcessing, setNeedsProcessing] = useState(false);
  const [updateContext, setUpdateContext] = useState<UpdateContext | null>(null);
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [initialDetailId, setInitialDetailId] = useState<string | null>(null);

  useEffect(() => {
    getMe()
      .then(setUser)
      .catch(() => setUser(null));
  }, []);

  function handleCaptured(id: string, processing: boolean) {
    setWorkflowId(id);
    setNeedsProcessing(processing);
    setStage("processing");
  }

  function backToLibrary() {
    setWorkflowId(null);
    setNeedsProcessing(false);
    setUpdateContext(null);
    setInitialDetailId(null);
    setStage("library");
  }

  function openWorkflowInDetail(id: string) {
    setInitialDetailId(id);
    setStage("library");
  }

  function startNewWorkflow() {
    setUpdateContext(null);
    setStage("capture");
  }

  function addSourcesToExisting(id: string, ownerId: string | null) {
    setWorkflowId(id);
    setUpdateContext({ workflowId: id, scope: null, ownerId });
    setStage("capture");
  }

  function updateExisting(id: string, scope: DeltaScope, ownerId: string | null) {
    setWorkflowId(id);
    setUpdateContext({ workflowId: id, scope, ownerId });
    setStage("capture");
  }

  if (stage === "processing" && workflowId) {
    return (
      <Processing
        needsTranscription={needsProcessing}
        workflowId={workflowId}
        onReady={() => setStage("clarify")}
      />
    );
  }

  return (
    <main className="app">
      <Topbar user={user} onOpenWorkflow={openWorkflowInDetail} />
      <Subbar stage={stage} workflowId={workflowId} onBack={backToLibrary} />

      {stage === "library" && user && (
        <Library
          user={user}
          initialWorkflowId={initialDetailId}
          onNewWorkflow={startNewWorkflow}
          onUpdateFlow={updateExisting}
          onAddSources={addSourcesToExisting}
        />
      )}
      {stage === "library" && !user && (
        <div className="workarea">
          <div className="canvas">
            <div className="lib-state">Loading session.</div>
          </div>
        </div>
      )}
      {stage === "capture" && user && (
        <Capture
          currentUser={user}
          onCaptured={handleCaptured}
          updateContext={updateContext}
        />
      )}
      {stage === "clarify" && workflowId && (
        <Clarify
          workflowId={workflowId}
          onReadyForSop={() => setStage("sop")}
        />
      )}
      {stage === "sop" && workflowId && (
        <Sop workflowId={workflowId} onStartOver={backToLibrary} />
      )}
    </main>
  );
}
