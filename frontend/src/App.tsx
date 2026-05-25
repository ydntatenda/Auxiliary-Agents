import { useState } from "react";
import Capture from "./pages/Capture";
import Clarify from "./pages/Clarify";
import Processing from "./pages/Processing";
import Sop from "./pages/Sop";
import { Subbar, Topbar } from "./components/Shell";

type Stage = "capture" | "processing" | "clarify" | "sop";

export default function App() {
  const [stage, setStage] = useState<Stage>("capture");
  const [workflowId, setWorkflowId] = useState<string | null>(null);
  const [needsProcessing, setNeedsProcessing] = useState(false);

  function handleCaptured(id: string, processing: boolean) {
    setWorkflowId(id);
    setNeedsProcessing(processing);
    setStage("processing");
  }

  function reset() {
    setWorkflowId(null);
    setNeedsProcessing(false);
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
      <Topbar />
      <Subbar stage={stage} workflowId={workflowId} />

      {stage === "capture" && <Capture onCaptured={handleCaptured} />}
      {stage === "clarify" && workflowId && (
        <Clarify workflowId={workflowId} onReadyForSop={() => setStage("sop")} />
      )}
      {stage === "sop" && workflowId && <Sop workflowId={workflowId} onStartOver={reset} />}
    </main>
  );
}
