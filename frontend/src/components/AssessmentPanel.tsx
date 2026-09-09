import { Bot, RefreshCw, ShieldAlert, UserRoundCog } from "lucide-react";
import { useEffect, useState } from "react";

import { AssessmentRecord, createAssessment, getAssessment } from "../api/client";


export default function AssessmentPanel({ workflowId }: { workflowId: string }) {
  const [assessment, setAssessment] = useState<AssessmentRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAssessment(workflowId)
      .then(setAssessment)
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load assessment."))
      .finally(() => setLoading(false));
  }, [workflowId]);

  async function generate() {
    setGenerating(true);
    setError(null);
    try {
      setAssessment(await createAssessment(workflowId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Assessment failed.");
    } finally {
      setGenerating(false);
    }
  }

  if (loading) return <section className="assessment-panel"><div className="lib-state">Loading assessment.</div></section>;

  if (!assessment) {
    return (
      <section className="assessment-panel assessment-empty">
        <Bot size={20} />
        <div><h2>Design the future workflow.</h2><p>Assess gaps, automation potential, controls, worker transitions and knowledge updates from the approved graph and worker profiles.</p></div>
        <button className="btn btn-primary" type="button" onClick={generate} disabled={generating}>{generating ? "Assessing" : "Run assessment"}</button>
        {error && <div className="error">{error}</div>}
      </section>
    );
  }

  const report = assessment.report;
  return (
    <section className="assessment-panel">
      <div className="assessment-head">
        <div><span className="label-mono">Organisational assessment · workflow v{assessment.workflow_version}</span><h2>Future operating model</h2></div>
        <button className="btn btn-ghost" type="button" onClick={generate} disabled={generating}><RefreshCw size={13} />{generating ? "Reassessing" : "Reassess"}</button>
      </div>
      <p className="assessment-summary">{report.executive_summary}</p>
      <div className="opportunity-list">
        {report.opportunities.map((item) => (
          <article className="opportunity" key={item.step_id}>
            <div className="opportunity-score">{item.automation_score}</div>
            <div><span className="label-mono">{item.disposition.replace(/_/g, " ")} · {item.step_id}</span><h3>{item.step_title}</h3><p>{item.rationale}</p>{item.controls.length > 0 && <div className="control-line"><ShieldAlert size={12} /> {item.controls.join(" · ")}</div>}</div>
          </article>
        ))}
      </div>
      {report.role_transitions.length > 0 && <div className="assessment-section"><h3><UserRoundCog size={15} /> Role transition options</h3>{report.role_transitions.map((item) => <article className="role-transition" key={`${item.worker_id}-${item.proposed_role}`}><strong>{item.worker_name}: {item.proposed_role}</strong><p>{item.new_responsibilities.join(" · ")}</p><span className="label-mono">Worker and manager review required</span></article>)}</div>}
      <div className="assessment-columns">
        <List title="Future workflow" items={report.future_workflow} />
        <List title="Knowledge updates" items={report.knowledge_updates} />
        <List title="Before deployment" items={report.deployment_prerequisites} />
        <List title="Success metrics" items={report.success_metrics} />
      </div>
      {error && <div className="error">{error}</div>}
    </section>
  );
}


function List({ title, items }: { title: string; items: string[] }) {
  return <div className="assessment-list"><h3>{title}</h3><ol>{items.map((item, index) => <li key={`${title}-${index}`}>{item}</li>)}</ol></div>;
}
