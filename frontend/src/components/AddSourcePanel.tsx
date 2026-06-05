import {
  FileText,
  MessageSquare,
  Mic,
  MonitorUp,
  Plus,
  Type,
  Upload,
} from "lucide-react";
import { FormEvent, useRef, useState } from "react";

import {
  Source,
  addChatSource,
  addFileSource,
  addTextSource,
} from "../api/client";
import ChatCapture from "./ChatCapture";
import ScreenRecorder from "./ScreenRecorder";
import VoiceRecorder from "./VoiceRecorder";

type Tab = "text" | "voice" | "screen" | "document" | "chat";

type Props = {
  workflowId: string;
  contributorRole: string | null;
  onSourceAdded: (source: Source) => void;
};

const TABS: ReadonlyArray<{ id: Tab; label: string; icon: typeof Type }> = [
  { id: "text", label: "Text", icon: Type },
  { id: "voice", label: "Voice", icon: Mic },
  { id: "screen", label: "Screen", icon: MonitorUp },
  { id: "document", label: "Document", icon: FileText },
  { id: "chat", label: "Chat", icon: MessageSquare },
] as const;

const DOCUMENT_ACCEPT = ".pdf,.docx,.png,.jpg,.jpeg";

export default function AddSourcePanel({
  workflowId,
  contributorRole,
  onSourceAdded,
}: Props) {
  const [tab, setTab] = useState<Tab>("text");
  const [label, setLabel] = useState("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  function reset() {
    setLabel("");
    setText("");
    setError(null);
  }

  async function withBusy<T>(work: () => Promise<T>) {
    setBusy(true);
    setError(null);
    try {
      const out = await work();
      return out;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Add source failed");
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function submitText(event: FormEvent) {
    event.preventDefault();
    if (!text.trim()) return;
    const result = await withBusy(() =>
      addTextSource(workflowId, text, contributorRole, label.trim() || undefined),
    );
    if (result) {
      onSourceAdded(result);
      reset();
    }
  }

  async function submitVoice(blob: Blob | null) {
    if (!blob) return;
    const result = await withBusy(() =>
      addFileSource(
        workflowId,
        "voice",
        blob,
        "voice.webm",
        contributorRole,
        label.trim() || undefined,
      ),
    );
    if (result) {
      onSourceAdded(result);
      reset();
    }
  }

  async function submitScreen(blob: Blob | null) {
    if (!blob) return;
    const result = await withBusy(() =>
      addFileSource(
        workflowId,
        "screen",
        blob,
        "screen.webm",
        contributorRole,
        label.trim() || undefined,
      ),
    );
    if (result) {
      onSourceAdded(result);
      reset();
    }
  }

  async function submitDocument(event: FormEvent) {
    event.preventDefault();
    const file = fileInputRef.current?.files?.[0];
    if (!file) return;
    const result = await withBusy(() =>
      addFileSource(
        workflowId,
        "document",
        file,
        file.name,
        contributorRole,
        label.trim() || file.name,
      ),
    );
    if (result) {
      onSourceAdded(result);
      reset();
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function submitChat(messages: { question: string; answer: string }[]) {
    if (!messages.length) return;
    const result = await withBusy(() =>
      addChatSource(
        workflowId,
        messages,
        contributorRole,
        label.trim() || undefined,
      ),
    );
    if (result) {
      onSourceAdded(result);
      reset();
    }
  }

  return (
    <section className="addsource">
      <div className="addsource-head">
        <span className="label-mono">Add source</span>
        <div className="addsource-tabs" role="tablist">
          {TABS.map(({ id, label: tabLabel, icon: Icon }) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={tab === id}
              className={`addsource-tab${tab === id ? " active" : ""}`}
              onClick={() => {
                setTab(id);
                setError(null);
              }}
              disabled={busy}
            >
              <Icon size={13} />
              {tabLabel}
            </button>
          ))}
        </div>
      </div>

      <div className="addsource-labelrow">
        <label className="label-mono" htmlFor="addsource-label">
          Label
        </label>
        <input
          id="addsource-label"
          className="text-input"
          value={label}
          onChange={(event) => setLabel(event.target.value)}
          placeholder="Optional. Helps you tell sources apart later."
          disabled={busy}
        />
      </div>

      <div className="addsource-pane">
        {tab === "text" && (
          <form className="addsource-textform" onSubmit={submitText}>
            <textarea
              className="text-input"
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder="Type what happens, in your own words. Order does not need to be perfect."
              disabled={busy}
            />
            <div className="addsource-submit">
              <button
                type="submit"
                className="btn btn-primary"
                disabled={busy || !text.trim()}
              >
                <Plus size={13} />
                Add text source
              </button>
            </div>
          </form>
        )}

        {tab === "voice" && (
          <VoiceRecorder onRecordingReady={submitVoice} />
        )}

        {tab === "screen" && (
          <ScreenRecorder onRecordingReady={submitScreen} />
        )}

        {tab === "document" && (
          <form className="addsource-docform" onSubmit={submitDocument}>
            <div className="addsource-doc">
              <Upload size={20} />
              <div>
                <div className="addsource-doc-title">Upload a document</div>
                <div className="addsource-doc-sub">
                  PDF, Word, or an image of a form. Scanned PDFs are read with OCR.
                </div>
              </div>
              <input
                ref={fileInputRef}
                type="file"
                accept={DOCUMENT_ACCEPT}
                disabled={busy}
              />
            </div>
            <div className="addsource-submit">
              <button type="submit" className="btn btn-primary" disabled={busy}>
                <Plus size={13} />
                Add document source
              </button>
            </div>
          </form>
        )}

        {tab === "chat" && (
          <ChatCapture busy={busy} onSubmit={submitChat} />
        )}
      </div>

      {error && <div className="error">{error}</div>}
    </section>
  );
}
