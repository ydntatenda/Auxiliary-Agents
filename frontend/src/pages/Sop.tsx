import { useEffect, useMemo, useState } from "react";
import { getSop, sopDownloadUrl } from "../api/client";
import MarkdownDocument from "../components/MarkdownDocument";

type Props = {
  workflowId: string;
  onStartOver: () => void;
};

export default function Sop({ workflowId, onStartOver }: Props) {
  const [sop, setSop] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getSop(workflowId)
      .then((result) => {
        if (!cancelled) setSop(result.sop);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "SOP generation failed");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [workflowId]);

  const title = useMemo(() => {
    const firstHeading = sop
      .split("\n")
      .find((line) => line.startsWith("# "))
      ?.replace("# ", "")
      .trim();
    return firstHeading || "Generated SOP";
  }, [sop]);

  return (
    <section className="sop-shell">
      <div className="sop-toolbar">
        <span className="status">
          <span className="dot" />
          Graph rendered
        </span>
        <span>{workflowId.slice(0, 8)}</span>
        <div className="right">
          <a className="btn btn-secondary" href={sopDownloadUrl(workflowId)}>
            Download .md
          </a>
          <button className="btn btn-primary" onClick={onStartOver} type="button">
            Start over
          </button>
        </div>
      </div>

      <div className="sop-layout">
        <nav className="sop-toc">
          <h5>Document</h5>
          <ol>
            <li>Overview</li>
            <li>Procedure</li>
            <li>Reference</li>
          </ol>
        </nav>

        <article className="sop-doc">
          <header className="sop-header">
            <div className="sop-eyebrow">Standard operating procedure</div>
            <h1 className="sop-title">{title}</h1>
          </header>
          {loading && <p>Rendering SOP...</p>}
          {error && <div className="error">{error}</div>}
          {sop && <MarkdownDocument markdown={sop} />}
        </article>

        <aside className="sop-rail">
          <h5>Source</h5>
          <div className="entity">
            <span>Graph</span>
            <span>JSONB</span>
          </div>
          <div className="entity">
            <span>Renderer</span>
            <span>LLM</span>
          </div>
          <div className="entity">
            <span>Format</span>
            <span>Markdown</span>
          </div>
        </aside>
      </div>
    </section>
  );
}
