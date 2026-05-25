import { ArrowRight } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { answerClarification, startClarification } from "../api/client";

type Props = {
  workflowId: string;
  onReadyForSop: () => void;
};

type HistoryItem = {
  role: "question" | "answer";
  content: string;
};

const MAX_QUESTIONS = 8;

export default function Clarify({ workflowId, onReadyForSop }: Props) {
  const [question, setQuestion] = useState<string | null>(null);
  const [answer, setAnswer] = useState("");
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    startClarification(workflowId)
      .then((result) => {
        if (cancelled) return;
        setDone(result.done);
        setQuestion(result.question);
        if (result.question) setHistory([{ role: "question", content: result.question }]);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Clarification failed");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [workflowId]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!answer.trim() || loading) return;
    const currentAnswer = answer;
    setAnswer("");
    setLoading(true);
    setError(null);
    setHistory((items) => [...items, { role: "answer", content: currentAnswer }]);
    try {
      const result = await answerClarification(workflowId, currentAnswer);
      setDone(result.done);
      setQuestion(result.question);
      if (result.question) {
        setHistory((items) => [...items, { role: "question", content: result.question! }]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Answer failed");
    } finally {
      setLoading(false);
    }
  }

  const questionCount = history.filter((item) => item.role === "question").length;

  return (
    <section className="clarify">
      <div className="clar-main">
        <div className="clar-progress">
          <span>{done ? "Ready for SOP" : "Clarification loop"}</span>
          <div className="bars">
            {Array.from({ length: MAX_QUESTIONS }).map((_, index) => (
              <i
                className={index < questionCount ? "done" : index === questionCount ? "active" : ""}
                key={index}
              />
            ))}
          </div>
          <span>
            {questionCount}/{MAX_QUESTIONS}
          </span>
        </div>

        <div className="clar-context">Current gap</div>
        <h1 className="clar-q">
          {done
            ? "The workflow graph is ready to render into an SOP."
            : question || (loading ? "Preparing the next clarification question..." : "No question returned.")}
        </h1>
        <p className="clar-hint">
          Answer only the question shown. Modus will patch the graph, resolve the gap, and ask the
          next question until the graph is ready or the eight-question cap is reached.
        </p>

        {done ? (
          <button className="btn btn-primary" onClick={onReadyForSop} type="button">
            Generate SOP
            <ArrowRight size={14} />
          </button>
        ) : (
          <form onSubmit={submit}>
            <div className="clar-input">
              <input
                onChange={(event) => setAnswer(event.target.value)}
                placeholder="Type the operator's answer..."
                value={answer}
              />
              <button className="btn btn-primary" disabled={loading || !answer.trim()} type="submit">
                Submit
              </button>
            </div>
          </form>
        )}

        <div className="clar-actions">
          <span>{loading ? "Updating graph..." : "One question per turn"}</span>
        </div>
        {error && <div className="error">{error}</div>}
      </div>

      <aside className="clar-rail">
        <h4>Run state</h4>
        <div className="rail-item">
          <div className="k">Workflow</div>
          <div className="v">{workflowId.slice(0, 8)}</div>
        </div>
        <div className="rail-item">
          <div className="k">Question cap</div>
          <div className="v">8 max</div>
        </div>
        <div className="rail-item">
          <div className="k">Status</div>
          <div className="v">{done ? "Ready to render" : loading ? "Thinking" : "Waiting for answer"}</div>
        </div>

        <h4>History</h4>
        <div className="history">
          {history.map((item, index) => (
            <div className="history-row" key={`${item.role}-${index}`}>
              <div className="role">{item.role}</div>
              <div className="content">{item.content}</div>
            </div>
          ))}
        </div>
      </aside>
    </section>
  );
}
