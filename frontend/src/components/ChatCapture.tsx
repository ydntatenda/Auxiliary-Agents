import { ArrowRight, RotateCcw } from "lucide-react";
import { FormEvent, useState } from "react";

export const CHAT_SEED_QUESTIONS: readonly string[] = [
  "Walk me through the process from start to finish.",
  "What are the most common mistakes or exceptions?",
  "Who else is involved and what do they do?",
  "What tools or systems do you use?",
  "How do you know when the process is complete?",
] as const;

type Pair = { question: string; answer: string };

type Props = {
  busy?: boolean;
  onSubmit: (messages: Pair[]) => Promise<void>;
};

export default function ChatCapture({ busy, onSubmit }: Props) {
  const [answers, setAnswers] = useState<string[]>(() =>
    CHAT_SEED_QUESTIONS.map(() => ""),
  );
  const [current, setCurrent] = useState(0);
  const [draft, setDraft] = useState("");

  const total = CHAT_SEED_QUESTIONS.length;
  const isLast = current === total - 1;

  function handleNext(event: FormEvent) {
    event.preventDefault();
    const trimmed = draft.trim();
    if (!trimmed) return;
    const next = [...answers];
    next[current] = trimmed;
    setAnswers(next);
    if (isLast) {
      const pairs: Pair[] = CHAT_SEED_QUESTIONS.map((question, index) => ({
        question,
        answer: next[index] ?? "",
      })).filter((pair) => pair.answer);
      void onSubmit(pairs);
      return;
    }
    setCurrent(current + 1);
    setDraft(answers[current + 1] ?? "");
  }

  function handleBack() {
    if (current === 0) return;
    const next = [...answers];
    next[current] = draft;
    setAnswers(next);
    setCurrent(current - 1);
    setDraft(answers[current - 1] ?? "");
  }

  function handleReset() {
    setAnswers(CHAT_SEED_QUESTIONS.map(() => ""));
    setCurrent(0);
    setDraft("");
  }

  return (
    <form className="chatcap" onSubmit={handleNext}>
      <div className="chatcap-progress">
        <span className="label-mono">
          Question {current + 1} of {total}
        </span>
        <div className="chatcap-bars">
          {CHAT_SEED_QUESTIONS.map((_, index) => (
            <i
              key={index}
              className={
                index < current
                  ? "done"
                  : index === current
                    ? "active"
                    : undefined
              }
            />
          ))}
        </div>
      </div>

      <div className="chatcap-question">{CHAT_SEED_QUESTIONS[current]}</div>

      <textarea
        className="text-input chatcap-textarea"
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        placeholder="Type the answer. Plain language is fine."
        disabled={busy}
      />

      <div className="chatcap-actions">
        <button
          type="button"
          className="btn btn-ghost"
          onClick={handleBack}
          disabled={current === 0 || busy}
        >
          Back
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          onClick={handleReset}
          disabled={busy}
        >
          <RotateCcw size={12} />
          Start over
        </button>
        <button
          type="submit"
          className="btn btn-primary"
          disabled={!draft.trim() || busy}
        >
          {isLast ? "Add chat source" : "Next"}
          <ArrowRight size={12} />
        </button>
      </div>
    </form>
  );
}
