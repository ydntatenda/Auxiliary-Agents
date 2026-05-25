import { useEffect, useRef, useState } from "react";
import { extractWorkflow, getStatus } from "../api/client";
import { Topbar } from "../components/Shell";

type Props = {
  workflowId: string;
  needsTranscription: boolean;
  onReady: () => void;
};

const processingRuns = new Map<string, Promise<void>>();

function getProcessingRun(
  workflowId: string,
  needsTranscription: boolean,
  onStatus: (status: string) => void,
) {
  const key = `${workflowId}:${needsTranscription}`;
  const existing = processingRuns.get(key);
  if (existing) return existing;

  const run = (async () => {
    if (needsTranscription) {
      while (true) {
        const current = await getStatus(workflowId);
        onStatus(current.status);
        if (current.status === "failed") throw new Error("Background processing failed");
        if (current.status === "transcribed") break;
        await new Promise((resolve) => window.setTimeout(resolve, 2000));
      }
    }
    onStatus("extracting");
    await extractWorkflow(workflowId);
  })();

  processingRuns.set(key, run);
  return run;
}

export default function Processing({ workflowId, needsTranscription, onReady }: Props) {
  const [status, setStatus] = useState(needsTranscription ? "transcribing" : "transcribed");
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const onReadyRef = useRef(onReady);

  useEffect(() => {
    onReadyRef.current = onReady;
  }, [onReady]);

  useEffect(() => {
    const timer = window.setInterval(() => setElapsed((value) => value + 1), 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    let cancelled = false;
    getProcessingRun(workflowId, needsTranscription, (nextStatus) => {
      if (!cancelled) setStatus(nextStatus);
    })
      .then(() => {
        if (!cancelled) onReadyRef.current();
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Processing failed");
      });
    return () => {
      cancelled = true;
    };
  }, [needsTranscription, workflowId]);

  return (
    <main className="processing">
      <Topbar />
      <div className="proc-stage">
        <div>
          <div className="proc-window">
            <div className="pw-head">
              <div className="pw-dots">
                <i />
                <i />
                <i />
              </div>
              <div className="pw-title">{workflowId.slice(0, 8)} · workflow graph</div>
            </div>
            <div className="pw-body">
              <div className="code-lines">
                {Array.from({ length: 15 }).map((_, index) => (
                  <div className="code-line" key={index}>
                    <span className="gutter" />
                    <span
                      className={`bar ${index % 4 === 0 ? "teal" : ""}`}
                      style={{ width: `${28 + ((index * 17) % 52)}%` }}
                    />
                  </div>
                ))}
              </div>
            </div>
          </div>
          <div className="proc-caption">
            <div className="label">
              {status === "extracting" ? "Extracting workflow structure" : "Transcribing capture"}
            </div>
            <div className="sub">Elapsed {elapsed}s · source of truth is the graph</div>
          </div>
          {error && <div className="error">{error}</div>}
        </div>
      </div>
    </main>
  );
}
