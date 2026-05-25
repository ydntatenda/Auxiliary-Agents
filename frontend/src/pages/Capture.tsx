import { ArrowRight, FileText, Mic, MonitorUp } from "lucide-react";
import { FormEvent, useState } from "react";
import type { ReactNode } from "react";
import { captureScreen, captureText, captureVoice } from "../api/client";
import ScreenRecorder from "../components/ScreenRecorder";
import TextCapture from "../components/TextCapture";
import VoiceRecorder from "../components/VoiceRecorder";

type Mode = "text" | "voice" | "screen";

type Props = {
  onCaptured: (workflowId: string, needsProcessing: boolean) => void;
};

const modalities: Array<{
  id: Mode;
  icon: ReactNode;
  title: string;
  desc: string;
  tag: string;
}> = [
  {
    id: "text",
    icon: <FileText size={22} />,
    title: "Typed description",
    desc: "Describe the workflow in your own words.",
    tag: "TEXT",
  },
  {
    id: "voice",
    icon: <Mic size={22} />,
    title: "Voice walkthrough",
    desc: "Record yourself talking through the process.",
    tag: "AUDIO",
  },
  {
    id: "screen",
    icon: <MonitorUp size={22} />,
    title: "Screen recording",
    desc: "Record yourself doing the work end-to-end.",
    tag: "VIDEO",
  },
];

export default function Capture({ onCaptured }: Props) {
  const [mode, setMode] = useState<Mode>("text");
  const [name, setName] = useState("Citation appeals processing");
  const [unit, setUnit] = useState("GT P&T");
  const [text, setText] = useState("");
  const [voiceBlob, setVoiceBlob] = useState<Blob | null>(null);
  const [screenBlob, setScreenBlob] = useState<Blob | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const response =
        mode === "text"
          ? await captureText(name, unit, text)
          : mode === "voice"
            ? await captureVoice(name, unit, voiceBlob!)
            : await captureScreen(name, unit, screenBlob!);
      onCaptured(response.workflow_id, mode !== "text");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Capture failed");
    } finally {
      setSubmitting(false);
    }
  }

  const canSubmit =
    Boolean(name.trim()) &&
    Boolean(unit.trim()) &&
    (mode === "text" ? Boolean(text.trim()) : mode === "voice" ? Boolean(voiceBlob) : Boolean(screenBlob));

  return (
    <div className="workarea">
      <form className="canvas" onSubmit={submit}>
        <div className="step-eyebrow">
          <span className="num">01 / 04</span>
          <span>Capture</span>
        </div>
        <h1 className="page-title">Tell Modus how this workflow gets done.</h1>
        <p className="page-sub">
          Text, voice, and screen recordings all become a transcript first. The system extracts the
          workflow graph, then asks focused questions to close important gaps.
        </p>

        <div className="field-row">
          <div className="field-label">
            Workflow name<span className="req">*</span>
            <span className="hint">Short and descriptive. This appears in the SOP header.</span>
          </div>
          <div>
            <input className="text-input" onChange={(event) => setName(event.target.value)} value={name} />
          </div>
        </div>

        <div className="field-row">
          <div className="field-label">
            Department<span className="req">*</span>
            <span className="hint">The unit that owns this procedure.</span>
          </div>
          <div>
            <input className="text-input" onChange={(event) => setUnit(event.target.value)} value={unit} />
          </div>
        </div>

        <div className="field-row">
          <div className="field-label">
            Input modality<span className="req">*</span>
            <span className="hint">Pick the clearest way to describe the work.</span>
          </div>
          <div>
            <div className="modality-grid">
              {modalities.map((item) => (
                <button
                  className={`modality${mode === item.id ? " selected" : ""}`}
                  key={item.id}
                  onClick={() => setMode(item.id)}
                  type="button"
                >
                  <span className="m-tag">{item.tag}</span>
                  <span className="icon">{item.icon}</span>
                  <span className="m-title">{item.title}</span>
                  <span className="m-desc">{item.desc}</span>
                </button>
              ))}
            </div>

            <div className="input-pane">
              <div className="input-pane-head">
                <span className="label-mono">
                  {mode === "text" ? "Typed description" : mode === "voice" ? "Voice walkthrough" : "Screen recording"}
                </span>
                <span className="label-mono">MVP capture</span>
              </div>
              {mode === "text" && <TextCapture text={text} onChange={setText} />}
              {mode === "voice" && <VoiceRecorder onRecordingReady={setVoiceBlob} />}
              {mode === "screen" && <ScreenRecorder onRecordingReady={setScreenBlob} />}
            </div>
          </div>
        </div>

        {error && <div className="error">{error}</div>}

        <div className="actions">
          <button className="btn btn-ghost" type="button">
            Draft only
          </button>
          <div className="right">
            <span className="label-mono">Graph-first SOP pipeline</span>
            <button className="btn btn-primary" disabled={!canSubmit || submitting} type="submit">
              {submitting ? "Submitting" : "Run extraction"}
              <ArrowRight size={14} />
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
