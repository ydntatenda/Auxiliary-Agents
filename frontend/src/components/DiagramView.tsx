import { useEffect, useRef, useState } from "react";

import { getDiagram } from "../api/client";

type Step = {
  id: string;
  order: number;
  title: string;
  terminal?: boolean;
};

type Graph = {
  steps: Step[];
};

type Props = {
  workflowId: string;
  selectedStepIds: string[];
  onToggleStep: (stepId: string) => void;
  onClear: () => void;
};

let mermaidLoaded = false;

async function initMermaid() {
  if (mermaidLoaded) return;
  const mermaid = (await import("mermaid")).default;
  mermaid.initialize({
    startOnLoad: false,
    securityLevel: "loose",
    theme: "neutral",
    fontFamily: '"Helvetica Neue", Helvetica, Arial, sans-serif',
  });
  mermaidLoaded = true;
}

async function renderMermaidSvg(
  source: string,
  id: string,
): Promise<string> {
  await initMermaid();
  const mermaid = (await import("mermaid")).default;
  const { svg } = await mermaid.render(id, source);
  return svg;
}

export default function DiagramView({
  workflowId,
  selectedStepIds,
  onToggleStep,
  onClear,
}: Props) {
  const [graph, setGraph] = useState<Graph | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const svgContainer = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    getDiagram(workflowId)
      .then(async (response) => {
        if (!alive) return;
        try {
          const svg = await renderMermaidSvg(
            response.mermaid,
            `diagram-${workflowId.slice(0, 8)}`,
          );
          if (!alive) return;
          if (svgContainer.current) {
            svgContainer.current.innerHTML = svg;
          }
          setGraph(response.graph as Graph);
        } catch (err) {
          if (alive) {
            setError(err instanceof Error ? err.message : "Diagram render failed.");
          }
        }
      })
      .catch((err) => {
        if (alive) {
          setError(err instanceof Error ? err.message : "Diagram load failed.");
        }
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [workflowId]);

  const selectedSet = new Set(selectedStepIds);

  return (
    <section className="diagram-view">
      <div className="diagram-svg-frame">
        {loading && <div className="diagram-status">Loading diagram</div>}
        {error && <div className="diagram-status diagram-error">{error}</div>}
        <div ref={svgContainer} className="diagram-svg" />
      </div>

      <div className="diagram-step-list">
        <div className="diagram-step-head">
          <span className="label-mono">Steps</span>
          <span className="diagram-step-hint">
            Click steps to scope an update.{" "}
            {selectedStepIds.length > 0 && (
              <button
                type="button"
                className="btn btn-ghost btn-tight"
                onClick={onClear}
              >
                Clear selection
              </button>
            )}
          </span>
        </div>
        {graph?.steps?.length ? (
          <ul className="diagram-steps">
            {graph.steps.map((step) => (
              <li key={step.id}>
                <button
                  type="button"
                  className={`diagram-step${selectedSet.has(step.id) ? " selected" : ""}`}
                  onClick={() => onToggleStep(step.id)}
                >
                  <span className="step-num">{step.order ?? "?"}</span>
                  <span className="step-title">{step.title}</span>
                  {step.terminal && <span className="step-terminal">terminal</span>}
                </button>
              </li>
            ))}
          </ul>
        ) : (
          !loading && <div className="diagram-status">No steps in this graph yet.</div>
        )}
      </div>
    </section>
  );
}
